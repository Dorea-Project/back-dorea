# Console d'administration Dorea — note de design (le back-office de l'éditeur)

**Statut :** note de design (non implémentée). Décidé le 2026-07-23.
**Portée :** le **3ᵉ plan d'autorisation** — le staff de **Dorea l'éditeur** qui exploite la plateforme
(provisionne les églises, gère les abonnements, assiste les clients). À ne confondre ni avec
l'**Ownership** (les clés d'une église) ni avec le **RBAC église** (`RoleCode` : pastor/admin/…).

> Dorea livre une **infrastructure** (Church OS). L'éditeur a besoin de son propre back-office
> **nominatif et tracé** — pas d'un secret partagé. Aujourd'hui tout acte plateforme passe par un
> unique `X-Service-Token` : aucune traçabilité (qui a suspendu cette église ?), aucun moindre
> privilège. Cette console corrige cela (et adresse la dette d'audit **R6** de `Security_Audit.md`).

---

## 1. Les trois plans d'autorisation (ne jamais mélanger)

| Plan | Qui | Portée | Mécanisme |
| :-- | :-- | :-- | :-- |
| **Ownership** | l'Owner d'une église | tout pouvoir sur **son** tenant | `is_active_owner` (étage 1) |
| **RBAC église** | pastor/admin/church_leader/… | **un** tenant, scopé | `RoleCode` + `Permission` |
| **RBAC Dorea** *(cette note)* | staff de l'éditeur | **la plateforme** (tous les tenants) | `PlatformRole` + `PlatformPermission` |

Le RBAC Dorea est un enum **séparé** (`PlatformRole` ≠ `RoleCode`) avec ses propres permissions et son
propre service d'autorisation. Un staff Dorea n'a **pas** de `Membership` d'église : il a une
**assignation de rôle plateforme**.

---

## 2. Les rôles Dorea (validés 2026-07-23)

`PlatformRole` — extensible (le « etc. » viendra) :

| Rôle | En un mot |
| :-- | :-- |
| `main_admin` | super-admin — **tout**, y compris gérer le staff Dorea |
| `manager` | exploitation — tout **sauf** gérer le staff |
| `support` | SAV / service après-vente — **lecture + assistance**, aucun acte destructeur/financier |

## 3. Permissions plateforme × rôles (carte validée)

| `PlatformPermission` | `main_admin` | `manager` | `support` |
| :-- | :--: | :--: | :--: |
| `PROVISION_TENANT` (créer une église) | ✓ | ✓ | · |
| `MANAGE_TENANT_LIFECYCLE` (suspendre/réactiver) | ✓ | ✓ | · |
| `TRANSFER_OWNERSHIP` (succession) | ✓ | ✓ | · |
| `ADD_ANNEXE` (ajouter une annexe) | ✓ | ✓ | · |
| `MANAGE_SUBSCRIPTION` (plan/période d'une église) | ✓ | ✓ | · |
| `MANAGE_PROMOTIONS` (promos/remises) | ✓ | ✓ | · |
| `MODERATE_CONTENT` (annonces Dorea, retrait d'événement) | ✓ | ✓ | · |
| `VIEW_TENANT_DIRECTORY` (annuaire des églises) | ✓ | ✓ | ✓ |
| `VIEW_BILLING` (statut de facturation) | ✓ | ✓ | ✓ |
| `ASSIST_TENANT` (débloquer un owner, aide) | ✓ | ✓ | ✓ |
| `MANAGE_PLATFORM_STAFF` (comptes/rôles Dorea) | ✓ | · | · |

> `MANAGE_SUBSCRIPTION`, `ADD_ANNEXE`, `MANAGE_PROMOTIONS` **résolvent la question E** de la matrice
> église : ce ne sont **pas** des permissions de `RoleCode`, mais des permissions **plateforme**.

---

## 4. Authentification du staff Dorea

- Un membre du staff = un `Account` **avec une assignation `PlatformRole`** (aucune `Membership`).
- **Login dédié** : email + mot de passe + **OTP** (2FA — l'accès plateforme est très privilégié),
  session propre (cookie distinct du `dorea_backoffice_session` des owners d'église).
- Le compte système **`Dorea Platform`** (P0.1, non-authentifiable) reste l'acteur **machine**
  (`created_by` des actes automatisés). Les humains ont désormais leurs **propres comptes tracés**.
- **`X-Service-Token`** : conservé **uniquement** pour les actes **machine/cron** (dispatch
  notifications) — plus jamais pour un acte humain.

## 5. Les routes — nouvelle surface `/api/admin/*`

Surface Dorea distincte et explicite (décidé 2026-07-23), **role-gardée** (≠ token) :

```
/api/admin/auth/login | verify | logout | me          # auth staff Dorea (email+password+OTP)
/api/admin/staff                                       # CRUD staff Dorea         (MANAGE_PLATFORM_STAFF)
/api/admin/tenants            POST | GET                # provisionner | annuaire  (PROVISION_TENANT / VIEW_TENANT_DIRECTORY)
/api/admin/tenants/{id}                                # fiche église             (VIEW_TENANT_DIRECTORY)
/api/admin/tenants/{id}/suspend | reactivate           #                          (MANAGE_TENANT_LIFECYCLE)
/api/admin/tenants/{id}/transfer-ownership             #                          (TRANSFER_OWNERSHIP)
/api/admin/tenants/{parent_id}/annexes   POST          # ajouter une annexe       (ADD_ANNEXE)
/api/admin/tenants/{id}/subscription                   # plan/période             (MANAGE_SUBSCRIPTION)
/api/admin/tenants/{id}/assist                         # débloquer/aider un owner (ASSIST_TENANT)
/api/admin/promotions         CRUD                      # promos/remises           (MANAGE_PROMOTIONS)
/api/admin/moderation/announcements                    # annonces Dorea           (MODERATE_CONTENT)
/api/admin/moderation/events/{id}/takedown             # retrait d'événement      (MODERATE_CONTENT)
```

**Migration** : les actes plateforme actuels sous `/api/backoffice/platform/*` **et** le
provisionnement/suspension sous `/api/backoffice/tenants` (aujourd'hui token-gardés) **déménagent**
vers `/api/admin/*` role-gardé. Le dispatch notifications machine peut rester token-gardé (cron).

## 6. Traçabilité (le gain clé)

Chaque acte plateforme est **attribué à un compte staff** (`performed_by_account_id` + horodatage) —
un journal d'audit interrogeable. Réponse directe à **R6** (« pas d'audit trail IAM ») : on saura
*qui* a suspendu, transféré, remisé, quand.

---

## 7. Décisions ouvertes

| # | Décision | Piste |
| :-- | :-- | :-- |
| **A1** | 2FA staff à chaque login, ou seulement nouvel appareil (comme l'owner) ? | à chaque login (privilège élevé) |
| **A2** | `support` peut-il déclencher un **reset d'accès owner** (OTP/mot de passe), ou seulement *voir* ? | reset assisté, tracé |
| **A3** | Rôles supplémentaires (« etc. ») : `finance` (facturation seule) ? `moderator` (contenu seul) ? | à cadrer au besoin |
| **A4** | Périmètre du journal d'audit (tous les actes, ou seulement mutations) ? | mutations d'abord |
| **A5** | Garde-fou « au moins 1 `main_admin` » (ne pas se verrouiller dehors) | oui, règle domaine |

---

*Note de design — fait foi pour la décision, pas pour l'implémentation. Nouveau contexte borné
probable : `platform_admin` (ou extension `iam` avec un axe plateforme). À promouvoir en spec une fois
A1–A5 tranchés.*
