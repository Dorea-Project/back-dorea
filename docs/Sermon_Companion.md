# Sermon & Compagnon — la Parole qui vit au-delà du dimanche (source de vérité)

> Établi par cas d'usage avec l'utilisateur (2026-07-18). Contexte `sermon`. La dernière brique :
> le sermon du pasteur, résumé par l'IA en **capsules** publiées au fil ; un **compagnon** privé
> accompagne le membre (« as-tu vécu le culte ? »), consolide (oui) ou enseigne l'essentiel (non).

---

## 1. L'idée

Le sermon ne meurt pas le dimanche midi. Le pasteur le dépose → l'IA le **résume** et en tire des
**capsules** courtes, publiées comme des annonces. Quand un membre ouvre une capsule, un **compagnon**
se lance : *« As-tu vécu le culte aujourd'hui, que je sache comment te parler ? »*

- **Oui** → on enregistre le signal, puis un **Q&R de consolidation** (approfondir ce qui a été reçu).
- **Non** → on **enseigne les points essentiels** (rattrapage) — la main tendue, tournée vers l'intérieur.

## 2. Les cinq piliers (gravés avant tout code)

Les faiblesses de l'idée, retournées en forces :

1. **Deux axes séparés.** `attendance` (le corps était-il là ?) reste intouché et sacré. Le compagnon
   mesure un axe **neuf** : la **Résonance** (la Parole a-t-elle porté ?). On peut être présent de corps
   et absent de cœur, ou absent du banc et rejoint par une capsule. Le signal déclaré ne **peut donc
   jamais** empoisonner l'alerte d'absence — et Dorea gagne une mesure qu'il n'avait pas :
   **voir le cœur refroidir avant que le corps parte.**
2. **Le pasteur approuve — l'IA ne publie jamais seule.** Cycle `brouillon → approuvé → publié`.
   L'approbation est l'**onction** : c'est elle qui donne du poids à la capsule (≠ blabla d'IA).
3. **Le « non » est le ministère, pas la punition.** C'est là que le membre reçoit **le plus de soin**
   → personne ne triche pour l'éviter. Métrique du pasteur = la **portée** (« la Parole a touché 40,
   dont 15 absents dimanche »), jamais une liste de honte.
4. **Compagnon privé, agrégat pour le pasteur.** La question est intime → confidentielle. Le privé
   produit la **vérité** (on ose dire « non »). Le pasteur voit des nombres, jamais des noms.
5. **Graines d'intelligence** (récolte à un chantier « intelligence », façon M7) : la Résonance est un
   **flux d'événements** (pas un booléen) → trajectoire ; les blocages de compréhension **s'agrègent**
   → **canal de retour** au pasteur (« beaucoup ont buté sur le pardon ») ; les capsules sont
   **planifiables** → distillation jour après jour via l'outbox [[notifications-model]].

## 3. L'IA : un seul appel, un arbre gelé, un runtime gratuit

Tout le travail IA (résumé + capsules + questions + réponses + points essentiels) est **pré-généré en
UN appel** au dépôt (patron `MistralVerseResolver` de Mission : `json_object`, repli déterministe sans
clé). Le pasteur relit, approuve → l'arbre est **gelé**. Le compagnon au runtime **déroule l'arbre**,
de façon **déterministe** : zéro appel LLM, zéro token par membre. Coût en **O(sermons)**, jamais en
O(membres × interactions) — quelques centimes/semaine/église, quel que soit le nombre de fidèles.

## 4. Le « oui » et la présence (axe physique, additif)

Le « oui, j'étais au culte » peut poser une présence **déclarée** au **culte du jour** (rencontre
église-entière *get-or-create* — ce que M6 avait reporté [[attendance-model]]), **source `declared`**,
la plus basse de la hiérarchie de confiance : elle **ajoute** une présence, elle n'**éteint jamais**
une alerte « sans nouvelles ». Un scan reste roi.

---

## 5. Plan de construction (contexte `sermon`)

