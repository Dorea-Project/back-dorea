# M7 — Intelligence pastorale (source de vérité)

> Établi par cas d'usage avec l'utilisateur (2026-07-16). Transforme la présence (M6) en
> **état de marche** de chaque personne, **au service du soin**. Complète
> [M6_Attendance_Model](M6_Attendance_Model.md). Vit dans le contexte `attendance` (lecture).

---

## 1. Le principe : un **révélateur**, pas un juge

Chaque signal doit pointer vers un **geste d'amour** (« prends de ses nouvelles », « réjouis-toi »),
jamais vers un reproche. **Le système éclaire ; l'humain décide.** Aucun retrait d'effectif, aucun
changement de statut **automatique** — jamais.

## 2. Le rythme est **personnel** (comprendre, pas juger)

On n'alerte pas sur un seuil absolu, mais sur **l'écart au rythme de *cette* personne**.
- **Awa** vient chaque semaine → 3 manqués = 3 semaines.
- **Yao** vient une fois par mois → 3 manqués = ~3 mois.
Même règle (« ~3× son rythme »), temps réel étiré selon la personne. **Démarrage à froid** : pas
assez d'historique → état « nouveau », **jamais d'alarme sur du vide**.

## 3. L'absence a **trois** sens (le cas Mme Richmond)

Mme Richmond vit à cheval sur deux temples (Peniel-Yopougon et AD-Soba). Vue de Peniel elle est
« souvent absente » — mais elle n'a **pas décroché**, elle est **active ailleurs**. Donc :
1. elle **décroche** (silence réel) → inquiétant ;
2. elle a **prévenu** (excusé transitoire, M6-2) → pas inquiétant ;
3. elle est **active ailleurs** dans le réseau → **partagée, pas perdue**.

**La règle d'or :** on ne s'inquiète / on ne sort de l'effectif **que si la personne est silencieuse
*partout* dans le réseau Dorea.** Le **compte global** (téléphone = une identité) permet de le voir —
on ne surface qu'un booléen « actif ailleurs », **sans révéler où** (isolation des églises respectée).

## 4. L'effectif : local, généreux, **suggéré**

- On ne **dé-compte** personne pour une absence *ici* : Mme Richmond reste membre de Peniel, marquée
  **« partagée »** (chiffres honnêtes).
- Sortir de l'effectif / passer `external_participant` = **acte pastoral** (via `TransitionStatus`,
  déjà existant), **proposé** par le système, jamais imposé.
- La **gravité des tags** (M6-2 : `transient`/`watch`/`structural`) module la suggestion
  (`moved` = candidat fort). Un futur **transfert de membre** entre églises = acte gouverné (comme
  l'émancipation / le transfert d'ownership).

## 5. Portée

D'abord **par cellule** (la vue du responsable de *sa* cellule) ; l'agrégat 360° église = vue
backoffice, plus tard.

---

## 6. Plan de construction

| # | Chantier | Cœur | État |
| :-- | :-- | :-- | :-- |
| **M7-0** | **Pulsation de la cellule** | état de marche par membre (nouveau/engagé/à-interpeller/partagé/dormant), rythme personnel, seuil 3×, override « actif ailleurs » | ✅ fait |
| **M7-1** | **Effectif réel** | effectif vivant pondéré par la gravité ; candidats à sortir (suggestion, jamais auto) | ✅ fait |
| **M7-2** | **Alertes de soin** | la liste « à interpeller » consolidée, le *nudge* au responsable | ✅ fait |
| **M7-3** | **`ready_to_multiply` honnête** | rebrancher la santé de cellule (G-3) sur les présents *réels* | ✅ fait |

### M7-0 — l'algorithme (règles lisibles)
- **Rythme** = écart médian (en nombre de rencontres) entre deux venues. `< 2` venues → **nouveau**.
- **Silence concerné** = rencontres *absentes* (ni présent, ni excusé) depuis la dernière venue.
- **Actif ailleurs** (présent dans une autre église du réseau depuis la dernière venue ici) → **partagé**.
- Sinon : silence `< 3×` rythme → **engagé** ; `≥ 3×` → **à interpeller** ; `≥ 6×` → **dormant**.
- Lecture seule (aucune table). Autorisation `VIEW_PASTORAL_ALERTS`. Route mobile `…/groups/{id}/pulse`.

### État livré (2026-07-16)
- **M7-0 ✅** : `attendance/domain/pulse.py` — `WalkState` (new/engaged/at_risk/shared/dormant) +
  `compute_walk_state(outcomes)` **pur** (rythme = écart médian entre venues ; seuils
  `AT_RISK_FACTOR=3` / `DORMANT_FACTOR=6` ; excusé ne compte pas). L'override **`shared`** est appliqué
  par la requête `GetGroupPulse` via `has_present_in_other_tenant_since` (booléen « actif ailleurs »,
  **ne révèle pas où** — compte global). Route `GET /api/mobile/attendance/tenants/{tid}/groups/{gid}/pulse`
  (`VIEW_PASTORAL_ALERTS`). **Aucune migration** (lecture sur les tables M6). 9 tests dont **Mme Richmond**
  (silence local + actif ailleurs → `shared`, pas d'alarme) et **Yao** (3 absences = normal à son rythme).

---

- **M7-1 ✅** (effectif réel) : le calcul de l'état de marche est extrait en service partagé
  `GroupPulseComputer` (réutilisé par la pulsation et l'effectif ; ajoute la **gravité de l'absence en
  cours**). `GetGroupEffectif` — l'effectif **honnête** : `active_count` (engaged+at_risk+shared+new,
  hors dormants & déménagés), `shared_count` (Mme Richmond), `at_risk_count`, et `review_candidates`
  (**suggestions** : `dormant` → `prolonged_silence` ; absence gravité `structural` → `declared_moved`).
  Le retrait / `external_participant` reste un **acte pastoral** (`TransitionStatus`), jamais auto.
  Route `GET /…/groups/{gid}/effectif` (`VIEW_PASTORAL_ALERTS`). Aucune migration. 10 tests pulse+effectif.

