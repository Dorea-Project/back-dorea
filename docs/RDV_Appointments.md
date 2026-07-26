# Rendez-vous — l'agenda du pasteur, gardé par la secrétaire (source de vérité)

> Établi par cas d'usage avec l'utilisateur (2026-07-18). Contexte `appointments` (dépend de
> `iam` + `groups`). Premier module de la paire **Event / Appointment** — Appointment d'abord ;
> **Event** fera l'objet d'une discussion de philosophie séparée.

---

## 1. La philosophie

Le temps du pasteur est fini. Un rendez-vous est un acte d'**accueil et de soin**, pas un ticket
de file. Quatre principes, cohérents avec le reste de Dorea :

- **La secrétaire garde la porte.** Elle est *les mains du pasteur* (spec §5.6 : le pasteur est en
  lecture seule pour la gouvernance ; la secrétaire organise son temps pour lui). C'est elle qui
  tient l'agenda.
- **Confidentialité.** Le sujet d'un rendez-vous peut être intime. Il n'est visible **que** du
  demandeur et des gardiens de l'agenda — jamais exposé aux autres membres (même posture que la
  liste de soin M7 et la consolation M8 : *remis, pas exposé*).
- **L'humain décide.** Confirmer / décliner / reprogrammer est un discernement pastoral, jamais
  automatique. Un déclin porte **un mot doux** (`decision_note`), jamais un rejet froid —
  *révélateur, pas juge*.
- **Le demandeur garde son agency.** Il annule quand il veut ; il voit ses demandes et leur statut.

## 2. Le parcours (l'agrégat `Appointment`)

```
requested ──confirm──▶ confirmed ──complete──▶ completed
    │                      │
 decline                cancel (demandeur)
    ▼                      ▼
 declined              cancelled
```

- **`requested`** — le membre a demandé (sujet + créneau souhaité optionnel + note). En attente.
- **`confirmed`** — la secrétaire a posé un créneau (`scheduled_at`). Reprogrammer = re-`confirm`.
- **`declined`** — la secrétaire n'a pas retenu la demande **en attente**, avec un mot.
- **`cancelled`** — le demandeur s'est rétracté (tant que non résolu).
- **`completed`** — le rendez-vous a eu lieu.

Un rendez-vous **résolu** (décliné / annulé / honoré) ne se ré-ouvre pas (`AppointmentClosedError`,
409). On ne décline qu'une demande *en attente* ; on ne marque honoré qu'un rendez-vous *confirmé*.

## 2bis. Émetteur et catégorie

Un rendez-vous a un **émetteur** qui peut être :
- un **membre** (compte) — il l'a demandé lui-même depuis le mobile ;
- un **walk-in** — quelqu'un qui passe **au bureau** : la secrétaire l'ouvre en son nom
  (`requester_name` + `requester_phone`, **sans compte**). `requester_account_id` est donc
  *optionnel* ; il faut un compte **ou** un nom (`RequesterIdentityRequiredError`).

Et une **catégorie** (`AppointmentCategory`) pour trier l'agenda et adapter l'accueil : `prayer`
(prière), `marriage` (mariage), `visit` (visite), `counsel` (conseil), `administrative`, `other`.

## 3. Qui fait quoi (autorité)

| Acte | Qui | Vérification |
| :-- | :-- | :-- |
| **Demander** (mobile) | tout **membre actif** | `MembershipRepository.get_active` (sinon `RequesterNotMemberError` 403) |
| **Ouvrir au bureau** (walk-in / pour un membre) | gardien de l'agenda | `MANAGE_APPOINTMENTS` — créneau fourni → RDV né confirmé |
| Annuler *sa* demande | le **demandeur** lui-même | `requester_account_id == actor` (sinon `NotAppointmentRequesterError` 403) |
| Confirmer / décliner / honorer / **fermer** / voir l'agenda | gardien de l'agenda | **`MANAGE_APPOINTMENTS` église-entière** (`ensure_church_wide`) |

**`MANAGE_APPOINTMENTS`** (nouvelle permission) → **Secrétaire** (ses mains) + **Admin**
(gouvernance) + **Pasteur** (décision produit : il tient **son propre** agenda, seule exception à
sa « lecture seule » §5.6) + **Owner** (propriété).

## 4. Deux surfaces (comme les Annonces M8)

- **Mobile** (le demandeur — JWT) : `POST /api/mobile/appointments/tenants/{tid}` (demander),
  `GET /…/tenants/{tid}/mine` (mes demandes + statut), `POST /…/{id}/cancel` (annuler).
