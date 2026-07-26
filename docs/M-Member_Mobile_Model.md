# MODULE M-MEMBER — Modèle Membre (Mobile)

## Source de vérité du côté **membre** (app mobile Flutter)

**But :** figer, avant tout code, comment un membre existe, s'onboarde, se rattache à une (ou
plusieurs) église(s), s'authentifie, et comment ses rôles/permissions lui sont exposés. Complète M0
(Tenant/Owner) et M1 (IAM) côté **Owner/backoffice** — ce document couvre la **face membre**, restée
en angle mort. Issu de la découverte par les cas d'usage (activation, self-registration, groupe,
multi-église, zones d'ombre).

---

## 1. La clé : deux axes **indépendants**

La confusion vient de ce qu'on mélange deux questions distinctes. Un membre est **un point dans une
grille 2×2** :

|                       | membership OUI (dans une église) | membership NON |
| :--- | :--- | :--- |
| **credentials OUI** (peut se connecter) | membre complet (normal) | auto-inscrit **sans** église |
| **credentials NON** | enrôlé **pas encore activé** (le visiteur dans l'annuaire) | n'existe pas vraiment |

**Tous les flux ne font que déplacer la personne dans cette grille.**

---

## 2. Les deux sens de « membre » (ne pas confondre)

| Sens | Ce que c'est | Quand |
| :--- | :--- | :--- |
| **Rattaché** (appartient à l'église) | la `Membership` **existe** | à l'**enrôlement / au rattachement** |
| **Membre confirmé** | statut = `confirmed_member` | **plus tard** (parcours d'intégration) ou **bootstrap** (staff) |

- On devient **rattaché d'abord** (souvent `invited`), **confirmé ensuite**.
- Un visiteur `invited` **est déjà rattaché** (il a une Membership) — pas encore *confirmé*.
- **Activer l'app ≠ devenir membre.** Trois choses **indépendantes** : rattachement (Membership),
  confirmation (statut), activation (credentials).
- « Être membre » n'est **jamais global** : toujours **relatif à une église**.

---

## 3. Deux niveaux de rattachement : **Église** puis **Groupe**

- **Église (tenant)** = rattachement primaire (`Membership`). **1 seule appartenance active par
  église** (`uq_active_membership_per_tenant`).
- **Groupe (cellule/département, M4)** = sous-structure du tenant. On peut appartenir à **plusieurs
  groupes** d'une même église, ou à **aucun**.
- **Groupe ⊂ Église** : rejoindre un groupe **crée d'abord** la Membership à l'église (si absente),
  **puis** le rattachement au groupe. On ne peut pas être dans un groupe sans être membre de l'église.
- « Trouver mon groupe » ≠ « être membre de l'église » : on peut être membre **sans** groupe.

---

## 4. Taxonomie d'onboarding — **une seule logique** `register`

Ces cas ne sont **pas** N endpoints : c'est **un** endpoint `register` qui décide selon deux entrées
(*token d'invitation présent ?* et *le numéro existe-t-il ?*).

| `register` reçoit | État du numéro | Résultat | Cas |
| :--- | :--- | :--- | :--- |
| **token d'invitation** | (peu importe) | réclame/crée le compte **+ crée la Membership** du token | **1.B** |
| **pas de token** | existe, **enrôlé** (membership, sans pin) | **réclame** le compte (pose le PIN) | **1.A** |
| **pas de token** | existe, **déjà activé** | erreur « déjà activé → connecte-toi » | — |
| **pas de token** | **nouveau** | crée compte `self_service`, **sans** église | **2.A** |

- **Catégorie 1 — s'inscrit ET rattaché** : il y a un rattachement (token, ou membership
  pré-existante). → cas **1.A** (enrôlé puis active), **1.B** (lien d'invitation), **1.C** (2ᵉ église,
  compte réutilisé).
- **Catégorie 2 — s'inscrit seulement** : ni token ni membership → **compte seul** (**2.A**), en
  attente de rejoindre une église.

Le socle commun (OTP → set PIN → réclamer/créer) couvre **1.A** et **2.A** d'un coup (= chantier M-1).

---

## 5. Les 5 scénarios concrets (vécu du membre)

Le vécu dépend de 3 questions : **① église sur Dorea ? ② l'église me connaît-elle (enrôlé) ? ③ ai-je
un moyen d'entrer dans mon groupe (lien) ?**

1. **App, église PAS sur Dorea** → auto-inscrit `self_service`, **aucune** église. « Flottant ». →
   levier de croissance : « **inviter mon église** » branche le funnel Owner. Membre **quand l'église
   rejoint**.
2. **Église sur Dorea, enrôlé, sans groupe** → active → **membre de l'église, sans cellule**. Normal
   (église ≠ groupe).
3. **Église sur Dorea, PAS enrôlé, pas de lien** → l'église est là mais **impossible de rejoindre**
   (les groupes ne se rejoignent pas librement). → « demande le lien à ton responsable » / demande de
   rattachement / le staff l'enrôle. **Pas encore membre.**
4. **Église sur Dorea, enrôlé DANS son groupe** → active → **église + groupe** directement. Idéal.
5. **Église sur Dorea, a le lien du groupe** → `register(token)` → PIN + **rattaché église + groupe**
   en un geste.

---

## 6. DÉCISION C (tranchée) — le credential : **deux emplacements**

Un `Account` porte **deux** credentials **optionnels**, posés **à l'activation selon la surface** :

```
Account
- password_hash   (+ email)  → credential BACKOFFICE (Owner/Admin/Pasteur)
- pin_hash        (+ phone)  → credential MOBILE (membre, rôles terrain)
```

- **Login mobile** (phone) → vérifie `pin_hash`. **Login backoffice** (email) → vérifie `password_hash`.
- Une personne **double-surface** (Admin à A + membre à B, ou Owner qui veut l'app) a **les deux**.
- **Le type de credential mappe la surface**, posé **à l'activation**, pas à l'enrôlement.

**Corrige un bug actuel :** `EnrollMember` pose aujourd'hui un **PIN** à un Pasteur/Admin (backoffice) —
faux. Désormais l'enrôlement du staff **ne pose plus de credential** ; le staff active son **mot de
passe backoffice** (comme l'Owner), le membre active son **PIN mobile**.

*(Option (c) — table `credentials` N par compte — reportée : (b) suffit, migration douce plus tard si
passkeys.)*

---

## 7. Zones d'ombre — **résolutions**

| # | Zone | Résolution |
| :--- | :--- | :--- |
| A | **Téléphone = identité unique** | OTP = seule preuve. Faute de frappe à l'enrôlement → **confirmer le numéro** + correction par le staff (tracée). SIM swap → **risque assumé** (comme WhatsApp) + OTP nouvel appareil. **1 numéro = 1 compte** (R3, limite V1). |
| B | **Comptes en double** (même humain, 2 numéros) | Numéro = seule clé ; enrôler un numéro présent → **réutilise** (M-2). Vrais doublons → **fusion** staff/Dorea, **différée** mais nommée. |
| C | **PIN vs mot de passe** | **Tranchée §6** : deux emplacements. |
| D | **Groupe ⊂ église** | Rejoindre un groupe crée la Membership église (si absente) puis le groupe. Multi-groupes OK, 1 seule appartenance église. |
| E | **Multi-église sur mobile** | **Sélecteur d'église** ; tout est scopé au tenant sélectionné. `/me` = une entrée par appartenance (statut + rôles + permissions résolues). Seule l'identité (nom, numéro) est globale. |
| F | **Sortie / suspension** | Appartenance clôturée → l'église disparaît, le **compte survit**. Tenant suspendu → **lecture seule / gelé** pour les membres. Compte suspendu → **plus de login**. |
| G | **Découverte** | **Pas de recherche ouverte** : entrée **toujours** par lien (responsable) ou enrôlement (staff). « Église visible mais pas mon groupe » = normal. *(ouvert : autoriser une « demande de rattachement » approuvée par le staff ?)* |
| H | **Appartenances fantômes** | `invited` jamais venu/activé → **auto-clôture** `inactivity` (worker M7/M9), câblé plus tard. |

---

## 8. Multi-église

- **Un `Account`, N `Membership`** — chacune avec **son** statut et **ses** rôles.
- On peut être `confirmed_member` à Bethel **et** `group_leader` à Sion **simultanément**.
- Le mobile a un **sélecteur d'église** ; rôles/permissions/statut/fil sont **par tenant sélectionné**.
- « Changer d'église » = clôturer une Membership + en ouvrir une autre ; **cumuler** est aussi permis.

---

## 9. Plan de construction (côté membre)

| # | Chantier | Résout | Dépend | État |
| :--- | :--- | :--- | :--- | :--- |
| **M-0** | Schéma : ajouter `accounts.pin_hash` ; login mobile → `pin_hash` ; `EnrollMember` ne pose plus de credential | Décision C | — | ✅ fait |
| **M-1** | **Register/verify** (réclamer OU créer) + set PIN (couvre 1.A + 2.A) | #1, #3 | P1 OTP ✅ | ✅ fait |
| **M-2** | **Réutilisation du compte global** à l'enrôlement (au lieu de rejeter) | #2 | — | ✅ fait |
| **M-3** | `/me` mobile avec **permissions résolues** (ce que le membre peut faire) | #4 | — | ✅ fait |
| **M-4** | **OTP nouvel appareil** au login mobile | #5 | P1 ✅, P2 devices ✅ | ✅ fait |
| **M-5** | **Rejoindre une église** (lien/code d'invitation, 1.B) | #3 | M4 Groupes | ✅ fait |

**M-0 + M-1 + M-2 = le cœur** (accès membre + cohérence du compte global) — **livré**.

**M-5 ✅** (2026-07-18) — `ChurchInvitation` (contexte `iam`) : le pendant *église-niveau* de
l'invitation de groupe (G-1b), qui fait entrer en `invited` **sans forcer une cellule**. Lien
réutilisable/expirable (TTL 30j)/révocable ; le **code EST l'autorisation** au join. `CreateChurchInvitation`
+ `RevokeChurchInvitation` (autorité **`ENROLL_MEMBER` église-entière** : un rôle scopé n'invite pas
au nom de l'église — testé), `JoinChurchByCode` (compte authentifié → appartenance `invited`,
réutilise le compte global M-2, **tolérant** si déjà membre). Table `church_invitations` (migration
`c2d8e9f1a3b5`, **à appliquer quand Docker/Postgres est up**). Routes backoffice
`POST /api/backoffice/iam/tenants/{tid}/church-invitations` + `.../church-invitations/{id}/revoke` ;
mobile `POST /api/mobile/iam/join-church`. 8 tests.

**Notes d'implémentation (M-0/M-1/M-2, livré) :**
- `accounts.pin_hash` (nullable) — migration `b7c9d1e2f3a4` ; `AuthCredentials.pin_hash`.
- Login mobile → slot `pin_hash` (`verify_credentials(..., use_pin=True)`). Backoffice garde `password_hash`.
- Le « code secret » mobile **est** le PIN : `ChangePassword` (mobile) écrit `pin_hash` via `set_pin`.
- `EnrollMember` / `EnrollInvitedMember` / `BulkEnrollMembers` : aucun credential à l'enrôlement,
  et **réutilisent** un compte global existant (`add_membership`) au lieu de rejeter — sauf s'il
  est **déjà membre actif** de ce tenant (`DuplicateActiveMembershipError`).
- Auto-inscription : `POST /api/mobile/auth/register` (OTP `mobile_registration`) puis
  `POST /api/mobile/auth/verify-registration` (pose le PIN, réclame ou crée `self_service`, connecte).
  Numéro déjà pourvu d'un PIN → `409 AUTH_PHONE_ALREADY_REGISTERED`.

**Notes d'implémentation (M-3, livré) :**
- `/api/mobile/iam/me/memberships` et `/me/tenants/{id}/membership` renvoient désormais deux
  champs de plus : `is_owner` (bool) et `permissions` (liste de verbes **résolus** dans le tenant).
- Résolution `resolved_permissions(membership, is_owner)` (domaine, `iam/domain/services.py`) :
  owner → **toutes** les permissions (1ᵉʳ étage, cohérent avec `AccessControl`) ; sinon union des
  `permissions_for(role)` des rôles actifs. Appartenance close/absente → aucune permission.
- La **portée** reste portée par `active_roles[]` (le `group_id` d'un responsable) — `permissions`
  dit *quels* verbes, pas *sur quel périmètre*. `is_owner` résolu par tenant via `OwnershipChecker`.

**Notes d'implémentation (M-4, livré) :**
- Login mobile **device-aware** (mirroir du backoffice P2, brique `trusted_devices` réutilisée) :
  `POST /login` `{phone_number, secret_code, device_id}` → appareil connu = `200` + jetons ;
  appareil inconnu = `202 {status:"otp_required"}` + OTP SMS `NEW_DEVICE` (pas de jetons).
  `POST /verify-device` `{phone_number, otp, device_id}` → l'appareil devient de confiance + jetons.
- `device_id` est désormais **requis** sur `/login` et `/verify-registration`.
- `verify-registration` **fait confiance à l'appareil d'inscription** (l'OTP a déjà prouvé le
  numéro) → pas de nouvel OTP au premier login. `Login` renvoie un `MobileAuthOutcome(tokens?, otp_required)`.

---

## 10. Décisions encore **ouvertes** (à trancher avant les chantiers concernés)

- **G** — autorise-t-on une **« demande de rattachement »** (le membre demande, le staff approuve),
  en plus du lien/enrôlement ?
- **A/B** — **fusion de comptes** : quand ? par qui (staff église vs Dorea) ?
- **PIN provisoire** : le membre choisit son PIN à l'activation (hypothèse retenue) — confirmé.

---

**Fin M-Member.** Toute évolution ici doit précéder le développement des chantiers M-0 → M-5.
