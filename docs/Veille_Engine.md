# Moteur de veille — noyau fermé, bords ouverts

**Statut :** blocs 1 et 2 livrés — ledger, registre, intake, interpreters purs, arbitrage
complet (fusion, priorité, plafond), machine à états du `Signal`, mémoire du lien, reprojection.
Bloc 3 (échéances, worker, rétraction) à venir.
**Étend :** [M8_Announcement_Watch_Effects.md](M8_Announcement_Watch_Effects.md),
[M6_Attendance_Model.md](M6_Attendance_Model.md), [M7_Pastoral_Intelligence.md](M7_Pastoral_Intelligence.md).

---

## 1. Le principe

On ne protège pas les invariants du produit par la discipline, on les protège par la structure.
Un greffon ne peut pas violer ce à quoi il n'a pas accès.

Trois zones, un sens de flux unique :

- **les sources** proposent — elles n'émettent que des faits, et n'écrivent jamais d'état ;
- **l'engine** décide — fermé, versionné, cinq étages ;
- **les sorties** restituent — elles ne lisent que des vues autorisées.

Aujourd'hui deux sources sont enregistrées : les **Annonces** (`LIFE_EVENT_ANNOUNCED`) et la
**Présence** (`PRESENCE_RECORDED`). Aucune des deux n'écrit plus rien elle-même.

---

## 2. Ce que le typage rend impossible

C'est le cœur du dispositif. L'asymétrie fondatrice — *la parole est un signal, le silence n'est
rien* — n'est pas une règle de gestion qu'on applique à chaque écriture : c'est l'absence de
`DID_NOT_REACT`, `MEMBER_INACTIVE_ON_APP`, `MESSAGE_UNREAD` dans `FactKind`.

Un développeur futur, bien intentionné, voudra un jour signaler les membres inactifs sur
l'application. Il n'y a pas de forme pour le dire. S'il en ajoute une, `SourceRegistry.register`
lève au **démarrage** de l'application — pas à la revue de code, pas en production.

Trois familles sont fermées ([facts.py](../app/contexts/watch/domain/facts.py)) :

| Famille | Ce qu'elle interdit |
|---|---|
| `inaction` | `did_not_*`, `never_*`, `*_inactive`, `unread`, `ignored` |
| `financier` | `donation`, `contribution`, `tithe`, `offering`, `payment`… |
| `inféré` | `*_inferred`, `*_predicted`, `sentiment_*`, `*_score` |
| `télémétrie` | `*_opened`, `session_start`, `login`, `last_seen`, `screen_view`, `activity_ping` |

La quatrième famille est venue de l'algorithme du Compagnon. Elle est le complément indispensable
de la première : on interdisait déjà de **dire** l'absence, il fallait interdire de la
**dériver d'une fréquence**. Sans elle, `COMPANION_OPENED` passait le filtre — et « il l'ouvre
moins souvent » redevenait un signal, déguisé en donnée positive. Ouvrir une application n'est
pas un acte de vie ; ne pas l'ouvrir n'est pas un silence.

La suite d'invariants balaie l'enum entier à chaque exécution des tests, et vérifie qu'aucun
membre ne relève d'une de ces familles.

Le compagnon collectif tient par la même mécanique : son fait porte `subject_kind = GROUP`. Il
n'y a pas de donnée individuelle à protéger — il n'y en a jamais eu.

---

## 3. Le contrat de fait

```python
Fact(
    fact_id,        # idempotence — dérivé de la source, donc stable au rejeu
    tenant_id,      # Dorea est multi-église : sans lui, aucune projection isolable
    occurred_at,    # quand c'est ARRIVÉ — fait courir les durées
    recorded_at,    # quand on l'a APPRIS — donne l'ordre du rejeu et la version d'interpreter
    source,         # greffon enregistré
    kind,           # registre extensible, sous filtre
    subject_kind,   # PERSON | GROUP
    subject_id,
    payload,        # typé, versionné
    consent,        # obligatoire pour certains kinds
    seq,            # ordre TOTAL du ledger — assigné à l'écriture, jamais par la source
)
```

Trois décisions que le document d'architecture ne prenait pas, et qu'il fallait trancher :

**`seq`, l'ordre total.** `recorded_at` peut être à égalité ; `occurred_at` peut remonter le
temps. Sans ordre total reproductible, l'invariant de déterminisme n'est pas testable. C'est la
clé primaire du ledger.

