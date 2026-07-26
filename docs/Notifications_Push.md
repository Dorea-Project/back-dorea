# Notifications push — le socle transverse (source de vérité)

> Établi par cas d'usage (2026-07-18). Contexte `notifications` (service partagé). **Transverse** :
> Event / Annonces / RDV s'en servent pour prévenir des personnes. Patron **OtpSender** : câblage +
> repli sûr, s'active avec des identifiants ; **une push ne casse jamais l'action qui la déclenche**.

---

## 1. Le socle

- **`Device`** — l'appareil d'une personne (jeton push FCM/APNs, plateforme ios/android/web).
  Ré-enregistrer le même jeton le **rafraîchit** (rattache au compte courant, pas de doublon).
  Routes mobile : `POST /api/mobile/notifications/devices` (enregistrer),
  `POST /…/devices/remove` (oublier), `GET /…/devices` (mes appareils).
- **`PushSender`** (port) — l'acheminement réel : `HttpPushSender` (POST vers FCM / passerelle, via
  `httpx` + Bearer) ou **`LoggingPushSender`** (repli dev). `build_push_sender(settings)` : le réel
  si `push_provider_url` est posé, sinon le log (le dev tourne sans fournisseur).
- **`Notifier`** (port) + **`PushNotifier`** (impl) — ce que les **autres contextes** appellent :
  `notify(account_ids, PushNotification(title, body, data))`. Il résout les **jetons** des comptes
  visés (`DeviceRepository.tokens_for_accounts`) et les envoie un à un. **Best-effort** : un échec
  (jeton périmé, fournisseur down) est journalisé, **jamais propagé**.

## 2. Comment un contexte s'en sert (le point d'entrée)

`notifications.interface.dependencies.build_notifier(session)` renvoie l'adaptateur `Notifier`
(sender réel ou repli). Un contexte l'injecte en **dépendance optionnelle** (défaut `None` → aucune
push, aucune casse pour les tests existants) et appelle `notify(...)` après son acte.

## 2b. Le fan-out asynchrone (outbox) — envoi différé

Certains envois ne peuvent pas se faire dans le chemin de la requête : soit **plus tard** (rappel de
RDV avant l'heure), soit vers une **audience trop large** (plateforme, sous-arbre de groupe). D'où un
**outbox** :

- **`ScheduledNotification`** (agrégat) — un envoi **planifié** : cible **déjà résolue**
  (`account_ids`) + `scheduled_for` + statut `pending`/`sent`. Table `scheduled_notifications`
  (migration `c2930415c6d7`, index `(status, scheduled_for)`).
- **`NotificationScheduler`** (port) + **`OutboxScheduler`** (impl) — ce qu'un contexte appelle pour
  **planifier** : `schedule(account_ids, notification, *, at)`. Enqueue un job `pending`.
  Point d'entrée : `build_scheduler(session)` (même patron que `build_notifier`, dépendance
  optionnelle → `None` = aucun rappel, aucune casse pour les tests existants).
- **`DispatchDueNotifications`** (`run`) — le **dispatcher** : liste les jobs dus
  (`pending` et `scheduled_for <= now`), les envoie via le `Notifier` (best-effort) et les marque
  `sent`. Pas de boucle en process, testable en appelant `.run()`.

**Deux déclencheurs, un seul dispatcher** :
- **Runner one-shot** (le cron de prod) — `scripts/dispatch_notifications.py` : accès DB direct, ni
  HTTP ni jeton. Il **draine** la file (helper `drain()` : passes de `run()` jusqu'à un lot non
  plein → un arriéré se vide en une invocation) puis sort. Le cron l'appelle chaque minute
  (`python -m scripts.dispatch_notifications` ; ligne cron Linux + Planificateur de tâches Windows
  documentés dans l'en-tête du script).
- **Route Plateforme** (manuel/distant) — `POST /api/backoffice/platform/notifications/dispatch`,
  gardée par `require_platform_token`. Un `run()`, pour déclencher à la demande.

Premier client : le **rappel de RDV** (voir §3).

## 3. Livré + première démonstration (RDV)

Contexte `app/contexts/notifications/`. `Device` + `RegisterDevice`/`UnregisterDevice` ; ports
`PushSender`/`Notifier` ; `PushNotifier` ; `HttpPushSender`/`LoggingPushSender` +
`build_push_sender`. Table `devices` (migration `b1829304b5c6`, **à appliquer quand Docker up**).
Config : `push_provider_url` + `push_provider_key` (+ prop `push_enabled`). Outbox :
`ScheduledNotification` + `OutboxScheduler`/`DispatchDueNotifications` + route Plateforme
`/platform/notifications/dispatch` + runner one-shot `scripts/dispatch_notifications.py` (drain).
Table `scheduled_notifications`, migration `c2930415c6d7`. **14 tests.**

**Déclencheurs câblés** (dépendance optionnelle, best-effort) :
- **RDV** — `ConfirmAppointment` / `DeclineAppointment` préviennent le **demandeur** (jamais un
  walk-in sans compte) ; `ConfirmAppointment` **planifie** en plus un **rappel** (via le
  `NotificationScheduler`) à `scheduled_at - REMINDER_LEAD` (1 h). Voir `docs/RDV_Appointments.md`.
- **Event** — `PublishEvent` **broadcast** à l'audience atteinte : église → membres de l'église
  (synchrone), dénomination → membres de la dénomination (synchrone), **plateforme → enqueue dans
  l'outbox** (`all_tenant_ids` → audience résolue, `scheduler.schedule(at=now)`, dispatché hors
  requête) ; `CancelEvent` → présents confirmés ; `TakeDownEvent` (modération) → auteur ;
  `ConfirmParticipation` → organisateur (pas soi-même). Voir `docs/Event_Model.md`.
- **Mission** — `AcceptInvitation` prévient l'**inviteur** (« … a répondu à ton invitation »,
  lien personnel seulement). La joie de la main tendue. Voir `docs/M9_Mission.md`.
- **Annonces** — `PublishAnnouncement` prévient la **personne concernée** (`concerns_account_id`,
  « une annonce vous concerne ») ; **église-entière → broadcast synchrone** ; **portée groupe →
  enqueue dans l'outbox** (`member_account_ids_in_subtree` via le chemin matérialisé →
  `scheduler.schedule(at=now)`). Voir `docs/M8_Announcements.md`.

## 4. Reporté / à venir

- **Planifier le runner en prod** : brancher le cron/Planificateur de tâches sur
  `scripts/dispatch_notifications.py` (le script + sa doc existent ; reste l'acte de déploiement).
- **Envoi réel** : activer avec un fournisseur (FCM HTTP v1 : clé de service, URL projet) — comme
  l'OtpSender s'active avec un SMTP/SMS. Regrouper les envois (batch), gérer les jetons périmés.
- Préférences de notification par personne (quels types recevoir), badges, canaux.
