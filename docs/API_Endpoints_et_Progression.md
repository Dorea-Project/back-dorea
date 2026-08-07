# Dorea — inventaire des endpoints et état des lieux

*Établi le 05/08/2026. Les routes sont **lues dans le schéma OpenAPI de l'application montée**,
pas recopiées des décorateurs : ce qui est ici est ce que le serveur sert réellement.*

**187 routes, 15 contextes.**

## Les trois surfaces

| Surface | Préfixe | Client | Garde |
| :-- | :-- | :-- | :-- |
| Mobile | `/api/mobile/*` | Flutter (le fidèle, le responsable) | jetons + appareil de confiance |
| Backoffice | `/api/backoffice/*` | PWA Next.js (Owner, pasteur, admin) | cookie de session |
| Publique | `/api/*` | sans authentification | le **code** est l'autorisation |
| Plateforme | `/api/backoffice/platform/*` | crons et admin central Dorea | jeton de service |

---

# 1. Inventaire par contexte

## Auth — 14 routes

**Mobile** (`/api/mobile/auth`) — `POST /register`, `POST /verify-registration`, `POST /login`,
`POST /verify-device`, `POST /refresh`, `POST /logout`.

**Mon compte** (`/api/mobile/account`) — `POST /change-phone/request|confirm`,
`POST /change-password/request|confirm`.

**Backoffice** (`/api/backoffice/auth`) — `POST /login`, `POST /verify`, `GET /me`, `POST /logout`.

> Deux profils, deux credentials : Owner en e-mail + mot de passe, membre en téléphone + PIN.
> L'OTP vérifie **l'appareil**, jamais l'identité.

## IAM — 18 routes

**Mobile** (`/api/mobile/iam`) — `POST /join-church`, `GET /me/memberships`,
`GET /me/tenants/{tid}/membership`, `PUT /me/birthday`, `GET /me/tenants/{tid}/birthdays`.

