# Chantier du moteur de veille — plan d'exécution arrêté le 30 juillet 2026

> **Nature :** plan d'exécution. Consolide `Decisions_2026-07-30.md` *(fourni hors dépôt)* et
> [Moteur_Corrections_et_Regime_Hybride.md](Moteur_Corrections_et_Regime_Hybride.md) après
> confrontation ligne à ligne avec le dépôt. Les deux specs restent valables comme **raisonnement** ;
> ce document est ce qui sera **codé**, dans cet ordre.
>
> **Ce qu'il ajoute aux deux specs :** l'état réellement vérifié du code (plusieurs prémisses
> avaient bougé), six écarts qu'aucune des deux ne nommait, et quatre décisions prises le 30/07.

---

## 0. Le principe, et l'ordre qu'il impose

> La boucle chaude décide — cinq étages, déterministes.
> La boucle froide observe et calibre — elle ne produit que des propositions de `WatchParam`.
> La frontière est structurelle : la boucle froide ne peut pas écrire un effet, et aucun objet
> de calibration ne porte l'identifiant d'une personne.

L'ordre des lots découle de deux faits, pas d'une préférence : **la fuite de confidentialité du
rendez-vous est active en production**, et **la détection d'absence n'existe pas** — donc le
différenciateur du produit n'est pas encore branché.

---

## 1. État vérifié du moteur (30 juillet 2026)

| Organe | État |
| :-- | :-- |
| Ledger, registre, intake, 5 interpreters, arbitrage, matérialisation | livrés |
| `Referent`, `ResolveReferent`, `ResolveSignalOwner` | livrés, **non branchés sur la pipeline** |
| `watch_scheduled_checks` + `SqlScheduledCheckStore` + écriture par le `Materializer` | **livrés** (migration `c5fc0c1d2e3f`) |
| `FireDueChecks` + route Plateforme + garde anti-orage (`CHECK_BURST_CAP = 20`) | **livrés** |
| `CheckFiredV1` | **n'existe pas** |
| `OpenCase(origin=ABSENCE)` | émis par **rien** |
| `Signal.release()` — réévaluation des `HELD` | jamais appelé |
| `CoverageSignal` matérialisable | non |
| Régimes de rodage, sous-module `calibration` | rien |

**Le worker tire déjà dans le vide.** `FireDueChecks` écrit des `CHECK_FIRED` au ledger ; aucun
interpreter n'est enregistré pour ce kind, donc `InterpreterRegistry.interpret` renvoie `[]`. Le
temps entre dans le moteur et ne produit aucun effet. Le chaînon manquant n'est pas le worker :
c'est **l'interpreter du check**.

---

## 2. Les six écarts relevés à la relecture

**A. Une partie du worker est déjà là.** `watch_scheduled_checks` existe, `SCHEDULE_CHECK` et
`CANCEL_SCHEDULED_CHECKS` sont dans `MATERIALIZABLE` et déjà écrits. Reste de ce volet :
`subject_kind` / `source_ref` absents de la table, et `CoverageSignal` non matérialisable.

**B. L'idempotence du tir n'existe pas.**
[`fire_checks.py`](../app/contexts/watch/application/fire_checks.py) fait `fact_id=self._new_id()`
— un `uuid4`, pas un `uuid5(namespace, check_id)`. Le contrôle de doublon de l'intake ne peut donc
rien attraper ; `mark_fired` arrive *après* `submit` ; il n'y a pas de `SKIP LOCKED`. Deux passes
de cron qui se chevauchent tirent deux fois la même échéance.

**C. La reprojection perd toutes les échéances — aucune des deux specs ne le dit.**
[`projections.py`](../app/contexts/watch/application/projections.py) construit
`Materializer(store, signals)` **sans store d'échéances**. Le matérialiseur n'écrit un
`ScheduleCheck` que si `self._checks is not None` ; sinon l'effet retombe en `deferred`, et
`deferred` est jeté par tous les appelants. Dès que la détection d'absence reposera sur des
échéances, **une reprojection décapitera silencieusement la veille de toute l'église**. C'est le
premier correctif du lot 2, et il justifie que « les différés cessent d'être silencieux » passe
avant le worker.