**Le temps entre par le ledger.** Un interpreter ne lit jamais l'horloge — sinon rejouer demain
donnerait un autre résultat. Une échéance se matérialise en `SCHEDULE_CHECK` ; quand elle tombe,
le worker **écrit un `CHECK_FIRED`**. C'est ce fait, pas le tic d'horloge, que le rejeu relit.

**`tenant_id` sur le fait.** Absent du contrat d'origine, indispensable ici.

---

## 4. Les cinq étages

### 01 — Intake ([intake.py](../app/contexts/watch/application/intake.py))

Refuse : source non enregistrée, kind non déclaré par la source, payload incomplet, consentement
manquant, doublon, sujet retiré de la veille. Sinon écrit au ledger.

> **Note sur le rejeu et l'exclusion.** Le contrôle « personne exclue » vit ici, à l'entrée : il
> filtre ce qui **entre**, et le rejeu ne repasse pas par l'intake — il rejoue un journal déjà
> filtré. Le déterminisme tient. Ce qui ne tient pas encore, c'est l'exclusion **rétroactive** :
> un décès survenu en mars et annoncé en avril laisse derrière lui des semaines de faits
> légitimement admis. La réponse n'est pas un second contrôle, c'est la rétraction — bloc 3.

### 02 — Interprétation ([interpretation.py](../app/contexts/watch/application/interpretation.py))

Un interpreter par `FactKind`, **pur** : pas d'I/O, pas de dépôt, pas d'horloge. Il reçoit le
fait et une vue en lecture seule chargée par la couche applicative, et renvoie des propositions.

Il est **versionné** : changer une règle, c'est publier une V2 avec une date d'effet. La version
est choisie sur `recorded_at` — sinon une saisie tardive ressusciterait un interpreter retiré.
Le passé ne change jamais de sens.

Un fait dont le kind n'a **pas encore** d'interpreter n'est pas une erreur : il reste au ledger,
et le jour où l'interpreter arrive, une reprojection lui donne rétroactivement son sens.

### 03 — Arbitrage ([arbitration.py](../app/contexts/watch/application/arbitration.py))

Le seul étage qui décide de ce qui devient visible. Fixe, non extensible. Quatre décisions, dans
cet ordre :

1. **L'exclusion absorbe.** Une personne retirée de la veille ne reçoit plus rien, sauf
   l'exclusion elle-même. Le garde est ici, pas dans chaque interpreter — un seul endroit à
   tenir, valable pour tout greffon présent et futur.
2. **Fusion par personne.** Un second cas sur quelqu'un qui en a déjà un devient un
   enrichissement. Sinon deux responsables appellent la même personne le même soir, chacun se
   croyant seul.
3. **Priorité par origine du dire** — `declared > deadline > announcement > absence`. Personne
   ici ne note la gravité d'une vie.
4. **Plafond de débit.** Au-delà de N cas, le surplus est **retenu** (`HELD`), pas perdu. Un
   responsable noyé ne traite pas plus de cas : il les ignore tous. Le déclaré n'y entre jamais.

Les **nombres** vivent dans `ArbitrationPolicy`, à calibrer sur le terrain. La forme, elle, est
écrite avec la machine à états — jamais après, quand la file du premier responsable déborde.

> Tant que `Referent` n'existe pas, `owner_of()` renvoie NULL et tous les cas sans propriétaire
> partagent le même budget. C'est volontairement le côté prudent de l'erreur : on ne fait pas
> semblant d'avoir réparti la charge.

### 04 — Matérialisation ([materialization.py](../app/contexts/watch/application/materialization.py))

Seul chemin d'écriture. Sait écrire : `NEUTRALISE`, `EXTINGUISH`, `EXCLUDE_FOREVER`,
`OPEN_CASE`, `ENRICH_CASE`, `RECORD_MEMORY`.

Reste différé : `SCHEDULE_CHECK`, `CANCEL_SCHEDULED_CHECKS`, `COVERAGE_SIGNAL` — ils attendent
le worker et le `Referent`. Ils ne sont pas perdus : les faits sont au ledger, et une
reprojection les honorera. C'est vérifié par un test — on simule l'état d'avant le bloc 2, puis
on rejoue avec le store branché, et le cas de l'endeuillée s'ouvre rétroactivement.

