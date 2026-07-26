# MT — Transfert de membre entre églises (source de vérité)

> Établi par cas d'usage avec l'utilisateur (2026-07-17) — le cas **Mme Richmond** (bascule
> officielle de Soba à Peniel). Vit dans le contexte `iam` (gouvernance des appartenances).

---

## 1. L'idée-clé : un transfert n'est **pas** une migration de données

L'identité est **globale** (le téléphone = un `Account`, partagé par tout le réseau). Le compte de
Mme Richmond **ne bouge jamais**. Un transfert est un **événement de gouvernance** en deux moitiés :
- **Libérer** (source, Soba) : clôturer son appartenance avec la raison `changed_church`, ce qui
  **cascade la révocation de ses rôles** et la fait **quitter les groupes** de Soba (effectif honnête).
- **Recevoir** (destination, Peniel) : ouvrir / confirmer une appartenance `confirmed_member`.

L'état **`shared`** (M7, « active ailleurs ») se **résout tout seul** : une fois Soba clôturé, elle
n'est plus « active ailleurs » — elle est simplement membre de Peniel.

## 2. Le principe de gouvernance : **souveraineté du tenant**

Aucune super-autorité ne règne sur deux églises (`NETWORK_SUPERVISOR` est lecture seule ; il n'existe
pas de regroupement formel « réseau »). **Une église ne mute jamais les données d'une autre.** D'où la
**poignée de main** :

```
Peniel (destination)                     Soba (source)
  │ RequestTransfer                       │
  │  (autorité TRANSFER_MEMBER sur Peniel)│
  ├───────────── pending ────────────────▶│
  │                                       │ AcceptTransfer
  │                                       │  (autorité TRANSFER_MEMBER sur Soba)
  │◀──────────── accepted ────────────────┤  ↳ close(changed_church) + cascade rôles
  ▼                                       ▼  ↳ quitte les groupes de Soba
 membership confirmed_member          membership closed
 (+ placement cellule optionnel)
```

Chaque côté **n'agit que sur sa maison**. Décliner (source) ou annuler (destination) sont des
résolutions simples sans effet de bord.

## 3. Décisions figées

- **Gouvernance** : poignée de main (destination demande → source accepte). *Choisi.*
- **Atterrissage destination** : `confirmed_member` (une croyante établie qui vient d'une église sœur,
  pas un visiteur qui recommence le parcours). *Choisi.*
- **Autorité** : permission `TRANSFER_MEMBER` (Admin + Owner via 1ᵉʳ étage), des deux côtés.
- **Garde-fous source** (réutilisés de la clôture) : jamais le **dernier Owner**, jamais le **dernier
  responsable** d'un groupe (sinon Soba doit d'abord réassigner).
- **Tolérance** : si elle est déjà membre `shared` à Peniel → on **officialise** (transition vers
  `confirmed_member`), on ne recrée pas ; placement cellule **idempotent**.
- **Anti-doublon** : une seule demande `pending` par (compte, source, destination).

## 4. Architecture (layering)

`iam` ne dépend **pas** de `groups`. Les mouvements de roster (quitter les groupes source, placer dans
une cellule destination) passent par un **port** `MemberRosterPort` (défini dans `iam.application.ports`),
implémenté par `GroupRosterAdapter` **côté groups** (`groups → iam`, sens correct). iam reste pur.

- Agrégat `iam/domain/transfer.py` : `MemberTransfer` (pending → accepted/declined/cancelled).
- Commandes `iam/application/commands/transfer_member.py` : `RequestTransfer`, `AcceptTransfer`
  (la saga), `DeclineTransfer`, `CancelTransfer`. Requête `list_transfers.py`.
- Réutilise les ports existants : `MembershipLifecycleStore.close_membership` (libération + cascade),
  `MemberEnrollmentStore.add_membership` (nouvelle appartenance), `MembershipTransitionStore` (officialiser).
- Table `member_transfers` (migration `e7d3f4a1b6c8`). FK `account_id → accounts`.

## 5. Routes (backoffice, cookie de session)

- `POST /api/backoffice/iam/tenants/{tid}/transfer-requests` — la destination (`tid`) demande
  (body : `account_id`, `from_tenant_id`, `to_group_id?`).
- `POST /api/backoffice/iam/transfers/{id}/accept` — la source libère (exécute la saga).
- `POST /api/backoffice/iam/transfers/{id}/decline` — la source refuse.
- `POST /api/backoffice/iam/transfers/{id}/cancel` — la destination se rétracte.
- `GET /api/backoffice/iam/tenants/{tid}/transfers` — entrants (à traiter) / sortants (émis).

**MT-0 livré** (2026-07-17) — 14 tests. Migration `e7d3f4a1b6c8`.

## 6. Reporté

- Notification à l'église destination quand la source accepte/refuse (M8 annonces).
- Historique « d'où vient ce membre » exposé côté destination (lecture cross-tenant volontairement
  minimale pour l'instant).
- Transfert d'un membre **staff** avec réassignation guidée de ses groupes avant libération.
