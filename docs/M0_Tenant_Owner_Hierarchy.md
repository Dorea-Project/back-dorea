# MODULE M0 — Tenant, Owner & Hiérarchie

## Fondations du modèle — source de vérité conceptuelle

**But :** figer les invariants du **Tenant** (l'église), de l'**Owner** (son siège
administratif) et de la **hiérarchie ecclésiale** (dénomination / filiation / annexe) *avant* tout
code. Ce document précède et conditionne M1 (nomenclature IAM). Il est issu de la découverte du modèle
par les cas d'usage (genèse, mobilité pastorale, autonomisation d'annexe).

> **Architecture (voir spec §14) :** un **seul backend, ce monolithe FastAPI**, propriétaire du schéma
> et des migrations. Les **écritures** décrites ici (provisionnement, succession, émancipation) sont
> exposées sur la surface **backoffice** (`/api/backoffice/*`, consommée par le front PWA Next.js). La
> **lecture** du membre est exposée sur la surface **mobile** (`/api/mobile/*`, front Flutter). Les
> deux surfaces sont dans **le même backend** ; il n'y a pas de service NestJS.

---

## 1. Les 6 notions et leur projection

| Notion | Définition | Objet technique |
| :--- | :--- | :--- |
| **Identity** | Qui est la personne — **globale**, clé = téléphone | `Account` (racine) |
| **Credential** | Comment elle prouve son identité | contexte `auth` (`password_hash`, code) |
| **Membership** | Rattachement d'une Identity à un Tenant, porte le **statut** | `Membership` (racine) |
| **Role** | Capacité fonctionnelle dans une **portée** | `RoleAssignment` (interne à Membership) |
| **Token** | Preuve réémise après connexion (identité, **pas** les rôles) | JWT (`auth`) |
| **IdentityAccess** | Les opérations IAM elles-mêmes | commandes / requêtes M0–M1 |

**Deux constantes structurantes**, validées par tous les scénarios :
1. **L'`Account` (la personne) ne bouge jamais.** Une mutation/émancipation ne fait que **repointer**
   ses `Membership`. Un humain = un compte à vie, N appartenances.
2. **Un Owner ne naît que par la Plateforme.** Jamais de l'intérieur de l'église.

---

## 2. Le Tenant

