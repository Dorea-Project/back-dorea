# Moteur de veille — corrections et régime hybride de calibration

> **Nature :** spec d'exécution, trois parties. La partie 1 corrige ce qui est fragile. La
> partie 2 fait entrer le temps dans le moteur — le worker. La partie 3 ajoute le régime
> hybride : une boucle froide qui observe, simule et calibre, sans jamais décider d'un cas.
>
> **Le principe qui gouverne les trois parties :**
>
> > La boucle chaude décide — cinq étages, déterministes, inchangés.
> > La boucle froide observe et calibre — elle ne produit que des propositions de `WatchParam`.
> > La frontière entre les deux est structurelle : la boucle froide n'a pas le droit d'écrire
> > un effet, et aucun objet de calibration ne porte l'identifiant d'une personne.
>
> Références code au 30 juillet 2026. Complète `Decisions_2026-07-30.md` *(fourni hors dépôt)*
> (qui reste valable) et s'appuie sur la carte
> [Veille_Moteur_Carte_du_Code.md](Veille_Moteur_Carte_du_Code.md).

---

## 0. Le constat qui ordonne tout

Relecture faite avant d'écrire, un fait qu'aucun document ne dit :

**La détection d'absence n'a pas d'émetteur.** `CasePriority.ABSENCE` existe dans
[`effects.py`](../app/contexts/watch/domain/effects.py), l'arbitrage sait la trier, la machine à
états sait la porter — mais aucune source n'émet de `OpenCase(origin=ABSENCE)`. `attendance`
n'émet que `PRESENCE_RECORDED` (le retour) ; le `pulse_service` calcule le pouls pour les écrans
pastoraux mais ne parle pas au moteur. *« Awa, trois rencontres, sans nouvelles »* — la phrase
fondatrice du produit — n'est aujourd'hui produite par rien.

C'est cohérent avec la doctrine (le silence ne peut pas entrer comme fait, donc seule une
**échéance qui tombe** peut le constater), et c'est pour ça que l'ordre de ce document n'est pas
négociable : les corrections d'abord (le moteur va être sollicité), le worker ensuite (il rend la
détection possible), la calibration enfin (elle règle une détection qui existe).

---

# PARTIE 1 — Corrections

## 1.1 Le lecteur d'état paresseux

### Le défaut, mesuré

Chaque `Intake.submit()` appelle `load_state()`, qui exécute **trois requêtes à l'échelle du
tenant** : `live_cases(tenant_id)` (objets ORM complets), `excluded_subject_ids(tenant_id)`,
`open_neutralizations(tenant_id)`. Les interpreters et l'arbitrage ne posent pourtant que quatre
questions, toutes bornées à `(subject_id, owner_id)` — et **les index pour ces accès étroits
existent déjà** (`ix_watch_signals_subject`, `ix_watch_signals_owner`).

Conséquence : le coût d'un fait est proportionnel à la **taille de l'église**, pas au fait. Une
église de 5 000 membres paie ~100 fois le prix d'une église de 50 pour écrire la même présence.
Et à la reprojection, `load_state()` est dans la boucle : complexité quadratique sur l'opération
qu'on lance précisément quand quelque chose est déjà cassé.

### La décision — remplacer la vue matérialisée par un lecteur

`WatchStateView` (dataclass de données) devient `WatchStateReader` (objet de requêtes), **même
interface publique** :

```python
class WatchStateReader:
    """Les quatre questions d'un interpreter, répondues à la demande, bornées au sujet.

    Le contrat reste : lecture seule, aucun effet de bord, mêmes réponses que la vue
    matérialisée sur les mêmes données — c'est ce que le test d'équivalence (§1.5) prouve."""

    async def is_excluded(self, subject_id: UUID) -> bool: ...          # 1 EXISTS indexé
    async def neutralizations_of(self, subject_id: UUID) -> tuple[...]: ...  # 1 SELECT indexé
    async def case_of(self, subject_id: UUID) -> OpenCaseView | None: ...    # 1 SELECT indexé
    async def open_cases_of_owner(self, owner_id: UUID | None) -> int: ...   # 1 COUNT indexé
```

Trois requêtes tenant-entières deviennent au plus quatre requêtes ponctuelles par fait — et en
pratique deux ou trois, car un fait de présence sur quelqu'un sans cas s'arrête tôt.

