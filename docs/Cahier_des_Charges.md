# Dorea — Cahier des charges (consolidé)

**Version :** 2.0 — état réellement livré
**Date :** 2026-07-18
**Nature :** backend FastAPI (monolithe DDD) — propriétaire du schéma PostgreSQL, sert deux surfaces.

> Ce document consolide en un seul lieu la vision fondatrice ([DOREA_CHURCH_Specs_V1](DOREA_CHURCH_Specs_V1.md))
> **et** le système tel qu'il a été construit, module par module (les docs `docs/*.md`).
> Il fait foi sur *ce qui existe* ; chaque module renvoie à sa spec détaillée pour le *pourquoi*.
>
> **Écart assumé avec la V1 pilote.** La V1 (§3.2) reportait en « V2 » les events, la billetterie et
> tout ce qui touche au paiement. Le produit a depuis dépassé ce cadre : **Event, compte Business
> (carte prépayée), Mission, Notifications push** sont livrés. Ce CDC décrit donc un périmètre plus
> large que le pilote initial — c'est voulu.

---

## 1. Positionnement & principes fondateurs

**Dorea permet à une communauté chrétienne de connaître réellement ses membres :** qui est actif, qui
est malade, qui a voyagé, qui ne vient plus, qui a changé d'église — pour **prendre soin**, pas pour
surveiller.

