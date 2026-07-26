# M8 — Annonces : le fil d'actualité de l'église (source de vérité)

> Établi par cas d'usage avec l'utilisateur (2026-07-17). Contexte `announcements`
> (dépend de `groups` + `iam`). L'arbre M4 est l'audience ; M6 est pointé par « convoquer ».

---

## 1. Le piège à éviter : le mégaphone

Une annonce naïve = un **tableau d'affichage** top-down qui fait du bruit. C'est, pour la
communication, l'équivalent du « pointage » pour la présence. Dorea réinvente : **une annonce n'est
pas un mégaphone — c'est le système nerveux de l'église qui porte un signal à exactement qui le
concerne, et laisse la réponse remonter.** Le rendu visé est un **fil d'actualité**.

## 2. Deux axes : le **type** pilote, l'**intention** est dérivée

C'est la décision structurante. L'utilisateur choisit **ce à quoi il pense** (un type) ; le type
porte la **couleur**, les **emojis** autorisés et une **intention par défaut** — surchargeable.

| Type (`category`) | Couleur (`tone`) | Intention par défaut | Emojis |
| :-- | :-- | :-- | :-- |
| `death` (décès) | `mourning` | **`mobilize`** (voir §5) | 🙏 🖤 😢 |
| `birth` (naissance) | `joy` | `inform` | 🎉 ❤️ 👶 |
| `wedding` (mariage) | `celebration` | `inform` | 🎉 ❤️ 👏 |
| `baptism` (baptême) | `celebration` | `inform` | 🎉 🙏 👏 |
| `service` (culte) | `solemn` | `convene` | 🙏 ❤️ |
| `meeting` (réunion) | `neutral` | `convene` | 👍 🙏 |
| `call` (appel à servir) | `call` | `mobilize` | 🙌 👏 |
| `prayer` (requête) | `solemn` | `pray` | 🙏 ❤️ |
| `testimony` (témoignage) | `joy` | `inform` | 🎉 🙏 👏 |
| `info` | `neutral` | `inform` | 👍 |

Un **mariage** informe par défaut, mais peut **convoquer** avec RSVP (surcharge). `tone` est une
**clé sémantique** : le backend ne choisit pas un hexa, le client rend l'effet.
Source : `domain/category.py` (`CATEGORY_PROFILE`).

**L'intention** (`intent`) reste la mécanique : `inform` / `convene` (+ `event_at`, `gathering_id`) /
`mobilize` (`slots_needed` **optionnel**) / `pray`.

## 3. Deux registres de retour — jamais un accusé de lecture

- **Réaction** (emoji) — légère, sur **toute** annonce (même « informer »). **Palette fixe imposée
  par le type** : pas de 🎉 sur un décès (`ensure_emoji_allowed`). **Une par personne, changeable**.
- **Engagement** — « je viens / je sers / je porte », structurant, **seulement** si l'intention le
  demande. Idempotent ; une mobilisation **plafonnée** refuse une réponse de trop et se retirer
  libère la place ; une mobilisation **sans plafond** (la veillée) ne se remplit jamais.

**Pas de commentaires** (choix figé) : zéro modération, zéro drama.

## 4. L'anti-vitrine : ce qui empêche le fil de devenir un « m'as-tu-vu »

Un fil social a une pathologie connue : le compteur devient un **score**, le fil devient une
**scène**, et la réaction gratuite devient une **décharge morale** (40 🙏 et personne à la veillée).
Trois règles structurelles l'empêchent :

**① L'auteur n'est pas le sujet.** `author_account_id` (qui publie, traçabilité) ≠
`concerns_account_id` (**de qui** ça parle : la famille en deuil, les parents). Une annonce de décès
ne concerne pas la secrétaire qui l'a tapée.

**② Le décompte des réactions est *remis*, pas *exposé*.** Il n'apparaît **nulle part** dans le fil
(`reaction_counts = None` — non divulgué). Il est remis :
- au **sujet** (`GetConsolation` → « 32 personnes vous portent ») — une **consolation privée** ;
- à l'**autorité pastorale** — pour voir la vérité (« 40 réactions, **2** à la veillée »).
**L'auteur ne récolte rien.** La boucle de vanité meurt à la racine : le crédit va à celui qui
traverse l'épreuve, pas à celui qui publie.

**③ La ligne de partage** : **l'engagement se compte** (c'est de l'*organisation* : places, veillée,
volontaires → public) ; **la réaction ne se compte pas en public** (c'est de l'*affection*).

**Visibilité des noms** (choix figé) : **l'auteur** (ou un responsable de la portée) voit **les noms
des engagés** — il en a besoin pour coordonner.

**④ L'Église parle, pas la personne (dé-identification du fil).** Le fil ne montre **pas** l'auteur
(`author_account_id = None`) : rien ne s'accumule en vitrine au nom d'une personne. La voix, sur la
carte, c'est la **portée** (Dorea / l'église / la cellule). Le sujet (`concerns_account_id`) n'est pas
exposé non plus : la carte porte seulement un booléen **`concerns_me`** (« ceci vous concerne »), que
seul le sujet voit à `true`. Le **backoffice**, lui, révèle l'auteur et le sujet (redevabilité privée
— même seuil que le décompte des réactions).

**⑤ Le clic n'absout pas (la réaction ouvre un geste).** Réagir 🙏 à un décès ne clôt rien : la carte
porte une **`invitation`** vers l'acte coûteux (`come` / `confirm` / `reach_out`, dérivée de
l'intention — `Announcement.invitation()`). Elle disparaît une fois qu'on s'est **engagé** (le geste
est fait) ou si l'intention n'attend rien (« informer »). Réaction = compassion ; engagement =
présence. Et le pasteur voit déjà l'écart (`GetConsolation` : « 40 réactions, 2 à la veillée »).