| # | Chantier | Cœur | État |
| :-- | :-- | :-- | :-- |
| **S-0** | **Socle sermon (texte)** | `Sermon`, dépôt texte, cycle `brouillon → approuvé → publié`, `PUBLISH_SERMON` | ✅ fait |
| **S-1** | **Digestion IA** | `SermonDigester` Mistral (résumé + capsules + Q&R + points), un appel au dépôt, repli déterministe | ✅ fait |
| **S-2** | **Capsules au fil** | capsules publiées comme annonces (type `sermon`) à la publication | ✅ fait |
| **S-3** | **Le compagnon** | `CompanionSession`, « as-tu vécu le culte ? », branches oui/non, arbre déterministe | ✅ fait |
| **S-4** | **Présence déclarée** | le « oui » → présent au culte du jour (source `declared`, additive) | ✅ fait |
| **S-5** | **Ingestion PDF / PPTX** | extracteurs pypdf / python-pptx derrière le port | ✅ fait |
| **S-6** | Ingestion audio | transcription STT (le plus lourd) | à faire |

Le **texte d'abord** : PDF/PPTX/audio ne sont que des adaptateurs derrière **un seul port
d'extraction** (l'IA ne voit que du texte) — ajoutés sans refonte du domaine.

### État livré (S-0, 2026-07-18)

Contexte `app/contexts/sermon/`. **`Sermon`** (agrégat) : dépôt **texte** (`deposit` → **brouillon**,
titre + texte requis), cycle de vie `approve` (brouillon → approuvé, `approved_at`) / `publish`
(approuvé → publié ; publier hors approuvé → `SER_NOT_EDITABLE`). Graines plantées : `source_kind`
(text/pdf/pptx/audio — seul `text` en S-0), `preached_on` (date du culte, pour S-4), `reference`
(passage biblique). Autorité **`PUBLISH_SERMON`** (église-entière) accordée au **PASTEUR** (son 2ᵉ acte
d'écriture avec l'agenda) + **ADMIN** + Owner. Commandes `DepositSermon` / `ApproveSermon` /
`PublishSermon` ; requêtes `ListTenantSermons` / `GetSermon` (vue du gardien). Table `sermons`
(migration `d3a4b5c6e7f8`, en attente Docker). Routes **mobile** `/api/mobile/sermons` :
`POST|GET /tenants/{tid}`, `GET /{id}`, `POST /{id}/approve`, `POST /{id}/publish`. **14 tests.**

### État livré (S-1, 2026-07-19)

Objets de valeur `domain/digest.py` : **`Capsule`** (title, body), **`CompanionQuestion`** (prompt,
guidance = la réponse préparée qui emmène à comprendre), **`SermonDigest`** (summary, key_points,
capsules, questions). Port **`SermonDigester`** (`digest(text, *, title, reference) → SermonDigest`).
Adaptateurs `infrastructure/digester.py` : **`MistralSermonDigester`** (**un seul appel**
`json_object`, import paresseux du SDK, patron Mission) + **`KeywordSermonDigester`** (repli
**déterministe** sans clé : découpe le texte, questions génériques) + `build_sermon_digester(settings)`
(gate `sermon_digester_enabled` = la clé Mistral de Mission). `DepositSermon` reçoit le digesteur
(dépendance **optionnelle**) et **génère + attache** le digest au dépôt ; il est exposé dans la vue
(le pasteur le relira à l'approbation). Digest 1:1 persisté dans **`sermon_digests`** (migration
`e4b5c6d7f809`, JSON), chargé/écrit par le `SqlSermonRepository` avec le sermon. **+3 tests** (17).

### État livré (S-3, 2026-07-19)

