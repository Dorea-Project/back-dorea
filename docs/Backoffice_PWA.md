# Dorea — Backoffice PWA : conception UX/UI & endpoints

> Fichier de référence pour **concevoir l'UX/UI** du backoffice **et** brancher les **endpoints**.
> Source des routes : l'OpenAPI **live** de ce backend (`/api/backoffice/*`, 59 endpoints).
> À tenir à jour avec le code (`app/contexts/*/interface/backoffice_router.py`).

---

## 1. Cadre

- **Front** : PWA **Next.js / React** (installable, hors-ligne partiel), consomme **`/api/backoffice/*`**.
- **Auth** : **session par cookie** (`dorea_backoffice_session`, HttpOnly, SameSite=Lax) après
  `login` → éventuel `verify` OTP nouvel appareil. Le contexte de l'acteur vient de `/auth/me`.
- **Deux audiences, un même front** :
  - **L'église** (Owner · Admin · Secrétaire · Pasteur) — la gestion quotidienne. Autorité = **rôles
    IAM** bornés par la portée (RBAC).
  - **Dorea Plateforme** (admin central) — provisionnement, modération, annonces plateforme.
    Autorité = **jeton de service** (`X-Service-Token`), routes sous `/api/backoffice/platform/*`
    et quelques actes tenant/onboarding.
- **Média** : upload d'images par corps brut (`PUT /media`) → URL à replacer dans les formulaires.

### Identité de marque (logo)
Le logo fixe la direction : un **« d » rouge argile** qui glisse vers l'**orange** sur « orea ».
Palette de travail :

| Rôle | Hex | Usage |
|------|-----|-------|
| **Rouge Dorea** | `#C0341C` | accent profond, attention, le « d » |
| **Orange Dorea** | `#EF7E1B` | accent vif, actions, liens |
| **Ambre** | `#F5A623` | fin de dégradé, surbrillance |
| Encre chaude | `#211A16` | texte |
| Papier chaud | `#F7F3EE` | fond clair |