**D. Le vocabulaire des issues de la calibration était inventé.** `WELL`, `DIFFICULTY_*`,
`LEFT_CHURCH` ne sont pas dans `SignalOutcome`. Le vrai vocabulaire est déjà là et il est
meilleur : `NOTHING_TO_REPORT` **est** le faux positif — [`signal.py`](../app/contexts/watch/domain/signal.py)
le dit explicitement. Et `MeasureConcernPrecision` + `UNCONFIRMED_OUTCOMES` sont déjà un embryon
d'`OutcomeJudge` : on l'étend, on ne le crée pas.

**E. La détection d'absence est aveugle à celui qu'on n'a jamais vu.** L'échéance se pose *au
moment d'une présence* ; quelqu'un qui n'est jamais venu n'en a aucune, donc n'est jamais détecté.
Tranché en §3, décision 3.

**F. Les deux specs se croisent dans `Intake._run`, et l'ordre n'est pas neutre.** Le lecteur
paresseux borne l'état **au sujet du fait** ; mais le plafond de débit interroge
`open_cases_of_owner(owner)` sur le **propriétaire résolu**, qui n'est presque jamais le sujet.
Livrés naïvement, le compteur répond 0 et le plafond ne retient plus rien — la protection du
responsable disparaît sans un seul test rouge. L'ordre à écrire une fois pour toutes :

```
interpréter (vue réduite au sujet)
  → résoudre les destinataires (étage 02bis)
  → précharger le compteur des propriétaires résolus
  → arbitrer
  → matérialiser
```

`StateScopeError` porte sur les **questions-sujet** uniquement — le compteur du propriétaire en est
exclu, sinon la garde casse l'arbitrage.

---

## 3. Les quatre décisions du 30 juillet

1. **Ordre :** lot 0 puis lot 1, ensuite 2 et 3. La fuite active passe avant la charge.
2. **Repli ultime du propriétaire d'un cas : le propriétaire du tenant.** Quand l'église n'a ni
   détenteur de `MANAGE_APPOINTMENTS`, ni pasteur, ni admin, le cas revient à l'Owner — il existe
   toujours (M0). `owner_account_id NOT NULL` tient donc sans qu'aucun signalement ne soit jamais
   perdu, et le trou reste consigné en `watch_coverage_gaps` au niveau du tenant. C'est ce qui
   lève la contradiction avec la docstring de `RaiseConcern` (« s'il est nul, on émet quand même »).
3. **Celui qu'on n'a jamais vu : les deux mécanismes, chacun pour ce qu'il dit.**
   - le groupe ne saisit **aucune** rencontre → `CoverageGap.BLIND`. Le dispositif est aveugle ;
     ce n'est pas un cas sur la personne, c'est un défaut d'église. Calculé par la passe nocturne,
     écrit dans `watch_coverage_gaps` — **aucun fait n'est inventé**.
   - le groupe saisit, mais la personne ne vient pas → **première échéance posée à l'adhésion**,
     via un fait `JOINED_GROUP` (un acte, pas une omission : la forme passe le filtre de
     `FORBIDDEN_KIND_PATTERNS`), émis par une nouvelle source `groups`.
4. **Backfill :** forme décidée à l'ouverture du lot 1, après lecture de la base. La migration est
   écrite défensivement dans les deux cas — elle échoue bruyamment s'il reste un `NULL`.

---

## 4. Les lots

### Lot 0 — Hygiène du dépôt

Committer les deux migrations (`b4fc0c1d2e3f`, `c5fc0c1d2e3f`) et les fichiers non suivis
(`fire_checks.py`, `persistence/checks.py`, `platform_router.py`, `admit_person.py`,
`derived_status.py`, et leurs tests). Sans ça, toute migration nouvelle part d'une tête instable.

### Lot 1 — Le propriétaire du cas RDV et `owner_account_id NOT NULL`

*Ferme la fuite de `Decisions` §1 et la dette `owner_id` de `Veille_Engine` §9 dans le même geste.*

| # | Modification |
| :-- | :-- |
| 1a | `appointments/application/watch_facts.py` — `with_pastor_account_id` et `handled_by_account_id` au payload. Le propriétaire vient **du fait**, pas d'une cascade : le cas revient au pasteur à qui *cette* main était tendue, et la dette d'un refus à celui qui a refusé. |
| 1b | `interpreters/appointment_requested.py` — `REQUESTED` ne renvoie plus d'effet (le fait reste au ledger ; le devoir de répondre est déjà tenu par `relay_appointments.py`). Les trois états d'échec **ouvrent** un cas et portent un `owner_kind` de repli. |
| 1c | `domain/effects.py` — `owner_kind` sur `OpenCase` (`AGENDA_KEEPER \| PASTOR \| REFERENT`) : une **intention de destinataire**, jamais une identité, pour que l'interpreter reste pur. |
| 1d | **Étage 02bis** — `watch/application/owner_assignment.py` : remplit `owner_account_id` selon `owner_kind`, injecté dans `Intake` **et** `RebuildProjections` (sinon la reprojection réécrit des `NULL`). |
| 1e | `referent_ports.py` + `infrastructure/directories.py` — `PeopleDirectory.agenda_keeper(tenant_id)` : détenteur `MANAGE_APPOINTMENTS` église-entière (`SECRETARY → PASTOR → ADMIN`), ordre d'assignation pour le déterminisme. Puis l'Owner (décision 2). |
| 1f | `arbitration.py` — la fusion `OpenCase → EnrichCase` porte désormais `annotation` et `priority` pour **toutes** les origines. Sans ça, « A annulé le rendez-vous qu'il avait demandé » disparaît dès qu'un cas d'absence est déjà ouvert, et le signal le plus urgent du produit cesse de remonter. |
| 1g | `owner_account_id → nullable=False` + migration sur la tête `c5fc0c1d2e3f`. |

**Pourquoi 1b n'est pas une perte.** `enrich_case` est un **no-op** quand aucun cas n'est vivant :
les trois états d'échec ne fonctionnent aujourd'hui que parce que `REQUESTED` avait ouvert le cas.
Les faire ouvrir est donc obligatoire, et c'est ce qui rend 1f obligatoire aussi.

**Tests :** les cinq de `Decisions` §1.5, plus — *une annulation sur une personne qui a déjà un cas
d'absence garde l'annotation et remonte la priorité* (le trou de 1f).

### Lot 2 — Le moteur tient la charge

**2a — livré** (`dbf1f83`, `463601d`) : matérialisation complète dans la reprojection, différés
journalisés et comptés, avertissement sur `intake=None`, acteur obligatoire pour tout kind capable
de retirer quelqu'un de la veille (contrôle **à l'enregistrement**, donc au démarrage), purge des
échéances limitée à ce qui pend, et **garde-fou de reprojection** (cf. lot 3bis).

