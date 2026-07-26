# MODULE M1 — IAM
## Nomenclature technique (EN) — Dictionnaire de référence

**But :** fixer une fois pour toutes les noms d'entités, d'attributs, d'enums et de codes d'erreur en
anglais, pour que le code (FastAPI/SQLAlchemy) et la base PostgreSQL utilisent exactement le même
vocabulaire. Aucune traduction locale au moment du développement — ce document **est** la source de
vérité du nommage.

> **Note (voir spec §14) :** ce document parlait à l'origine de deux stacks (NestJS + FastAPI). Il n'y
> a en réalité **qu'un backend FastAPI**. Les *noms* (entités, enums, erreurs) restent valables tels
> quels ; seules les mentions d'un second service sont caduques.

**Convention retenue :**
- Tables et colonnes PostgreSQL : `snake_case`
- Types/classes (Pydantic, SQLAlchemy) : `PascalCase`
- Enums (valeurs stockées en base) : `snake_case`, en minuscules, stables (ne jamais les renommer
  après mise en prod — seulement en ajouter)
- Booléens : préfixe `is_` / `has_`

---

## 1. Entités → Tables

| Nom métier (FR) | Nom technique (EN) | Table PostgreSQL |
| :--- | :--- | :--- |
| Compte | `Account` | `accounts` |
| Appartenance | `Membership` | `memberships` |
| Attribution de rôle | `RoleAssignment` | `role_assignments` |
| Réseau | `Network` | `networks` |
| Rattachement Tenant | `NetworkTenantLink` | `network_tenant_links` |
| Tenant (Église/Annexe) | `Tenant` | `tenants` *(porté par M0, référencé ici)* |
| Groupe | `Group` | `groups` *(porté par M4, référencé ici)* |

---

## 2. `Account` (ex-Compte)

| Attribut FR | Attribut EN | Type | Notes |
| :--- | :--- | :--- | :--- |
| id | `id` | UUID | PK |
| téléphone | `phone_number` | string | unique, non nul |
| email | `email` | string | unique, nullable |
| nom | `last_name` | string | nullable |
| prénom | `first_name` | string | nullable |
| password_hash | `password_hash` | string | nullable |
| version d'algorithme de hash | `hash_algo_version` | int | |
| téléphone vérifié | `is_phone_verified` | boolean | défaut `false` |
| email vérifié | `is_email_verified` | boolean | défaut `false` |
| date de création | `created_at` | timestamp | |
| créé par (type) | `created_by_type` | enum `AccountCreationSource` | voir §7.1 |
| statut du compte | `status` | enum `AccountStatus` | voir §7.2 |

---

## 3. `Membership` (ex-Appartenance)

*Agrégat racine.*

| Attribut FR | Attribut EN | Type | Notes |
| :--- | :--- | :--- | :--- |
| id | `id` | UUID | PK |
| compte_id | `account_id` | UUID | FK → `accounts` |
| tenant_id | `tenant_id` | UUID | FK → `tenants` |
| statut | `status` | enum `MembershipStatus` | voir §7.3 |
| statut précédent | `previous_status` | enum `MembershipStatus` | nullable |
| date dernière transition | `last_transition_at` | timestamp | |
| date de création | `created_at` | timestamp | |
| créé par | `created_by_account_id` | UUID | FK → `accounts` |
| qualification d'absence active | `active_absence_reason` | enum `AbsenceReason` | nullable — voir M7 |
| date de clôture | `closed_at` | timestamp | nullable |
| motif de clôture | `closure_reason` | enum `MembershipClosureReason` | nullable |

**Contrainte d'unicité :** `(account_id, tenant_id)` sur les lignes non clôturées →
`uq_active_membership_per_tenant`.

---

## 4. `RoleAssignment` (ex-Attribution de rôle)

*Entité interne à l'agrégat `Membership`.*

| Attribut FR | Attribut EN | Type | Notes |
| :--- | :--- | :--- | :--- |
| id | `id` | UUID | PK |
| appartenance_id | `membership_id` | UUID | FK → `memberships` (parent) |
| rôle | `role` | enum `RoleCode` | voir §7.4 |
| groupe_id | `group_id` | UUID | nullable — obligatoire si `role = group_leader` |
| date d'attribution | `assigned_at` | timestamp | |
| attribué par | `assigned_by_account_id` | UUID | FK → `accounts` |
| date de révocation | `revoked_at` | timestamp | nullable |
| révoqué par (cause) | `revoked_reason` | enum `RevocationReason` | nullable |

---

## 5. `Network` (ex-Réseau) & `NetworkTenantLink` (ex-Rattachement)

| Attribut FR | Attribut EN | Type | Notes |
| :--- | :--- | :--- | :--- |
| id | `id` | UUID | PK — table `networks` |
| nom | `name` | string | |
| créé par | `created_by_account_id` | UUID | FK → `accounts` |
| date de création | `created_at` | timestamp | |

| Attribut FR | Attribut EN | Type | Notes |
| :--- | :--- | :--- | :--- |
| id | `id` | UUID | PK — table `network_tenant_links` |
| réseau_id | `network_id` | UUID | FK → `networks` |
| tenant_id | `tenant_id` | UUID | FK → `tenants` |
| statut | `status` | enum `NetworkLinkStatus` | voir §7.5 |
| rattaché par | `linked_by_account_id` | UUID | FK → `accounts` |
| date de rattachement | `linked_at` | timestamp | nullable |

**Contrainte d'unicité :** un `tenant_id` avec au plus une ligne `status = active` →
`uq_active_network_per_tenant`.

---

## 6. Codes d'erreur de domaine