Trois principes non négociables, gravés dans le *modèle* (pas seulement l'UI) :

1. **Non-surveillance.** Pas de pointeuse, pas de QR à la porte. La présence est **du soin, pas du
   contrôle** : « comment va cette personne ? », jamais « était-elle là à l'heure ? ».
2. **L'absence n'est pas binaire.** Une absence sans cause n'est pas un signal. On la **qualifie**
   (malade / voyage / excusé / déménagé / sans nouvelles) ; **seul « sans nouvelles » appelle une
   attention fraternelle**. Tout le reste est une information. C'est ce qui évite le bruit qui tue le
   produit.
3. **Non-exposition.** Le fidèle voit ce qui l'aide à participer, **jamais** les absences des autres,
   les alertes pastorales, les notes de suivi ou les statistiques privées.

Moteur d'adoption assumé : **les annonces** (décès, naissances, conventions) — on ouvre l'app pour
**savoir**, et on marque sa présence parce qu'on est déjà là. Annonces et Présence sont co-centraux.

---

## 2. Architecture technique (verrouillée)

**Un seul backend** : ce **monolithe FastAPI**, qui **possède** le schéma PostgreSQL et le fait
évoluer par migrations Alembic. Les deux « fronts » sont des **clients** : PWA Next.js/React
(backoffice) et Flutter (mobile). Aucun autre service ; aucun broker ; aucun cache externe.

### 2.1. Pile technique

| Couche | Choix |
| :-- | :-- |
| Langage | **Python ≥ 3.13** |
| Framework HTTP | **FastAPI** (+ Uvicorn) |
| Modèles / validation | **Pydantic v2** + pydantic-settings |
| ORM | **SQLAlchemy 2.0 async** |
| Base | **PostgreSQL** via **asyncpg** (propriété du backend) |
| Migrations | **Alembic** (`migrations/`, autogenerate) ; `scripts/dev_bootstrap.py` = dépannage local |
| Auth | **PyJWT** (mobile) + session cookie (backoffice) ; hachage **argon2id** (argon2-cffi) |
| Journalisation | **structlog** |
| Tests | **pytest** + pytest-asyncio (`asyncio_mode=auto`), **fakes** en mémoire, **aiosqlite** pour l'override de session |
| Lint | **ruff** (E,F,I,N,UP,B,ASYNC,RUF ; ligne 100) |

### 2.2. Découpage — DDD par contextes bornés

Le code est organisé en **contextes bornés** sous `app/contexts/`, chacun avec ses couches
`domain / application / infrastructure / interface` :

```
auth · iam · tenant · groups · attendance · announcements · media
mission · appointments · events · billing · notifications
```

Un contexte n'appelle un autre qu'à travers un **port** (interface abstraite) + **adaptateur**, ou en
important le port d'un service transverse partagé (ex. `MediaStore`, `Notifier`). Règle de
dépendance : pas de couplage inverse (ex. `iam` ne dépend pas de `groups`).

### 2.3. Les quatre surfaces HTTP

| Surface | Préfixe | Client | Authentification |
| :-- | :-- | :-- | :-- |
| **Mobile** | `/api/mobile/*` | Flutter (le membre) | **JWT** (`CurrentActor`) |
| **Backoffice** | `/api/backoffice/*` | PWA Next.js (owner/admin) | **session cookie** (`CurrentBackofficeUser`) |
| **Publique** | `/api/*` (onboarding, cartes mission) | navigateur, sans compte | aucune (le code/lien *est* l'entrée) |
| **Plateforme** | `/api/backoffice/platform/*` | ops / cron / admin central Dorea | **jeton de service** (`require_platform_token`) |

Composition dans `app/api/router.py` ; chaque contexte expose ses routeurs
(`interface/*_router.py`) montés sous leur préfixe.

---

## 3. Modèle d'autorité, d'identité et de sécurité

### 3.1. Les trois notions IAM (M1)

| Notion | Définition | Propriétaire |
| :-- | :-- | :-- |
| **Compte** | Identité de la personne. **Globale.** Survit à tout. | La personne |
| **Appartenance** (Membership) | Lien Compte ↔ Église. Porte le **statut**. | L'église |
| **Attribution de rôle** | Permission dans une **portée** (église ou groupe). | L'église |

> Une église ne **possède** jamais un Compte : elle ne peut que **clôturer une appartenance**. C'est
> ce qui rend possible « qui a changé d'église » et l'identité globale (transfert, réutilisation).

**Chaîne de statuts :** `invité → visiteur → sympathisant → nouveau → membre confirmé` (+ `participant
externe` hors chaîne ; sortie = `appartenance clôturée`). **Bootstrap :** l'enrôlement par l'Owner
confère directement *membre confirmé* (sinon l'invariant « un rôle exige un membre confirmé » rend la
création d'église impossible). La rétrogradation **révoque les rôles dans la même transaction**.

### 3.2. Rôles & modèle de permission (RBAC borné par la propriété)

Rôles : **Owner** (tenant) · **Pasteur** (lecture seule, sauf son agenda RDV) · **Admin** · **Responsable
de groupe** (1 à 6, portée = son groupe) · **Responsable en formation** (« Timothée ») · **Accueil** ·
**Intégration**. Le *fidèle* est une capacité de base, pas un rôle.

> **Un acteur peut faire A si un rôle accorde A ET que la ressource tombe dans sa portée.**
> Le rôle donne le verbe ; la propriété donne le périmètre.

L'autorité est centralisée dans `GroupAccessPolicy` (`ensure_can` / `ensure_can_manage` /
`ensure_church_wide`) et la table `ROLE_PERMISSIONS` (`iam/permissions.py`). Une attribution de portée
groupe **porte l'ID du groupe** ; « responsable » seul ne donne aucun droit.

### 3.3. Authentification — deux profils, deux canaux

| Profil | Identifiant | Preuve |
| :-- | :-- | :-- |
| **Owner / backoffice** | **e-mail** | **OTP** (code à usage unique, lié à l'appareil) |
| **Membre / mobile** | **téléphone** | **PIN** |

Le compte porte deux credentials possibles (`pin_hash` + `password_hash`), hachés **argon2id**.
L'OTP suit le patron **OtpSender** (câblage réel activé par la config, repli sûr sinon).

### 3.4. Contraintes de sécurité permanentes

- **Aucun secret persisté sur disque** (clés de service, jetons) — variables d'environnement/config
  seulement.
- **PCI :** on ne stocke jamais un PAN complet — uniquement marque, 4 derniers chiffres, expiration,
  jeton du prestataire (cf. Billing).
- **Best-effort transverse :** une notification push ne casse **jamais** l'action qui la déclenche.

---

## 4. Les contextes livrés

Chaque module a sa spec détaillée en référence. État : **livré** sauf mention.

### 4.1. Tenant, Owner & Hiérarchie — *fondations* → [M0](M0_Tenant_Owner_Hierarchy.md)
Provisionnement d'un **tenant** (l'église, indépendante ou principale), son **Owner** unique, la
hiérarchie (`parent_id` nullable pour les annexes), la **dénomination** (`str | None`, `None` =
indépendante). Cloisonnement : une annexe ne voit jamais une autre annexe. Onboarding auto-servi de
l'aspirant Owner (surface publique).

### 4.2. IAM — *identité & rôles* → [M1](M1_IAM_Nomenclature_EN.md)
Les agrégats Compte / Appartenance / Attribution de rôle, les statuts, la cascade de rétrogradation,
les permissions. Écritures backoffice, lectures mobile (`/iam/me/...`).

### 4.3. Membre mobile — *le parcours du fidèle* → [M-Member](M-Member_Mobile_Model.md)
Le modèle du membre côté app : **deux axes** (le compte global vs l'appartenance à une église), **deux
credentials** (PIN + mot de passe), l'onboarding, le tunnel **visiteur → membre**. Chantiers M-0 à M-5
livrés.

### 4.4. Groupes — *l'arbre vivant* → [M4](M4_Groups_Model.md)
Arbre **typé et récursif** (cellule, département, association, ministère, équipe, commission), **chemin
matérialisé** (`/racine/…/self/`) pour l'autorisation par **sous-arbre** en O(1). 1 à 6 responsables
égaux. Le **type porte une politique** (poids pastoral de l'absence), pas une étiquette. Multiplication
de cellule (lignée, génération). G-0 → G-5 + G-1b (lien d'invitation) livrés.

### 4.5. Présence — *le cœur, du soin pas du pointage* → [M6](M6_Attendance_Model.md)
**Présence = conversation à deux voix**, consentie : le membre dit « je suis là » (self-check-in par
**code de séance** façon Kahoot) *ou* « je ne serai pas là, et pourquoi » (**pré-déclaration**) ; le
responsable confirme et complète. La **Rencontre** (`Gathering`) est ouverte puis close ; le **roster
attendu est dérivé** (jamais stocké) ; **l'absence est déduite** (attendu − présents − excusés). Saisie
**idempotente** (hors-ligne d'abord). Visiteurs capturés hors-roster → tunnel `invité → …`. Autorité
`RECORD_ATTENDANCE` (portée sous-arbre). Livré : M6-0 → M6-3 + conversion visiteur.

### 4.6. Intelligence pastorale — *comprendre la trajectoire* → [M7](M7_Pastoral_Intelligence.md)
Au-dessus de la présence : **rythme personnalisé** (écart au rythme habituel de *cette* personne, pas
un seuil brutal), **gravité d'absence** (`transient` / `watch` / `structural`) pour ajuster l'effectif
réel et repérer le **point de non-retour**, alerte-*nudge* de soin au responsable (jamais une
sanction), **arbre de multiplication**. Backoffice B7/B7+. Livré (la gravité est déjà plantée dans le
modèle de présence).

### 4.7. Annonces — *le fil, moteur d'adoption* → [M8](M8_Announcements.md)
Fil d'actualité où **le type pilote** la couleur, les emojis et l'intention. **Réactions emoji** (sans
commentaires — pas de fil de dispute). **Trois portées** : groupe (sous-arbre) → église → **Dorea
plateforme** (admin central). Broadcast à la publication : personne concernée + église-entière
(synchrone) ; **portée groupe → outbox** (fan-out asynchrone). Livré.

### 4.8. Mission — *la main tendue vers l'extérieur* → [M9](M9_Mission.md)
Lien d'invitation → **carte** (texte et/ou image ; un verset flou devient une carte : **l'IA Mistral**
retrouve la *référence*, la Bible **LSG 1910** donne le *texte exact*). Le **chercheur** (Seeker) +
réactions. Boucle **Inviter → Accompagner (relais humain) → Intégrer** (Seeker → membre, réutilise le
tunnel visiteur → membre). Livré (M9-0, M9-1, M9-3, M9-4).

### 4.9. Rendez-vous — *l'agenda du pasteur, gardé par la secrétaire* → [RDV](RDV_Appointments.md)
Le membre **demande** ; le gardien (`MANAGE_APPOINTMENTS` : secrétaire / admin / owner) **confirme /
décline** (avec un mot doux) **/ honore / ferme** ; le **pasteur gère aussi son agenda**. La secrétaire
**ouvre** un RDV pour un **walk-in** au bureau. **Catégories** (mariage, prière, visite…). **Plages de
disponibilité** (récurrence hebdomadaire, plusieurs pasteurs, créneaux réservables par le membre *ou* la
secrétaire, premier pasteur disponible). Sujet **confidentiel**. **Rappel** planifié via l'outbox.
Livré.

### 4.10. Event — *le happening publié* → [Event](Event_Model.md)
L'événement publié (date, lieu, géo). **Tout membre publie pour son église (gratuit)** ; rayonner
**dénomination / plateforme** est un **acte institutionnel** qui exige le **compte Business** de
l'auteur. Réactions + **participants confirmés** + **tableau de bord rayonnement** (portée, vues par
dénomination, intéressés manifestés). **Modération** (signaler → retrait par la Plateforme). Broadcast
à la publication : église/dénomination synchrone, **plateforme → outbox**. Livré.

### 4.11. Billing / compte Business — *la porte du rayonnement* → [Business](Business_Account.md)
Le **compte Business d'une personne** (l'Owner ou le membre), **activé en enregistrant une carte
prépayée Visa** (validée `brand == visa` ET prépayée ; **non facturé** pour l'instant). Ouvre les
portées élargies d'Event via le port `BusinessTierPort`. **PCI :** jamais de PAN — marque, last4,
expiration, jeton prestataire seulement. Livré.

### 4.12. Notifications push + outbox — *le socle transverse* → [Notifications](Notifications_Push.md)
`Device` (jeton FCM/APNs) + port **`Notifier`** (best-effort, patron OtpSender). **Fan-out asynchrone
(outbox)** : `ScheduledNotification` + `OutboxScheduler` (enqueue, cible déjà résolue) +
`DispatchDueNotifications` (le dispatcher). Deux déclencheurs, un dispatcher : **runner one-shot**
`scripts/dispatch_notifications.py` (cron de prod, draine la file) et **route Plateforme**
`POST /platform/notifications/dispatch`. Câblé sur : RDV (confirmé/décliné + **rappel** planifié),
Event (publication, annulation, retrait, participation), Mission (accept), Annonces (concerné +
broadcast). Livré.

### 4.13. Média — *l'upload d'images*
Contexte `media` : corps brut (sans multipart), backend **Local** (dev) ou **S3/MinIO** (prod) par
config. Port `MediaStore` réutilisé par les contextes qui portent des images (annonces, events,
cartes). Livré.

### 4.14. Transfert de membre — *entre églises* → [MT](MT_Member_Transfer.md)
Poignée de main **destination → source**, **souveraineté du tenant**, **identité globale** du compte.
MT-0 livré.

---

## 5. Données & migrations

- **PostgreSQL** est propriété exclusive de ce backend ; les modèles ORM des contextes **sont** la
  définition du schéma.
- Évolution par **Alembic** (`migrations/versions/`, autogenerate) ; chaque module livre sa/ses
  migration(s). `scripts/dev_bootstrap.py` (`create_all` + seed) reste réservé au **dev local**
  (refuse tout autre `ENVIRONMENT`).
- Environnement de dev : Postgres en **conteneur Docker** sur le port hôte **55432** (le Postgres natif
  Windows occupe 5432/5433).

---

## 6. Patterns transverses (invariants d'ingénierie)

Ces patterns se répètent volontairement — les respecter garde le code cohérent :

- **Ports & adaptateurs** — un contexte exprime son besoin en interface abstraite ; l'adaptateur
  branche l'implémentation (souvent en lisant un autre contexte sans le coupler).
- **Injection de dépendance optionnelle** — un nouveau collaborateur transverse (notifier, scheduler)
  est ajouté en `param=None` **avant** `*, clock`, pour que les appels existants (et les tests) ne
  cassent pas ; les helpers best-effort sortent tôt si la dépendance est `None`.
- **Adaptateur-avec-repli + fabrique** (patron OtpSender) — `build_X(settings)` renvoie l'adaptateur
  réel si configuré, sinon un repli sûr ; import paresseux de la lib optionnelle dans l'`__init__`.
- **Outbox / fan-out** — pour le différé (rappel) ou l'audience trop large (plateforme, sous-arbre) :
  on **résout la cible à l'enqueue**, le dispatcher se contente d'envoyer.
- **Best-effort** — les notifications n'interrompent jamais l'action métier (try/except, journalisé).
- **Idempotence terrain** — la capture de présence est rejouable (hors-ligne d'abord).

---

## 7. Qualité

- **Tests unitaires avec fakes** en mémoire (chaque fake implémente le port/dépôt abstrait) ; la
  session est surchargée en SQLite (aiosqlite), pas de `create_all` en conftest. **467 tests** au
  dernier point, **ruff clean**.
- Convention : ligne 100, tri des imports (`ruff check --fix`), pas d'unicode ambigu dans le code.

---

## 8. Reste à faire (backlog)

- **Présence/intelligence** : rythme personnalisé affiné (fenêtre glissante), seuils d'alerte réels,
  rencontre **église-entière** (culte), proximité/geofence au self-check-in.
- **Notifications** : **envoi réel FCM** (activer `HttpPushSender` avec des identifiants — zone
  sensible, aucun secret sur disque) ; programmer le **cron** de dispatch en prod ; batch, jetons
  périmés, préférences par personne.
- **Billing** : **facturation réelle** (PSP, prélèvements) — aujourd'hui « carte enregistrée =
  Business ».
- **Event** : publication backoffice (secrétaire), modération au niveau dénomination.
- **Ops** : appliquer les migrations en attente une fois Docker relancé.
- **Gouvernance réseau** (dénomination comme entité formelle) : préalable aux annonces réseau entre
  églises sœurs.

---

## 9. Risques résiduels

| # | Risque | État |
| :-- | :-- | :-- |
| **R2** | Screenshot d'un code de séance envoyé à un absent → faux négatif pastoral | **Assumé** (dissuasion sociale : traçabilité + fenêtre courte) |
| **R3** | Unicité par téléphone : un couple partageant un numéro = un seul Compte | Non résolu |
| **R4** | RGPD / suppression d'un Compte global ; rétention des présences | **Élevé — juridique, non traité** |
| **R6** | Pas d'audit trail IAM (qui a rétrogradé qui, quand) | Moyen |
| **R7** | Owner unique = point de défaillance s'il perd son accès | Moyen |
| **Sécurité** | Envoi réel FCM / PSP introduira des secrets — garder hors disque, hors PAN | À surveiller à l'activation |

---

*Fin du cahier des charges consolidé. Chaque module fait foi dans sa spec dédiée (`docs/*.md`) ; ce
document est la carte, pas le territoire.*