### 04 bis — La machine à états ([signal.py](../app/contexts/watch/domain/signal.py))

```
HELD → OPEN → ASSIGNED → IN_CONTACT → CLOSED(outcome)
  └──────┴─────────┴──────────┴────→ RETRACTED
```

Quatre règles **compilées dans les transitions**, pas validées par l'application :

- **`CLOSED` exige un acte humain**, sauf cause système. Sans cette règle, le premier réflexe
  d'exploitation serait de fermer automatiquement les vieux signaux pour « nettoyer la file » —
  et le produit deviendrait un théâtre.
- **`DO_NOT_CONTACT` et `DECEASED` sont absorbants** : aucune transition sortante n'existe.
- **La `reason` est écrite à l'ouverture, jamais réécrite.** Enrichir ajoute une source, pas une
  phrase.
- **`RETRACTED` n'est pas `CLOSED`.** Un signal rétracté n'a rien résolu ; il sort des métriques
  au lieu d'y figurer comme un succès.

`HELD` est un état à part entière, distinct d'`OPEN` : confondre « retenu » et « ouvert » ferait
mentir toutes les mesures du plafond au moment précis où elles comptent.

**Décision en attente :** `ExtinguishCause.LIFE_SIGN` existe au vocabulaire mais **n'est pas**
dans `SYSTEM_CLOSURE_CAUSES`. Autoriser une reconnaissance déposée à fermer un cas serait la
seconde clôture système du produit — c'est un arbitrage à prendre, pas un détail d'implémentation.
Tant qu'il n'est pas pris, le cas reste ouvert : c'est le côté prudent de l'erreur. Une ligne à
changer le jour venu, et un test qui le dit.

### R — Le Referent ([referent.py](../app/contexts/watch/domain/referent.py))

*Une personne, quelqu'un qui la connaît.* Matérialisé **sans créer un champ à maintenir** :
aucun `current_referent_id` sur la personne, aucun `is_primary` sur l'appartenance. Le référent
est **résolu à la lecture**. Un champ que personne n'a intérêt à tenir à jour pourrit en trois
mois, et on retrouve des gens à zéro ou deux primaires — l'indétermination qu'on voulait
supprimer.

Ce qui est stocké, et seulement cela : les **désignations explicites**, l'**override de groupe
primaire**, et l'**historique observé** (pour dater les trous).

**La cascade** — `MANUAL` → `GROUP_LEAD` → `INVITER` → `WELCOME_TEAM` → trou. Un candidat
inéligible ne bloque pas : on continue de descendre.

`GROUP_LEAD` est un **pointeur calculé**. Remplacer Jean par Paul change le référent des dix-huit
membres de Béthel **sans une seule écriture**, et leur histoire relationnelle reste attachée à
elles. C'est exactement ce qu'un groupe WhatsApp ne sait pas faire.

**Le rang des types de groupe est une donnée, pas une constante.** Il vit dans
`watch_group_type_policies` : le résolveur ne contient le nom d'aucun type — c'est vérifié par un
test qui inspecte les littéraux du module. Enrichir `GroupType` devient une insertion de ligne.

Le défaut livré, ordonné par **durabilité du lien** et non par intensité :

| Type | `bears_veille` | `primacy_rank` |
|---|---|---|
| `cellule` | vrai | 1 |
| `ministere` | vrai | 2 |
| `classe` | vrai | 3 |

Une classe d'intégration s'achève en quelques mois, un ministère dure : quelqu'un qui est dans
les deux voit son référent basculer tout seul à la fin de la classe. Aucun type n'est exclu
aujourd'hui — le mécanisme `bears_veille` est en place **avant** le risque, prêt pour le jour où
`COMMISSION` existera.

**Le référent n'est pas le propriétaire d'un signal.** Le premier est un lien durable et **peut
être nul** — « personne ne connaît cette personne » est la donnée la plus utile du module. Le
second est une assignation et ne l'est **jamais** ; quand il faut escalader, le motif est
renvoyé pour être stocké avec le signal — un pasteur qui reçoit un cas inexplicable l'ignore.

> Si l'escalade remplissait le référent, la couverture vaudrait mécaniquement 100 % et la
> métrique la plus vendable du produit ne mesurerait plus rien. Un pasteur référent de deux cents
> personnes n'est le référent de personne.