- **Le Tenant EST l'Église** (indépendante ou principale). Il a **exactement un Owner**.
- Le Tenant **préexiste** à tout humain : on le crée vide, puis on y installe l'Owner.
- Le Tenant est **stable** : quand une personne (même l'Owner) part, le tenant ne bouge pas.

### 2.1. Cycle de vie du Tenant *(révisé 2026-07-23, cf. §4.1)*

| Mouvement | Déclencheur | Effet |
| :--- | :--- | :--- |
| **Naissance** (genèse) | Plateforme — `ProvisionTenant` | Tenant + 1er Owner, en une transaction atomique |
| **Ajout d'annexe** | Plateforme — `POST /tenants/{parent_id}/annexes` *(à construire)* | Une **église-fille** (tenant à `parent_id` + **Owner propre**), comme une genèse filiée |
| **Émancipation d'un groupe** | Plateforme — `promote_group_to_church` *(livré)* | Un groupe qui a grandi devient un tenant fille |
| **Suspension / réactivation** | Plateforme | `status` = suspended ↔ active (jamais supprimé) |

### 2.2. Champs du Tenant — modèle validé (2026-07-23)

Regroupement **conceptuel** ci-dessous (branding / contact / régional). *Implémentation : colonnes
**à plat** sur `tenants` — seul `Location` reste un value object ; les autres groupes sont des
colonnes directes, par pragmatisme (moins de plomberie). Migrations `c3d4e5f6a7b8` (ajouts + index
slug) et `d4e5f6a7b8c9` (suppression scaffolding annexe, D5).*

| Groupe | Champ | Type | Note |
| :--- | :--- | :--- | :--- |
| **Identité** | `id` | UUID | — |
| | `name` | str | **immuable** via l'édition de profil |
| | `slug` | str **unique** | 🆕 identifiant lisible pour liens/QR (ex. `beta-cotonou`) ; auto-généré du nom, éditable ; index unique partiel |
| | `status` | `active`/`suspended` | — |
| | `parent_id` | UUID? | `null`=principal ; **à valider** en écriture (D6) |
| | `created_at` | datetime | — |
| **Branding** | `logo_url` | str? | 🆕 image via contexte media (`PUT /media` → url) |
| | `short_description` | str? | 🆕 tagline courte |
| **Dénomination** | `denomination` | str? | descriptif (≠ `Network`) |
| **Contact** | `contact_name` | str? | 🆕 responsable/contact de l'église |
| | `contact_phone` | str? | 🆕 contact public (≠ tél de l'Owner) |
| | `contact_email` | str? | e-mail de l'église (≠ e-mail Owner) |
| **Localisation** (`Location`) | `country` `city` `address` `latitude` `longitude` | value object | existant |
| **Régional** 🆕 (`Regional`) | `timezone` | str | IANA (défaut `Africa/Abidjan`, dérivable de `country`) |
| | `language` | str | locale (défaut `fr`) |
| | `currency` | str | ISO 4217 — défaut **`XOF`**, supporte **`XAF`** (FCFA = 2 devises) |
| **Facturation** | `estimated_member_count` | int? | taille **déclarée** = assiette d'abonnement |
| | `operates_annexes` | bool | 🆕 déclaré au signup, **lu par le module `subscription`** (choix du plan famille) ; toujours `false` pour une annexe |

> **Bénéfice `timezone`** : la clé « culte du jour » du Sermon S-4 (aujourd'hui *minuit UTC du dimanche*)
> devrait devenir **minuit LOCAL** — plus juste dès qu'on dépasse un seul fuseau. À corriger le jour venu.
>
> **Non stockés sur le Tenant** (module `subscription`) : `billing_period`, `tier` (dérivé), promotions.
> **Supprimés** (dette D5) : table `annexes`, `annexe_id`×2.

---

## 3. L'Owner — un siège, pas une personne

L'Owner est un **`RoleAssignment(role=owner, group_id=null)`** de portée **Tenant**, posé sur une
`Membership`. C'est un **siège transférable**, occupé par une personne à un instant T.

### 3.1. Les trois portes d'accès au siège Owner (les seules)

| Porte | Contexte | Opération |
| :--- | :--- | :--- |
| **Genèse** | L'église n'existait pas | `ProvisionTenant` (`bootstrap_owner`) |
| **Succession** | L'église existe, le titulaire change | `TransferOwnership` |
| **Émancipation** | Une annexe devient tenant | `PromoteAnnexeToTenant` (bootstrap sur le nouveau tenant) |

**Les trois sont des actes Plateforme.** L'Owner ne s'auto-crée pas, l'Owner sortant n'adoube pas son
successeur, l'Owner-mère n'adoube pas l'Owner-fille — la Plateforme exécute toujours.

### 3.2. Règle de bootstrap (résout le paradoxe œuf-poule)

> **L'enrôlement par l'Owner confère directement le statut `confirmed_member`.**

Sans elle, l'invariant « un rôle exige `confirmed_member` » rend toute création d'église impossible.
S'applique à l'Owner lui-même **et** à ceux qu'il enrôle directement (Pasteur, Admin).

---

## 4. Les TROIS mécanismes de hiérarchie (ne pas les confondre)

C'est le point le plus source de confusion. Trois axes **distincts** :

| Axe | Mécanisme | Nature | Owner ? |
| :--- | :--- | :--- | :--- |
| **Dénomination ↔ églises** | `Network` + `NetworkTenantLink` | Fédération lâche, lecture agrégée | Chaque église garde le **sien** |
| **Église-mère ↔ église-fille (= annexe)** | `parent_id` (tenant→tenant) | **Filiation / lignée** | Chaque tenant (mère **et** annexe) a le **sien** |

> ⚠️ **Ce tableau a été révisé le 2026-07-23 (voir §4.1).** L'ancienne 3ᵉ ligne « Église ↔ annexe
> (`annexe_id`, partition interne, aucun Owner) » est **supprimée** : une annexe **est** désormais une
> église-fille (un tenant à `parent_id`), avec **son propre** Owner. Il ne reste que **deux** mécanismes.

`parent_id` et `Network` **coexistent** : une église-fille peut avoir `parent_id = mère` **et** être
rattachée au `Network` de sa dénomination. Ne jamais utiliser `parent_id` pour la dénomination.

### 4.1. Design de l'annexe — **décision révisée (2026-07-23) : église-fille à Owner propre**

**Décision en vigueur.** Une « annexe » est une **église semi-autonome** : une ligne `tenants` avec
`parent_id = mère` et **sa propre `Ownership` active** (son pasteur/responsable détient ses clés).
C'est exactement ce que produit déjà l'émancipation d'un groupe (`promote_group_to_church`).

- **Cohérent avec I1** : chaque tenant, y compris une annexe, a **exactement 1 Owner**. On ne rejoue
  donc **pas** le Design B (Owner *nullable*) — ici l'Owner est bien présent, distinct de celui de la mère.
- **Filiation plate en V1** : une annexe **ne peut pas** avoir d'annexe (le parent doit être un
  principal, `parent.parent_id IS NULL`). → « nombre d'annexes » = enfants directs, sans ambiguïté.
- **Création** : acte **Plateforme**, une annexe à la fois — ✅ **`POST /api/backoffice/tenants/{parent_id}/annexes`
  livré le 2026-08-03**. Le `parent_id` vient du **chemin** (jamais du corps) et il est **validé** :
  mère existante, active, et elle-même **principale** (une annexe ne peut pas avoir d'annexe →
  `422 TENANT_INVALID_PARENT`). L'annexe naît avec **son propre Owner** et `operates_annexes=false`.
- **Abonnement** : le principal porte l'abonnement de la **famille** (mère + annexes), cf.
  `docs/Tenant_Subscription.md`.

**Superseded — Design A (sous-espace `annexe_id`)** *(décision initiale, abandonnée le 2026-07-23)* :
l'annexe était un compartiment **interne** (`annexe_id` nullable sur `Membership` + table
`annexes(id, tenant_id, name)`), sans Owner propre, cloisonné via `covers()` / `WHERE annexe_id = X`.
**Motif du renversement** : le besoin réel est une annexe **semi-autonome** (son pasteur, ses membres,
sa vie), pas une partition. Le scaffolding correspondant (`annexe_id`, table `annexes`) n'a jamais été
écrit et est à **supprimer** (cf. §8 Dette). *Design B (annexe = tenant-enfant à Owner nullable) reste
rejeté — mais le design en vigueur n'est pas B : l'Owner de l'annexe n'est jamais nul.*

### 4.2. Le tenant comme **instance du Church OS** — tablette autonome & vue famille

Dorea est une **infrastructure** (« Church OS ») : chaque `Tenant` porte, isolée par `tenant_id`, **toute**
la pile (IAM, Groupes, Présence, Annonces, RDV…). C'est ce qui rend le renversement §4.1 non seulement
correct mais **nécessaire** :

> **Une tablette suit un tenant.** Donner une tablette autonome à une annexe = lui donner **son tenant**.

**Deux unités, deux usages :**

| Unité | Mécanisme | Sert à |
| :-- | :-- | :-- |
| **Isolation** | le **tenant** (`tenant_id`) | La tablette de l'annexe = session scopée à SON tenant → voit et gère **uniquement** son annexe (ses responsables, cellules, groupes, membres). **Natif**, aucun code transverse. |
| **Consolidation** | la **famille** (`parent_id`) | La tablette du principal = sa vue + une **lecture agrégée** sur le sous-arbre `parent_id` (total membres, présence, une carte par annexe). |

**Décision de gouvernance (2026-07-23) : subsidiarité — supervision en LECTURE SEULE.**
Le principal **voit** toute la famille mais **n'agit pas** dans une annexe : chaque annexe se gouverne
elle-même (nomme ses propres responsables, gère ses groupes). Le pouvoir du principal est
un **rôle de veille** (tableau de bord famille) + la relation de propriété/abonnement, **pas** la
micro-gestion. → Pas d'autorité trans-tenant à implémenter (ni à sécuriser) : plus simple **et** plus
respectueux de l'autonomie ecclésiale.

**Ce que ça coûte à construire** : **une seule brique neuve** — la *lecture famille*. Tout le reste
(isolation, gouvernance locale, logins séparés) **tombe** du modèle multi-tenant existant.

> ✅ **Lecture famille — LIVRÉE le 2026-08-03.** `GET /api/backoffice/tenants/{id}/family`
> (session Owner) → `{principal, annexes[], family_member_count, active_annexe_count}`.
> Repo `TenantRepository.list_children` · query `GetTenantFamily` (gardée par l'ownership du
> principal, comme la lecture du profil). **Filiation plate ⇒ enfants directs, aucune récursion.**
> `family_member_count` = Σ des tailles **déclarées** sur la famille (assiette d'abonnement,
> cf. `Tenant_Subscription.md §2`) ; `active_annexe_count` **exclut les annexes suspendues** (elles
> sortent du plan mais **restent visibles** du principal). Un non-Owner reçoit `403` — la
> supervision ne se délègue pas. Le même calcul sert le tableau de bord **et** l'abonnement :
> un seul endroit.

*Pourquoi le Design A aurait échoué ici* : donner une tablette autonome à une annexe-partition aurait
exigé un filtre `WHERE annexe_id` dans **chacun des 14 contextes** + une portée `covers()` partout
(dette D3), sans jamais offrir à l'annexe son propre login/Owner. Le tenant-annexe rend la tablette
d'annexe **triviale** et ne laisse que la vue famille à bâtir.

**Vocabulaire des responsables (décidé 2026-07-23)** : **pas de rôle « diacre »**. Le leadership se
lit sur **trois niveaux de portée**, tous des rôles `RoleCode` :

| Rôle | Portée | Rôle |
| :-- | :-- | :-- |
| `group_leader` *(existe)* | **un groupe** (cellule/ministère, via `group_id` + `covers()`) | responsable de cellule |
| `church_leader` *(**à ajouter**, 2026-07-23)* | **l'église entière** (le tenant, non scopé) | responsable d'église / d'annexe |
| `leader_in_training` *(existe)* | aucune autorité | « Timothée », en formation |

`church_leader` est **additif** (`role_assignments.role` est une String → **aucune migration**), nommé
ainsi par cohérence avec `group_leader`. ✅ **Livré le 2026-08-03** (`RoleCode.CHURCH_LEADER`,
entrée `ROLE_PERMISSIONS`, entrée `ROLE_AUTHORITY`, 11 tests).

**Sa place** : `church_leader` = le **responsable/visage** d'une église (ou annexe) qui la **conduit**
sans en détenir les **clés** (≠ `owner`) ni se limiter à un groupe (≠ `group_leader`) ; distinct du
`pastor` (spirituel, lecture seule §5.6).

**Ses permissions — décidé 2026-07-23 (Option A : leadership opérationnel, SANS gouvernance).**
`church_leader` est « un `group_leader` à l'échelle de l'église ». Jeu **arrêté** pour `ROLE_PERMISSIONS` :

```
VIEW_MEMBER_DIRECTORY, VIEW_PASTORAL_ALERTS,
RECORD_ATTENDANCE, QUALIFY_ABSENCE,
ENROLL_MEMBER, PUBLISH_ANNOUNCEMENT, MANAGE_GROUP
```
**Exclus** (la gouvernance reste `owner`/`admin`) : `MANAGE_STAFF`, `MANAGE_TEAM`, `MANAGE_MEMBERSHIP`,
`CLOSE_MEMBERSHIP`, `TRANSFER_MEMBER`. → il **conduit et opère** l'église/annexe (présence, enrôlement,
annonces, groupes) mais **ne gouverne pas** (ne nomme pas, ne clôture pas) → nettement distinct de
l'`admin`. Portée = **le tenant entier** (non scopé, contrairement à `group_leader` borné par `group_id`).