**Ce qui ne change pas, et c'est la contrainte de conception :** les interpreters restent purs.
Ils ne reçoivent pas le reader — la couche applicative interroge le reader **pour le sujet du
fait** et construit une `WatchStateView` réduite (le sujet + son éventuel propriétaire), qu'elle
leur passe comme aujourd'hui. La pureté est préservée, la signature `Interpreter.interpret(fact,
state)` est intacte, aucun interpreter n'est réécrit.

Le protocole `Interpreter` ne bouge pas ; seule `load_state()` change d'implémentation :

```python
async def load_state(reader: WatchStateReader, fact: Fact) -> WatchStateView:
    """L'état RÉDUIT AU SUJET du fait — tout ce qu'un interpreter a le droit de demander."""
```

**⚠ Un garde-fou nouveau devient nécessaire.** La vue réduite ne contient que le sujet du fait ;
un interpreter futur qui voudrait raisonner sur *une autre personne* recevrait des réponses
vides et se tromperait en silence. La vue réduite lève donc `StateScopeError` si on l'interroge
sur un `subject_id` différent de celui pour lequel elle a été construite. C'est un invariant de
plus, pas une gêne : un interpreter n'a **jamais** eu de raison légitime de regarder quelqu'un
d'autre.

### Fichiers touchés

| Fichier | Modification |
| :-- | :-- |
| `watch/application/interpretation.py` | `WatchStateView.for_subject(...)` + `StateScopeError` |
| `watch/application/intake.py` | `load_state(reader, fact)` ; `Intake` prend un reader |
| `watch/application/ports.py` | `SignalStore.case_of_subject()`, `open_cases_count(owner)` ; `NeutralizationStore.is_excluded(subject)`, `neutralizations_of_subject()` |
| `watch/infrastructure/persistence/signals.py` | les deux requêtes indexées + le COUNT |
| `watch/infrastructure/neutralization_store.py` | les deux requêtes ponctuelles |
| `watch/application/projections.py` | voir §1.2 |

`live_cases(tenant_id)` **reste** — il sert les écrans et la calibration (§3), plus le chemin
d'écriture.

## 1.2 La reprojection en curseur, vérifiée contre elle-même

Deux changements :

- **`FactLedger.stream()` devient un flux** (`AsyncIterator[Fact]`, curseur serveur), jamais une
  liste. 200 000 faits ne montent plus en RAM.
- **Le chemin rapide est vérifié par le chemin lent.** La reprojection naïve actuelle (état relu
  à chaque pas) est conservée sous le nom `ReferenceReplay` — elle devient l'implémentation de
  référence du test de déterminisme. Le chemin de production (`RebuildProjections`) tient l'état
  en mémoire et le met à jour au fil des effets qu'il écrit. Un test de fixture (église
  synthétique, ~5 000 faits couvrant tous les kinds) exige que les deux produisent un état final
  **identique octet pour octet**. Si le chemin rapide diverge un jour, c'est ce test qui le dit
  — pas une église.

## 1.3 L'acteur d'une exclusion ne peut plus être le défunt

`_actor_of()` retombe sur `fact.subject_id` quand le payload ne porte pas d'acteur. Sur une
exclusion `DECEASED`, le défunt est alors enregistré comme ayant déclaré sa propre exclusion —
une donnée d'audit fausse sur l'acte le plus grave du système.

**Décision :** les kinds dont l'interpreter peut produire `ExcludeForever` exigent
`actor_account_id` dans `required_payload_keys` (contrôle §5.1-3 de l'intake, qui **lève**). Le
repli sur le sujet reste légitime pour tout le reste — une auto-déclaration *est* un acte du
sujet. La règle s'écrit dans le registre, à côté des sources concernées, avec un test qui balaie :
tout kind capable d'exclure exige un acteur.

## 1.4 Les effets différés cessent d'être silencieux

`MaterializationResult.deferred` est renvoyé puis jeté par tous les appelants. Un interpreter
peut proposer `SCHEDULE_CHECK` et ne rien produire, sans qu'aucune trace n'existe.

**Décision :** le `Materializer` journalise chaque effet différé en `WARNING` avec le kind, la
source et le fact_id — et un compteur par kind est exposé (métrique interne). À la livraison du
worker (§2), `SCHEDULE_CHECK` et `CANCEL_SCHEDULED_CHECKS` sortent de la liste des différés ; le
warning ne doit alors plus jamais apparaître en production, ce qui en fait aussi un test de
complétude du déploiement.

Dans le même geste : un **avertissement au démarrage** quand un `Emit*Facts` est construit avec
`intake=None` (le no-op silencieux du patron `Intake | None`, §12 de la carte).

## 1.5 Tests de la partie 1

1. **Équivalence** : sur le fixture, `WatchStateReader` répond identiquement à l'ancienne vue
   matérialisée pour chaque fait du journal.
2. **Portée** : interroger la vue réduite sur un autre sujet lève `StateScopeError`.
3. **Déterminisme** : `ReferenceReplay` ≡ `RebuildProjections` sur le fixture complet.
4. **Charge** : lot de 1 000 faits sur une église synthétique de 5 000 membres / 100 000 faits —
   le gain attendu est d'un ordre de grandeur ; s'il n'y est pas, la spec est fausse et on
   s'arrête.
5. **Acteur** : un fait menant à `ExcludeForever` sans `actor_account_id` est refusé à l'intake.

---

# PARTIE 2 — Le worker : le temps entre dans le moteur

## 2.1 Ce que le worker est, et n'est pas

Le worker ne décide **rien**. Il fait une seule chose : quand une échéance tombe, il écrit un
fait `CHECK_FIRED` au ledger, par l'intake, comme n'importe quelle source. La décision reste aux
interpreters — c'est ce qui garde le temps **rejouable** : rejouer le journal rejoue les
échéances tombées, dans le même ordre, avec le même résultat.

```
posé aujourd'hui                          tombera plus tard
────────────────                          ────────────────
interpreter propose ScheduleCheck(at, kind)
   └─ Materializer écrit → watch_scheduled_checks (nouvelle table, projetée)
                                          worker (cron, 1/h) :
                                            SELECT … WHERE due_at <= now AND fired_at IS NULL
                                            pour chaque : Intake.submit(Fact(
                                                source="watch_scheduler",
                                                kind=CHECK_FIRED,
                                                payload={check_id, check_kind, …}))
                                            marque fired_at
                                          └─ CheckFiredV1 interprète → effets
