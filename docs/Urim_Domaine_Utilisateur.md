# Urim — Architecture du domaine utilisateur

> **Nature :** spec d'architecture. Répond à une question qui paraît simple et ne l'est pas :
> *où vit quoi entre Auth, Account, Profile et Settings, et qu'est-ce qui appartient à Urim ?*
>
> **La découverte de la vérification :** trois des quatre existent déjà et sont **corrects** —
> `auth` (identité), `account` (opérations sensibles), `iam/me` (profil et appartenances). Il
> manque un seul contexte : **les réglages Urim.** Et il y a un piège de placement que ce
> document existe pour éviter.
>
> Vérifié sur `main` à `4c56d54` — 199 opérations HTTP, aucune collision (analyse OpenAPI).

---

## 1. La règle de placement

> **Ce qui est vrai de la personne vit dans le noyau. Ce qui n'est vrai que d'Urim vit dans
> Urim.**

C'est la règle qui tranche chaque cas, et elle a une conséquence contre-intuitive : **la date de
naissance n'appartient pas à Dorea**, elle appartient à la personne — donc elle est déjà dans
`iam/me`, et Urim la lit sans la posséder. À l'inverse, **la version biblique par défaut
n'appartient pas à la personne** au sens du noyau : elle n'a de sens que pour préparer un sermon,
donc elle vit dans `urim`.

Le test opérationnel : *si Urim disparaissait demain, cette donnée aurait-elle encore un sens ?*
Oui → noyau. Non → Urim.

---

## 2. Les quatre domaines

```
┌──────────────────────────────────────────────────────────────────┐
│  NOYAU — partagé Dorea / Urim, ne connaît aucune application     │
│                                                                  │
│  auth        « qui est-ce ? »        téléphone, PIN, appareils   │
│  account     « opérations sensibles »  changer PIN / téléphone   │
│  iam/me      « qui suis-je ? »       profil, anniversaire,       │
│                                       appartenances, rôles       │
└──────────────────────────────────┬───────────────────────────────┘
                                   │  Actor(account_id)
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│  URIM — n'a de sens que pour préparer                            │
│                                                                  │
│  urim/settings   version par défaut, langue d'étude, capture     │
│  urim/workspace  espace personnel ou église (L1)                 │
└──────────────────────────────────────────────────────────────────┘
```

### 2.1 `auth` — l'identité *(existant, complet à trois routes près)*

`/api/mobile/auth` : `register`, `verify-registration`, `login`, `verify-device`, `refresh`,
`logout`. Il ne sait rien de l'église, ni de l'application, ni du profil. `Actor` ne porte que
`account_id`.

**Manque** (cf. [le contrat des endpoints](Urim_Auth_Endpoints.md)) : réinitialisation du PIN,
suppression de compte, gestion des appareils. **Aucune n'est propre à Urim** — ce sont des
lacunes du noyau que la distribution publique rend visibles.

### 2.2 `account` — les opérations sensibles *(existant, et bien conçu)*

`/api/mobile/account` : `change-password/{request,confirm}`, `change-phone/{request,confirm}`.

Le patron **request → confirm avec OTP** est déjà en place, et c'est exactement le bon modèle
pour les trois routes manquantes : `reset-secret-code` et `delete-account` doivent le suivre
plutôt qu'inventer une forme nouvelle.