Préfixe `IAM_` pour tout code émis par ce module — permet de tracer l'origine du contexte borné
dans les logs et les réponses API, quelle que soit la surface (backoffice ou mobile) qui les relaie.

| Code | Cas | Déclenché par |
| :--- | :--- | :--- |
| `IAM_INVALID_TRANSITION` | Transition hors table §3.2 de la spec métier | `TransitionStatus` |
| `IAM_STATUS_SKIP_FORBIDDEN` | Saut de palier (`invited → confirmed_member` direct) | `TransitionStatus` |
| `IAM_ROLE_REQUIRES_CONFIRMED_MEMBER` | Attribution de rôle sur statut < `confirmed_member` | `AssignRole` |
| `IAM_GROUP_LEADER_CAP_EXCEEDED` | 7ᵉ `group_leader` sur un même groupe | `AssignRole` |
| `IAM_GROUP_LAST_LEADER_REMOVAL_BLOCKED` | Retrait du dernier `group_leader` sans remplaçant | `RevokeRole` |
| `IAM_DUPLICATE_ACTIVE_MEMBERSHIP` | Violation de `uq_active_membership_per_tenant` | `CreateMembership` |
| `IAM_ACCOUNT_PHONE_ALREADY_EXISTS` | Violation d'unicité téléphone | `RegisterAccount` |
| `IAM_NETWORK_LINK_PENDING_CONSENT` | Lecture 360 demandée sur un lien non `active` | `GetNetworkDashboard` |
| `IAM_NETWORK_MULTI_LINK_FORBIDDEN` | Violation de `uq_active_network_per_tenant` | `LinkTenantToNetwork` |
| `IAM_UNAUTHORIZED_SCOPE` | Rôle valide mais ressource hors portée (§6.1 spec métier) | `CanPerform` (garde transverse) |

---

## 7. Enums (valeurs stockées — stables, ne jamais renommer)

### 7.1. `AccountCreationSource`
```
owner | walk_in_registration | self_service
```
*(`walk_in_registration` = ex-"accueil" ; enregistrement en présentiel par une équipe d'accueil)*

### 7.2. `AccountStatus`
```
active | suspended
```

### 7.3. `MembershipStatus`
```
invited | visitor | sympathizer | newcomer | confirmed_member
external_participant | closed
```
*(`external_participant` = statut parallèle, hors chaîne progressive — voir spec métier §5.5)*

### 7.4. `RoleCode`
```
owner | pastor | admin | group_leader | welcome_team | integration_team | network_supervisor
```
*(`welcome_team` = ex-"accueil" ; `integration_team` = ex-"intégration" ;
`network_supervisor` = ex-"superviseur_reseau")*

### 7.5. `NetworkLinkStatus`
```
active | pending_acceptance | detached
```

### 7.6. `RevocationReason`
```
admin_action | demotion_cascade
```

### 7.7. `MembershipClosureReason`
```
changed_church | inactivity | member_request | other
```

### 7.8. Événements de transition (`MembershipTransitionEvent`)
*(valeurs utilisées en paramètre de `TransitionStatus`, pas stockées telles quelles — journalisées
dans `previous_status`/`status`)*
```
bootstrap_owner | enroll_invited | first_attendance_recorded
qualify_sympathizer | qualify_newcomer | confirm_member
demote | close | create_external_participant
```

---

## 8. Opérations (commandes/requêtes) — noms de méthode

*Correspondance avec §7 de la spec métier — appliquée en anglais pour tout code.*

### 8.1. Commandes

| Nom métier (FR) | Nom technique (EN) |
| :--- | :--- |
| ProvisionnerTenant | `ProvisionTenant` |
| EnregistrerCompte | `RegisterAccount` |
| CreerAppartenance | `CreateMembership` |
| TransitionnerStatut | `TransitionStatus` |
| EnregistrerPremierePresence | `RecordFirstAttendance` |
| AttribuerRole | `AssignRole` |
| RevoquerRole | `RevokeRole` |
| RetrograderAppartenance | `DemoteMembership` |
| CloturerAppartenance | `CloseMembership` |
| VerifierTelephone | `VerifyPhoneNumber` |
| ProvisionnerReseau | `ProvisionNetwork` |
| RattacherTenantExistant | `LinkExistingTenantToNetwork` |
| AccepterRattachement | `AcceptNetworkLink` |
| DetacherTenant | `DetachTenantFromNetwork` |

### 8.2. Requêtes

| Nom métier (FR) | Nom technique (EN) |
| :--- | :--- |
| ObtenirRolesActifs | `GetActiveRoles` |
| ObtenirStatut | `GetMembershipStatus` |
| EstMembreConfirme | `IsConfirmedMember` |
| ListerResponsablesDuGroupe | `ListGroupLeaders` |
| PeutFaire | `CanPerform` |
| ObtenirTableauDeBordReseau | `GetNetworkDashboard` |

---

## 9. Endpoints — convention de routage (préparatoire à M2)

*Non détaillé ici (hors périmètre IAM pur), mais fixé pour cohérence future :*

> **Note (voir spec §14) :** un seul backend FastAPI, deux **surfaces** de routes selon le front.

- Backoffice (front PWA Next.js) : `/api/backoffice/iam/*` — écritures IAM
- Mobile (front Flutter, lecture + `RecordFirstAttendance`) : `/api/mobile/iam/*` *(surface
  volontairement réduite — la majorité des commandes IAM ne sont pas exposées côté mobile)*

---

**Fin de la nomenclature IAM.**

*Toute évolution du modèle métier (fichier `M1_IAM_Spec.md`) doit être répercutée ici avant le début
du développement — ce document est la seule source de vérité pour les noms de code.*