*Qui nomme un `church_leader` ?* → **`MANAGE_STAFF`, donc l'Owner seul** (décidé à l'implémentation,
2026-08-03). Motif : sa portée est l'**église entière** (non scopée) ; il rejoint donc `secretary` et
`treasurer`, dont la nomination est un **acte d'état-major**, pas un geste opérationnel délégable à un
Admin. Les rôles en `MANAGE_TEAM` sont tous bornés (groupe, ou équipe fonctionnelle) — lui ne l'est pas.

---

## 5. Invariants

| # | Invariant | Statut code |
| :--- | :--- | :--- |
| I1 | **Exactement 1 `owner` actif par tenant** | 🟡 **décidé (Phase 0)**, à implémenter — voir §9 |
| I2 | Un `RoleAssignment` exige `Membership.status = confirmed_member` | ✅ `aggregates.py` |
| I3 | `bootstrap_owner` est la seule transition `(néant) → confirmed_member` | à porter (transitions) |
| I4 | Toute naissance d'Owner passe par la Plateforme | règle, à garder en garde-fou |
| I5 | Rétrogradation/clôture révoque tous les rôles **atomiquement** | à porter (backoffice) |
| I6 | Portée d'annexe appliquée par `covers()` | ⚠️ `covers()` ne borne **que** `group_leader` |

