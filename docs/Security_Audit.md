# Rapport d'audit de sécurité — Dorea (back-dorea)

**Cible :** backend monolithe FastAPI (Python 3.13, SQLAlchemy 2.0 async / PostgreSQL), surfaces `/api/mobile` (Flutter), `/api/backoffice` (PWA), `/api/backoffice/platform` (jeton de service), `/api` public.
**Date :** 2026-07-19
**Nature :** audit statique exhaustif (revue de code fichier par fichier), simulation de scénarios d'attaque, revue des dépendances et de la configuration.
**Verdict global :** architecture **saine sur le fond** (autorisation à deux étages cohérente, requêtes SQL paramétrées, cryptographie correcte). Les risques réels sont concentrés dans **la configuration/les secrets par défaut**, **l'absence de garde-fous au démarrage et sur les uploads**, et un **cluster de race conditions**. **1 vulnérabilité Critique, 4 Hautes, 14 Moyennes, 9 Faibles, 5 Informationnelles.**

---

## 1. Résumé exécutif (pour décideurs)

Le code de Dorea est **bien construit** : l'isolation entre églises, la vérification des droits, la protection contre les injections de base de données et le hachage des mots de passe sont solides et cohérents. Il n'y a **aucune injection SQL, aucune désérialisation dangereuse, aucun vol de fichier par chemin (path traversal), aucune fuite de secret sur le disque**.

Les problèmes trouvés sont surtout des **filets de sécurité manquants pour la mise en production** :

- **Le plus grave** — l'application démarre avec des **secrets « par défaut » connus** (le secret qui signe les jetons de connexion, et le jeton qui protège les actes d'administration de la plateforme). Si un déploiement oublie de les remplacer, **n'importe qui peut se faire passer pour n'importe quel utilisateur**, ou **créer/suspendre des églises**. Rien n'empêche aujourd'hui l'application de démarrer dans cet état. **Correctif rapide et à fort impact.**
- **Politique CORS trop ouverte** et **absence d'en-têtes de sécurité HTTP** — durcissement web standard à ajouter avant la mise en ligne.
- **Uploads sans limite de taille** (sermons, images) — un seul utilisateur peut saturer la mémoire du serveur et faire tomber **toutes** les églises.
- **Pas de blocage après plusieurs mauvais essais** de code PIN, et **codes OTP écrits en clair dans les journaux** si un canal d'envoi n'est pas configuré.
- Trois **fils d'actualité en lecture** (annonces, événements) laissent voir le contenu **d'une autre église** — un correctif d'une ligne, déjà appliqué ailleurs dans le code.
- Des **situations de concurrence** (deux clics simultanés) peuvent créer des doublons (double appartenance, double réservation de rendez-vous) faute de contrainte d'unicité en base.

**Aucun de ces points n'est un défaut de conception** : ce sont des durcissements ciblés. La priorité n°1 (secrets obligatoires + refus de démarrage en configuration faible) neutralise à elle seule le risque le plus élevé.

---

## 2. Périmètre et méthodologie

**Périmètre :** l'intégralité de `app/` (14 contextes bornés), `migrations/`, `scripts/`, `pyproject.toml`, `uv.lock`, `docker-compose.yml`, `.env` / `.env.example`, `alembic.ini`.

**Méthode :**
1. Cartographie de la stack, de l'architecture et des points d'entrée (routeurs, gardes, composition root).
2. Analyse statique fichier par fichier, par **cinq axes parallèles** : (a) authentification/sessions/crypto ; (b) contrôle d'accès/autorisation ; (c) injection & couche de données ; (d) parsing d'entrées non fiables & I/O externe ; (e) configuration/secrets/en-têtes/dépendances.
3. Simulation de scénarios : injection (SQL/XSS/SSTI/command), broken access control (IDOR, inter-tenant), exposition de secrets, SSRF, désérialisation, race conditions, path traversal, XXE, DoS.
4. Vérification des versions de dépendances (CVE connues, intégrité du lock).
5. **Recoupement manuel** des findings critiques par relecture directe du code.

**Référentiels :** OWASP Top 10 (2021), CWE Top 25. Chaque finding cite `fichier:ligne`.

---

## 3. Tableau récapitulatif (criticité décroissante)

