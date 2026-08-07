# Front — Parcours « du Tenant au Login Owner » (wizard d'onboarding & pages)

**Statut :** spec front (base pour la première implémentation). 2026-07-23.
**Front concerné :** la **PWA backoffice (Next.js/React)** — pages **publiques** d'onboarding
(sans compte) + pages **authentifiées** (session owner). Consomme ce backend FastAPI
(`/api/onboarding/*` public, `/api/backoffice/*` backoffice). Aucun NestJS.

> Deux portes existent vers la création d'église (cf. `M0 §6`) :
> 1. **Onboarding self-service** — l'aspirant owner candidate, vérifie, Dorea valide. **← ce doc.**
> 2. **Provisionnement direct** — Dorea crée l'église depuis sa console admin (`Dorea_Platform_Admin.md`).
>
> Ce document décrit le **parcours de l'église** (porte 1) + la connexion de son Owner.

---

## 1. Le workflow complet (états)

```
   [ Aspirant Owner - PUBLIC ]                    [ Dorea ]              [ Owner - authentifié ]

   Wizard (3 écrans)                                                    
        │  POST /api/onboarding/submit
        ▼
   status = submitted ───────────────► (OTP e-mail envoyé)
        │  POST /api/onboarding/verify-email {request_id, otp}
        ▼
   status = email_verified ─────────►  écran « en attente de validation »
                                            │
                                            │  POST /api/backoffice/onboarding/{id}/approve
                                            ▼
                                       status = approved  ⇒ GENÈSE
                                       (Tenant + Owner + Membership + Ownership créés)
                                            │  (e-mail « votre église est prête » → lien /login)
                                            ▼
                                                                  Login (email + mot de passe)
                                                                       │  202 otp_required (nouvel appareil)
                                                                       ▼
                                                                  Verify device (OTP)  → 204 + cookie session
                                                                       ▼
                                                                  Dashboard backoffice

   (chemin alternatif) status = rejected ⇒ écran « demande refusée » (+ raison)
```

**Invariant clé** : rien n'est créé dans `tenants`/`accounts` avant `approved`. Tant que Dorea
n'a pas validé, la candidature est une simple ligne `onboarding_requests`.

---

## 2. Le wizard d'onboarding (public, sans compte)

Un formulaire multi-étapes qui aboutit à **UN seul** appel `POST /api/onboarding/submit`.
Les données s'accumulent côté client (état local du wizard) ; on n'envoie qu'au récapitulatif.