```

Idempotence : `fact_id = uuid5(namespace_scheduler, check_id)` — un cron qui repasse n'écrit
rien deux fois (contrôle §5.1-5 de l'intake). Verrouillage : `SELECT … FOR UPDATE SKIP LOCKED`,
pour que deux workers concurrents ne tirent jamais le même check. Pas de broker, conforme à la
décision V1 : un `scripts/watch_scheduler.py` one-shot, cadencé par cron, sur le modèle de
`watch_concerns.py`.

### Matérialisation

`SCHEDULE_CHECK` et `CANCEL_SCHEDULED_CHECKS` deviennent matérialisables : la table
`watch_scheduled_checks(id, tenant_id, subject_kind, subject_id, kind, due_at, fired_at,
cancelled_at, source_ref)` est une **projection** — purgée et reconstruite au rejeu comme les
autres. `CoverageSignal` devient matérialisable vers `watch_coverage_gaps` (le magasin existe).

## 2.2 Premier usage : la détection d'absence — l'émetteur manquant

C'est ici que naît enfin `OpenCase(origin=ABSENCE)`. Le mécanisme respecte l'asymétrie
fondatrice : on ne constate jamais le silence, on pose une échéance **au moment d'une parole**,
et c'est l'échéance qui, en tombant, regarde ce qui s'est passé depuis.

- `PresenceRecordedV1` (V2 de l'interpreter, datée) propose, en plus de ses effets actuels :
  `ScheduleCheck(at = occurred_at + fenêtre_du_groupe, kind = "absence_watch")` — et
  `CancelScheduledChecks(kind="absence_watch")` pour remplacer l'échéance précédente. Une
  présence repousse toujours l'échéance : tant qu'Awa vient, rien ne tombe jamais.
- Quand le check tombe, `CheckFiredV1` reçoit dans le payload ce que le worker a joint : le
  nombre d'occurrences du groupe depuis la dernière présence (calculé côté `attendance`, sur les
  rencontres **tenues** — `OCCURRENCE_ACKNOWLEDGED` protège des semaines sans rencontre). Si ce
  nombre atteint le seuil et qu'aucune neutralisation ne couvre : `OpenCase(origin=ABSENCE,
  reason="Sans nouvelles — N rencontres de <groupe>")`. Sinon : rien, et l'échéance suivante
  est posée.

La règle des groupes reste celle des politiques : seuls les types de groupe à politique d'alerte
forte (cellules) posent des échéances — `watch_group_type_policies` l'écrit déjà.

## 2.3 Deuxième usage : la réévaluation des `HELD`

Une passe nocturne par tenant : pour chaque responsable sous son plafond, les cas `HELD` les
plus anciens passent `OPEN` (transition existante), dans l'ordre de l'arbitrage. C'est une
opération de **matérialisation**, pas une décision — elle n'invente rien, elle émet ce qui avait
été détecté et retenu.

## 2.4 Nouveaux paramètres

Trois lignes au catalogue `WatchParam`, avec défauts :

```
ABSENCE_OCCURRENCES_THRESHOLD = 3   # occurrences manquées avant ouverture
ABSENCE_CHECK_GRACE_DAYS      = 2   # marge après la rencontre attendue
HELD_REVIEW_HOUR_UTC          = 2   # heure de la passe nocturne
```

## 2.5 Tests de la partie 2

1. Une présence pose une échéance et annule la précédente ; le rejeu reproduit la même chaîne.
2. Un check tombé sur une personne neutralisée (deuil, voyage) n'ouvre **rien**.
3. Un check tombé à N ≥ seuil ouvre un cas `ABSENCE` ; à N < seuil, il repose une échéance.
4. Deux exécutions du worker sur les mêmes checks dus n'écrivent qu'un seul `CHECK_FIRED` chacun.
5. La passe `HELD` ne dépasse jamais le plafond du responsable, et respecte l'ordre d'arbitrage.
6. `OCCURRENCE_ACKNOWLEDGED` sur deux semaines gèle le compteur : personne ne devient « absent »
   d'une rencontre qui n'a pas eu lieu.

---

# PARTIE 3 — Le régime hybride : observer, simuler, calibrer

## 3.1 Ce que « hybride » veut dire ici — et ce qu'il ne voudra jamais dire

La boucle froide apprend **des issues** pour régler **des seuils**. Elle ne touche jamais un
cas, jamais une personne. Sa seule sortie est une `CalibrationProposal` : « pour cette église,
pour ce type de groupe, tel paramètre devrait valoir tant, et voici ce que ça aurait changé ».

**Les interdits, structurels — pas des consignes :**

1. **Aucun objet de calibration ne porte d'identifiant de personne.** Les agrégats sont par
   `(tenant, group_type)` au plus fin. Un test balaie les modèles du sous-module et échoue si
   une colonne `subject_id`/`person_id`/`account_id` apparaît.
2. **La boucle froide ne peut pas écrire un effet.** Le sous-module `calibration` n'importe ni
   `Materializer`, ni `SignalStore` en écriture — un test d'imports l'atteste, sur le modèle du
   test qui inspecte les littéraux du résolveur.
3. **Aucun fait inféré n'entre au ledger.** La calibration ne passe jamais par l'intake. Ses
   sorties vivent dans ses propres tables.
4. **Pas de score par personne, visible ou non.** La sensibilité au contexte s'exprime par deux
   mécanismes publics et contestables : le rythme du groupe (§3.4) et l'écart-à-soi-même comme
   annotation factuelle (§3.5). La famille `score` de `FORBIDDEN_KIND_PATTERNS` reste le
   grillage ; ce paragraphe en est la doctrine côté calibration.

## 3.2 L'insight : le ledger est un simulateur

`RebuildProjections` sait rejouer un journal sous une `ArbitrationPolicy` donnée. Le simulateur
est ce rejeu, **en mémoire, sans écrire** :

```python
class Simulator:
    """Rejoue le ledger d'un tenant sous des paramètres candidats. N'écrit rien.

    Réutilise ReferenceReplay (§1.2) avec des stores en mémoire — c'est la même mécanique
    que le test de déterminisme, pointée sur un autre usage."""

    async def run(self, tenant_id: UUID, candidate: dict[WatchParam, int]) -> SimulationOutcome