> **Décision : les trois routes manquantes vont dans `account`, pas dans `auth`** — sauf la
> réinitialisation du PIN, qui doit rester dans `auth` parce qu'elle s'exécute **sans être
> connecté** (c'est tout son objet). `delete-account` et `devices` sont des opérations d'un
> utilisateur authentifié sur son propre compte : leur place est `account`.

### 2.3 `iam/me` — le profil *(existant, et il porte déjà l'anniversaire)*

`/api/mobile/iam/me` : `memberships`, `tenants/{id}/membership`, `birthday` (PUT),
`tenants/{id}/birthdays`. Plus `join-church`.

**`PUT /iam/me/birthday` est livré**, avec le champ de visibilité — la spec anniversaire est
implémentée. Urim n'a rien à ajouter ici : il **lit** le profil, il ne le possède pas.

**Manque, et c'est un vrai manque pour Urim :** il n'y a pas de `GET /iam/me`. Le mobile ne peut
pas récupérer prénom, statut, date de naissance en un appel. Urim en a besoin dès le premier
écran (« Continuer en tant que [prénom] »).

### 2.4 `urim/settings` — **le seul contexte à créer**

Ce qui n'a de sens que pour préparer.

---

## 3. Les réglages Urim

### 3.1 Le contenu

```json
GET /api/mobile/urim/settings
{
  "default_version": { "id": "…", "code": "LSG", "name": "Louis Segond 1910" },
  "available_versions": [
    { "id": "…", "code": "LSG", "name": "Louis Segond 1910", "available": true },
    { "id": "…", "code": "OST", "name": "Ostervald",         "available": true },
    { "id": "…", "code": "DBY", "name": "Darby",             "available": true },
    { "id": "…", "code": "S21", "name": "Segond 21",         "available": false,
      "note": "Disponible avec une église sur Dorea" }
  ],
  "capture_enabled": true,
  "default_workspace": { "id": "…", "kind": "personal" },
  "workspaces": [
    { "id": "…", "kind": "personal", "label": "Personnel" },
    { "id": "…", "kind": "church",   "label": "Église Emmanuel" }
  ]
}
```

```json
PATCH /api/mobile/urim/settings
{ "default_version_id": "…", "default_workspace_id": "…", "capture_enabled": false }
```

### 3.2 Trois décisions de conception

**Le catalogue est calculé, jamais stocké.** `available_versions` se dérive de l'espace courant :
en espace personnel, seules les versions du domaine public sont disponibles (plafond zéro, L1
§5) ; en espace église, celles que le plafond autorise. Stocker un catalogue par compte créerait
une seconde vérité qui divergerait du corpus.

**`available: false` n'est pas un bouton grisé.** La règle du cheval de Troie est explicite : *ne
jamais dégrader Urim pour pousser Dorea.* La version indisponible s'affiche avec une note
factuelle, sans mécanisme de déblocage, sans « connectez votre église pour débloquer ». Elle
informe, elle ne rançonne pas.

**Un réglage invalide ne casse rien.** Si le `default_version_id` d'un pasteur devient
indisponible (il quitte son église), le résolveur **replie silencieusement sur la LSG** — le
comportement `DEGRADE` du moteur, jamais une erreur au démarrage. La contrainte
`licence_coherente` garantit que ce repli est increvable.

### 3.3 Le schéma

```sql
CREATE TABLE urim_user_settings (
    account_id            uuid PRIMARY KEY,
    default_version_id    uuid,        -- NULL = LSG
    default_workspace_id  uuid,        -- NULL = espace personnel
    capture_enabled       boolean NOT NULL DEFAULT true,
    updated_at            timestamptz NOT NULL
);
```

Une ligne par compte, créée paresseusement au premier `PATCH`. **Aucune FK vers `versions`** —
même doctrine que le reste d'Urim : le corpus est destiné à migrer vers une base séparée, et une
FK inter-bases n'existe pas. Un identifiant devenu invalide se résout par le repli.

**`default_workspace_id` est ici et non dans `urim_workspace`**, parce que c'est une préférence
d'affichage de la personne, pas une propriété de l'espace. Le même espace église est le défaut
d'un pasteur et pas de son collègue.

---

## 4. Ce qu'Urim ne possède pas — et le piège à éviter

| Donnée | Vit dans | Pourquoi pas dans Urim |
| :-- | :-- | :-- |
| Prénom, téléphone, PIN | `auth` / `iam` | vrai de la personne, pas de l'usage |
| Date de naissance et sa visibilité | `iam/me` | **déjà livré** — Urim lit, ne duplique pas |
| Appartenances, rôles | `iam` | c'est l'église qui les confère |
| Appareils de confiance | `auth` | la sécurité est transverse |
| Langue de l'interface | `iam` (à créer) | vaut pour Dorea aussi |
| Version biblique par défaut | **`urim`** | n'a de sens que pour préparer |
| Espace de travail préféré | **`urim`** | idem |

> **Le piège : un « profil Urim » séparé.** La tentation est forte — un écran de compte dans
> l'application, donc une table de profil dans le contexte. Ce serait une seconde source de
> vérité sur la personne, qui divergerait au premier changement de prénom, et qui casserait
> l'unicité de compte que toute l'architecture de l'identité partagée protège. **Urim n'a pas de
> profil. Il a des réglages.**

---

## 5. L'écran de compte dans Urim — assemblage, pas duplication

L'écran que le pasteur ouvre est **composé** de quatre sources ; aucune donnée n'est recopiée.

```
┌────────────────────────────────┐
│  Mon compte                    │
│                                │
│  Kouassi Jean          iam/me  │
│  +225 07 00 00 00 01   iam/me  │
│                                │
│  ── Préparation ──             │
│  Version   Louis Segond 1910   │  urim/settings
│  Espace    Personnel           │  urim/settings
│                                │
│  Vos préparations personnelles │  ← la ligne du §5.3 de
│  ne sont visibles par aucune   │    l'identité partagée
│  église.                       │
│                                │
│  ── Église ──                  │
│  Église Emmanuel — Pasteur     │  iam/me/memberships
│  [ Rejoindre une église ]      │  iam/join-church
│                                │
│  ── Sécurité ──                │
│  Changer mon code              │  account
│  Mes appareils                 │  account (à créer)
│  Supprimer mon compte          │  account (à créer)
└────────────────────────────────┘
```

La ligne sur la confidentialité des préparations n'est pas décorative : sans elle, un pasteur qui
découvre le compte partagé se demande si son église voit ses préparations. **La réponse est non ;
il faut la lui dire, pas la supposer.**

---

## 6. Ce qu'il faut construire

| # | Élément | Contexte | Taille | Bloquant pour |
| :-- | :-- | :-- | :-- | :-- |
| 1 | `GET /iam/me` — profil en un appel | `iam` | trivial | le premier écran d'Urim |
| 2 | `urim_user_settings` + `GET`/`PATCH /urim/settings` | `urim` | petit | le choix de version |
| 3 | `urim_workspace` + résolution paresseuse (L1) | `urim` | petit | tout Urim autonome |
| 4 | `POST /auth/reset-secret-code` (+ confirm) | `auth` | petit | **la distribution** |
| 5 | `POST /account/delete-account` (+ confirm) | `account` | petit | les stores, la loi 2013-450 |
| 6 | `GET`/`DELETE /account/devices` | `account` | petit | la parade sécurité |
| 7 | Langue d'interface | `iam` | petit | l'internationalisation, plus tard |

**Les points 4, 5 et 6 ne sont pas des chantiers Urim.** Ce sont des lacunes du noyau que la
distribution publique rend visibles — et les traiter maintenant profite aussi à Dorea.

Aucun ne bloque une **bêta fermée par invitation** ; tous bloquent la publication.

---

## 7. Tests

1. `GET /iam/me` sans appartenance → 200, profil complet, `memberships: []`.
2. `GET /urim/settings` sur un compte neuf → LSG en défaut, catalogue limité au domaine public,
   **aucune ligne écrite en base** avant le premier `PATCH`.
3. `PATCH` d'une version indisponible dans l'espace courant → refus explicite, ou acceptation
   avec repli — **jamais** un état où la préparation échoue.
4. Un pasteur qui quitte son église et dont le défaut devient indisponible → la préparation
   suivante sert la LSG, la trace le dit, aucune erreur.
5. Aucune donnée de profil (prénom, téléphone, naissance) n'est stockée dans une table `urim_*` —
   balayage du schéma, même patron que le test des agrégats non nominatifs.
6. L'écran de compte d'Urim n'appelle **aucune** route de mutation de profil : il lit `iam/me` et
   n'écrit que dans `urim/settings`.
