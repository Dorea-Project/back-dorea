# M4 — Modèle des Groupes (source de vérité)

> Établi par cas d'usage avec l'utilisateur (2026-07-16). Complète
> [M0_Tenant_Owner_Hierarchy](M0_Tenant_Owner_Hierarchy.md) (Tenant/Owner/annexe) et
> [M-Member_Mobile_Model](M-Member_Mobile_Model.md) (membre/mobile). **Toute évolution du
> modèle Groupe doit précéder le développement des chantiers G-0 → G-4.**

---

## 1. « Groupe » n'est pas un concept — c'en est trois

Une église dit « groupe » pour des réalités aux règles différentes :

| Type | Logique | Se multiplie ? | Exemple |
| :--- | :--- | :--- | :--- |
| **cellule** | soin pastoral (suivi, présence, santé) | **oui** (division) | « famille » de maison |
| **ministère** | service / organisation d'équipe | non | louange, accueil, enfants |
| **classe** | cohorte temporaire (début → fin) | non | préparation baptême |

**Décision : un seul agrégat `Group` typé** (`type ∈ {cellule, ministere, classe}`), même
table, même appartenance. Le **type est une couche de règles** par-dessus (seule la cellule
porte multiplication / générations / santé). On évite de tripler le code, on garde la porte ouverte.

## 2. Deux liens de parenté distincts (⚠️ point crucial)

La scène « la Jeunesse crée des cellules *famille* ; la famille A se multiplie en B, les deux
restent sous la Jeunesse » prouve qu'il faut **deux liens**, pas un :

- `parent_group_id` → **appartenance structurelle** (famille ⊂ Jeunesse ⊂ Église). Récursif.
- `multiplied_from_id` → **lignée / généalogie** (famille B ← famille A). Cellule uniquement.

Sans ce dédoublement, impossible de compter les générations d'une Jeunesse tout en gardant les
familles rangées sous le même ministère.

## 3. Récursivité et mixité des types

L'arbre est **libre** : une cellule (« famille ») vit à l'intérieur d'un ministère (« Jeunesse »).
Le type **ne dicte pas** qui contient qui — il dicte le comportement. (Contraintes de nesting
par type = possibles plus tard, non bloquantes en G-0.)

## 4. Autorisation : la portée devient « sous-arbre »

Reprend l'autorisation à deux étages (propriété, puis rôle borné par la portée, cf. `AccessControl`).
**Créer/gérer un groupe = `MANAGE_GROUP` dont la portée couvre le nœud visé.** La portée d'un rôle
scopé n'est plus « ce nœud exact » mais **son sous-arbre** (ascendance dans l'arbre) :

> un responsable couvre X **si son groupe est un ancêtre-ou-égal de X**.

**Choix technique : chemin matérialisé** (`path`) stocké sur chaque groupe (ex.
`/{racine}/{enfant}/{self}/`). Contrôle d'accès en O(1) (« `/{gid}/` est-il dans `node.path` ? »).
Arbres profonds mais petits, déplacements rares → la lecture d'autorisation (chemin chaud) reste triviale.

### Qui crée quoi (subsidiarité)
- **Groupe racine** (`parent = null`, ex. un ministère de haut niveau) → acte **église-entière** :
  Owner ou Admin (`MANAGE_GROUP` non scopé).
- **Sous-groupe** (ex. une *famille* sous la Jeunesse) → **le responsable du parent**, de façon
  **autonome, sans validation** (c'est interne). L'Admin/Owner peuvent aussi (portée plus large).

### Principe « on gère son nœud ; on le *structure* depuis au-dessus » (décidé 2026-07-16, G-5)
- Actes **DANS** le nœud (ajouter des membres, créer des sous-groupes, l'animer, renommer,
  `active↔dormant`) → autorité **du nœud** (`ensure_can_manage`, portée sous-arbre).
- Actes **SUR** le nœud (le **fermer**, **nommer/révoquer ses responsables pleins**) → autorité
  **du parent** (`ensure_can_manage_structure` = couvrir le parent, ou Owner/Admin). Un nœud racine
  → Owner/Admin seulement. **Empêche l'auto-attribution** (un responsable ne se blinde pas de
  co-responsables ni ne dissout sa propre équipe).
