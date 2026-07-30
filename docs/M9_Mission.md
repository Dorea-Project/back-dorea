# M9 — Mission : l'écosystème missionnaire (source de vérité)

> Établi par cas d'usage avec l'utilisateur (2026-07-18). Contexte `mission`
> (dépend de `groups`, `iam`, `tenant`). **La main tendue** : Dorea se tourne vers ceux qui ne
> sont **pas encore** dans l'église.

---

## 1. Le basculement : de l'intérieur vers l'extérieur

Tout le reste (membres, groupes, présence, soin, annonces) regarde **vers l'intérieur**. M9 regarde
**vers l'extérieur** — mais avec la même âme : *le système facilite, l'humain accompagne ;
révélateur, pas juge ; l'humain garde la place essentielle.* Les 5 verbes de la vision :

- **Inviter** — chaque membre (ou groupe) partage un QR/lien personnel. ✅ **M9-0**
- **Dialoguer** — un assistant IA répond au chercheur. *(M9-2, à venir)*
- **Discerner** — l'IA situe la personne dans son parcours, **sans la cataloguer** (= notre posture
  M7 appliquée avant l'appartenance). *(à venir)*
- **Accompagner** — un membre prend le relais quand la personne le souhaite. *(M9-3, à venir)*
- **Intégrer** — cellule / culte / formation / baptême / service → **le tunnel qu'on a déjà bâti**
  (visitor→membre, chaîne de statuts, care-list). Le missionnaire *déverse* dedans.

## 2. Le lien d'invitation (M9-0)