1. ~~**Le bug C d'abord** : `Materializer` complet dans la reprojection ; `deferred` journalisé en
   `WARNING` avec kind/source/`fact_id`, plus un compteur par kind.~~ **fait**
2. ~~lecteur borné, `WatchStateView.for_subject()`, `StateScopeError`, avec l'ordre du §2-F.~~
   **fait** (`a9da449`) — les interpreters n'ont pas été touchés : la signature
   `interpret(fact, state)` est intacte et la pureté préservée.
3. ~~`FactLedger.stream()` → `AsyncIterator` sur curseur serveur.~~ **fait** (`75a2bbc`)
4. `ReferenceReplay` + chemin rapide en mémoire + test d'équivalence — **recommandé à l'abandon,
   décision en attente.** Le raisonnement de la spec tenait à la complexité quadratique du rejeu :
   `load_state` était dans la boucle et lisait toute l'église. Le point 2 l'a supprimée — le rejeu
   est désormais linéaire, à trois lectures ponctuelles indexées par fait. Le chemin rapide
   n'économiserait plus que ces trois lectures, au prix d'une **seconde implémentation de
   l'évolution de l'état**, qui doit refléter exactement la matérialisation ; c'est précisément
   pourquoi la spec exigeait un test d'équivalence. On ajouterait le risque le plus cher du lot
   pour le gain le plus faible. La clause d'arrêt du lot s'applique à ce point comme au reste.

   Conséquence pour le lot 6 : le `Simulator` se construira sur `RebuildProjections` lui-même,
   avec des dépôts en mémoire — c'est le même objet, il n'a jamais eu besoin d'être dédoublé.
5. ~~`actor_account_id` exigé au registre pour tout kind capable de produire `ExcludeForever`.
   Avertissement quand un `Emit*Facts` est construit avec `intake=None`.~~ **fait**