- **Backoffice** (la secrétaire / le pasteur — cookie de session, sur la PWA) :
  `GET /api/backoffice/appointments/tenants/{tid}` (l'agenda vivant : en attente d'abord, puis
  confirmés par créneau), `POST /…/tenants/{tid}/open` (émettre au bureau : membre ou walk-in),
  `POST /…/{id}/confirm` (créneau), `POST /…/{id}/decline` (mot), `POST /…/{id}/complete`
  (honoré), `POST /…/{id}/close` (fermer un RDV qui ne se fera pas).

## 5. Livré

Contexte `app/contexts/appointments/`. Agrégat `Appointment` (+ `AppointmentStatus`,
`AppointmentCategory`) : émetteur membre **ou** walk-in ; fabriques `request` (membre) /
`open_at_office` (secrétaire, walk-in ou membre, confirmé si créneau donné). Commandes
`RequestAppointment` / `CancelAppointment` (demandeur) ; `OpenAppointment` / `ConfirmAppointment` /
`DeclineAppointment` / `CompleteAppointment` / `CloseAppointment` (gardien). Requêtes
`ListMyAppointments` / `ListTenantAgenda`. Dépôt `AppointmentRepository`. Table `appointments`
(migration `fb2c3d4e5f60`, **à appliquer quand Docker/Postgres up**). Permission
`MANAGE_APPOINTMENTS` (Secrétaire + Admin + **Pasteur**). Disponibilités récurrentes
(`AvailabilityRule`) + réservation de créneaux (`BookSlot`, `ListOpenSlots`) — migration
`fc3d4e5f6071`. **36 tests.** Sans IA.

## 5bis. Disponibilités et créneaux (livré)

Deux dimensions, comme demandé : **le calendrier de créneaux** et **plusieurs pasteurs**.

- **Récurrence hebdomadaire** (`AvailabilityRule`) : un gardien pose, *pour un pasteur* (le membre
  visé doit vraiment avoir le rôle Pasteur, sinon `NotAPastorError`), une plage « tel jour, de
  telle heure à telle heure, par créneaux de N min ». Les heures sont en **minutes depuis minuit,
  UTC** (localisation par fuseau du tenant plus tard). La règle **engendre** les créneaux concrets.
- **« Qui est libre quand »** (`ListOpenSlots`, du/au) : engendre les créneaux de *tous* les
  pasteurs sur la plage, **retire** ceux déjà réservés (un RDV confirmé occupe `(pasteur, heure)`)
  et le passé, trie par heure. C'est la réponse à « autre pasteur disponible » : si l'un n'a rien,
  la liste montre les autres. Ouverte à tout **membre actif**.
- **Réserver** (`BookSlot`, mobile self-service) : le membre prend un créneau ouvert → RDV **né
  confirmé**, `with_pastor_account_id` **déduit du créneau** (« premier dispo », pas de choix de
  pasteur en amont). Revalidation serveur (règle + futur + non pris) → anti double-réservation
  (`SlotNotAvailableError`). La secrétaire place aussi, via `open` (+ `with_pastor_account_id`).

Routes : mobile `GET /…/tenants/{tid}/open-slots?from_date&to_date[&pastor_account_id]` +
`POST /…/tenants/{tid}/book` ; backoffice `POST /…/tenants/{tid}/availability` +
`POST /…/availability/{rule_id}/deactivate`. Migration `fc3d4e5f6071` (`availability_rules` +
colonne `with_pastor_account_id`).

## 6. Reporté / à venir

- **Localisation par fuseau** — les créneaux sont engendrés en UTC ; un fuseau par tenant
  (`Africa/Abidjan` = UTC+0 aujourd'hui) viendra avec le champ tz du tenant.
- **Résolution des noms dans l'agenda** — le DTO expose `requester_account_id` (+ `requester_name`
  pour un walk-in) ; pour un membre, la PWA résout le nom via l'annuaire (la secrétaire a
  `VIEW_MEMBER_DIRECTORY`). Un port `AppointmentDirectory` (comme `InviterDirectory` en Mission)
  pourra le faire côté serveur.
- **Suivi post-RDV** (une note de suivi après l'entretien) ; **rappels / notifications push** ;
  rendez-vous avec un pasteur précis (plusieurs pasteurs).
- **Event** — le happening publié + RSVP (sans billetterie) : à concevoir après la discussion de
  philosophie. La géoloc du lien Mission (`place_label`/`latitude`/`longitude`) en est le pont.