| ID | Criticité | Vulnérabilité | CWE | OWASP |
|----|-----------|---------------|-----|-------|
| DOREA-001 | 🔴 **Critique** | Secrets par défaut faibles (JWT + jeton Plateforme), aucun refus au démarrage | 798, 1188, 347 | A07/A05 |
| DOREA-002 | 🟠 Haute | CORS `*` avec `allow_credentials=True` | 942 | A05 |
| DOREA-003 | 🟠 Haute | Corps de requête non borné → DoS mémoire (upload sermon + média) | 400 | A05 |
| DOREA-004 | 🟠 Haute | Aucune limitation d'essais sur le login PIN/mot de passe | 307 | A07 |
| DOREA-005 | 🟠 Haute | Codes OTP journalisés en clair sans garde d'environnement | 532 | A09 |
| DOREA-006 | 🟡 Moyenne | Aucun en-tête de sécurité HTTP (HSTS/CSP/nosniff/X-Frame) | 693, 16 | A05 |
| DOREA-007 | 🟡 Moyenne | Comparaison non constante du jeton de service | 208 | A02 |
| DOREA-008 | 🟡 Moyenne | Race : double appartenance active (pas de contrainte unique) | 362 | A04 |
| DOREA-009 | 🟡 Moyenne | Race : doublon de « culte du jour » | 362 | A04 |
| DOREA-010 | 🟡 Moyenne | Race : créneau de RDV double-réservé | 362 | A04 |
| DOREA-011 | 🟡 Moyenne | Bombe zip PPTX / épuisement PDF au parsing | 409, 400 | A05 |
| DOREA-012 | 🟡 Moyenne | Lecture inter-tenant du fil d'annonces | 863, 639 | A01 |
| DOREA-013 | 🟡 Moyenne | Lecture inter-tenant du fil d'événements | 863 | A01 |
| DOREA-014 | 🟡 Moyenne | IDOR : tout événement lisible par son id | 639 | A01 |
| DOREA-015 | 🟡 Moyenne | Énumération d'utilisateurs + oracle temporel (login) | 204, 208 | A07 |
| DOREA-016 | 🟡 Moyenne | Jetons refresh/session sans révocation ; logout inefficace | 613, 384 | A07 |
| DOREA-017 | 🟡 Moyenne | Chaîne d'appro : `uv.lock` désync ; pypdf/python-pptx/lxml non verrouillés | 1104 | A06 |
| DOREA-018 | 🟡 Moyenne | STARTTLS SMTP sans vérification de certificat (OTP e-mail MITM) | 295 | A02 |
| DOREA-019 | 🟡 Moyenne | XSS stocké latent si SVG un jour autorisé (média même origine) | 79 | A03 |
| DOREA-020 | 🔵 Faible | Cookie de session backoffice non `Secure` par défaut | 614 | A05 |
| DOREA-021 | 🔵 Faible | Plages `>=` ouvertes (plancher `pyjwt` exposé à CVE-2024-53861) | 1104 | A06 |
| DOREA-022 | 🔵 Faible | Aucun plafond d'émission d'OTP → flooding SMS/e-mail | 770 | A04 |
| DOREA-023 | 🔵 Faible | Désenregistrement d'appareil sans contrôle de propriété | 639 | A01 |
| DOREA-024 | 🔵 Faible | `kind` non recoupé aux magic bytes du fichier | 345 | A04 |
| DOREA-025 | 🔵 Faible | JSON du modèle IA : type confusion → 500 non géré | 20 | A05 |
| DOREA-026 | 🔵 Faible | Aucune borne de longueur sur le texte envoyé au modèle | 400 | A05 |
| DOREA-027 | 🔵 Faible | PII (téléphone/e-mail) journalisée à l'envoi d'OTP | 532 | A09 |
| DOREA-028 | 🔵 Faible | Identifiants BDD de dev committés (`dorea:dorea`) | 798 | A05 |
| DOREA-029 | ⚪ Info | Injection de prompt dans le digest IA (relayée par validation humaine) | 74 | A03 |
| DOREA-030 | ⚪ Info | `DEBUG=true` dans le gabarit `.env` | 1188 | A05 |
| DOREA-031 | ⚪ Info | Oracle d'appartenance via la demande de transfert | 863 | A01 |
| DOREA-032 | ⚪ Info | Métadonnées de sermon en query string (journaux) | 532 | A09 |
| DOREA-033 | ⚪ Info | JWT sans claims `iss`/`aud` | — | A07 |

---

## 3bis. Statut de remédiation (2026-07-19)

Premier lot correctif appliqué (505 tests verts, ruff propre) :