## 5. Le décès n'est pas une information qu'on like

Dans une église (Yopougon, Soba…), un décès est une **mobilisation** : la veillée, la cotisation,
l'accompagnement de la famille. **40 🙏 et personne à la veillée est un échec, pas un succès.**
D'où `death → mobilize` par défaut — et une mobilisation **sans plafond** : on ne plafonne pas une
veillée (`slots_needed = None` → elle compte, elle ne se remplit jamais).

## 6. Trois portées (dérivées, non stockées)

| Portée | `tenant_id` | `scope_group_id` | Qui publie |
| :-- | :-- | :-- | :-- |
| `platform` | **NULL** | NULL | **Dorea, admin central** (jeton de service Plateforme) → **toutes les églises** |
| `church` | église | NULL | Admin/Owner **et la `secretary`** (la voix du pasteur) |
| `group` | église | groupe | Le `group_leader`, **borné à son sous-arbre** |

- Autorité : `PUBLISH_ANNOUNCEMENT` via `GroupAccessPolicy.ensure_can` (scopée) /
  `ensure_church_wide`. Un responsable **ne peut pas** s'adresser à toute l'église (testé).
- Portée du membre : port `AudiencePort.covering_group_ids` = **ancêtres-ou-soi** de ses groupes
  actifs (chemin matérialisé). `reaches()` : plateforme/église atteignent tous ; un groupe borne à
  son sous-arbre.
- **Souveraineté** : une église **ne peut pas archiver** une annonce Dorea (testé).

## 7. Le fil d'actualité

`ListMyAnnouncements` **fusionne les trois portées** (Dorea + mon église + mes groupes), ne montre
que les annonces **vivantes**, plus récentes d'abord, **paginées au curseur** (`limit` ≤ 50,
`before` sur `published_at`, `next_before` rendu). Chaque carte porte : type, **couleur**, images,
**ma** réaction (pas le score — §4), engagement + **mon état**, places restantes,
`concerns_me`, et l'**`invitation`** vers le geste coûteux (§4). **L'auteur est tu** (l'Église parle).

## 8. Médias & archivage

- **Images** : `media_urls` = liste d'**URL** (JSON). L'**upload vit ailleurs** (choix figé) —
  le client téléverse vers un stockage externe. Un module média reste à bâtir.
- **Archivage** (choix figé : **manuel + automatique**) : `expires_at` sort l'annonce du fil **toute
  seule** ; `ArchiveAnnouncement` est le geste **manuel** (même autorité que publier dans la portée).
  `is_live(now)` = publiée **et** non expirée. L'**archive reste consultable**
  (`ListChurchAnnouncements`, backoffice) — rien n'est détruit.

## 9. Livré (M8-3)

Agrégats `Announcement`, `AnnouncementEngagement`, `AnnouncementReaction`. Commandes
`PublishAnnouncement`, `PublishPlatformAnnouncement`, `EngageAnnouncement`/`WithdrawEngagement`,
`SetReaction`/`RemoveReaction`, `ArchiveAnnouncement`. Requêtes `ListMyAnnouncements` (le fil),
**`GetConsolation`** (le décompte remis au sujet), `ListResponders`, `ListChurchAnnouncements`
(l'archive + le pilotage). Port `AudiencePort` + adaptateur groups.

**Broadcast à la publication** (best-effort, via le socle Notifications) : `PublishAnnouncement`
prévient la **personne concernée** (`concerns_account_id`) ; puis, selon la portée — **église-entière
→ envoi synchrone** (`MemberDirectoryPort.member_account_ids`), **portée groupe → enqueue dans
l'outbox** (`member_account_ids_in_subtree(tenant, group)` = le groupe + ses descendants via le chemin
matérialisé → `NotificationScheduler.schedule(at=now)`, dispatché hors requête). L'auteur ne se
notifie jamais lui-même. Voir `docs/Notifications_Push.md`.
Tables `announcements` (tenant **nullable**, category, media_urls JSON, expires_at,
**concerns_account_id**) + `announcement_responses` + `announcement_reactions`
(migrations `f8e4a5b2c9d1`, `a9f5b6c3d2e4`, `b1c7d8e9f0a2`). **33 tests.** M8-3 (fil dé-identifié + `invitation`) : **aucune migration** (champs dérivés).

Routes **mobile** `/api/mobile/announcements` : `POST|GET /tenants/{tid}/announcements`,
`PUT|DELETE /{id}/reaction`, `POST|DELETE /{id}/engage`, **`GET /{id}/consolation`**,
`GET /{id}/responders`, `POST /{id}/archive`.
Routes **backoffice** `/api/backoffice/announcements` : `POST|GET /tenants/{tid}/announcements`,
`GET /{id}/responders`, `POST /{id}/archive`.
Route **Dorea** : `POST /api/backoffice/platform/announcements` (jeton de service Plateforme).

## 10. Reporté / à trancher

- **Module média** (upload, vignettes, limites de taille).
- **Notifications push** : l'urgence du type → push vs fil ambiant.
- **Atténuation par le pulse M7** : ne pas sur-notifier les fragiles.
- **Conversion RSVP → roster M6** (le « je viens » qui pré-remplit la présence attendue).
- Annonces **réseau** entre églises sœurs (≠ plateforme) — exige une gouvernance réseau absente
  (cf. [MT_Member_Transfer](MT_Member_Transfer.md)).