---

## 6. Opérations clés (préconditions → effet atomique)

### `ProvisionTenant` (Plateforme)
1. Créer `Tenant` (`parent_id` = null si indépendante).
2. Créer `Account` de l'Owner (`created_by_type = owner`) + credentials.
3. `Membership(confirmed_member)` via `bootstrap_owner` + `RoleAssignment(owner)`.
→ **Une transaction.** Résultat : tenant avec exactement 1 Owner (I1).

### `TransferOwnership` (Plateforme) — succession
Préconditions : nouveau titulaire identifié dans le **même** tenant.
1. Poser `owner` sur la nouvelle `Membership` (créée `confirmed_member` si besoin).
2. Révoquer `owner` de l'ancienne + clôturer sa `Membership` (`closure_reason` adéquat).
→ **Ordre critique : poser le nouveau AVANT de retirer l'ancien.** Jamais 0 Owner (I1).

### Naissance d'une église-fille (Plateforme) — *révisé 2026-07-23*
Depuis la révision §4.1, une annexe **est** une église-fille (tenant à `parent_id` + Owner propre). Deux
chemins la font naître, tous deux **Plateforme**, chacun en **une transaction** (les `Account` ne bougent
pas — repointage seul) :

- **Ajout direct d'annexe** — `POST /tenants/{parent_id}/annexes` (à construire) : crée le `Tenant` fille
  (`parent_id = mère`, validé), son `Account` Owner + `Ownership(bootstrap)`, comme une genèse filiée.