**Les trous sont datés.** Un trou de trois jours (le responsable vient de partir) et un trou de
huit mois ne portent pas la même information. « Sans référent » n'est pas actionnable ; « sans
référent depuis quatre mois » l'est.

**Désigner est explicite.** Traiter un signal ne crée jamais de référent : un appel ponctuel ne
fait de personne un lien durable. L'écran de résolution *propose* l'action, elle reste un tap
séparé. Sans cette proposition le trou remonte indéfiniment ; implicite, il se comble sur le
papier seulement.

### 05 — Notification

Pas encore construit. Le budget de parole vient avec le bloc 3.

---

## 5. Où vit la neutralisation

Dans `planned_absences`, avec `source = 'announcement'` — **pas** dans une table de projection
séparée.

Neuf fichiers lisent `PlannedAbsenceRepository`, dont sept en lecture pastorale : roster, pouls,
liste de soin, effectif, tendance, trajectoire, arbre de multiplication. Une table séparée les
obligerait tous à unir deux sources, et **oublier un seul site ferait réapparaître un endeuillé
comme absent silencieux** — la panne même qu'on veut supprimer.

La pureté « projection » n'exige pas une table à part : elle exige un **chemin d'écriture
unique** et une purge sûre.

- Le chemin unique est [neutralization_store.py](../app/contexts/watch/infrastructure/neutralization_store.py).
- La purge est `delete_projected(tenant)`, filtrée sur `source` — seule méthode autorisée à
  effacer du projeté. Elle ne touche jamais à ce qu'un membre a déclaré lui-même : sa parole
  n'est pas une projection, et une reconstruction ne doit pas pouvoir l'effacer. C'est testé.

L'exclusion (`watch_exclusions`) est également une projection, reconstruite intégralement.

---

## 6. La reprojection

```
purge du projeté  →  rejeu du ledger par `seq`  →  état identique
```

L'intake n'est pas rejoué : le journal ne contient déjà que des faits admis. L'état est relu à
chaque pas, pour qu'un effet posé par le fait *n* éclaire le fait *n+1*, exactement comme en
direct.

C'est la même opération pour trois besoins : une saisie tardive, une règle corrigée, un
interpreter nouveau qui donne enfin du sens à des faits vieux de six mois.

---

## 7. Ce qui a changé dans l'existant

| Avant | Après |
|---|---|
| `announcements.WatchPort` + `AttendanceWatchAdapter` | supprimés — l'annonce émet un fait |
| `ApplyWatchEffects` | `EmitAnnouncementFacts` — une source, plus un exécuteur |
| `AnnouncementSubject.applied_at` | supprimé — l'idempotence vient de `fact_id` |
| `SubjectRole`, `WatchEffect`, `ROLE_RULES` dans Annonces | descendus dans `watch/domain/role_rules.py` |
| `DetectReturn` fermait les neutralisations | émet un `PRESENCE_RECORDED`, l'engine décide |

La descente du vocabulaire était nécessaire : une source parle la langue de l'engine, jamais
l'inverse. Sans elle, `watch` et `announcements` s'importaient mutuellement.

Les Annonces gardent ce qui leur appartient vraiment : quels rôles un type propose
(`ROLES_FOR_CATEGORY`), quels types refusent tout sujet, et **l'accord du sujet avant
publication**. Cette dernière garde est plus forte qu'un filtre en aval : un rôle intime sans
accord n'émet simplement jamais de fait. Il n'y a rien à filtrer.

**Backfill obligatoire** avant toute reprojection en production :

```
python -m scripts.backfill_watch_ledger [tenant_id]
```

Les effets posés avant le moteur n'ont pas de fait derrière eux. Sans ce script, la première
reprojection effacerait des neutralisations légitimes sans savoir les reconstruire.

---

## 8. Invariants testés

[tests/contexts/watch/test_engine_invariants.py](../tests/contexts/watch/test_engine_invariants.py) ·
[test_pipeline.py](../tests/contexts/watch/test_pipeline.py)

