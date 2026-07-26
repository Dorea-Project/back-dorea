# Event — le happening publié (source de vérité)

> Établi par cas d'usage avec l'utilisateur (2026-07-18), après la discussion de philosophie.
> Contexte `events` (dépend de `iam`). **La première chose de Dorea qui peut dépasser les murs
> d'une église.** Bâti **par cas d'usage** : E-0 (portée église, gratuit) livré ; le tier Business
> + les portées élargies suivent.

---

## 1. Ce qu'est un Event

Un **événement** = un happening *publié à l'avance* (convention, veillée, concert, séminaire,
culte spécial, sortie, formation) avec une **date + un lieu (+ géo, affiche)**, auquel les membres
**réagissent** (signal léger) et **confirment leur présence** (RSVP « je serai là »). Distinct :
- du **Gathering** (présence M6) qui *relève* la présence après coup ;
- de l'**Annonce** (M8) qui est le *fil d'actualité*.

C'est **l'invitation à un rendez-vous collectif**.

## 2. La philosophie du rayonnement

- **Ton église, gratuitement, pour tous.** N'importe quel membre publie un événement pour sa
  communauté. Le corps local est la priorité, sans péage.
- **Rayonner plus loin est un acte institutionnel.** Toucher toute sa **dénomination** (ou toute la
  plateforme) n'est plus un geste personnel — c'est l'église qui parle à un corps plus large. Ça
  demande un **compte Business** (à venir).
- **Ce n'est pas de la vitrine.** On ne paie pas pour crier plus fort chez soi (local = gratuit et
  intime) ; on cadre le **cercle élargi**, parce qu'un événement dénominationnel engage
  l'institution, pas une personne. *Local = gratuit et intime ; large = institutionnel et gardé.*

**Les portées** (`EventScope`) : `church` (gratuit) → `denomination` (Business) →
`platform` / tout Dorea (Business). En **E-0, seule `church` est publiable** ; au-delà →
`WiderReachRequiresBusinessError` (débloqué avec le tier Business).

## 3. Décisions figées (discussion de philosophie)

- **Module distinct** `events` (pas une évolution des Annonces).
- **Échelle** : église → dénomination → plateforme (trois crans).
- **Le compte Business appartient à la _personne_** (l'Owner / le membre qui publie), pas à l'église.
- **Ordre** : l'Event à portée église d'abord (gratuit), puis le tier Business + portées élargies.

## 4. Livré (E-0 — portée église, gratuit)

- **`Event`** : `author_account_id`, catégorie (`EventCategory`), titre, description, `starts_at`
  (+ `ends_at`), `place_label` + `latitude`/`longitude` (géo, comme la carte Mission), `media_urls`
  (affiche), `scope`, `status` (published/cancelled). `publish()` valide titre/géo/fin ; bloque
  au-delà de l'église (`business_active=False` en E-0). `cancel()` (l'auteur).
- **Réactions** (`EventReaction` : interested / blessed / pray) — **une par membre**, changeable
  (re-réagir change le type). **Le décompte agrégé n'est PAS exposé** sur la carte ni le détail
  (invariant anti-compteur d'engagement, correctif P3) : le fil/détail ne renvoie que `my_reaction`
  (mon propre état). La donnée reste enregistrée (`event_reactions`, `counts_by_kind`) et le
  décompte ne vit plus que dans `/stats`, réservé à l'organisateur (§4bis). Réversible ; sort
  définitif tranché après le pilote.
- **Présence confirmée** (`EventParticipant`) — RSVP « je serai là », idempotent, retirable. Le
  **compte** est visible de tous ; la **liste** est réservée à l'organisateur (l'auteur).
- **Autorité** : publier / réagir / confirmer = **membre actif** de l'église
  (`NotAChurchMemberError` 403) ; annuler / voir la liste = l'**auteur** (`NotEventAuthorError` 403).

Contexte `app/contexts/events/`. Commandes `PublishEvent` / `CancelEvent` ; `ReactToEvent` /
`ConfirmParticipation` / `WithdrawParticipation`. Requêtes `ListChurchEvents` / `GetEvent`
(nombre de présents + mes marques, **sans** décompte de réactions) / `ListParticipants` (organisateur). Tables `events` +
`event_participants` + `event_reactions` (migration `fd4e5f607182`, **à appliquer quand Docker up**).
Surface **mobile** `/api/mobile/events`. Plus le **rayonnement** (§4bis) : `EventView` +
`RecordEventView` + `GetEventStats` + port `EventAudiencePort`. **20 tests.** Sans IA.