- **M7-2 ✅** (alertes de soin) : `GetCareList(tenant)` — consolide les `at_risk`/`dormant` **à travers
  tous les groupes** de l'église (les `shared`/Mme Richmond n'y figurent **jamais**), triés « plus
  silencieux d'abord ». Autorité **église-entière** (`ensure_church_wide` : Owner/Admin/pasteur ; un
  scopé passe par la pulsation de sa cellule). Route `GET /…/tenants/{tid}/care-list`.
- **M7-3 ✅** (`ready_to_multiply` honnête) : `GetCellHealth` — **inscrits vs présents réels** : une
  cellule de 40 sur le papier mais 15 réels n'est **pas** prête. `ready_to_multiply = cellule ET
  active_count (réel) >= MULTIPLY_THRESHOLD`. Reboucle la vision cellulaire (G-3) sur la réalité.
  Route `GET /…/groups/{gid}/health`.
- **Correctif algo important** : `new` est jugé sur le **nombre de rencontres depuis l'arrivée**
  (`GroupMembership.joined_at`), pas sur le nombre de présences — sinon un membre fraîchement enrôlé
  d'une vieille cellule apparaîtrait « dormant » à tort. Le calcul ne regarde que les rencontres
  postérieures à son adhésion. `classify_effectif` : le **déménagement** (`structural`) prime sur le
  silence comme raison de revue.

**M7 COMPLET (M7-0 → M7-3)** — 234 tests. La boucle **présence → multiplication** est fermée. Aucune
migration pour tout M7 (lecture seule sur les tables M6).

## B7 — Le backoffice perçoit (tableau de bord & détail mobile)

Jusque-là, la présence & l'intelligence vivaient sur le **mobile** (le terrain). Le **backoffice**
(PWA, le poste de pilotage du pasteur) ne voyait que la *structure*, pas la *vie*. B7 comble ça.

- **Vitals partagés** (`compute_group_vitals`) : la « carte » d'un groupe = **infos** (nom, type, statut,
  génération) + **réalités** (effectif réel, à-risque, partagés, candidats à revoir, `ready_to_multiply`).
- **Mobile — détail du groupe** : `GetGroupOverview` → les vitals d'un groupe (l'écran « détails » du
  responsable). Route `GET /api/mobile/attendance/tenants/{tid}/groups/{gid}/overview` (`VIEW_PASTORAL_ALERTS` scopé).
- **Backoffice — cockpit** : `GetChurchDashboard` → la **grille de tous les groupes** + totaux
  (`groups_count`, `cells_ready_to_multiply`, `members_needing_care` **distincts**). Route
  `GET /api/backoffice/attendance/tenants/{tid}/dashboard`. Et la **care-list** exposée sur backoffice.
  Surface **cookie de session** ; autorité **église-entière** (`ensure_church_wide`). 3 tests.

**B7-0 livré** (237 tests).

### B7+ — le backoffice avancé (comprendre, mesurer, voir la reproduction)

Trois lentilles qui prolongent le cockpit, toutes lecture seule, fidèles à *le système éclaire,
l'humain décide* :

- **Trajectoire individuelle** (`GetMemberTrajectory`) — le **drill-down** : la *frise* d'un membre
  (présent / excusé / absent depuis son adhésion), son état, depuis quand il est silencieux, s'il a
  **prévenu** (tag M6-2), s'il est **actif ailleurs**. Ferme la boucle de la care-list : voir *qui*
  → comprendre *pourquoi* → puis appeler. L'**histoire** tendue à l'humain, pas un verdict.
  Routes mobile + backoffice `…/groups/{gid}/members/{account_id}/trajectory`. 3 tests.
- **Série temporelle** (`GetGroupTrend`) — la **dérivée** : on rejoue le calcul **pur** avec
  l'horloge reculée sur N semaines (garde-fou 26) → une sparkline `active`/`at_risk` qui révèle le
  **momentum** (« monte » vs « fond »). Correctif de justesse : un membre pas encore arrivé à la date
  de référence ne compte pas dans le snapshot passé. Routes mobile + backoffice `…/groups/{gid}/trend`
  (param `weeks`). 2 tests.
- **Arbre de multiplication** (`GetMultiplicationTree`) — la **vision** : la forêt de reproduction des
  cellules (`multiplied_from_id` / `generation`), vitals attachés à chaque nœud, `max_generation`.
  Révèle la **fertilité** (qui enfante, qui reste stérile). Une fille orpheline (mère clôturée)
  redevient racine visible. Autorité **église-entière**. Route backoffice `…/multiplication-tree`.
  3 tests.

**B7+ livré** (245 tests). Le cockpit voit désormais l'**individu** (frise), le **temps** (tendance)
et la **reproduction** (arbre). Aucune migration (lecture seule sur M6).