- **Exception mentorat** : nommer/révoquer un **responsable-en-formation** (Timothée) reste au
  responsable du nœud (c'est du mentorat, pas de la gouvernance).

Le créateur nomme le responsable du nouveau nœud (dans le cap de 6, cf. §5).

## 5. Leadership

`group_leader` (rôle existant, **cap 1 à 6 par nœud**) attaché à un `group_id`. À venir (G-2) :
**responsable-en-formation** (le « Timothée » du G12, futur responsable de la cellule-fille) —
central au mécanisme de multiplication.

## 6. Appartenance au groupe (G-1)

`GroupMembership` (compte × groupe), **distincte** de la Membership église. Règles :
- Rejoindre un groupe **exige/crée d'abord** l'appartenance à l'église (déjà décidé, M-Member).
- Un humain peut être dans **0..N groupes** simultanément (une cellule **et** l'équipe louange —
  axes différents).
- (Statut *dans* le groupe — visiteur de cellule ≠ membre engagé — à trancher en G-1.)

## 7. Gradient de gouvernance (principe unificateur)

**Le poids de la gouvernance croît avec l'autonomie accordée :**
- créer un sous-groupe **interne** → responsable local, **autonome** (léger) ;
- promouvoir un groupe en **annexe / église** → **gouverné + validé Dorea** (lourd).

Créer une famille ne coûte rien ; faire naître une église coûte un **Owner** et une **validation**.

## 8. Un groupe n'est **jamais** une église — mais il peut le **devenir**

Un « groupe libre autonome qui serait une église » **sans devenir tenant** créerait un trou de
gouvernance (qui possède ? qui Dorea valide/facture ? où sont isolées les données ?). Donc **non**.

Mais le **church planting** est un continuum, dont on a déjà bâti la fin (émancipation M0) :

```
cellule → (multiplication) → groupe de cellules → annexe → (émancipation) → église autonome (tenant)
  [Group dans un tenant]                            [partition]              [nouveau Tenant + Owner]
```

La **filiation** est une seule notion, de la cellule (`multiplied_from_id`, G1→G2) à l'église-fille
plantée (`parent_id` / Network, M0). Promotion = événement **gouverné** : naissance d'un Owner,
**re-pointage** des appartenances (comptes globaux inchangés, téléphone = clé), migration/snapshot
de l'historique (à trancher). **G-0 pose les crochets** (type, lignée, statut) ; la promotion est un
chantier dédié (G-4) qui réutilise l'émancipation M0.

### « Groupe libre » (informel) — axe orthogonal
*Qui crée* le groupe : leadership (structure officielle) vs membres (spontané). Un groupe informel
**reste dans le tenant**, hors organigramme officiel — simple attribut, **aucun impact de gouvernance**.
À ne pas confondre avec l'autonomie (§8). Attribut léger, potentiel G-1+.

---

## 9. Plan de construction (Groupes)

| # | Chantier | Contenu | État |
| :--- | :--- | :--- | :--- |
| **G-0** | **Socle** | Agrégat `Group` typé + récursif (`parent_group_id`, `path` matérialisé, `multiplied_from_id` hook, `type`, `status`) ; `CreateGroup` racine + sous-groupe ; autorisation **subtree-aware** (`MANAGE_GROUP` scopé via `path`) ; persistence + migration | **en cours** |
| **G-1** | **Appartenance** | `GroupMembership` (join/leave), exige la Membership église ; multi-appartenance ; (statut intra-groupe) ; attribut `is_official` | **en cours** |
| **G-2** | **Leadership** | Nomination `group_leader` sur un nœud (cap 6) ; responsable-en-formation | **en cours** |
| **G-3** | **Multiplication** | Événement de multiplication (famille A → B), lignée, générations, santé de cellule (dashboard) | **en cours** |
| **G-4** | **Promotion → église** | Pipeline gouverné (réutilise émancipation M0), naissance d'Owner, re-pointage des appartenances | ✅ fait |
| **G-5** | **Administration** | Modifier (renommer, dormant), fermer (cascade), révoquer le leadership ; autorité « depuis au-dessus » | ✅ fait |

**G-0 = le socle** : l'arbre, les types, la lignée en crochet, et l'autorisation par sous-arbre.

### État livré (2026-07-16)
- **G-0 ✅** : contexte `app/contexts/groups/`, agrégat `Group` (chemin matérialisé), `CreateGroup`
  (racine + sous-groupe), `GroupAccessPolicy` subtree-aware. Migration `c3f8a1d420be` (table `groups`).
  Route `POST /api/backoffice/tenants/{tid}/groups`.
- **G-1 ✅** : `GroupMembership` (`active`/`left`), `AddGroupMember` / `RemoveGroupMember` /
  `ListGroupMembers`. **Prérequis exigé** : Membership église active (le contexte Groupes n'enrôle
  pas — frontière propre) → `422 GROUP_REQUIRES_CHURCH_MEMBERSHIP`. Dédup → `409`. Autorisation
  `ensure_can_manage` (même portée sous-arbre). Migration `d4a2b7e9c1f0` (table `group_memberships`).
  Routes `POST|GET /…/groups/{gid}/members`, `DELETE …/members/{account_id}`.
  **Reporté** : self-join mobile (G-1b), statut intra-groupe, attribut `is_official` (§10).
- **G-2 ✅** : le leadership = **rôle IAM scopé** (pour rester lu par l'autorisation sous-arbre).
  Deux grades : `leader` → `RoleCode.GROUP_LEADER` (cap 6/nœud) ; `in_training` →
  `RoleCode.LEADER_IN_TRAINING` (« Timothée », permissions VIEW + RECORD_ATTENDANCE, **sans**
  gouvernance). Commande `AppointGroupLeadership` (contexte Groupes, autorisée par `ensure_can_manage`)
  écrit le rôle via le port `ChurchRoleStore` (adaptateur en infra groups → table `role_assignments`).
  Prérequis Membership église ; dédup `409` ; cap `422`. **Aucune migration** (rôle = valeur texte).
  Route `POST /…/groups/{gid}/leaders`. `RoleAssignment` : rôles scopés généralisés
  (`GROUP_SCOPED_ROLES = {group_leader, leader_in_training}`). **Reporté** : révocation dédiée
  (réutilise `RevokeRole` IAM), promotion trainee→leader à la multiplication (G-3).
- **G-3 ✅** : `MultiplyCell` (explicite, seule une cellule se multiplie) — enfante une **fille**
  (sœur : même parent structurel via `Group.multiply` + « échange de segment » du chemin ; lignée
  `multiplied_from_id` ; `generation = mère + 1`), **déplace** les membres choisis (quittent la mère,
  rejoignent la fille), et **promeut** le nouveau responsable (le Timothée) en `group_leader` de la
  fille (via `ChurchRoleStore`), le tout atomiquement. Champ `generation` sur `Group`
  (migration `e5b1c8f302a7`). Lecture `GetCellReport` (effectif, `ready_to_multiply` = cellule &
  effectif ≥ `MULTIPLY_THRESHOLD`=12, génération, filles). Routes `POST /…/groups/{gid}/multiply`,
  `GET /…/groups/{gid}/report`. **Reporté** (§10) : seuil configurable par tenant, statut `MULTIPLYING`
  transitoire, santé plus riche.
- **G-4 ✅** : `PromoteGroupToChurch` — **acte Plateforme (Dorea)** gardé par le jeton de service
  (`require_platform_token`). Émancipe un groupe en **église autonome** : nouveau `Tenant`
  (`parent_id` = tenant source → filiation), `Ownership` **`emancipation`** pour l'owner, sa Membership
  `confirmed_member`, et **re-pointage** des membres (nouvelles Memberships, non destructif). La cellule
  source est **clôturée** (`CLOSED`). Atomique via le port `ChurchPlantStore` (adaptateur infra groups →
  `tenants`/`tenant_ownerships`/`memberships`). Prérequis : owner membre actif de la source ; groupe non
  déjà promu (`409`). **Aucune migration**. Route `POST /api/backoffice/groups/{gid}/promote-to-church`.
  **Reporté** : clôture des anciennes appartenances (non destructif assumé), migration des sous-cellules.

- **G-5 ✅** (administration) : `ModifyGroup` (renommer, `active↔dormant` — autorité **nœud** ;
  type immuable, pas de déplacement V1), `CloseGroup` (fermeture douce → `closed` ; **bloquée si
  sous-groupes actifs** ; cascade : appartenances → `left`, rôles du nœud **révoqués** ; autorité
  **parent**), `RevokeGroupLeadership` (pendant de G-2 ; `group_leader` → parent, `in_training` →
  nœud). Raffinement G-2 : nommer un `group_leader` passe en autorité **parent** ; Timothée reste au
  nœud. Nouvelle `ensure_can_manage_structure` + `is_structure_covered_by` (couvre le parent via le
  chemin). Ports role-store : `revoke_group_role` / `revoke_all_group_roles`. **Aucune migration**.
  Routes `PATCH`/`DELETE /…/groups/{gid}`, `DELETE /…/groups/{gid}/leaders`.

- **G-1b ✅** (self-join mobile — **1ère surface mobile du contexte**) : lien/code d'invitation
  (`GroupInvitation`, réutilisable + expiration 30 j + révocable ; migration `f6c2d9a10b34`).
  `CreateGroupInvitation` / `RevokeGroupInvitation` (responsable, `ensure_can_manage`). **`JoinGroupByCode`** :
  le code *est* l'autorisation ; **porte d'onboarding** — si le compte n'est pas membre de l'église,
  le lien l'y rattache (`invited`, via `ChurchEnrollmentStore`) puis au groupe. `LeaveGroup` (self).
  Appartenance **par nœud** (l'ascendance reste structurelle). Le lien est **l'amont de la
  multiplication** (un membre invite un ami → la cellule grossit → G-3). Routes mobile
  `POST /api/mobile/groups/{...}/invitations`, `/join`, `/{gid}/leave`. **Reporté** : demande de
  rattachement sans lien (décision G, modèle membre).

**M4 COMPLET (G-0 → G-5 + G-1b)** — 196 tests verts. Reste : « la **vie** du groupe » (présence M6,
absents M7, annonces M8 — permissions déjà définies).

---

## 10. Décisions ouvertes (à trancher au chantier concerné)

- **G-1** : statut *dans* le groupe (visiteur/engagé) ou simple présence ? Attribut `is_official` (informel).
- **G-3** : seuil de multiplication — automatique (taille/générations) ou décision humaine ?
- **G-4** : historique à la promotion — **migre** avec les membres ou **snapshot** dans l'église-mère ?
- **Nesting par type** : contraintes (une classe peut-elle contenir une cellule ?) — libre en G-0.

---

**Fin M4-Groups.**