- **Émancipation d'un groupe** — `promote_group_to_church` (déjà livré, contexte Groups) : un groupe
  qui a grandi devient un `Tenant` fille, son Owner = l'ex-responsable, ses membres repointés.

*Obsolète — l'ancien `PromoteAnnexeToTenant` (transformer une partition interne `annexe_id` en tenant)
n'a plus lieu d'être : il n'y a plus de partition interne. Reste à définir (différé) : la **détacher**
(annexe → indépendante, `parent_id → null`) pour une autonomie complète.*

---

## 7. Périmètre V1 vs différé

**V1 — à construire :** cas **église indépendante**. `ProvisionTenant` (genèse) + relecture IAM mobile.
`parent_id = null`, aucune annexe, aucune dénomination dans les données.

**Schéma préparé mais non exposé :** `parent_id` (conservé — c'est le mécanisme d'annexe retenu).

> ⚠️ **Révisé 2026-07-23 :** la table `annexes` et la colonne `annexe_id` (`Membership`,
> `RoleAssignment`) sont **abandonnées** (jamais écrites) — à supprimer (§8 Dette). L'annexe n'est plus
> une partition interne mais une **église-fille** (`parent_id` + Owner propre, §4.1).

**Différé (surface backoffice, quand le besoin réel arrive) :** `TransferOwnership` *(livré depuis)*,
ajout d'annexe (`POST /tenants/{parent_id}/annexes`), détachement d'annexe (`parent_id → null`),
rattachement `Network`.