Sémantique de soin (distincte de l'accent) : **florissant** (vert), **à veiller** (bleu ardoise),
**sans nouvelles** (rouge profond). Principes UX repris du produit : *le soin pas le contrôle*,
*non-exposition* (jamais l'absence/note d'un autre au fidèle ; le backoffice, lui, voit l'agrégat).

---

## 2. Architecture d'information (rail latéral)

```
Tableau de bord        ← Présence & Soin (l'écran d'atterrissage)
Membres                ← IAM : annuaire, enrôlement, statuts, transferts
Groupes                ← arbre, responsables, multiplication
Annonces               ← publier, archive, engagés
Agenda                 ← rendez-vous, disponibilités
Sermons *              ← (mobile aujourd'hui ; backoffice à venir)
Mon église             ← profil du tenant (Owner)
─────────── Dorea (plateforme) ───────────
Églises · Onboarding · Annonces Dorea · Modération · Notifications
```
`*` Sermons : dépôt/approbation existent côté mobile ; un écran backoffice est un chantier ouvert.

---

## 3. Modules

Chaque module : **rôle**, **écrans clés**, **endpoints**. Autorité — 🏛️ = jeton Plateforme
(`X-Service-Token`), sinon session backoffice (rôle IAM).

### 3.1 Authentification
**Rôle** : entrer dans le backoffice, gérer l'appareil de confiance.
**Écrans** : login (email + mot de passe), défi OTP (nouvel appareil), garde de session.

| Méthode | Chemin | Objet |
|---|---|---|
| POST | `/auth/login` | Connexion (email + mot de passe + appareil) |
| POST | `/auth/verify` | Vérifier l'OTP d'un nouvel appareil → session |
| GET | `/auth/me` | L'utilisateur authentifié (cookie) |
| POST | `/auth/logout` | Déconnexion (efface le cookie) |

### 3.2 Tableau de bord — Présence & Soin *(l'écran phare)*
**Rôle** : décider en un coup d'œil qui va bien, qui décroche, quelle cellule est prête à se
multiplier. **La boussole pastorale.** *(voir §4 pour la simulation)*
**Écrans** : la **grille des groupes** (totaux, tendance), la **liste de soin** (« à interpeller »),
le **drill-down** vers la trajectoire d'un membre / la tendance d'un groupe, l'**arbre de
multiplication**.

| Méthode | Chemin | Objet |
|---|---|---|
| GET | `/attendance/tenants/{tenant_id}/dashboard` | Grille des groupes + totaux |
| GET | `/attendance/tenants/{tenant_id}/care-list` | Liste « à interpeller » (qui visiter) |
| GET | `/attendance/tenants/{tenant_id}/groups/{group_id}/trend` | Tendance d'un groupe dans le temps |
| GET | `/attendance/.../groups/{group_id}/members/{account_id}/trajectory` | Trajectoire d'un membre |
| GET | `/attendance/tenants/{tenant_id}/multiplication-tree` | Arbre de multiplication (fertilité) |

### 3.3 Membres (IAM)
**Rôle** : enrôler, faire évoluer les statuts, gérer les rôles, importer, transférer entre églises.
**Écrans** : annuaire, fiche membre (statut + rôles), enrôlement (membre à rôle / fidèle invité),
import CSV (onboarding M3), liens d'invitation église, file des transferts (entrants/sortants).

| Méthode | Chemin | Objet |
|---|---|---|
| POST | `/iam/tenants/{tenant_id}/members` | Enrôler un membre porteur d'un rôle |
| POST | `/iam/tenants/{tenant_id}/invited-members` | Enrôler un fidèle ordinaire (`invited`) |
| POST | `/iam/tenants/{tenant_id}/members/import` | Import en masse (best-effort par ligne) |
| POST | `/iam/tenants/{tenant_id}/members/{account_id}/transitions` | Faire évoluer le statut |
| POST | `/iam/tenants/{tenant_id}/members/{account_id}/revoke-role` | Révoquer un rôle |
| POST | `/iam/tenants/{tenant_id}/members/{account_id}/close` | Clôturer une appartenance (cascade rôles) |
| POST | `/iam/tenants/{tenant_id}/church-invitations` | Générer un lien d'invitation église |
| POST | `/iam/church-invitations/{invitation_id}/revoke` | Révoquer un lien |
| GET | `/iam/tenants/{tenant_id}/transfers` | Transferts entrants/sortants |
| POST | `/iam/tenants/{tenant_id}/transfer-requests` | Demander à recevoir un membre |
| POST | `/iam/transfers/{transfer_id}/accept` · `/decline` · `/cancel` | Traiter un transfert |

### 3.4 Groupes
**Rôle** : bâtir l'arbre des groupes, nommer les responsables (cap 6 + formation), gérer le roster,
**multiplier** une cellule, lire la santé/lignée.
**Écrans** : arbre des groupes, fiche groupe (roster, responsables, rapport santé), assistant de
multiplication, promotion en église (Plateforme).

| Méthode | Chemin | Objet |
|---|---|---|
| POST | `/tenants/{tenant_id}/groups` | Créer un groupe |
| PATCH · DELETE | `/tenants/{tenant_id}/groups/{group_id}` | Modifier / fermer un groupe |
| POST · DELETE | `/tenants/{tenant_id}/groups/{group_id}/leaders` | Nommer / révoquer un responsable |
| GET · POST · DELETE | `/tenants/{tenant_id}/groups/{group_id}/members[...]` | Roster : lister / rattacher / retirer |
| POST | `/tenants/{tenant_id}/groups/{group_id}/multiply` | Multiplier la cellule |
| GET | `/tenants/{tenant_id}/groups/{group_id}/report` | Santé & lignée |
| 🏛️ POST | `/groups/{group_id}/promote-to-church` | Émanciper un groupe en église (church planting) |

### 3.5 Annonces
**Rôle** : publier à la bonne portée (groupe / église), consulter l'archive, voir les engagés.
**Écrans** : composer (type → couleur/emojis auto, portée, média), fil/archive, liste des engagés.

| Méthode | Chemin | Objet |
|---|---|---|
| POST | `/announcements/tenants/{tenant_id}/announcements` | Publier (communauté ou portée) |
| GET | `/announcements/tenants/{tenant_id}/announcements` | L'archive (incluant archivées/expirées) |
| POST | `/announcements/{announcement_id}/archive` | Archiver (sortir du fil) |
| GET | `/announcements/{announcement_id}/responders` | Qui s'est engagé (les noms) |

### 3.6 Agenda — Rendez-vous
**Rôle** : la secrétaire garde l'agenda du pasteur ; confirmer/décliner/honorer, ouvrir un walk-in,
poser des disponibilités récurrentes.
**Écrans** : agenda (en attente + confirmés), fiche RDV (confirmer/décliner avec un mot/fermer/
honoré), ouverture au bureau, gestion des disponibilités.

| Méthode | Chemin | Objet |
|---|---|---|
| GET | `/appointments/tenants/{tenant_id}` | L'agenda (en attente + confirmés) |
| POST | `/appointments/tenants/{tenant_id}/open` | Ouvrir un RDV au bureau (membre ou walk-in) |
| POST | `/appointments/{appointment_id}/confirm` · `/decline` · `/complete` · `/close` | Cycle du RDV |
| POST | `/appointments/tenants/{tenant_id}/availability` | Poser une disponibilité récurrente |
| POST | `/appointments/availability/{rule_id}/deactivate` | Retirer une disponibilité |

### 3.7 Mon église (Tenant) & Média
**Rôle** : l'Owner édite le profil de son église ; upload d'images pour les annonces.

| Méthode | Chemin | Objet |
|---|---|---|
| GET · PATCH | `/tenants/{tenant_id}` | Lire / éditer le profil de mon église (Owner) |
| PUT | `/media` | Téléverser une image → URL |

### 3.8 Dorea Plateforme *(admin central — 🏛️ jeton de service)*
**Rôle** : provisionner et gouverner le parc d'églises, modérer la diffusion élargie, piloter les
annonces Dorea et le dispatch des notifications.
**Écrans** : annuaire des églises, file d'onboarding, composer une annonce Dorea, file de modération
d'événements, bouton/cron de dispatch.

| Méthode | Chemin | Objet |
|---|---|---|
| 🏛️ GET · POST | `/tenants` | Annuaire · provisionner une église (Tenant + Owner) |
| 🏛️ POST | `/tenants/{tenant_id}/suspend` · `/reactivate` | Suspendre / réactiver une église |
| 🏛️ POST | `/tenants/{tenant_id}/transfer-ownership` | Transférer le siège Owner (succession) |
| 🏛️ POST | `/onboarding/{request_id}/approve` · `/reject` | Valider / rejeter une demande d'église |
| 🏛️ POST | `/platform/announcements` | Publier une annonce Dorea (toutes les églises) |
| 🏛️ GET · POST | `/platform/events/reported` · `/platform/events/{id}/takedown` | Modération d'événements |
| 🏛️ POST | `/platform/notifications/dispatch` | Dispatcher les notifications dues (cron) |

---

## 4. La simulation du dashboard (ce qui nous attend)

L'écran d'atterrissage croise **présence** (le corps) et **résonance** (le cœur) :

- **Bandeau de métriques** : présents 8 semaines · portée du dernier sermon · nombre « à veiller ».
- **Grille des groupes** : une ligne par cellule/département — effectif réel, tendance (sparkline),
  drapeau « prête à multiplier ». *(→ `dashboard`, drill-down `trend`)*
- **Liste de soin** : des cartes « à interpeller » — *présent mais éteint* / *absent mais affamé* /
  *à veiller* — chacune une **invitation à agir**, jamais un fichier de honte. *(→ `care-list`,
  `trajectory`)*
- **Arbre de multiplication** : la forêt des cellules qui se reproduisent. *(→ `multiplication-tree`)*

> Maquette visuelle : voir l'artifact « Dorea — Backoffice (simulation du dashboard) ».

---

## 5. Transverse (pour l'implémentation)

- **Réponses d'erreur** stables : `{ error: { code, message, details } }` — mapper `code` → toasts.
  429 (`AUTH_TOO_MANY_ATTEMPTS`) sur le login → afficher `retry_after_seconds`.
- **Autorité côté front** : masquer/afficher les actions selon `/auth/me` (rôles) ; le backend
  reste l'arbitre (une action masquée reste refusée côté serveur).
- **Non-exposition** : le backoffice montre l'agrégat et les invitations de soin, jamais la réponse
  intime d'un membre (ex. compagnon du sermon).
- **Offline PWA** : lecture en cache (annuaire, agenda) tolérable ; les écritures exigent le réseau.
- **En-têtes de sécurité** déjà servis par le backend (`nosniff`, `X-Frame-Options: DENY`, HSTS
  hors local) ; le front doit rester servable sous ces contraintes (pas d'iframe cross-origin).

---

*Fichier vivant — régénérer la liste d'endpoints depuis `/openapi.json` à chaque évolution.*