1. Aucun `FactKind` ne décrit une inaction — vérifié sur l'enum entier
2. Aucun `FactKind` ne peut porter une donnée financière
3. Aucun `FactKind` ne peut porter une inférence IA attribuée à une personne
4. Enregistrer un kind d'une famille interdite échoue au démarrage
5. Le compagnon collectif porte un groupe, jamais une personne
6. Un fait d'une source non enregistrée est rejeté
7. Une source ne dit que ce qu'elle a déclaré — les Annonces ne sont pas une source de présence
8. L'exclusion est absorbante : aucun effet ne survit à l'arbitrage sur une personne retirée
9. L'exclusion elle-même n'est jamais écartée (sinon pas de rejeu possible)
10. `EXIT` absorbe — le décès éteint et retire, rien d'autre n'est évalué
11. Le cas de l'endeuillé est proposé et différé, jamais perdu
12. Un fait antérieur garde l'interpreter avec lequel il est entré
13. Un fait sans interpreter est conservé, pas rejeté
14. Rejouer une publication ne duplique rien (`fact_id` dérivé)
15. Rejouer le ledger reconstruit un état identique
16. Une reconstruction n'efface jamais ce qu'un membre a déclaré

---

## 9. La suite

| Bloc | Contenu | État |
|---|---|---|
| 1 | Ledger, registre, intake, interprétation, reprojection | **livré** |
| 2 | Machine à états du `Signal`, arbitrage complet, mémoire du lien | **livré** |
| **R** | `Referent` — cascade, lien primaire dérivé, trous datés, désignation | **livré** |
| 3 | `Episode`, `owner_id` NOT NULL, escalade horaire, `ContactAttempt` + boomerang | prochain |
| 4 | `SCHEDULE_CHECK`, worker, rétraction, réévaluation des retenus | après 3 |
| 5 | Notification, budget de parole, écran Veille (API) | après 3 |
| 6 | Compagnon (8 sous-blocs) | après 4 et 5 |

### Deux dettes ouvertes par les documents Referent et Signal

**Le propriétaire d'un signal n'est pas le référent.** `Signal.owner_account_id` est aujourd'hui
nullable — c'est exactement la confusion que le module Referent interdit. Le référent **peut**
être nul (« personne ne connaît cette personne » est une donnée) ; le propriétaire d'un cas
**jamais** (sinon le cas n'a personne pour le traiter). La colonne devient NOT NULL une fois
`resolve_signal_owner` écrit, avec son motif d'escalade stocké.

**`owner_id` reste nullable en base.** La colonne devient NOT NULL au bloc 3, quand tout signal
passera par `ResolveSignalOwner` à l'ouverture. Le résolveur existe déjà ; il n'est pas encore
branché sur la matérialisation.

**Le rang des types de groupe est réglé** — il est en table (§ R), pas dans le code. La question
« quels types mettre dans le rang » ne se pose plus au niveau du code : c'est une ligne à
insérer, par église si besoin.

### Ce qui reste suspendu, et ce que ça bloque

| En attente | Nature | Bloque |
|---|---|---|
| `Referent` + lien primaire | fondation P1 | propriétaire du cas, escalade, plafond par personne réelle, `COVERAGE_SIGNAL`, carte du Compagnon |
| Étape 0 terrain (3 cellules) | observation | calibration de `open_cases_cap` et des seuils |
| `LIFE_SIGN` comme clôture système | **décision produit** | l'interpreter gratitude du Compagnon |
| Invariant 15 vs `THIRD_PARTY_CONCERN` §6 | **décision produit** | le greffon « le tiers » |
| `case.gravity` | définition manquante | l'extinction conditionnelle par signe de vie |
| Identité du déclarant dans le `ConsentProof` | **décision produit** | le greffon « le tiers » |

**Les deux contradictions à trancher, formulées nettement :**

*La transparence.* L'invariant 15 promet que le membre peut lister tout ce que le moteur sait de
lui. L'algorithme du Compagnon promet que la personne n'apprend jamais qu'un tiers a parlé
d'elle. Les deux ne peuvent pas être vrais. Il existe déjà une exception déclarée (« pas les
notes du référent ») ; en ajouter une seconde transforme la transparence en liste d'exceptions.

*La clôture système.* Une reconnaissance déposée qui éteint un cas serait la deuxième clôture
sans humain. La justification est la même que pour l'annonce — le cas n'était pas réel — mais
chaque exception affaiblit la règle qui protège du « nettoyage automatique ».

**Le Compagnon** ne doit pas être construit avant le bloc 3. Il porte sa condamnation dans ses
propres métriques : *« % de passations sans réponse à 72h > 10 % → fermer le canal plutôt qu'il
ne mente »*. Un canal de passation branché sur un moteur qui ne sait pas encore escalader est à
100 % dès le premier jour.