**Abandonné :** portée d'annexe dans `covers()` et cloisonnement `WHERE annexe_id` (plus de partition
interne — l'annexe est un tenant à part, isolé par nature).

---

## 8. Dette identifiée

| Dette | Objet | Statut |
| :--- | :--- | :--- |
| **D1** | Invariant I1 « 1 owner actif / tenant » absent (autorise 0 ou 2 Owners) | ✅ **tranchée** → §9 P0.2 |
| **D2** | `created_by`/`assigned_by` NOT NULL FK au bootstrap (créateur = Plateforme) | ✅ **tranchée** → §9 P0.1 |
| **D3** | `covers()` ne borne que `group_leader` (portée annexe non appliquée) | ❌ **caduque** (2026-07-23) — plus de portée annexe interne (§4.1) |
| **D4** | `TransferOwnership` absent (bloquant dès la 1ʳᵉ mutation pastorale) | ✅ **livré** (validé « membre confirmé du tenant », cohérent §6) |
| **D5** | Scaffolding annexe mort (`annexes`, `annexe_id`×2) — jamais écrit, à supprimer | ⏳ **à faire** (nettoyage + migration) — suite révision §4.1 |
| **D6** | `parent_id` non validé au provisioning (annexe orpheline possible) | ⏳ **à faire** — prérequis de l'abonnement famille |

---

## 9. Phase 0 — décisions gravées (ratifiées)

Socle transverse aux deux **surfaces** (backoffice + mobile), tranché avant tout code. Toute décision
de schéma est **implémentée dans ce backend** (migration Alembic + modèle ORM `models.py`), qui en est
propriétaire.