**`CompanionSession`** (agrégat `domain/companion.py`) : la conversation **privée** d'un membre —
porte l'**état** (`attended: bool | None`, `step`, `status`), le *contenu* venant du digest du
sermon. `start` / `answer_attendance(attended)` / `advance` / `complete`, avec garde
`CompanionClosedError`. Runtime **déterministe** (aucun appel IA) : la couche application combine
session + digest pour produire une **carte** (`CompanionCardDTO` : `stage` attendance/consolidation/
teaching/closing, prompt, guidance, index/total, done). Commandes `StartCompanion` (sermon **publié**
+ membre de l'église ; **reprend** une session en cours au lieu de dupliquer), `AnswerAttendance`
(oui → questions ; non → points essentiels, la branche **ministère** ; branche vide → clôture directe),
`AdvanceCompanion` (pas suivant → mot de clôture, tendre dans les deux branches). Session **privée**
(`NotSessionOwnerError`), pas de vue pasteur (l'agrégat sera un axe **Résonance** au chantier
intelligence). Table `companion_sessions` (migration `f5c6d7e8091a`). Routes **mobile**
`POST /{sermon_id}/companion`, `POST /companion/{sid}/attendance`, `POST /companion/{sid}/next`.
**+8 tests** (25).

### État livré (S-4, 2026-07-19)

Le « oui » du compagnon pose une **présence déclarée** au culte — l'axe **physique**, distinct de la
Résonance. Nouvelle source **`AttendanceSource.DECLARED`** (M6) : la confiance la plus basse,
**additive, n'éteint jamais** une alerte « sans nouvelles ». Port **`CulteAttendancePort`**
(`mark_declared_present(tenant, member, on_date, now)`) + adaptateur `SermonCulteAttendanceAdapter`
qui **rejoint ou crée** la rencontre **église-entière** du culte (`group_id = None`, type `service`,
datée à minuit UTC du dimanche — la clé déterministe par (tenant, jour) que M6 avait reportée) et
marque le membre présent, **idempotent** (une ligne par personne/rencontre, contrainte unique M6).
Câblé dans `AnswerAttendance` en **dépendance optionnelle** : appelé **seulement sur « oui »**, jamais
sur « non ». **Aucune migration** (réutilise les tables `gatherings`/`attendance_records`). **+2 tests**
(27).

### État livré (S-2, 2026-07-19)

À la **publication** du sermon, ses **capsules entrent dans le fil**. Nouveau type d'annonce
**`AnnouncementCategory.SERMON`** (M8, profil `SOLEMN` / `INFORM` / 🙏❤️🕊️ — la Parole méditée, sans
mécanique d'engagement). Port **`CapsuleFeedPort`** (`publish_capsules(tenant, author, capsules)`) +
adaptateur `AnnouncementCapsuleFeedAdapter` qui écrit **directement** via `SqlAnnouncementRepository`
une annonce **église-entière** par capsule (auteur = le pasteur) — sans repasser par la commande
`PublishAnnouncement` (le pasteur n'a pas `PUBLISH_ANNOUNCEMENT` ; l'autorité vient de `PUBLISH_SERMON`).
Câblé dans `PublishSermon` en **dépendance optionnelle** ; publié **une seule fois** (le cycle interdit
de republier). **Aucune migration** (réutilise les tables M8). **+2 tests** (29). Le membre découvre
désormais le sermon **dans le fil** ; le compagnon reste ouvert par l'ID du sermon.

### État livré (S-5, 2026-07-19)

Le pasteur peut déposer un **fichier PDF/PPTX**, pas seulement du texte collé. Port unique
**`SermonTextExtractor`** (`extract(data, *, kind) → str`) + **`CompositeTextExtractor`** qui aiguille
par format : **texte** (décodage UTF-8), **PDF** (`pypdf`), **PPTX** (`python-pptx`) — imports
**paresseux** ; **audio** → `UnsupportedSermonFormatError` (S-6). `DepositSermon` gagne un `extractor`
optionnel et une méthode **`execute_file(data, kind, …)`** : extrait le texte puis suit **le même
chemin** que le dépôt texte (factorisé dans `_deposit`) — **l'IA ne voit que du texte**. Route mobile
`POST /api/mobile/sermons/tenants/{tid}/upload` (corps brut = le fichier, métadonnées en query :
`title`, `preached_on`, `kind`, `reference`), patron du contexte média. Nouvelles dépendances
`pypdf` + `python-pptx` (pyproject). **Aucune migration.** **+7 tests** dont un **round-trip PPTX réel**
et une extraction PDF réelle (36).

---

**Fin Sermon & Compagnon.**