### Étape 1 — L'église
| Champ | Obligatoire | Type | Note |
| :-- | :-- | :-- | :-- |
| `tenant_name` | ✅ | texte | nom de l'église |
| `denomination` | — | texte | vide = indépendante |
| `estimated_member_count` | — | entier ≥ 0 | **taille déclarée** (assiette d'abonnement) |
| `operates_annexes` | — | booléen | « Votre église a-t-elle des annexes ? » (pilote le plan famille) |
| `short_description` | — | texte court | tagline de l'église |
| `contact_name` | — | texte | responsable/contact affiché |
| `contact_phone` | — | texte | contact public (≠ tél de l'Owner) |
| `contact_email` | — | e-mail | e-mail de l'église (≠ e-mail de l'Owner) |

> **Le logo n'est PAS dans le wizard public** : l'upload média (`PUT /api/backoffice/media`) exige
> une session. Le logo se pose **après login**, dans les réglages de l'église. Champ `logo_url`
> laissé vide à la candidature.

### Étape 2 — Localisation & régional
| Champ | Obligatoire | Type | Note |
| :-- | :-- | :-- | :-- |
| `country` | — | texte/code | ex. `CI`, `CM` |
| `city` · `address` | — | texte | |
| `latitude` · `longitude` | — | nombre | optionnel (géoloc) |
| `timezone` | — | IANA | défaut `Africa/Abidjan` — **pré-remplir depuis `country`** |
| `language` | — | locale | défaut `fr` |
| `currency` | — | ISO 4217 | défaut `XOF` ; **`XAF` pour l'Afrique centrale** (Cameroun, Gabon…) |

### Étape 3 — Le responsable (Owner) + récapitulatif
| Champ | Obligatoire | Type | Note |
| :-- | :-- | :-- | :-- |
| `owner_first_name` · `owner_last_name` | — | texte | |
| `owner_email` | ✅ | e-mail | **identifiant de connexion backoffice** |
| `owner_phone` | ✅ | tél | **unique** globalement |
| `owner_years_of_experience` | — | entier ≥ 0 | |
| `owner_password` | ✅ | mot de passe | **≥ 8 caractères** (règle serveur) |

Récapitulatif → bouton **« Soumettre »** → `POST /api/onboarding/submit`.

### Étape 4 — Vérification e-mail
Écran de saisie de l'**OTP** reçu par e-mail → `POST /api/onboarding/verify-email`.
*(En dev, l'OTP est dans les logs serveur, jamais renvoyé au client.)*

### Étape 5 — En attente de validation
Écran d'attente : « Votre demande est en cours de validation par Dorea. » L'owner recevra un
**e-mail** à l'approbation (avec un lien vers `/login`).

---

## 3. Les pages (routes, rôle, endpoints)

| Route (Next.js) | Rôle | Auth | Endpoints appelés |
| :-- | :-- | :-- | :-- |
| `/onboarding` | Wizard étapes 1→3 (état local) | publique | *(aucun jusqu'à l'envoi)* |
| `/onboarding` (submit) | Envoi de la candidature | publique | `POST /api/onboarding/submit` |
| `/onboarding/verify-email` | Saisie OTP e-mail | publique | `POST /api/onboarding/verify-email` |
| `/onboarding/pending` | En attente de validation | publique | *(statique ; e-mail à l'approbation)* |
| `/onboarding/rejected` | Demande refusée (+ raison) | publique | *(statique)* |
| `/login` | Connexion owner | publique | `POST /api/backoffice/auth/login` |
| `/verify-device` | OTP nouvel appareil | publique | `POST /api/backoffice/auth/verify` |
| `/dashboard` | Accueil backoffice après login | **session** | `GET /api/backoffice/auth/me` (+ « mon église », voir §6) |
| `/church/settings` | Éditer profil + **poser le logo** | **session** | `GET`/`PATCH /api/backoffice/tenants/{id}`, `PUT /api/backoffice/media` |

---

## 4. Contrat API (par appel)

### `POST /api/onboarding/submit` — publique
Corps : tous les champs des étapes 1→4 (obligatoires : `tenant_name`, `owner_email`,
`owner_phone`, `owner_password`). Réponse : `201 { request_id, status: "submitted" }`.
**À persister côté front : `request_id`** (nécessaire à l'étape OTP).

### `POST /api/onboarding/verify-email` — publique
Corps : `{ request_id, otp }`. Réponse : `200 { request_id, status: "email_verified" }`.
Erreurs : OTP faux → `4xx` domaine ; demande déjà tranchée → `409`.

### `POST /api/backoffice/auth/login` — publique
Corps : `{ email, password, device_id }`. Le front **génère et stocke un `device_id` stable**
(localStorage). Réponses :
- **`202 { status: "otp_required" }`** → appareil inconnu → aller à `/verify-device`.
- **`204`** (+ cookie de session) → appareil de confiance → aller à `/dashboard`.

### `POST /api/backoffice/auth/verify` — publique
Corps : `{ email, otp, device_id }`. Réponse : `204` + **cookie `dorea_backoffice_session`**
(HttpOnly, 12 h). Le front n'a rien à stocker — le cookie voyage tout seul.

### `GET /api/backoffice/auth/me` — session
Réponse : `200 { account_id }`. Sert à confirmer la session (garde de route `/dashboard`).

### `POST /api/backoffice/auth/logout` — session → `204` (efface le cookie).

### `GET` / `PATCH /api/backoffice/tenants/{id}` — session owner
Lecture / édition du profil (branding, contact, régional). `PATCH` n'édite **pas** `name` ni `slug`.

> **Fetch côté front** : toujours `credentials: "include"` (cookie de session cross-fetch).

---

## 5. Règles de validation (à refléter côté front)

- **Mot de passe** ≥ 8 caractères (sinon `422 AUTH_INVALID_PASSWORD`).
- **`owner_phone` unique** — doublon → `409 CONFLICT` (message générique, ne pas exposer le détail).
- **`owner_email` unique** — doublon → `409 CONFLICT`.
- **`estimated_member_count` ≥ 0**, **`owner_years_of_experience` ≥ 0**.
- **`device_id`** : identifiant stable généré par le front (UUID en localStorage), le même à
  chaque login sur cet appareil → évite de redemander l'OTP.
- **`slug`** : **auto-généré** par le serveur à la genèse (jamais saisi ; lisible ensuite).
- **`currency`** : proposer `XOF` (BCEAO) / `XAF` (BEAC) selon le pays.

---

## 6. Manques backend à combler (avant que le front soit complet)

| # | Manque | Impact front | État |
| :-- | :-- | :-- | :-- |
| **F1** | Endpoint « mes églises » | `/dashboard` doit savoir quelle église charger | ✅ **LIVRÉ (2026-08-03)** — `GET /api/backoffice/me/tenants` (session) → liste des églises dont je suis Owner **actif**, profil complet (`tenant_id`, `slug`, tous les champs). `401` sans session |
| **F2** | Suivi public de la candidature | `/onboarding/pending` doit *poller* l'approbation | ✅ **LIVRÉ (2026-08-03)** — `GET /api/onboarding/{request_id}` → `{request_id, status, submitted_at, decided_at?, rejection_reason?}`. **État seul** : aucune donnée du brouillon exposée. `404` si inconnu |
| **F3** | Renvoyer l'OTP d'onboarding | bouton « renvoyer le code » | ✅ **LIVRÉ (2026-08-03)** — `POST /api/onboarding/{request_id}/resend-otp`. Nouveau code envoyé **à l'e-mail de la demande** (jamais à une adresse fournie par l'appelant). Refusé si la demande n'attend plus de vérification → `409 ONBOARDING_INVALID_TRANSITION` ; `404` si inconnue |
| **F4** | Logo à l'onboarding impossible (upload authentifié) | logo posé **après** login (accepté, cf. §2) | — (décision assumée) |

**Détail F1 — `GET /api/backoffice/me/tenants`** (session owner)
Renvoie un tableau de `TenantDetailResponse`. Le front l'appelle **juste après login** :
tableau vide → aucune église ; 1 élément → charger le dashboard ; plusieurs → sélecteur d'église.

**Détail F2 — `GET /api/onboarding/{request_id}`** (public)
`status` ∈ `submitted` · `email_verified` · `approved` · `rejected`. Sur `approved` → rediriger
vers `/login` ; sur `rejected` → afficher `rejection_reason`. L'`request_id` (UUID non devinable)
fait office de **capacité** — à conserver côté client après la soumission.

---

## 7. Reco d'implémentation (ordre de démarrage)

1. **Le wizard `/onboarding`** (état local, 3 écrans) + `POST /submit` → écran OTP `/verify-email`.
2. **`/onboarding/pending`** — poller `GET /api/onboarding/{request_id}` (**F1/F2 livrés**).
3. **`/login` + `/verify-device`** (device_id en localStorage, cookie de session).
4. **`/dashboard`** — appeler `GET /api/backoffice/me/tenants` pour charger l'église.
5. **`/church/settings`** — édition profil + upload logo.

> **Le backend ne bloque plus rien** sur ce parcours (hors F3, confort). Tout est appelable.

**Pile suggérée** : Next.js (App Router) · fetch avec `credentials: "include"` · état du wizard en
mémoire (ou `sessionStorage` pour survivre à un refresh) · gestion d'erreurs sur la forme
`{ error: { code, message, details } }` renvoyée par le backend.

---

*Spec front — décrit le parcours candidat→owner et les pages. Les manques F1–F3 sont à ouvrir
côté backend pour un parcours complet.*