`MissionLink` porte une **carte** et appartient à **une personne OU un groupe** (exactement un) :
- **contenu libre** = un **message** (`message`) et/ou une **image** (`media_urls`) — **au moins
  l'un**. Trois façons de remplir la carte, au choix du membre : *écrire son propre texte*,
  *uploader sa propre image* (réutilise l'upload M-média), ou *générer une carte-verset par l'IA*
  (M9-1, **par envie** — voir §6bis). Une carte **image seule** (photo ou verset) est donc valide.
- **lieu** optionnel (`place_label`) + **géolocalisation** (`latitude`/`longitude`, les deux ou
  aucune) — le pont vers un rendez-vous physique (futur Event),
- le **visage** : l'inviteur (`inviter_account_id` **xor** `inviter_group_id`) + l'église.

**Deux types, deux attributions** (choix figé) :
| Type | Propriétaire | Attribution |
| :-- | :-- | :-- |
| **Personnel** | un membre (`CreateMyLink`, idempotent : un par membre et église) | individuelle — le fruit de chacun |
| **Groupe** | un responsable (`CreateGroupLink`, autorité `ensure_can_manage`) | collective — une campagne, une équipe |

Réutilisable, expirable (TTL 90 j), révocable (`RevokeLink` : l'auteur, ou un responsable du groupe).

## 3. La carte publique — le code EST l'entrée

`GET /api/mission/link/{code}` (**public, sans compte**) → la carte : *qui invite* (nom de la
personne / du groupe, résolu via le port `InviterDirectory` → iam/groups/tenant), l'église, le
message, l'image, le lieu/géo, et `active` (False si expiré/révoqué). Rien de sensible.

**Ce qui accroche** (anti-mégaphone, comme M8) : **personnel** (un visage, pas un blast),
**sans engagement** (pas de compte), **un seul pas doux**.

## 4. La voix du chercheur — du ressenti à l'engagement

Deux registres (exactement M8 : réaction légère vs engagement) :
- **Réaction** (`POST /link/{code}/react`) : `touched` / `edified` / `amen` — **légère, ANONYME**,
  aucun contact. `MissionReaction`, comptée.
- **Accepter** (`POST /link/{code}/accept`) : le chercheur laisse un **contact** (nom requis, tél
  optionnel) → devient un **`Seeker`** attribué à l'inviteur (l'attribution suit le lien). Franchi
  par **choix**, jamais par pression. **On peut être touché sans se livrer.**

Le `Seeker` est le **frère digital du Visiteur** (M6-3 = présence physique ; Seeker = engagement
digital). Les deux sont la bouche du tunnel. Statut `accepted` (puis `accompanied`/`integrated`,
à venir — jamais un verdict définitif, posture M7).

## 5. Le fruit missionnaire — privé (anti-vitrine)

`GET /…/my-seekers` : les chercheurs que *j'ai* amenés + le **signal** des réactions légères
(touché/édifié/Amen). C'est **mon** suivi, **pas un score public** — comme la consolation M8, le
décompte est *remis* à l'inviteur, pas exposé.

## 6. Livré (M9-0)

Contexte `app/contexts/mission/`. Agrégats `MissionLink`, `Seeker`, `MissionReaction`. Commandes
`CreateMyLink`, `CreateGroupLink`, `RevokeLink`, `ReactToCard`, `AcceptInvitation`. Requêtes
`GetCard` (publique), `ListMySeekers`. Ports `InviterDirectory` (adaptateur iam/groups/tenant) +
`InvitationCodeGenerator`. Tables `mission_links` + `seekers` + `mission_reactions`
(migration `e4f0a1b2c3d7`, **à appliquer quand Docker/Postgres up**). **13 tests.** Sans IA.

Routes **publiques** `/api/mission` : `GET /link/{code}`, `POST /link/{code}/react`,
`POST /link/{code}/accept`.
Routes **mobile** `/api/mobile/mission` : `POST /tenants/{tid}/my-link`,
`POST /tenants/{tid}/groups/{gid}/link`, `GET /tenants/{tid}/my-seekers`, `POST /links/{id}/revoke`.

## 6bis. Livré (M9-1) — le générateur de carte IA (un mode optionnel)

**Une** façon de remplir la carte parmi trois (texte propre / image uploadée / verset généré) —
choisie *par envie*, jamais imposée. `generate-card` ne crée pas le lien : il rend des **assets**
(`{reference, text, image_url}`) que le membre pose ensuite dans `CreateMyLink` (ou pas).

La personne cite un verset **mal décrit** → une **carte designée** portant le **texte exact**.
Le garde-fou en quatre temps, chacun derrière un **port** (repli sûr, s'active par config) :

1. **Reconnaître** — `VerseResolver` : l'IA (`MistralVerseResolver`, Mistral — bon marché — en
   sortie JSON `{found, book, chapter, verse}` — **aucun champ texte**, tout le garde-fou) rend la
   **référence**. Repli sans clé : `KeywordVerseResolver` (recouvrement de mots).
2. **Puiser** — `ScriptureSource` : la Bible **canonique** (Louis Segond 1910, domaine public —
   `JsonFileScriptureSource` sur dataset, repli `StaticScriptureSource` extrait dev) donne le
   **texte exact**. Jamais la mémoire de l'IA → zéro hallucination sur l'Écriture.
3. **Composer** — `CardRenderer` (`SvgCardRenderer`) : carte **designée** (fond nuit + typo serif,
   verset + référence), SVG sans dépendance (choix figé : pas d'image générée par IA).
4. **Ranger** — la carte est déposée via le `MediaStore` existant → URL, prête à devenir le média
   d'un lien (`CreateMyLink` / `CreateGroupLink`).

Route **mobile** `POST /api/mobile/mission/generate-card` (membre) → `{reference, text, image_url}`.
Config : `mistral_api_key` + `mistral_model` (défaut `mistral-small-latest`), `lsg_dataset_path`.
**Non configuré → repli mots-clés + extrait embarqué** (le dev et les tests tournent sans clé).
**17 tests** (dont le garde-fou : le texte vient de l'Écriture, jamais du résolveur). **Pas de
migration** (la carte est un fichier média, pas une table). L'IA **retrouve**, elle n'**invente** pas.

## 6ter. Livré (M9-3) — Accompagner (le relais humain, sans IA)

*L'humain garde la place essentielle.* Un chercheur `accepted` → un membre **prend le relais**
(`accompanied`, on grave **qui** `accompanied_by_account_id` et **quand** `accompanied_at`), ou le
parcours **se clôt sans jugement** (`closed`, `closed_at`). Jamais un verdict (posture M7) : un
parcours **résolu** (intégré/clôturé) ne revient pas en arrière (`SeekerAlreadyResolvedError`, 409) ;
`close` est idempotent.

**Autorité** (calquée sur `RevokeLink`) : chercheur **personnel** → son inviteur ; chercheur **de
groupe** → un responsable du groupe (`ensure_can_manage`). Comportement porté par l'agrégat
`Seeker.accompany()` / `Seeker.close()`. `my-seekers` expose désormais `accompanied_by` /
`accompanied_at` (le signal « quelqu'un s'en occupe »).

Routes **mobile** : `POST /api/mobile/mission/seekers/{id}/accompany` et `.../close`. Migration
`f9a3c1d05e28` (3 colonnes sur `seekers`, **à appliquer quand Docker up**). Sans IA.

## 6quater. Livré (M9-4) — Intégrer : le chercheur devient membre (la boucle se ferme)

Le Seeker (*frère digital du Visiteur* M6-3) est **versé dans le tunnel visiteur→membre déjà bâti**.
`IntegrateSeeker` **réutilise exactement** la machinerie de `ConvertVisitor` (attendance) :
- **identité globale par téléphone** — compte créé (`AccountCreationSource.SELF_SERVICE`, sans
  credential) *ou réutilisé* si le numéro existe déjà (M-2), via le port `MemberEnrollmentStore` ;
- **appartenance `invited`** (le début du tunnel — pas de rôle, pas de credential) ;
- **inscription au roster** de la cellule (seulement pour un chercheur de **groupe**).

Différence avec le Visiteur (qui est *supprimé* à la conversion) : le Seeker **reste**, passe à
`integrated` et **garde le lien** vers le compte qu'il est devenu (`integrated_account_id` — le
germe de l'**arbre d'attribution**). Téléphone **requis** (`SeekerPhoneRequiredError`, 422).

**Autorité = acte gouverné** (comme `ConvertVisitor`, `Permission.ENROLL_MEMBER`) : chercheur de
**groupe** → autorité d'enrôlement sur la cellule (`ensure_can`) ; chercheur **personnel** →
autorité **église-entière** (`ensure_church_wide`). Un parcours résolu (intégré/clôturé) ne se
ré-intègre pas (409).

Route **mobile** `POST /api/mobile/mission/seekers/{id}/integrate` (body : `phone?`/`first_name?`/
`last_name?`) → `{account_id, tenant_id, group_id, membership_status, reused_account, seeker_status}`.
Migration `fa1b2c3d4e5f` (2 colonnes sur `seekers`, **à appliquer quand Docker up**). Sans IA.

## 7. Reporté / à venir

- **M9-2 Dialoguer** (assistant IA), l'**arbre d'attribution** (« l'arbre des personnes » — à partir
  des back-links `integrated_account_id` + attribution des liens), les notifications push.
- Décision anti-vitrine à confirmer : un signal doux au chercheur (« tu n'es pas seul à être
  touché ») vs. rien — aujourd'hui **rien** sur la carte publique.

---

## Raccordement `mission` → `Signal` (2026-07-27)

> **`SeekerStatus` ne se remplace pas, il se scinde.**

Il confondait deux choses qui ont chacune déjà un propriétaire :

| Ce qu'il exprimait | Vrai propriétaire |
|---|---|
| `accepted → integrated` — **où en est la personne** | `MembershipStatus` (IAM) |
| `accompanied → closed` — **où en est le cas** | `Signal` (watch) |

`Seeker` garde ce qu'il est **seul** à savoir : la provenance — quel lien, quel inviteur, quand
accepté, quel compte il est devenu. Un enregistrement de provenance, pas un cycle de vie.

### Aucune capacité retirée

Les quatre URL sont inchangées. L'implémentation seule a bougé.

| Route | Ce qui s'écrit maintenant |
|---|---|
| `POST /seekers/{id}/accompany` | le cas est **assigné**, et le contact commence (`IN_CONTACT`) |
| `POST /seekers/{id}/close` | `close(outcome)` — défaut `unreachable_archived` |
| `POST /seekers/{id}/integrate` | **deux effets** : IAM admet la personne, *et* `close(RESTORED)` |
| `GET /tenants/{id}/my-seekers` | une **vue des cas**, jamais une seconde liste |

Le corps de `close` est **optionnel** : sans lui, exactement le comportement d'hier. Les clients
déjà déployés ne voient rien changer.

### La porte qui manquait

`known_and_followed` — « elle vient, on la connaît par son nom, elle ne veut pas encore de
cellule ». C'est une sortie **réussie**, pas un abandon. Sans elle, le module restait un entonnoir
de conversion quelle que soit la propreté de l'architecture en dessous.

### Pas de double écriture — garanti, pas recommandé

`Seeker.accompany` / `close` / `integrate` ont été **retirés de l'agrégat**. Ce n'est pas une
suppression de capacité : le geste existe toujours, aux mêmes URL. C'est ce qui rend la double
écriture *impossible* au lieu de déconseillée — deux machines écrites « le temps de migrer »
divergent pendant la fenêtre, et une fenêtre de migration s'étire toujours.

La colonne `status` subsiste jusqu'à l'étape E ; plus rien ne l'écrit après la création.

### Un seul écrivain du statut de personne

`AdmitPerson` (IAM) est désormais le **seul** endroit qui donne une première appartenance.
`mission` ne construit plus de `Membership` et ne nomme plus de palier. La progression, elle,
reste à `TransitionStatus` — elle existait déjà, et en créer une seconde aurait été exactement le
« trois modules, trois règles » qu'on voulait éviter.

### Autorisation : à périmètre égal, pas plus large

`tests/contexts/mission/test_authority_parity.py` fige la règle. Le test central : **un pasteur
propriétaire du cas par escalade n'a aucun droit sur un chercheur personnel** — la propriété du
cas ne donne rien qu'elle ne donnait pas.
