# M6 — Modèle de Présence (source de vérité)

> Établi par cas d'usage avec l'utilisateur (2026-07-16). Complète
> [M4_Groups_Model](M4_Groups_Model.md) (la présence *fait vivre* les groupes) et le modèle
> membre. **Toute évolution du modèle doit précéder les chantiers M6-0 → M7.**

---

## 1. Présence ≠ pointage (le principe fondateur)

Un **pointage** répond à « étais-tu là à l'heure ? » — c'est du **contrôle**. Dorea répond à
**« comment va cette personne, où en est-elle dans sa marche ? »** — c'est du **soin**. Le même
geste (« noter qui est venu ») a un sens opposé selon l'intention ; **le modèle porte cette
intention dans sa structure**, pas seulement dans l'UI.

- On note **qui est venu à une rencontre** (réunion, formation, culte, événement) — pas une horloge.
- La saisie **sert**, ne surveille pas : discrète (le responsable coche) **ou** volontaire (le membre se marque).
- **L'absence n'est pas une faute** : c'est un signal à *comprendre* (malade / voyage / déménagé…) et
  qui **ajuste l'effectif réel** — jamais une sanction.
- **Le membre voit sa propre présence ; le backoffice voit des tendances, personne ne voit un flicage.**

## 2. La réinvention : la présence est une **conversation à deux voix**

Pas un registre tenu *sur* le membre — un signal **partagé et consenti** :
- le **membre** dit « je suis là » (self-check-in) **ou** « je ne serai pas là, et pourquoi » (pré-déclaration) ;
- le **responsable** confirme et complète les trous ;
- **les deux voient la même trajectoire.**

Ce retournement tue la surveillance : la présence n'est plus subie, elle est **co-écrite**.

## 3. Le modèle

- **La Rencontre** (`Gathering`) — l'événement : `type` (réunion / formation / culte / événement),
  date, rattachée à **un groupe** (la cellule) ou à **l'église** (le culte). On l'**ouvre** puis on la **clôt**.
- **Le roster attendu n'est pas stocké** — il est **dérivé** des membres actifs du groupe.
- **On n'enregistre que les signaux** : les **présents** (self-check-in *ou* pointés) et les **excusés**
  (absence pré-déclarée + raison). **L'absence est déduite** : attendu − présents − excusés. C'est ce
  qui rend « présent par défaut » naturel et léger (pas 20 lignes « absent » par réunion).
- **Le visiteur** = un présent **hors roster** (visage nouveau) → l'entonnoir `invited → visitor → …`.

## 4. Les deux voix, concrètement

1. Le responsable **ouvre** la Rencontre → **code de séance** + fenêtre.
2. Les présents se **self-check-in** (code + fenêtre) → présent, source *self*.
3. Qui ne viendra pas **pré-déclare** (excusé + raison).
4. Le responsable voit le **roster malin** (pré-coché, à-risque en haut), ajuste les exceptions,
   ajoute les visiteurs, **clôt**.

## 5. L'intelligence (M7 — a besoin de données)

- **Rythme personnalisé** : on n'alerte pas sur un seuil brutal, mais sur **l'écart au rythme habituel
  de *cette* personne**. Un algorithme qui *comprend*, pas qui juge.