```

`SimulationOutcome` compte : cas ouverts, cas `HELD`, délai simulé d'ouverture, et — croisé avec
la vérité terrain — faux positifs et détections manquées.

## 3.3 La vérité terrain existe déjà en base

`OutcomeJudge` lit ce que les humains ont constaté, sans rien interpréter de neuf :

| Signal observé | Verdict |
| :-- | :-- |
| cas fermé `WELL` avec un seul contact, vite | probable **faux positif** — seuil trop sensible |
| `THIRD_PARTY_CONCERN` arrivé **avant** que le seuil d'absence n'ait déclenché | **détection manquée** — seuil trop lent ; un humain a vu avant le moteur |
| cas `ABSENCE` fermé `DIFFICULTY_*` ou `LEFT_CHURCH` | **vrai positif** |
| `first_seen_at` nul à 7 jours, récurrent chez un responsable | problème de **débit**, pas de seuil — pointe vers `OPEN_CASES_CAP` |

C'est ça, « comprendre le jeu de veille » : mesurer ses propres seuils contre ce que les
responsables ont constaté — jamais prédire des personnes.

## 3.4 Le seuil relatif au rythme du groupe

Le défaut actuel : « 3 occurrences » traite identiquement une cellule hebdomadaire et une
commission mensuelle — trois semaines de silence ici, un trimestre là.

**Décision :** le rythme est une propriété **du groupe**, apprise des rencontres tenues
(médiane de l'intervalle sur une fenêtre glissante, côté `attendance`, où vivent les
rencontres). Le seuil reste exprimé **en occurrences** (`ABSENCE_OCCURRENCES_THRESHOLD`) ; le
rythme ne sert qu'à convertir l'occurrence en date d'échéance (`ScheduleCheck.at`). Une cellule
vivante détecte à J+10 au lieu de J+21 ; une commission mensuelle ne crie pas au silence après
trois semaines normales.

Aucune donnée individuelle : le rythme est un agrégat de groupe, cohérent avec
`SubjectKind.GROUP` et avec la doctrine du compagnon collectif.

## 3.5 L'écart-à-soi-même — un fait, jamais un chiffre

Le besoin légitime derrière l'intuition du scoring : trois absences d'un membre très régulier ne
disent pas la même chose que trois absences d'un occasionnel. La réponse conforme :

Quand un cas `ABSENCE` s'ouvre, l'interpreter peut joindre une **annotation descriptive**,
dérivée des seules présences enregistrées (de la parole, jamais du silence) :

> « Présente 9 rencontres sur 10 ces six derniers mois — silence inhabituel. »

Trois contraintes qui la distinguent d'un score :

- c'est une **phrase de faits vérifiables**, que le responsable lit et peut contester — pas un
  nombre qui ordonne ;
- elle **n'entre pas dans l'arbitrage** : elle ne change ni la priorité, ni l'ordre de la file,
  ni le plafond. La priorité reste par origine du dire, point ;
- elle est listable par le membre (invariant de transparence §6 des Décisions : dérivée de ses
  propres actes).

Implémentation : le calcul vit côté `attendance` (qui a les présences), passe dans le payload du
`CHECK_FIRED` joint par le worker, et `CheckFiredV1` le pose en `annotation` — le canal existant
d'`EnrichCase`/`OpenCase`.

## 3.6 Les trois régimes de rodage

Un état par tenant — `watch_tenant_regime(tenant_id, regime, since, changed_by)` :

| Régime | Comportement | Sortie |
| :-- | :-- | :-- |
| **SHADOW** | le pipeline tourne entier, mais la matérialisation marque tout cas `HELD` avec `held_reason='shadow'` : détecté, journalisé, **jamais émis** à un responsable | un rapport hebdomadaire au pasteur : « voici ce que Dorea aurait signalé » + précision estimée par `OutcomeJudge` contre les gestes spontanés |
| **ASSISTED** | les cas sont émis normalement ; chaque `CalibrationProposal` attend une approbation (pasteur/admin) avant d'écrire le `WatchParam` | proposition + simulation à l'appui : « avec ce seuil, 4 cas de moins, 1 détection plus tôt » |
| **STEADY** | comme ASSISTED, mais les propositions **dans des bornes dures** s'appliquent seules, tracées et réversibles | journal des ajustements, alerte si une borne est touchée |

Les bornes de STEADY sont elles-mêmes des données (`watch_param_bounds`), jamais du code :
`ABSENCE_OCCURRENCES_THRESHOLD ∈ [2, 6]`, `OPEN_CASES_CAP ∈ [3, 10]`, etc. Une proposition hors
bornes retombe en ASSISTED — elle attend un humain.

Le point d'implémentation clef : SHADOW réutilise le canal `HELD` existant (détecté-non-émis est
déjà un concept du moteur) — on ajoute une **raison de rétention**, pas un état. La machine à
états ne bouge pas.

**Défaut produit : toute église nouvelle démarre en SHADOW.** C'est le rodage — et l'argument
commercial : *Dorea s'accorde à votre église avant de parler.*

## 3.7 Les objets du sous-module `watch/calibration/`

| Objet | Rôle | Écrit |
| :-- | :-- | :-- |
| `Simulator` | rejeu en mémoire sous paramètres candidats | rien |
| `OutcomeJudge` | la vérité terrain depuis les issues et les inquiétudes | rien |
| `Proposer` | balayage **borné** de l'espace de paramètres (grille, pas d'optimiseur — l'espace est minuscule), croise simulation et verdicts | `calibration_proposals` |
| `CalibrationProposal` | `(tenant, param, current, proposed, evidence, status)` — l'objet approuvable | — |
| `ApplyProposal` | l'écriture du `WatchParam`, après approbation ou dans les bornes STEADY | `watch_parameters` (le canal existant) |

Cadence : hebdomadaire par tenant (`scripts/watch_calibration.py`, cron, comme les autres). Le
volume d'une église pilote ne justifie rien de plus fréquent — et une calibration qui bouge plus
vite que les humains ne constatent calibrerait du bruit.

**La métrique de la calibration elle-même :** la précision des cas ouverts (part des cas fermés
en vrai besoin), église par église, doit monter d'un mois sur l'autre. Si elle ne monte pas, la
boucle froide n'apprend rien et on la coupe — même clause d'arrêt que l'animation du compagnon.

## 3.8 Tests de la partie 3

1. Aucun modèle de `calibration` ne porte d'identifiant de personne (balayage structurel).
2. `calibration` n'importe aucun chemin d'écriture du moteur (test d'imports).
3. En SHADOW, aucun cas n'apparaît dans `my_cases` d'aucun responsable ; tout est en base.
4. Une proposition hors bornes en STEADY n'est **pas** appliquée et attend une approbation.
5. Le simulateur sur le fixture, paramètres courants, reproduit exactement l'état réel
   (c'est le test de déterminisme §1.5-3, réutilisé).
6. L'annotation d'écart-à-soi-même ne modifie ni la priorité ni l'ordre de la file (test
   d'arbitrage : deux cas identiques, avec et sans annotation, sortent dans le même ordre).

---

## 4. Ordre d'exécution, et ce qui peut attendre

| Rang | Chantier | Statut |
| :-- | :-- | :-- |
| 1 | §1.1–1.2 lecteur paresseux + reprojection curseur/référence | **avant le pilote** — le moteur va être sollicité |
| 2 | §1.3–1.4 acteur d'exclusion + différés bruyants | avec le rang 1, petit |
| 3 | §2 worker + détection d'absence + réévaluation `HELD` | **avant le pilote** — sans lui, le différenciateur n'existe pas |
| 4 | §3.6 régime SHADOW seul | **avant le pilote** — c'est le mode de démarrage des églises |
| 5 | §3.4 rythme du groupe + §3.5 écart-à-soi-même | pilote, dès que des rencontres réelles existent |
| 6 | §3.2–3.3, 3.7 Simulator / OutcomeJudge / Proposer, ASSISTED puis STEADY | **pendant le pilote** — la boucle froide n'a rien à apprendre avant qu'il y ait des issues |

La ligne d'honnêteté du document : les rangs 1 à 4 sont nécessaires au pilote. Les rangs 5 et 6
sont ce qui fait du pilote un **entraînement** — le moteur se roule sur cent églises réelles, et
c'est cette accumulation (paramètres calibrés par type de groupe, précision mesurée, régimes
éprouvés) qui constituera l'avantage que WhatsApp ne peut pas copier. Mais en pilote, l'Étape 0
terrain calibre à la main plus vite qu'un simulateur : si le calendrier serre, le rang 6 glisse
sans que rien d'autre ne bouge.

## 5. Hors périmètre, dit explicitement

- **Tout score par personne**, caché ou visible — §3.1, définitif.
- L'étage 05 (notification, budget de parole) — spec séparée, après le worker.
- Le Compagnon relationnel — toujours barré derrière l'escalade, inchangé.
- Tout apprentissage sur le **contenu** (notes, annonces, sermons) : la calibration ne lit que
  des issues et des horodatages, jamais du texte.