## 4bis. Le rayonnement — le tableau de bord de l'organisateur (livré)

L'organisateur voit *jusqu'où* son événement porte, pas seulement qui vient :

- **Portée** (`reach`) — l'audience *potentielle* : pour la portée église, le nombre de **membres
  actifs** de l'église. Résolue par le port `EventAudiencePort` (adaptateur qui lit la dénomination
  du tenant + compte les appartenances actives, sans toucher l'interface `MembershipRepository`).
- **Vues par dénomination** — les **spectateurs distincts** (`EventView`, une vue par membre,
  idempotente), ventilés par dénomination. En E-0 (portée église), tous sont de la même
  dénomination — le mécanisme se généralise aux portées élargies. Tracé par `POST /{id}/view`.
- **Intéressés manifestés** — ceux qui ont posé la réaction « ça m'intéresse » (`interested`).
- **Présents confirmés** — le compte des RSVP.

`GET /{id}/stats` (organisateur seul, `GetEventStats`) → `{reach, views_total,
views_by_denomination, interested_count, confirmed_count, reaction_counts}`. Table `event_views`
(migration `fe5f60718293`).

## 4ter. Le rayonnement Business (livré) — la porte est ouverte

- **Compte Business** (contexte `billing`, `docs/Business_Account.md`) : sur **la personne**,
  activé en enregistrant une **carte prépayée Visa** (non facturé). Event le lit via le port
  **`BusinessTierPort`** (adaptateur `BillingBusinessTierAdapter`).
- **La porte** : `PublishEvent` autorise la portée **dénomination/plateforme** seulement si
  l'auteur est Business (sinon `WiderReachRequiresBusinessError`). L'église reste gratuite.
- **Le fil élargi** (`ListVisibleEvents`, désormais le fil `GET /tenants/{tid}`) fait remonter :
  **mon église** (toutes portées) + les événements **dénomination** de ma dénomination (les tenants
  partageant ma `denomination`) + les événements **plateforme** de toute la plateforme.

## 4ter. Broadcast à la publication (livré)

`PublishEvent` prévient l'audience atteinte (best-effort, via le socle Notifications) :
- **église** → membres du tenant, **dénomination** → membres des tenants de la dénomination :
  **envoi synchrone** (`Notifier`).
- **plateforme** → audience trop large pour la requête : **enqueue dans l'outbox**
  (`EventAudiencePort.all_tenant_ids()` → membres résolus → `NotificationScheduler.schedule(at=now)`),
  dispatché hors requête par le cron (voir `docs/Notifications_Push.md`). L'auteur ne se notifie
  jamais lui-même.

## 4quater. Modération — le rayonnement gouverné (livré)

Plus un événement porte loin, plus il demande un garde-fou. *Révélateur, pas juge* : le
signalement éclaire, l'humain de la Plateforme tranche.

- **Signaler** — tout **membre actif** signale un événement (`POST /events/{id}/report`, motif) ;
  un signalement par membre (`EventReport`, idempotent). Le garde-fou de la diffusion élargie.
- **File de revue** — la **Plateforme** voit les événements signalés, les plus signalés d'abord
  (`GET /api/backoffice/platform/events/reported`, `ListReportedEvents`).
- **Retrait** — la Plateforme **retire** un événement (`POST /…/platform/events/{id}/takedown`,
  motif) → statut `taken_down` (distinct de `cancelled` par l'auteur), avec `moderation_reason` +
  `taken_down_at`. Il quitte tous les fils et l'on n'y réagit plus (`EventTakenDownError`).

Gardé par le **jeton de service Plateforme** (`require_platform_token`, comme les annonces Dorea).
Migration `a071829304b5` (`event_reports` + colonnes de retrait sur `events`).

## 5. Reporté / à venir

- **Facturation réelle** (PSP, prélèvements) — aujourd'hui « carte enregistrée = Business ».
- Publication **backoffice** (la secrétaire), la géo comme pont vers un lieu, modération au niveau
  dénomination (aujourd'hui le retrait est un acte Plateforme).