6. Test de charge : 1 000 faits sur une église de 5 000 membres. **Si le gain n'est pas d'un ordre
   de grandeur, la spec est fausse et on s'arrête** — clause reprise telle quelle. La mesure est le
   **nombre de requêtes**, pas la durée : c'est l'invariant qu'on veut tenir (« le coût d'un fait ne
   dépend plus de la taille de l'église »), il est déterministe, et il se mesure sans Postgres —
   dont le daemon n'est pas joignable dans cet environnement.

### Lot 3bis — Les gestes du responsable entrent au ledger — **livré** (`6b02dfa`, `1b10948`)

Le ledger ne contient que des **faits**. Les gestes posés *sur* un cas n'y sont pas : l'avoir ouvert
(`first_seen_at`), avoir appelé (`first_contact_at`, `watch_contact_attempts`), l'avoir fermé avec
une issue (`outcome`, `closed_by_account_id`), avoir posé un geste (`gestures_count`), avoir remis
une consolation (`delivered_at`). Une reprojection les effaçait donc **sans pouvoir les
reconstruire** — y compris la chaîne d'épisode, qui se calcule depuis les cas clos supprimés, et
les deux métriques du pilote.

Quatre `FactKind` nouveaux — `CASE_SEEN`, `CASE_CLOSED`, `CONTACT_ATTEMPTED`,
`CONTACT_ANSWERED` — et trois règles qui les rendent sûrs :

- **le geste vise la personne, pas un identifiant de cas.** Un rejeu recrée les cas avec de
  nouveaux identifiants ; il y a au plus un cas vivant par personne, et c'est celui-là qu'on vise ;
- **l'agrégat tranche avant l'émission.** Un geste refusé déjà écrit ferait échouer chaque rejeu
  ultérieur, sur un acte qui n'a jamais eu lieu ;
- **les actes traversent l'exclusion.** Fermer le cas d'un défunt est justement ce qu'on attend du
  responsable ; le refuser ferait de la mort de quelqu'un un bug d'interface.

La péremption dure a suivi : elle vit dans l'interpreter, qui reçoit le décompte et l'origine du
cas dans le fait. Elle était une décision de commande, donc perdue au rejeu.

**Le garde-fou a rétréci en conséquence** : ne bloquent plus qu'une consolation déjà remise et les
gestes comptés. La reprojection redevient une opération ordinaire sur une église vivante.

À noter : le test d'équivalence prévu au lot 2 (`ReferenceReplay` ≡ `RebuildProjections`) n'aurait
rien protégé ici — les deux chemins détruisent autant, donc il serait passé au vert sur une
sémantique fausse.

### Lot 3 — Le temps produit enfin quelque chose

1. ~~**`CheckFiredV1`** — le chaînon manquant.~~ **fait** (`c068dfb`)
2. ~~Idempotence et concurrence : `fact_id = uuid5(ns, check_id)`, `FOR UPDATE SKIP LOCKED`,
   `mark_fired` avant l'entrée du fait.~~ **fait** — l'échéance porte aussi un `payload`
   (migration `e7fc0c1d2e3f`), sans lequel l'interpreter du tir devrait relire un état qui a bougé.
3. ~~`PresenceRecordedV2` (datée) : pose `absence_watch`, annule la précédente.~~ **fait**
   (`50f0658`) — la date vient du **rythme du groupe** (cadence déclarée, N-ième occurrence
   attendue + marge), calculée côté Présence et figée dans le fait.
4. ~~Le nombre d'occurrences **tenues** voyage dans le payload du `CHECK_FIRED`.~~ **fait** — par
   le port `CheckContext`. Compter les rencontres tenues dissout le problème de l'acquittement :
   une rencontre non tenue n'existe pas, donc personne ne l'a manquée.
5. ~~Réévaluation nocturne des `HELD`~~ **fait** (`f99606d`), avec la correction de
   `SignalStatus.OPEN` devenu inatteignable : un cas relâché va chez son destinataire
   (`HELD → ASSIGNED`) au lieu de redevenir « prenable ». Quatrième passe sur `platform_router`.