### P0.1 · Compte système « Dorea Platform » *(résout D2)*
- Un `Account` **système unique**, UUID constant bien connu, **seedé**.
- **Non-authentifiable** : sans `password_hash`, `status` interdisant le login.
- **Sans `Membership`** (n'appartient à aucune église) — acteur pur référencé par les `created_by`/`assigned_by`.
- **Enum** : ajouter `system` à `AccountCreationSource` (additif, stable) pour l'origine de ce compte.
- Bénéfice : FK toujours non-nulles + audit propre (atténue **R6**), sert genèse + succession + émancipation.

### P0.2 · Invariant I1 *(résout D1)*
- **« Au plus 1 »** → **index unique partiel** : `UNIQUE(tenant_id) WHERE role='owner' AND revoked_at IS NULL`.
  - **Prérequis schéma : dénormaliser `tenant_id` sur `role_assignments`** (l'index ne peut voir le
    `tenant_id` porté par `memberships`). Garantie DB forte, y compris en course concurrente.
- **« Au moins 1 »** → règle de domaine **`LAST_OWNER_REMOVAL_BLOCKED`** (réplique du pattern existant
  `IAM_GROUP_LAST_LEADER_REMOVAL_BLOCKED`) : clôturer la `Membership` d'un Owner sans successeur est refusé.

### P0.3 · Colonnes hiérarchie *(prépare annexe & émancipation)* — **partiellement caduc (2026-07-23)**
Posées **maintenant, nullable, non exposées** (spec §4.2) :

| Table | Colonne | V1 | Statut post-révision §4.1 |
| :--- | :--- | :--- | :--- |
| `tenants` | `parent_id` nullable FK→`tenants` (filiation) | `null` | ✅ **conservé** — mécanisme d'annexe |
| `memberships` | `annexe_id` nullable FK→`annexes` | `null` | ❌ **à supprimer** (jamais écrit) |
| `role_assignments` | `annexe_id` nullable (sélecteur de portée, ∥ `group_id`) | `null` | ❌ **à supprimer** (jamais écrit) |
| `annexes` *(nouvelle)* | `(id, tenant_id, name)` | définie, non utilisée | ❌ **à supprimer** (0 ligne, aucun writer) |

> L'annexe n'étant plus une partition interne mais une **église-fille** (§4.1), seul `parent_id`
> survit. Les trois autres artefacts sont du scaffolding mort → dette **D5** (§8).

Contrainte : **aucune** ne fige un membre à son annexe (migrabilité pour l'émancipation).

### Exécution (tout dans ce backend)
| Tâche | Emplacement |
| :--- | :--- |
| Migration Alembic (colonnes, index partiel, `tenant_id` sur `role_assignments`, table `annexes`) + seed du compte système | `migrations/` + `scripts/` |
| Modèle ORM `models.py`, `dev_bootstrap`, enum `system`, règle `LAST_OWNER_REMOVAL_BLOCKED` | contextes `iam` / `tenant` |

---

## 10. Flow réel — un backend, deux surfaces

### 10.1. Topologie
```
FRONTS (clients)                         BACKEND UNIQUE (ce FastAPI monolithe)          DB
────────────────                         ─────────────────────────────────────          ──
PWA Next.js / React  ──HTTP──►  /api/backoffice/*   ┐
  (gestion tenant & owner)                          ├──►  domaine + persistance  ──►  PostgreSQL
Flutter (mobile)     ──HTTP──►  /api/mobile/*        ┘        (schéma & migrations ici)
  (le membre)
```
- **Une** base de code, **une** base Postgres, **deux** préfixes de route selon le front appelant.
- `/api/backoffice/*` : écritures IAM (provisionnement, enrôlement, gestion). Auth **session**.
- `/api/mobile/*` : lecture du membre + `RecordFirstAttendance`. Auth **JWT**.
- Même hasher, même modèle de domaine partagés par les deux surfaces (plus de synchro inter-service).

### 10.2. Flow métier de bout en bout (ordre normal du projet)
```
① BACKOFFICE  Plateforme → ProvisionTenant → Tenant + Owner (bootstrap)      [porte d'entrée réelle]
② BACKOFFICE  Owner (session) → enregistre Pasteur(s) + Admin(s)
③ BACKOFFICE  Admin → crée Groupes + désigne Responsables
④ BACKOFFICE  Responsable → enregistre les Membres (formulaire / lien)
⑤ MOBILE      Membre (JWT) → /me/memberships → présences, absences, fil…      [en aval]
```
La construction **suit cet ordre** : on organise d'abord la **gestion du Tenant** (①), racine de tout
le reste. La surface mobile (⑤) est déjà amorcée (`/api/mobile/iam/me/memberships`) mais vient **après**
dans le flux : sans tenant ni owner provisionnés, elle n'a rien à lire.

---

**Fin M0.** Toute évolution ici doit être répercutée dans M1 (nomenclature) avant développement.