| ID | Statut | Correctif livré |
|----|--------|-----------------|
| DOREA-001 | ✅ **Corrigé** | Validateur `Settings._enforce_prod_hardening` : refus de démarrage en `staging`/`production` si `jwt_secret`/`backoffice_service_token`/`cors_origins`/`cookie_secure` restent faibles (vérifié : prod+défauts échoue, prod durci démarre, local inchangé). |
| DOREA-002 | ✅ **Corrigé** | `allow_credentials` désactivé quand `cors_origins` contient `*` ; joker refusé en prod par le validateur. |
| DOREA-006 | ✅ **Corrigé** | Middleware d'en-têtes : `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `COOP: same-origin`, `HSTS` hors local. |
| DOREA-003 | ✅ **Corrigé** | `read_body_capped` (rejet sur `Content-Length` + lecture streaming plafonnée) sur les uploads sermon (`sermon_max_bytes`) et média (`media_max_bytes`). |
| DOREA-005 | ✅ **Corrigé** | `build_otp_sender` **refuse** le repli-journal hors `local` (plus d'OTP en clair en prod). |
| DOREA-007 | ✅ **Corrigé** | `require_platform_token` compare le jeton avec `secrets.compare_digest`. |
| DOREA-012 | ✅ **Corrigé** | `ListMyAnnouncements` exige l'appartenance active au tenant (`NotAChurchMemberError`). |
| DOREA-013 | ✅ **Corrigé** | `ListVisibleEvents` exige l'appartenance au tenant demandé. |
| DOREA-014 | ✅ **Corrigé** | `GetEvent` filtre par portée (plateforme ouverte ; église → membre ; dénomination → membre d'une église sœur). |
| DOREA-004 | ✅ **Corrigé** | Verrou anti-brute-force : `LoginThrottle` + agrégat `LoginAttempt` (seuil 5, backoff doublant, `secrets`-safe), table `login_attempts` (migration `a1b2c3d4e5f6`), câblé sur le login mobile ET backoffice. Vérifié : 6ᵉ essai bloqué même avec le bon PIN, succès purge le compteur. |
| DOREA-015 | ✅ **Corrigé** | `verify_credentials` : suspension révélée **après** un secret correct + **hash leurre** pour un identifiant inconnu (équité temporelle) → plus d'oracle d'énumération. |

| DOREA-008 | ✅ **Corrigé (2026-08-03)** | Index unique partiel `uq_one_active_membership_per_account_tenant` — `UNIQUE (account_id, tenant_id) WHERE closed_at IS NULL`. Les appartenances **closes** restent en nombre (revenir dans une église quittée est un parcours normal). |
| DOREA-009 | ✅ **Corrigé (2026-08-03)** | Index unique partiel `uq_one_church_wide_gathering_per_slot` — `UNIQUE (tenant_id, type, scheduled_at) WHERE group_id IS NULL`. Le culte du jour est créé en *get-or-create* par le compagnon (S-4) ; deux « oui » simultanés scindaient l'assemblée en deux cultes. Les rencontres de **groupe** ne sont pas concernées. |
| DOREA-010 | ✅ **Corrigé (2026-08-03)** | Index unique partiel `uq_one_confirmed_appointment_per_slot` — `UNIQUE (with_pastor, scheduled_at) WHERE status='confirmed'`. Plusieurs personnes peuvent **demander** le même créneau ; seule la **confirmation** est exclusive (sinon le premier demandeur préempterait). Un créneau honoré se libère. |
| DOREA-016 | ✅ **Corrigé (2026-08-04)** | **Révocation par appareil.** Le JWT porte désormais l'appareil (claim `did`) ; `trusted_devices` gagne `revoked_at` (index d'unicité rendu partiel). Access, refresh et session **meurent ensemble** puisqu'ils désignent le même appareil. `logout` backoffice **révoque** au lieu d'effacer un cookie ; **`POST /api/mobile/auth/logout` créé** (il n'existait pas) avec `everywhere=true` pour « me déconnecter partout » ; le **refresh** vérifie l'appareil (il vivait 30 jours) ; les deux portes d'entrée vérifient à chaque requête. Un jeton **sans `did`** (émis avant le correctif) est refusé — non révocable. |

| DOREA-018 | ✅ **Corrigé (2026-08-04)** | `smtp.starttls(context=ssl.create_default_context())`. Sans contexte, STARTTLS chiffrait **sans authentifier** : ni chaîne de certificats, ni nom d'hôte — un intermédiaire pouvait se placer entre nous et le relais et **lire les codes OTP**. |
| DOREA-011 | ✅ **Corrigé (2026-08-04)** | Le plafond d'upload (15 Mo) bornait ce qui **entre**, pas ce que le fichier **coûte**. **PPTX** : `_guard_zip_bomb` décompresse réellement par tranches (on ne se fie pas à la taille déclarée, elle ment quand on l'attaque) et refuse au-delà de 200 Mio ou d'un taux d'expansion de 200. **PDF** : plafond de 2 000 pages + arrêt net du dépouillement au plafond de texte. Nouvelle erreur `SER_FILE_TOO_COMPLEX` (413). |
| DOREA-026 | ✅ **Corrigé (2026-08-04)** | Borne de 400 000 caractères sur le texte extrait — c'est ce qui part vers le modèle. |
| DOREA-027 | ✅ **Corrigé (2026-08-04)** | L'adresse e-mail et le numéro de téléphone ne sont plus journalisés à l'envoi d'OTP (`otp_email_sent` / `otp_sms_sent` ne portent que le `purpose`, qui suffit à diagnostiquer un acheminement). |

| DOREA-019 | ✅ **Corrigé (2026-08-04)** | **CSP sur le chemin média** : `default-src 'none'; sandbox`. Les médias sont servis en **même origine** ; un SVG ouvert directement dans un onglet s'exécuterait dans l'origine de l'application. Le générateur de carte missionnaire (M9-1) **échappe** son texte — rien n'est exploitable aujourd'hui — mais des SVG **existent** dans le dossier média, et la sûreté ne doit pas reposer sur le fait que chaque futur écrivain pense à échapper. `sandbox` place la réponse dans une origine unique ; un `<img src>` n'est pas affecté (c'est la CSP de la page qui s'applique), seule la **navigation directe** — le vecteur — est neutralisée. Tests : la CSP est présente sur le chemin média, **absente de l'API** (une CSP `none` sur l'API casserait Swagger), et le rendu de carte échappe bien `<script>`. |
| DOREA-017 | 🟡 **Partiellement traité (2026-08-04)** | **La dérive est désormais visible, pas réparée.** `pypdf`, `python-pptx` et `lxml` sont **absents de `uv.lock`** (ajoutés au `pyproject` puis installés via `pip`). Régénérer le lock exige **`uv`, absent de ce poste** → `uv lock` reste à faire. En attendant, `tests/test_supply_chain.py` **échoue de façon annoncée** (`xfail`) tant que le lock diverge : la dérive proteste au premier `pytest` au lieu de dormir jusqu'au déploiement. Le jour où le lock est régénéré, le test passe au vert et le `xfail` doit être retiré. |
| DOREA-021 | ✅ **Corrigé (2026-08-04)** | Test : **aucune dépendance sans plancher de version** (`>=`/`==`/`~=`). Une dépendance sans minimum accepte n'importe quel passé, CVE comprises. |

| DOREA-020 | ✅ **Déjà couvert — finding périmé** | `Settings._enforce_prod_hardening` **refuse le démarrage** hors `local` si `BACKOFFICE_COOKIE_SECURE` est faux. Le défaut `False` ne sert qu'au HTTP de développement. Rien à corriger. |
| DOREA-022 | ✅ **Corrigé (2026-08-04)** | **Plafond d'émission d'OTP** : 5 codes par contact et par heure, appliqué dans `OtpService.issue` — le **point de passage obligé** de toutes les portes (login, nouvel appareil, inscription, renvoi d'onboarding). Aucune table nouvelle : le compte se lit sur les défis eux-mêmes (`count_issued_since`), puisque émettre laisse déjà une trace datée. Fenêtre **glissante**, plafond **par contact** (le voisin n'est pas puni). Nouvelle erreur `AUTH_OTP_TOO_MANY_REQUESTS` (429), distincte de `OtpTooManyAttemptsError` qui borne les *essais* sur un code reçu. |
| DOREA-023 | ✅ **Corrigé (2026-08-04)** | `remove_by_token` **exige le compte** : le `WHERE` porte `token AND account_id`. `actor` était reçu par la route et **jamais utilisé** — connaître un jeton suffisait à faire taire les notifications d'autrui. Or un jeton n'est pas un secret : il transite, il se journalise, il s'échange avec le fournisseur push. |
| DOREA-024 | ✅ **Corrigé (2026-08-04)** | **Le type annoncé est recoupé aux octets réels.** Le `Content-Type` est *déclaré par le client* : il dit ce qu'il veut. `_looks_like` vérifie la signature du format (PNG `\x89PNG`, JPEG `\xff\xd8\xff`, GIF87a/89a, RIFF…WEBP, `ftyp` en position 4 pour MP4) et refuse un fichier qui ment — sinon un contenu arbitraire se rangeait sous une extension d'image, puis se faisait servir comme telle. Les formats non listés ne reçoivent pas d'avis (pas de faux refus). |
| DOREA-025 | ✅ **Corrigé (2026-08-04)** | **La sortie d'un modèle est une entrée non fiable.** `json_object` promet du JSON, pas une forme. `_parse_reference` (mission) et `_from_json` (sermon) ne lèvent plus : forme inattendue → `None` / digest vide, jamais 500. Et le digesteur Mistral **retombe sur le digesteur déterministe** quand la sortie est inexploitable — le modèle est un accélérateur, jamais une dépendance. **21 tests** sur les formes tordues qu'un modèle produit réellement. |