- **Poids par tag → effectif & « point de non-retour »** (idée utilisateur) : les tags n'ont pas le même
  poids sur la **rétention**. `AbsenceGravity` : `transient` (revient, reste dans l'effectif) /
  `watch` (à surveiller, l'accumulation compte) / `structural` (parti — candidat à **sortir de
  l'effectif**). M7 combinera gravité + durée + silence pour signaler **à quel moment l'absent ne
  reviendra plus**. La gravité est **déjà plantée** (`attendance/domain/gravity.py`, exposée dans la
  déclaration d'absence) ; la logique d'effectif/alerte vit en M7.
- **Invitation à qualifier** l'absence → l'**effectif s'ajuste** (réutilise `active_absence_reason` /
  `external_participant`, déjà dans le modèle membre).
- **Santé réelle** : présents ≠ inscrits → le `ready_to_multiply` d'une cellule (G-3) devient **honnête**.
- **Alerte pour interpeller** = un *nudge* de soin au responsable (« 3 rencontres que Koffi manque,
  prends de ses nouvelles »), jamais une sanction.

## 6. Autorisation

Marquer une présence = permission **`RECORD_ATTENDANCE`** (déjà définie ; portée **sous-arbre**
comme la gestion de groupe). Le `group_leader` **et** le `leader_in_training` (« Timothée ») la
portent — le formateur peut animer la présence sans gouverner. Owner/Admin partout.

## 7. Contrainte terrain

Les cellules se réunissent en maison, réseau capricieux → **hors-ligne d'abord** (affaire du client
Flutter). Côté backend : saisie **idempotente**, sans état de session (marquer deux fois = pareil),
pour que le client rejoue ses marques à la synchro.

---

## 8. Plan de construction (contexte `attendance`)

| # | Chantier | Cœur | État |
| :-- | :-- | :-- | :-- |
| **M6-0** | **Socle Rencontre + pointage responsable** | `Gathering` (ouvrir/clôturer, groupe), roster **dérivé**, marquer présent (idempotent), absence **déduite**, roster malin | ✅ fait |
| **M6-1** | **Self-check-in** | code de séance + fenêtre ; endpoint mobile membre « je suis là » (2ᵉ voix) | ✅ fait |
| **M6-2** | **Pré-déclaration d'absence** | le membre annonce (excusé + raison) — la dignité de prévenir | ✅ fait |
| **M6-3** | **Visiteurs** | capturer un présent hors-roster → alimente l'entonnoir | ✅ fait |
| **M7** | **Comprendre** | trajectoire, rythme personnalisé, à-risque, alertes de soin, effectif réel | à faire |

**M6-0 = le socle** : la Rencontre + la capture responsable, sur laquelle les trois autres voix se
branchent sans refonte (comme le socle Groupe portait tout le reste).

### État livré (2026-07-16)
- **M6-0 ✅** : contexte `app/contexts/attendance/`. `Gathering` (type/date, **groupe**, ouvrir→clôturer)
  + `AttendanceRecord` (présent/excusé, **un par personne/rencontre**). `CreateGathering`,
  `MarkPresent`/`UnmarkPresent` (**idempotents**), `CloseGathering`, `GetGatheringRoster` (roster
  **dérivé** des membres du groupe, **absence déduite** — on ne stocke jamais « absent »).
  Autorisation **`RECORD_ATTENDANCE`** via `GroupAccessPolicy.ensure_can` (généralisée, portée
  sous-arbre) — group_leader **et** leader_in_training. Pointer un non-membre → `422` (visiteur = M6-3).
  Tables `gatherings` + `attendance_records` (migration `a1e7d4c05f92`). Routes **mobile**
  `POST /api/mobile/attendance/tenants/{tid}/groups/{gid}/gatherings`, `.../roster`,
  `PUT|DELETE .../present/{account_id}`, `.../close`. 8 tests.
- **M6-1 ✅** (self-check-in — la 2ᵉ voix) : la Rencontre porte un **code de séance** court/lisible
  (généré à l'ouverture, `SessionCodeGenerator` : 6 car., alphabet sans 0/O/1/I). Le membre tape le
  code (façon Kahoot) → `SelfCheckIn` : **le code EST l'autorisation** ; résout la rencontre
  **ouverte** par code (la fenêtre = statut open), le membre doit être du groupe, marque présent
  **source `self`**, idempotent. Migration `b8f3e0a72c15` (`gatherings.check_in_code`). Route mobile
  `POST /api/mobile/attendance/self-check-in {code}`. Code non résolvant (invalide/clôturé) → `404` ;
  non-membre → `422`. 4 tests. **Reporté** (§9) : proximité/geofence.
- **M6-2 ✅** (pré-déclaration d'absence — la dignité de prévenir) : `PlannedAbsence` (compte × tenant ×
  **tag** × période `du…au…`, **tenant-large**). Tags `AbsenceReason` : sick/travel/work/family/studies/
  unavailable/moved/other (+ note libre facultative). `DeclareAbsence` (le membre, prérequis membre
  église) / `CancelAbsence` (la sienne) / `GetMyPlannedAbsences`. **Roster enrichi** : `present` /
  `excused` (déduit d'une absence couvrant la date) / absent (ni l'un ni l'autre) + `excused_count`.
  **Poids par tag** planté (`AbsenceGravity`, exposé dans la déclaration — crochet effectif M7).
  Filtrage de couverture **en mémoire** (évite les datetimes SQL naïf/aware ; `_aware` à la lecture).
  Migration `c9a4f1b6d208` (`planned_absences`). Routes mobile `POST|GET /…/tenants/{tid}/absences`,
  `DELETE /…/absences/{id}`. 8 tests.
- **M6-3 ✅** (visiteurs — l'entonnoir) : `Visitor` (nom + téléphone facultatif, **sans compte**),
  capturé **hors roster** à une rencontre. `AddVisitor`/`RemoveVisitor` (autorité `RECORD_ATTENDANCE`,
  rencontre ouverte) / `ListGatheringVisitors`. **Séparé du roster membres** (le visiteur n'est pas
  membre). Migration `d0b5e2c74a19` (`gathering_visitors`). Routes mobile
  `POST|GET /…/gatherings/{gid}/visitors`, `DELETE …/visitors/{id}`. 5 tests.
- **M6-3 conversion ✅** (2026-07-17, l'entonnoir **bouclé**) : `ConvertVisitor` — le responsable qui a
  capturé fait passer un visage → **membre église `invited`** (début du parcours, aucun rôle, aucun
  credential, source `walk_in_registration`) **et** l'inscrit au **roster de la cellule visitée** (le
  `group_id` de la rencontre → il entre aussitôt dans la pulsation/effectif M7). **Saga à cheval sur
  deux contextes** (iam : compte + appartenance ; groups : roster). Un seul verrou :
  `GroupAccessPolicy.ensure_can(ENROLL_MEMBER)` scopé sur la cellule (le `group_leader` la porte déjà).
  **Téléphone requis** (identité du compte ; pré-rempli depuis le visiteur, saisissable sinon).
  **Tolérant** : compte global réutilisé (M-2) ; déjà membre / déjà au roster → pas de doublon.
  La fiche visiteur est **supprimée** après conversion (choix : pas de trace, pas de migration).
  Route mobile `POST /…/gatherings/{gid}/visitors/{vid}/convert`. 5 tests. **Aucune migration.**

**Socle de capture COMPLET (M6-0 → M6-3 + conversion)** — les trois voix, les visiteurs, et
l'entonnoir qui referme (visiteur → membre inscrit). M7 fait ensuite parler la donnée.

---

## 9. Décisions ouvertes (à trancher au chantier concerné)

- **M6-0** : Rencontre **église-entière** (culte) — roster dérivé de tous les membres du tenant
  (lourd) → traité plus tard ; M6-0 se concentre sur les rencontres **de groupe**.
- **M6-1** : validation du self-check-in (code + fenêtre seuls, ou + proximité/geofence ?).
- **M7** : le rythme personnalisé (fenêtre glissante, modèle) ; seuils d'alerte.
- **WhatsApp** : capter la présence là où la communauté est déjà (intégration lointaine).

---

**Fin M6-Attendance.**