**Backoffice** (`/api/backoffice/iam`) — enrôlement (`/members`, `/invited-members`,
`/members/import`), rôles (`/revoke-role`), statuts (`/transitions`, `/close`), invitations
d'église (`/church-invitations`, `/revoke`), et les **transferts de membre** : `POST
/tenants/{tid}/transfer-requests`, `GET /tenants/{tid}/transfers`, puis `accept` / `decline` /
`cancel`.

## Tenant & onboarding — 16 routes

**Backoffice** — `GET|POST /tenants`, `GET /me/tenants`, `GET|PATCH /tenants/{tid}`,
`GET /tenants/{tid}/family`, `POST /tenants/{pid}/annexes`, `suspend` / `reactivate`,
`transfer-ownership`.

**Publique** (`/api/onboarding`) — `POST /submit`, `POST /verify-email`, `POST /{id}/resend-otp`,
`GET /{id}`. **Backoffice** — `POST /onboarding/{id}/approve|reject`.

## Groupes — 15 routes

**Mobile** (`/api/mobile/groups`) — `POST /join`, `POST /{gid}/leave`, génération et révocation
d'un lien d'invitation.

**Backoffice** — création, `PATCH`, fermeture, membres, responsables (cap 6), `POST
/{gid}/multiply` (multiplication de cellule), `GET /{gid}/report`, et
`POST /groups/{gid}/promote-to-church` (émancipation en église autonome).

## Présence — 28 routes, le plus gros contexte

**Saisie** — `POST /tenants/{tid}/groups/{gid}/gatherings`, `PUT|DELETE
/gatherings/{id}/present/{account_id}`, `POST /self-check-in` (code de séance à 6 caractères),
`POST /gatherings/{id}/close`, `GET /gatherings/{id}/roster`.

**Visiteurs** — `GET|POST /gatherings/{id}/visitors`, `DELETE .../{vid}`,
`POST .../{vid}/convert`.

**Absences déclarées** — `GET|POST /tenants/{tid}/absences`, `DELETE /absences/{id}`.

**Rythme** — `POST .../cadence`, `POST .../acknowledgements` (« pas de rencontre cette semaine »).

**Lectures pastorales (M7)** — `pulse`, `effectif`, `health`, `overview`, `trend`,
`members/{aid}/trajectory`, `care-list`.

**Backoffice** — `dashboard`, `care-list`, `trend`, `trajectory`, `multiplication-tree`,
`POST /suspensions`.

## Annonces — 15 routes

**Mobile** — `GET|POST /tenants/{tid}/announcements`, `POST /{id}/archive`,
`PUT|DELETE /{id}/reaction`, `POST|DELETE /{id}/engage`, `GET /{id}/responders`,
`POST /{id}/consent`, `GET /{id}/consolation`.

**Backoffice** — archive de l'église, publication, archivage, engagés.
**Plateforme** — `POST /platform/announcements` (annonce Dorea vers toutes les églises).

## Média — 2 routes

`PUT /api/mobile/media` et `PUT /api/backoffice/media` — corps brut, sans multipart.

## Mission — 11 routes

**Mobile** — `POST /tenants/{tid}/my-link`, `POST .../groups/{gid}/link`,
`POST /generate-card` (IA Mistral → référence, Bible LSG → texte), `GET /tenants/{tid}/my-seekers`,
`POST /seekers/{sid}/accompany|integrate|close`, `POST /links/{lid}/revoke`.

**Publique** (`/api/mission`) — `GET /link/{code}`, `POST /link/{code}/accept`,
`POST /link/{code}/react`.

## Rendez-vous — 14 routes

**Mobile** — `POST /tenants/{tid}` (demander), `POST /tenants/{tid}/book`,
`GET /tenants/{tid}/open-slots`, `GET /tenants/{tid}/mine`, `POST /{id}/cancel`.

**Backoffice** — `GET /tenants/{tid}/requests` (ma file), `GET /tenants/{tid}` (l'agenda),
`confirm`, `decline`, `complete`, `close`, `POST /tenants/{tid}/open` (walk-in), disponibilités
récurrentes.

## Événements — 14 routes

**Mobile** — publication, fil, détail, `react`, `confirm`, `withdraw`, `participants`, `view`,
`stats`, `cancel`, `report`.
**Publique** — `GET /api/events/{id}` (la carte partageable).
**Plateforme** — file des signalements et `takedown`.

## Billing — 3 routes

`POST /card`, `POST /card/remove`, `GET /status` — le compte Business d'une **personne**, activé
par carte prépayée Visa (non facturée).

## Notifications — 4 routes

`GET|POST /devices`, `POST /devices/remove`, et `POST /platform/notifications/dispatch`
(l'outbox, appelé par un cron).

## Sermon & compagnon — 10 routes

**Dépôt** — `POST /tenants/{tid}` (texte), `POST /tenants/{tid}/upload` (PDF/PPTX),
`GET /tenants/{tid}`, `GET /{sid}`, `approve`, `publish`.

**Compagnon** — `POST /{sid}/companion`, `POST /companion/{sess}/attendance`,
`POST /companion/{sess}/next`, `POST /tenants/{tid}/gratitude`.

## Veille fraternelle — 22 routes

**Le membre** — `POST /tenants/{tid}/concerns` (« je m'en occupe »),
`POST /tenants/{tid}/gestures` + `GET /gestures` (« je suis passé le voir »),
`POST|DELETE /tenants/{tid}/links[/{aid}]` (« voici par qui me rejoindre »),
`GET /tenants/{tid}/fraternal-reacts` (le react fraternel),
`POST /tenants/{tid}/stop-contacting-me`.

**Le responsable** — `GET /my-cases`, `POST /cases/{id}/see`, `GET /cases/{id}/context`,
`POST /cases/{id}/contact`, `GET /pending-contacts`, `POST /contacts/{aid}/answer`,
`POST /cases/{id}/close`, `GET /nuances`.

**Backoffice** — `GET /shadow-report`, `POST /regime`, `GET /calibration/proposals`,
`POST /calibration/proposals/{pid}`.

**Plateforme (crons)** — `POST /platform/watch/run`, `/calibrate`, `/shadow-digest`.

---

# 2. État des lieux

## Ce qui est livré et servi

| Contexte | Routes | État |
| :-- | --: | :-- |
| Auth | 14 | livré — 2 profils, OTP = appareil |
| IAM | 18 | livré — rôles, statuts, invitations, **transfert de membre** (MT-0) |
| Tenant / onboarding | 16 | livré — hiérarchie, annexes, succession |
| Groupes | 15 | livré — arbre typé, multiplication, émancipation |
| Présence + M7 | 28 | livré — 2 voix, absence déduite, 7 lectures pastorales |
| Annonces | 15 | livré — types, réactions, engagement, consolation |
| Média | 2 | livré — Local (dev) / S3-MinIO (prod) |
| Mission | 11 | livré — boucle Inviter → Accompagner → Intégrer fermée |
| Rendez-vous | 14 | livré — agenda du pasteur gardé par la secrétaire |
| Événements | 14 | livré — portées, rayonnement, modération |
| Billing | 3 | livré — compte Business par carte prépayée |
| Notifications | 4 | livré — socle push + outbox |
| Sermon | 10 | livré **sauf S-6** (audio / STT) |
| Veille | 22 | livré — voir ci-dessous |

## La veille, en détail — la journée du 05/08/2026

Sept lots, tous verts, **1180 tests** au vert sur l'ensemble du dépôt.

| Lot | Ce qu'il apporte |
| :-- | :-- |
| **G-1** | la porte du geste : `GESTURE_DONE` a enfin une source. `record_gesture()` et `gestures_count` avaient été écrits et n'avaient **aucun appelant** |
| **G-1b** | le responsable lit la visite **avant** de décrocher — en lecture seule, hors du chemin de décision |
| **G-1c** | la calibration compte « un humain a vu avant le moteur » quand une absence confirmée avait déjà été visitée |
| **G-2** | *(un bug, pas un lot)* l'absence **déclarée par le membre** neutralise enfin la veille |
| **G-3** | la relève : `LEADER_AWAY`, et on cesse d'accuser un voyageur d'être débordé |
| **G-4** | le lien par geste : on nomme celui qui est allé, jamais celui qui s'inquiète |
| **G-5** | le lien déclaré : trois noms au plus, retirables sans motif ni notification |
| **G-6** | le **react fraternel** : calculé sur vos propres gestes, jamais sur le silence des autres |

### Les gardes structurels que ces lots ont posés

- `closed_cases_since` ne peut pas rendre une personne — la calibration ne peut donc jamais
  descendre à quelqu'un ;
- toute lecture de lien est bornée à **une** personne, et `linked_account_id` est **interdit** en
  paramètre : le degré entrant n'existe pas, donc ni score de popularité ni carte d'isolement ;
- le geste **informe**, il ne ferme pas : `gesture=True` et jamais `life_sign=True` ;
- le react ne rend que vos gestes et leur date — jamais une mesure du silence d'autrui.

## Ce qui n'est pas construit

| Sujet | État | Où |
| :-- | :-- | :-- |
| **Urim** (préparation de prédication) | socle + anticorruption livrés, **aucune route HTTP**, pipeline vide | `docs/Plan_Implementation_Urim_Finance.md` |
| ↳ *son lien avec `sermon`* | **pas un mur, un pont** — `urim → sermon` uniquement (D-B, étendu par S32). Ni l'un ni l'autre n'est écrit : les deux contextes sont aujourd'hui des étrangers | idem, §S32 |
| **Abonnement d'église** | note de design, non implémentée | `docs/Tenant_Subscription.md` |
| **Console admin Dorea** | note de design, non implémentée — remplacerait le jeton de service | `docs/Dorea_Platform_Admin.md` |
| **Sermon S-6** | audio / speech-to-text | `docs/Sermon_Companion.md` |
| **G-6b — le react en push** | le pull est livré ; le push demande outbox + dédup + plafond | ce document |

## Les trois dettes ouvertes, par ordre de valeur

1. **Le motif d'escalade jeté.** `ResolveSignalOwner` calcule *« cette personne n'appartient à
   aucun groupe de suivi »*, sa docstring dit que ce motif est « renvoyé pour être stocké avec le
   signal », et `owner_assignment.py:87` ne garde que l'identité. Le cas de la personne que
   personne ne connaît arrive donc sur l'écran du pasteur **indistinguable** d'un cas correctement
   adressé. Correctif : un champ sur `OpenCase`, un sur `Signal`.
2. **La mesure d'impact.** `OutcomeJudge.execute()` donne gratuitement la ligne de base d'une
   église (cas fermés, confirmés, faux positifs par origine, taux d'ignorés). Le seul nombre
   manquant est **α** — la part des faux positifs où quelqu'un était déjà passé — et il s'obtient
   avec *une question facultative à la fermeture pendant quatre semaines*.
3. **Les docs.** `Veille_Boucle_Froide.md` liste trois verdicts, il y en a quatre depuis G-1c. Et
   le chantier geste / lien / react n'a pas encore sa note de conception.

## Le harnais qui reste

Deux fichiers de scénario jouent l'histoire de Sondet et d'Awa d'un bout à l'autre :
`tests/contexts/watch/test_scenario_invisible_care.py` et `test_scenario_two_silences.py`. Les
assertions qui portent *« devra s'inverser »* sont les critères d'acceptation des lots suivants ;
celles qui portent *« basculé le 05/08/2026 »* gardent la mémoire de ce qu'elles disaient avant.