6. ~~`FactKind.JOINED_GROUP` + source `groups` ; `CoverageGap.BLIND` ; `CoverageSignal`
   matérialisable.~~ **fait** (`adbf6b4`) — les deux moitiés de la décision 3 sont livrées.
   L'armement du regard est écrit une fois (`absence_watch.py`) et partagé par la présence et
   l'adhésion, pour qu'ils ne puissent pas diverger. Le défaut du groupe aveugle porte sur le
   **groupe**, jamais sur ses membres : accuser quelqu'un d'un silence qui est le nôtre serait
   l'erreur exactement inverse.

**Lot 3 clos.**

### Lot 4 — Le régime SHADOW, seul — **livré** (`aca1150`)

`held_reason` (une **raison de rétention**, pas un état — la machine à états n'a pas bougé),
`watch_tenant_regimes`, et le rapport « voici ce que Dorea aurait signalé ».

Quatre décisions qui font que ça tient :

- **l'absence de ligne vaut `SHADOW`.** Le rodage ne dépend ni d'un provisionnement ni d'un
  backfill : aucune église ne peut se mettre à parler par oubli ;
- **même le déclaré est retenu.** Le plafond laisse toujours passer « appelez-moi » ; le rodage
  non — une église qui n'a pas annoncé Dorea à ses responsables ne leur envoie aucun cas ;
- **la passe nocturne ne touche jamais au rodage.** C'est le pire bug possible du module : relâcher
  un cas retenu par le rodage ferait parler toute seule, la nuit, une église qui observait ;
- le rapport suit **l'ordre de l'arbitrage** — la file telle qu'elle aurait été. Il ne classe
  personne et ne propose aucune action : le rodage sert à décider si le moteur voit juste.

Hors lot : la route et l'envoi du rapport hebdomadaire, et la sortie de rodage côté surface (le
dépôt sait la faire, personne ne l'appelle encore).

### Lot 5 — Les chantiers produit — **livré** (`2d3e26c`, `76c1426`, `c0a7aba`)

- **§5 le mandat** — `BROADCAST_WIDER` à côté du compte Business : deux clés, le droit de payer et
  le droit de parler au nom d'un corps. Erreur distincte, parce qu'un refus de mandat n'est pas un
  refus de paiement ;
- **§2 le compteur au dénominateur** — `engagement_count` seulement si l'annonce est plafonnée, et
  le décompte des confirmés sorti du fil d'Event. `ConsolationDTO` inchangée ;
- **§6 la transparence** — refondée en frontière plutôt qu'allongée en liste d'exceptions, avec sa
  contrepartie : l'arrêt d'urgence du membre, sans motif et absorbant ;
- **§3 le signe de vie** — rétracte un cas `HELD`, n'éteint jamais un cas vu ; `RetractionCause`
  distingue « devenu faux » de « sans objet » ;
- **A l'anniversaire** — domaine, règle et refus posés ; l'adaptateur SQL et les routes restent ;
- **§4 + §7 les documents** — repris le 31/07.

**Ajouts du 30/07/2026 après [Spec_Anniversaire_et_Restitution.md](Spec_Anniversaire_et_Restitution.md) :**

- **A — l'anniversaire.** Aucune dépendance : ni worker, ni moteur, ni ledger. Il rejoint ici la
  famille des **réglages absorbants du membre** — `HIDDEN` éteint tout comme `DO_NOT_CONTACT`,
  et c'est la même idée que l'invariant de transparence de §6. Les deux se livrent ensemble.
  *Piège de frontière à trancher :* `birthday_scope = GROUPS` est défini comme « les groupes à
  politique d'alerte forte », or cette notion est `watch_group_type_policies` — une table de la
  **veille**. Faire lire le moteur de veille par un encart d'anniversaire est un mauvais échange :
  en V1, `GROUPS` = tous ses groupes.
- **La note du responsable — livrée** (`a9bec3d`). Elle débloque la restitution : R1 et R2
  résumaient des notes libres qui n'existaient nulle part. Portée par la tentative de contact,
  écrite une fois à la résolution, jamais listable par le membre, et nommée `commitment` — le nom
  fait partie de la règle.
- **B/R1 — la restitution déterministe**, **après le lot 3bis**. Elle assemble par gabarits ce qui
  existe déjà (épisodes, issues, `previous_case_note`, tentatives de contact, `reason` +
  `annotations`) et se livre sans un token d'IA. Mais elle fait de ces champs la surface produit —
  or c'est exactement ce qu'une reprojection efface aujourd'hui. Promettre une mémoire qu'une
  commande de maintenance supprime serait pire que ne rien promettre.
- **B/R2 — le résumé IA**, quand des `commitment` longs existeront réellement. Son post-filtre
  (« marqueurs d'inférence, côté texte ») peut réutiliser `forbidden_reason()`, déjà écrit pour les
  `FactKind`. Hors périmètre tant que le pilote n'a pas produit de vraies notes.

`Decisions` §2 (compteur au dénominateur, et `participant_count` sorti du fil Event), §5 (mandat
`BROADCAST_WIDER` à côté de `is_business`), §6 (invariant de transparence posé en domaine :
`is_listable_to_subject`), §3 (signe de vie qui rétracte un `HELD`, avec `RetractionCause`),
§4 + §7 (documents). Indépendants des lots 2 à 4.

### Lot 6 — La boucle froide, pendant le pilote

`Simulator` = `ReferenceReplay` sur stores en mémoire ; `OutcomeJudge` = extension de
`MeasureConcernPrecision` **contre le vrai enum** (écart D) ; rythme du groupe ;
écart-à-soi-même en annotation factuelle ; `Proposer` ; ASSISTED puis STEADY avec bornes en
table. Les quatre interdits structurels tenus par tests : aucun identifiant de personne dans les
modèles, aucun import d'un chemin d'écriture, aucun fait inféré au ledger, aucun score par
personne.

---

## 5. Dépendances

```
Lot 0 ✔ → Lot 1 ✔ → Lot 2 ✔ → Lot 3 ✔ → Lot 3bis ✔ → Lot 4 ✔ →
    (pilote) → Lot 6            ↑
                    Lot 5 : flottant, intercalable
```

État au 30/07/2026, branche `chantier/moteur-veille` : `82959d3` (lot 0), `b9e6223` (lot 1),
`dbf1f83` + `463601d` (lot 2a), `a9da449` (lot 2b), `75a2bbc` (lot 2c), `c068dfb` (lot 3a),
`50f0658` (lot 3b), `f99606d` (lot 3c), `a9bec3d` (note du responsable), `adbf6b4` (fin du
lot 3), `6b02dfa` + `1b10948` (lot 3bis), `aca1150` (lot 4). **824 tests**, ruff propre.

**Migrations validées contre un vrai Postgres** (17.6) le 30/07/2026, sur une base jetable montée
sur le serveur natif — le daemon Docker étant injoignable (`500 — check if the server supports the
requested API version`), la base du conteneur reste à migrer par un `alembic upgrade head` quand il
remontera. Ce qui a été prouvé, et qu'aucun test SQLite ne pouvait prouver :

- la chaîne complète (60 révisions, dont `d6fc0c1d2e3f`, `e7fc0c1d2e3f`, `f8fc0c1d2e3f`) s'applique
  d'un bout à l'autre ;
- les trois dernières sont **réversibles** : aller-retour `downgrade -3` / `upgrade head` ;
- le **rattrapage** de `d6fc0c1d2e3f` fonctionne sur des données réelles : un cas orphelin a bien
  été rattaché au propriétaire actif de son église (l'`UPDATE … FROM` est du SQL Postgres, non
  exprimable en SQLite) ;
- et son **échec bruyant** fonctionne aussi : sur une église sans propriétaire, la migration lève
  avec un message actionnable **et ne laisse aucun état à moitié appliqué** — le DDL étant
  transactionnel, la base reste à la révision précédente, colonne toujours nullable.

Le lot 2 est un prérequis **dur** du lot 6, pas une optimisation : sans `ReferenceReplay`, il n'y
a pas de simulateur.

---

## 6. Hors périmètre, dit explicitement

- Tout **score par personne**, caché ou visible.
- L'**étage 05** (notification, budget de parole) — spec séparée, après le worker.
- Le **Compagnon relationnel** — barré derrière l'escalade, inchangé.
- Le découpage `private_subject` / `shared_note` du rendez-vous (`Decisions` §1.6), P2.
- La **route de restitution** « ce que Dorea retient de moi » (`Decisions` §6.3).
- Tout apprentissage sur le **contenu** : la calibration ne lit que des issues et des horodatages.