> **Les trois courses (008/009/010) sont fermées par la base, pas par un `if`.** Une garde
> applicative lit « c'est libre » avant d'écrire : sous concurrence, deux requêtes lisent toutes
> deux « libre ». Un index unique partiel rend la seconde écriture **impossible**, et le handler
> `IntegrityError → 409` (DOREA-003bis) la traduit en réponse propre. Prouvé par 10 tests qui
> écrivent **directement en base**, sans passer par l'application — avec, pour chacune, son
> **jumeau légitime** (une contrainte qui interdit trop est une régression, pas une correction).

Findings Moyens/Faibles restants (dépendances, TLS SMTP, bombe zip, headers média…) : non traités dans ce lot, priorisés au §6.

---

## 4. Détail des vulnérabilités

### DOREA-001 — 🔴 Critique — Secrets par défaut faibles, aucun refus au démarrage
**CWE-798 / CWE-1188 / CWE-347**

**Localisation :** [config.py:38-41, 45-48, 57-59](app/core/config.py#L38-L59) ; signature JWT [jwt_service.py:69](app/contexts/auth/infrastructure/jwt_service.py#L69) ; garde Plateforme [tenant/interface/dependencies.py:33](app/contexts/tenant/interface/dependencies.py#L33).

**Preuve :**
```python
backoffice_service_token: str = Field(default="change-me-service-token", ...)   # :38
jwt_secret: str = Field(default="change-me-in-env", ...)                        # :57
database_url: PostgresDsn = Field(default="postgresql+asyncpg://dorea:dorea@localhost:5432/dorea")
```
Aucune validation dans `create_app()`/`lifespan` ([main.py](app/main.py)) ne refuse ces valeurs par défaut quand `environment ∈ {staging, production}`. Le même secret HS256 signe **tous** les jetons mobiles (accès/refresh) **et** le cookie de session backoffice.

**Scénario :** un déploiement omet `JWT_SECRET`. Le défaut étant public (dans le dépôt), l'attaquant forge `jwt.encode({"sub": <UUID cible>, "type": "access", ...}, "change-me-in-env", algorithm="HS256")` → **usurpation totale de n'importe quel membre ou utilisateur backoffice**. De même, `X-Service-Token: change-me-service-token` déverrouille **provisionnement/suspension de tenant, transfert de propriété, annonces Dorea, retrait d'événement, dispatch notifications**.

**Impact :** contournement complet de l'authentification et de l'autorisation Plateforme.

**Correctif :** rendre les secrets obligatoires (sans défaut) et **échouer au démarrage** en prod.
```python
from pydantic import model_validator
_INSECURE = {"change-me-in-env", "change-me-service-token", ""}

@model_validator(mode="after")
def _reject_weak_secrets(self):
    if self.environment in ("staging", "production"):
        if self.jwt_secret in _INSECURE or len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET doit être un secret fort et propre à l'environnement.")
        if self.backoffice_service_token in _INSECURE:
            raise ValueError("BACKOFFICE_SERVICE_TOKEN doit être défini en prod.")
    return self
```

---

### DOREA-002 — 🟠 Haute — CORS `*` avec `allow_credentials=True`
**CWE-942 · A05**

**Localisation :** [main.py:47-53](app/main.py#L47-L53), défaut [config.py:135](app/core/config.py#L135).

**Preuve :**
```python
app.add_middleware(CORSMiddleware,
    allow_origins=settings.cors_origins,  # défaut ["*"]
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
```
Avec `["*"]` **et** `allow_credentials=True`, Starlette **reflète** l'`Origin` de l'appelant et renvoie `Access-Control-Allow-Credentials: true`.

**Scénario :** un site malveillant émet des requêtes créditées vers `/api/backoffice/*` et lit les réponses authentifiées. *Atténuation réelle :* le cookie backoffice est `SameSite=Lax`, ce qui bloque l'envoi du cookie sur la plupart des requêtes cross-site (d'où **Haute** et non Critique) — mais la config reste un piège de production et tomberait si le schéma passait au Bearer.

**Correctif :** ne jamais combiner joker et credentials ; liste blanche explicite en prod, validée au démarrage.
```python
if settings.environment in ("staging","production") and "*" in settings.cors_origins:
    raise ValueError("CORS_ORIGINS doit être une liste blanche explicite en prod.")
```

---

### DOREA-003 — 🟠 Haute — Corps de requête non borné → DoS mémoire
**CWE-400 · A05**

**Localisation :** upload sermon [sermon/interface/mobile_router.py:74](app/contexts/sermon/interface/mobile_router.py#L74) (`data = await request.body()`) ; upload média [media/interface/router.py:24-33](app/contexts/media/interface/router.py#L24-L33) (validation de taille **après** bufferisation complète). Aucun middleware global de limite (`main.py` n'installe que le CORS).

**Scénario :** un acteur authentifié (membre, pour le média ; pasteur/admin, pour le sermon) envoie un corps de plusieurs Go → la mémoire du process explose → **indisponibilité de toutes les églises** (monolithe partagé). Le cap média de 5 Mo est inopérant car mesuré après `len(body)`.

**Correctif :** rejeter sur `Content-Length` puis lire en streaming avec plafond, idéalement via un middleware ASGI global.
```python
MAX = 20 * 1024 * 1024
if int(request.headers.get("content-length") or 0) > MAX:
    raise SermonFileTooLargeError(...)
data, total = b"", 0
async for chunk in request.stream():
    total += len(chunk)
    if total > MAX: raise SermonFileTooLargeError(...)
    data += chunk
```

---

### DOREA-004 — 🟠 Haute — Aucune limitation d'essais sur le login PIN/mot de passe
**CWE-307 · A07**

**Localisation :** [login.py:37-38](app/contexts/auth/application/commands/login.py#L37-L38) → `verify_credentials(...)` sans compteur/verrou ; PIN de **4 à 6 chiffres** ([secret_code.py](app/contexts/auth/domain/secret_code.py)). Même absence côté backoffice (`backoffice_authenticate.py`).

**Scénario :** connaissant le numéro d'une victime, l'attaquant brute-force le PIN (≤10⁴ requêtes, sans délai ni verrou). La vérif du PIN précède la branche appareil/OTP ([login.py:38](app/contexts/auth/application/commands/login.py#L38) avant `:40`), donc l'OTP « appareil inconnu » ne protège pas la **découverte** du PIN (oracle : succès `otp_required` vs erreur d'auth). L'OTP appareil-inconnu empêche la prise de contrôle directe, mais le PIN est divulgué (→ risque combiné SIM-swap/OTP).

**Correctif :** compteur d'échecs par compte **et** par IP avec backoff/verrou temporaire (429) ; imposer un PIN ≥ 6 chiffres.

---

### DOREA-005 — 🟠 Haute — Codes OTP journalisés en clair sans garde d'environnement
**CWE-532 · A09**

**Localisation :** [otp.py:34-39](app/contexts/auth/infrastructure/otp.py#L34-L39) (`LoggingOtpSender` logge `code=code`) ; sélection [otp_delivery.py:108-132](app/contexts/auth/infrastructure/otp_delivery.py#L108-L132) — le repli se fait **par canal** selon la présence de `smtp_host`/`sms_provider_url`, **pas** selon `environment`.

**Scénario :** une prod configure l'e-mail mais oublie le SMS (défauts `None`) → **chaque OTP SMS** (inscription, nouvel appareil, changement de PIN/téléphone) est écrit en clair dans stdout. Quiconque a accès aux journaux complète les défis OTP.

**Correctif :** refuser le repli journal hors `local`.
```python
def build_otp_sender(settings):
    if not settings.otp_email_enabled and not settings.otp_sms_enabled:
        if settings.environment != "local":
            raise RuntimeError("Aucun canal OTP réel configuré hors local.")
        return LoggingOtpSender()
    ...
```

---

### DOREA-006 — 🟡 Moyenne — Aucun en-tête de sécurité HTTP
**CWE-693 / CWE-16 · A05**

**Localisation :** [main.py:32-70](app/main.py#L32-L70) — seul le CORS est enregistré. Aucun `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options`/`frame-ancestors`, `Referrer-Policy`. Le média local est servi **même origine** via `StaticFiles` ([main.py:62](app/main.py#L62)).

**Impact :** clickjacking du backoffice, MIME-sniffing des images uploadées (sans `nosniff`).

**Correctif :** middleware ajoutant `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, HSTS (derrière TLS) ; servir le média depuis une origine distincte avec `Content-Disposition: attachment`.

---

### DOREA-007 — 🟡 Moyenne — Comparaison non constante du jeton de service
**CWE-208 · A02**

**Localisation :** [tenant/interface/dependencies.py:33](app/contexts/tenant/interface/dependencies.py#L33) — `x_service_token != settings.backoffice_service_token`. `str.__ne__` court-circuite au premier octet → fuite temporelle octet par octet du jeton qui garde tous les actes Plateforme.

**Correctif :**
```python
import secrets
if x_service_token is None or not secrets.compare_digest(
    x_service_token, settings.backoffice_service_token
):
    raise PlatformAuthRequiredError(...)
```

---

### DOREA-008 / 009 / 010 — 🟡 Moyenne — Races (TOCTOU) « vérifier-puis-insérer » sans contrainte unique
**CWE-362 · A04**

Le patron correct existe déjà dans le code : index partiel unique du propriétaire ([8e436e0a5089_tenant_ownership_table.py:35](migrations/versions/8e436e0a5089_tenant_ownership_table.py#L35), `postgresql_where`). À répliquer :

- **008 — double appartenance active** (le plus prioritaire : impacte autorisation et décomptes). Check [enroll_member.py:97](app/contexts/iam/application/commands/enroll_member.py#L97) ; modèle sans unique [iam/.../models.py:37-52](app/contexts/iam/infrastructure/persistence/models.py#L37-L52). Deux « rejoindre l'église » simultanés → deux appartenances actives.
- **009 — doublon de culte du jour.** [sermon/infrastructure/culte_attendance.py:67-99](app/contexts/sermon/infrastructure/culte_attendance.py#L67-L99). Deux « j'ai vécu le culte » simultanés → deux cultes église-entière le même dimanche (fausse la trajectoire M7).
- **010 — créneau de RDV double-réservé.** [book_slot.py](app/contexts/appointments/application/commands/book_slot.py) — le docstring promet « anti double booking » mais le garde est un read-then-write non atomique.

**Correctif (exemple 008) :** index partiel unique + capture d'`IntegrityError` traduite en erreur métier.
```python
Index("uq_membership_active_account_tenant", "tenant_id", "account_id",
      unique=True, postgresql_where=text("status != 'closed'"))
```
(migration Alembic équivalente). Idem : `gatherings` `(tenant_id, type, scheduled_at) WHERE group_id IS NULL` ; appointments `(with_pastor_account_id, scheduled_at) WHERE status = 'confirmed'`. *Race liens mission — Faible, même racine.*

---

### DOREA-011 — 🟡 Moyenne — Bombe zip PPTX / épuisement PDF
**CWE-409 / CWE-400 · A05**

**Localisation :** [extractor.py:26-45](app/contexts/sermon/infrastructure/extractor.py#L26-L45). OOXML = zip : un `.pptx` minuscule dont le XML gonfle à plusieurs Go épuise la RAM à `Presentation(BytesIO(data))` — **indépendant** du cap de corps (DOREA-003). Un PDF pathologique (streams Flate énormes, objets imbriqués) fait exploser `extract_text()` en CPU/mémoire, sur la coroutine de requête.

**Correctif :** contrôler le ratio d'inflation (somme des `ZipInfo.file_size`) avant parsing ; plafonner `len(reader.pages)` ; exécuter l'extraction dans un worker borné (`asyncio.to_thread`) avec timeout.

---

### DOREA-012 / 013 / 014 — 🟡 Moyenne — Lectures inter-tenant (fils & IDOR)
**CWE-863 / CWE-639 · A01**

Trois endpoints **de lecture** omettent le garde d'appartenance que tous les chemins d'**écriture** voisins appliquent. **Recoupé manuellement pour 012.**

- **012 — fil d'annonces.** [list_my_announcements.py:42-83](app/contexts/announcements/application/queries/list_my_announcements.py#L42-L83) : prend `tenant_id` du chemin, **aucun `MembershipRepository`, aucun `ensure_*`**. `Announcement.reaches` ([aggregates.py:171-178](app/contexts/announcements/domain/aggregates.py#L171-L178)) renvoie `True` pour toute portée CHURCH/PLATFORM quel que soit le `covering`. Un utilisateur passe le `tenant_id` d'une **autre** église → lit toutes ses annonces église-entière (décès, sujets de prière…).
- **013 — fil d'événements.** [view_events.py:90-110](app/contexts/events/application/queries/view_events.py#L90-L110) (`ListVisibleEvents`) ajoute **toutes portées** du tenant sans vérifier l'appartenance.
- **014 — IDOR événement.** [view_events.py:113-132](app/contexts/events/application/queries/view_events.py#L113-L132) (`GetEvent`) charge par id, **aucun contrôle de visibilité** → tout événement CHURCH lisible en devinant/énumérant l'id. (Les écritures `ReactToEvent`/`ConfirmParticipation` **sont** gardées — [engage_event.py:52,86](app/contexts/events/application/commands/engage_event.py#L52).)

**Correctif (patron déjà utilisé ailleurs) :**
```python
if await self._memberships.get_active(actor_account_id, tenant_id) is None:
    raise NotAChurchMemberError(...)
```
Pour `GetEvent` : exiger l'appartenance quand `event.scope is CHURCH` (DENOMINATION → tenant pair ; PLATFORM → ouvert).

---

### DOREA-015 — 🟡 Moyenne — Énumération d'utilisateurs + oracle temporel
**CWE-204 / CWE-208 · A07**

**Localisation :** [credential_check.py:27-33](app/contexts/auth/application/credential_check.py#L27-L33). `AccountInactiveError` (code distinct) est levé **avant** la vérif du mot de passe → tout secret sur un compte suspendu renvoie `AUTH_ACCOUNT_INACTIVE`, un compte inexistant `AUTH_INVALID_CREDENTIALS`. De plus, un compte existant subit un `verify` argon2 lent tandis qu'un inexistant répond immédiatement (pas de hash leurre) → oracle temporel.

**Correctif :** renvoyer l'erreur générique aussi pour les comptes inactifs (ou ne révéler l'inactivité qu'**après** un mot de passe correct) ; exécuter un `verify` argon2 contre un hash leurre fixe quand `cred is None`.

---

### DOREA-016 — 🟡 Moyenne — Jetons refresh/session sans révocation ; logout inefficace
**CWE-613 / CWE-384 · A07**

**Localisation :** [jwt_service.py:40-57](app/contexts/auth/infrastructure/jwt_service.py#L40-L57), [refresh_token.py](app/contexts/auth/application/commands/refresh_token.py) ; TTL refresh = 30 j ([config.py:62](app/core/config.py#L62)). Pas de `jti`, pas de dépôt/denylist. `RefreshToken.execute` émet une nouvelle paire sans invalider l'ancien refresh. Le `/logout` backoffice ([backoffice_router.py:98-99](app/contexts/auth/interface/backoffice_router.py#L98-L99)) ne fait que supprimer le cookie ; le JWT de session capturé reste valide jusqu'à expiration.

**Correctif :** persister une **famille**/`jti` de refresh avec denylist de réutilisation (invalider l'ancien `jti` à chaque refresh, révoquer la famille sur réutilisation) ; liste de révocation de session (ou TTL court + enregistrement serveur) pour rendre le logout effectif.

---

### DOREA-017 — 🟡 Moyenne — Chaîne d'appro : `uv.lock` désync ; pypdf/python-pptx/lxml non verrouillés
**CWE-1104 · A06**

**Localisation :** [pyproject.toml:18-19](pyproject.toml#L18-L19) déclare `pypdf>=6.0.0`, `python-pptx>=1.0.0` ; `uv.lock` ne contient **ni** pypdf, **ni** python-pptx, **ni** lxml (installés via pip hors résolveur, sans version verrouillée ni hash `sha256`). **lxml** est le parseur XML des `.pptx` — surface XXE (aujourd'hui neutralisée par `python-pptx`, cf. §5 « Vérifié sain », mais garantie liée à la version verrouillée).

**Correctif :** `uv add pypdf python-pptx && uv lock` ; committer le lock hashé ; imposer `uv sync --frozen`/`--locked` en CI/déploiement ; plancher sûr sur lxml.

---

### DOREA-018 — 🟡 Moyenne — STARTTLS SMTP sans vérification de certificat
**CWE-295 · A02**

**Localisation :** [otp_delivery.py:65-67](app/contexts/auth/infrastructure/otp_delivery.py#L65-L67) — `smtp.starttls()` sans `context` : contexte stdlib par défaut avec `check_hostname=False`, `verify_mode=CERT_NONE`. Le certificat serveur n'est pas vérifié → OTP e-mail interceptables (MITM réseau).

**Correctif :**
```python
import ssl
smtp.starttls(context=ssl.create_default_context())
```

---

### DOREA-019 — 🟡 Moyenne — XSS stocké latent si SVG un jour autorisé
**CWE-79 · A03**

**Localisation :** [media_store.py:15-23](app/contexts/media/infrastructure/media_store.py#L15-L23) garde `image/svg+xml` dans `EXTENSION_OF` ; média servi même origine ([main.py:59-64](app/main.py#L59-L64)). **Actuellement sain** car `media_allowed_types` exclut le SVG ([config.py:96](app/core/config.py#L96)). Ajouter `image/svg+xml` à la liste autoriserait un SVG contenant `<script>` servi depuis l'origine de l'app → XSS stocké.

**Correctif :** ne jamais autoriser l'upload SVG ; servir le média depuis une origine distincte, `Content-Disposition: attachment`, CSP restrictive.

---

### DOREA-020 → 028 — 🔵 Faible

- **020 — Cookie non `Secure` par défaut** (CWE-614) : [config.py:65](app/core/config.py#L65) `backoffice_cookie_secure=False`. Forcer `True` hors `local` (validator).
- **021 — Plages `>=` ouvertes** (CWE-1104) : [pyproject.toml:7-29](pyproject.toml#L7-L29). Plancher `pyjwt>=2.10.0` exposé à **CVE-2024-53861** (corrigé en 2.10.1 ; résolu actuel 2.13.0 = OK). Borner (`>=2.10.1,<3`).
- **022 — Pas de plafond d'émission d'OTP** (CWE-770) : [otp_service.py:42-65](app/contexts/auth/application/otp_service.py#L42-L65). Endpoints non authentifiés (`/register`, login, changement de téléphone vers un numéro fourni) → flooding SMS facturé. Limiter par (purpose, target) et par IP.
- **023 — Désenregistrement d'appareil sans propriété** (CWE-639) : [notifications/interface/mobile_router.py:40-45](app/contexts/notifications/interface/mobile_router.py#L40-L45) ignore `actor.account_id` → un utilisateur connaissant un jeton push désenregistre l'appareil d'autrui (déni de push). Passer `actor_account_id` et ne supprimer que si l'appareil lui appartient.
- **024 — `kind` non recoupé aux magic bytes** (CWE-345) : [mobile_router.py:68](app/contexts/sermon/interface/mobile_router.py#L68) → mauvais parseur si mismatch. Sniffer `%PDF-` / `PK\x03\x04`.
- **025 — JSON du modèle IA non défensif** (CWE-20) : [verse_resolver.py:69-73](app/contexts/mission/infrastructure/verse_resolver.py#L69-L73), [digester.py:65,94-113](app/contexts/sermon/infrastructure/digester.py#L65-L113). `int("abc")`/`data["book"]`/liste attendue → 500 non géré sur réponse adverse. Envelopper de `try/except (ValueError, TypeError, KeyError, JSONDecodeError)`.
- **026 — Pas de borne de longueur** (CWE-400) : [mission schemas](app/contexts/mission/interface/schemas.py), [sermon schemas](app/contexts/sermon/interface/schemas.py). `Field(max_length=...)` sur `query`/`content` (coût/latence, surface d'injection).
- **027 — PII journalisée à l'envoi d'OTP** (CWE-532) : [otp_delivery.py:57,91](app/contexts/auth/infrastructure/otp_delivery.py#L57). Masquer/hasher `target`.
- **028 — Identifiants BDD de dev committés** (CWE-798) : `docker-compose.yml`, `.env`, défaut [config.py:46](app/core/config.py#L46) (`dorea:dorea`). Rendre `DATABASE_URL` obligatoire hors local.

### DOREA-029 → 033 — ⚪ Informationnelles

- **029 — Injection de prompt dans le digest IA** (CWE-74) : le texte du sermon influence `summary/capsules/questions` (rendu en texte brut, sans sink HTML), mais **relayé par la validation humaine** (approve → publish). Signaler dans l'UI que le brouillon IA n'est pas vérifié.
- **030 — `DEBUG=true` dans `.env`/`.env.example`** (CWE-1188) : n'active pas `app.debug` FastAPI (pas de fuite de trace client) mais journaux verbeux si copié en prod. Défaut à `false`.
- **031 — Oracle d'appartenance via transfert** (CWE-863, faible) : [transfer_member.py:96-100](app/contexts/iam/application/commands/transfer_member.py#L96-L100) — un admin destination distingue « membre actif d'une église » via l'erreur. Booléen seul, privilège admin requis.
- **032 — Métadonnées de sermon en query string** (CWE-532) : [mobile_router.py:64-73](app/contexts/sermon/interface/mobile_router.py#L64-L73) — `title`/`reference` en query → journaux proxy. Préférer en-têtes/corps.
- **033 — JWT sans `iss`/`aud`** : durcirait contre la réutilisation inter-service si le secret venait à être partagé.

---

## 5. Ce qui a été vérifié SAIN (couverture)

Cette section atteste que les zones à risque ont bien été analysées et jugées correctes :

- **JWT** — algorithmes épinglés `algorithms=[self._algorithm]` (pas d'`alg=none`/confusion), `exp` + `type` vérifiés, `verify_signature` jamais désactivé ([jwt_service.py:73-78](app/contexts/auth/infrastructure/jwt_service.py#L73-L78)). Charge = `sub`+`type` seuls (rôles hors jeton → autorisation dynamique).
- **Hachage** — **argon2id** pour PIN/mot de passe ; OTP stockés hashés ; `verify` constant-time, pas de comparaison `==`.
- **Aléa** — **CSPRNG `secrets`** partout (OTP `secrets.randbelow`, codes de séance/invitation/mission `secrets.choice`/`token_urlsafe`). Aucun `random` non sûr.
- **OTP** — usage unique, lié à `device_id`+`account_id`, **verrou anti-brute-force** `MAX_ATTEMPTS=5`.
- **Cookie de session** — `HttpOnly`, `SameSite=Lax`, `path` scopé, jeton frais à chaque auth (**pas de fixation**).
- **Injection SQL** — **0** : ORM à paramètres liés partout ; les 2 sites `text()` utilisent des paramètres liés + colonnes constantes. LIKE sur `path` **sûr** (chemin d'UUID, aucun métacaractère `%`/`_`).
- **Désérialisation** — **0** : aucun `pickle`/`yaml.load`/`eval`/`exec`/`marshal` ; JSON via type `JSON` SQLAlchemy, reconstruction défensive (`str(...)`, `UUID(str(...))`).
- **Path traversal** — **0** : clés média = UUID serveur ; extension via whitelist par content-type ; aucun nom client sur le disque.
- **SSRF** — **0** utilisateur : toutes les URLs sortantes viennent de la config, pas de la requête ; **TLS httpx actif** (jamais `verify=False`).
- **XXE** — **neutralisé** : `python-pptx` parse avec `resolve_entities=False` (billion-laughs inerte, entités externes non substituées, `no_network=True`).
- **Garantie biblique (LSG)** — **appliquée** : l'IA ne rend qu'une **référence** ; le texte vient de la source canonique ; un champ texte émis par le modèle est ignoré ; référence hors dataset → erreur. L'injection de prompt ne peut pas fabriquer d'Écriture.
- **SVG des cartes** — **échappé** (`_escape` sur `&<>"`), pas de SSTI (aucun Jinja/`Template`/`render`).
- **Secrets** — **aucune clé Mistral sur disque** (la clé collée en chat n'a jamais été écrite) ; `.env` gitignoré ; `alembic.ini` = placeholder.
- **Autorisation** — deux étages (propriété + RBAC borné par portée) **cohérents** ; défense inter-tenant via `load_group_in_tenant` ; `account_id` toujours issu du jeton (jamais de l'URL/corps → pas de spoofing/mass-assignment) ; contextes **sermon, rendez-vous (sujets confidentiels), groupes, présence, IAM, tenant** et **garde Plateforme** vérifiés solides ; `author_account_id`/`tenant_id` jamais fixés depuis le corps.
- **Pas de fuite d'erreur** — handlers renvoient `{error:{code,message,details}}` stable ; app construite sans `debug=True` → pas de trace/SQL/chemin au client (CWE-209 absent).
- **`dev_bootstrap`** — refuse tout `environment ≠ local`.

---

## 6. Recommandations générales

**Priorité immédiate (avant toute mise en production) :**
1. **DOREA-001** — secrets obligatoires + refus de démarrage en config faible. *Un validator, ~15 lignes, neutralise le risque n°1.*
2. **DOREA-002 / 006** — liste blanche CORS + middleware d'en-têtes de sécurité.
3. **DOREA-003 / 011** — limite de taille de corps (middleware ASGI) + garde d'inflation/timeout au parsing de fichiers.
4. **DOREA-004 / 005** — verrou anti-brute-force sur le login ; refus du repli OTP-journal hors local.
5. **DOREA-012/013/014** — ajouter le garde d'appartenance sur les trois fils de lecture (patron déjà présent).

**Hygiène de code :**
- Généraliser le patron **index partiel unique** pour tous les invariants « un seul actif » (appartenance, culte, créneau confirmé) et traduire `IntegrityError` en erreur métier.
- Uniformiser le durcissement des I/O externes (timeouts déjà présents ; ajouter contextes TLS explicites, bornes de taille, `to_thread` pour le parsing lourd).
- Normaliser les erreurs d'auth (générique) et ajouter des hash leurres pour l'équité temporelle.

**CI/CD & chaîne d'appro :**
- **Verrou hashé** : `uv add` pour pypdf/python-pptx/lxml, puis `uv sync --frozen` imposé en CI/déploiement.
- **Scan de dépendances** (ex. `pip-audit`/`uv`-audit) en CI, échec sur CVE ≥ Haute ; borner les plages `>=x,<y`.
- **Détection de secrets** (gitleaks) en pré-commit et CI.
- **SAST** (bandit/semgrep) + tests d'autorisation inter-tenant automatisés (un test « membre A ne lit pas les données de l'église B » par endpoint de lecture).
- Journalisation : politique de masquage PII/OTP, revue des niveaux (`DEBUG` interdit en prod).

**Gouvernance des secrets Plateforme :** le jeton de service unique/statique (`M2/S3` en TODO du code) devrait à terme devenir un mécanisme rotatif/expirable (OIDC service-to-service ou jetons signés courts).

---

## 7. Annexes

**A. Répartition des findings :** 1 Critique · 4 Hautes · 14 Moyennes · 9 Faibles · 5 Info = **33**.

**B. Méthode de recoupement :** les items Critiques/Hauts de configuration ont été relus directement ([config.py](app/core/config.py), [main.py](app/main.py), [jwt_service.py](app/contexts/auth/infrastructure/jwt_service.py), [login.py](app/contexts/auth/application/commands/login.py), garde Plateforme) ; la fuite inter-tenant DOREA-012 a été confirmée par lecture de [list_my_announcements.py](app/contexts/announcements/application/queries/list_my_announcements.py). Les garanties « saines » XXE et LSG ont été vérifiées contre le code réel des bibliothèques/commandes.

**C. Limites :** audit **statique**. Non couverts : tests dynamiques (DAST) sur instance déployée, revue de l'infrastructure d'hébergement/TLS/WAF, fuzzing des parseurs de fichiers, revue du client mobile Flutter. La correction de DOREA-004 (limitation d'essais) suppose un magasin partagé (Redis/BDD) — choix d'architecture à valider.

---

*Fin du rapport d'audit de sécurité Dorea.*
