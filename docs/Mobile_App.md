# Dorea — App mobile (fidèle) : conception UX/UI & endpoints

> Fichier de référence pour **concevoir l'UX/UI** de l'app mobile **et** brancher les **endpoints**.
> Source des routes : l'OpenAPI **live** (`/api/mobile/*` + cartes mission publiques), 91 endpoints.
> Client : **Flutter**, JWT (téléphone + PIN), hors-ligne d'abord sur la présence.

---

## 1. Le manifeste — ce que Dorea mobile **n'est pas**

> On ne réinvente **ni un réseau social, ni Telegram/WhatsApp**. On répond au **contexte** de la vie
> d'église, avec une ergonomie **moderne, intuitive, calme**.

| ❌ Ce que ce n'est **pas** | ✅ Ce que c'est |
|---|---|
| Un **réseau social** (profils publics, abonnés, mur, scroll infini) | Un **compagnon contextuel** : l'app propose l'action juste au bon moment |
| Une **messagerie** (DM, fils de discussion, « vu à », statut en ligne) | Des **gestes à intention** : réagir, s'engager, marquer sa présence, inviter |
| Des **métriques de vanité** (compteurs de likes, scores) | La **non-exposition** : aucun score, jamais l'absence/la note d'un autre |
| Un moteur de **dopamine** (engagement pour l'engagement) | Le **calme** : on ouvre pour *savoir* et *agir*, puis on referme |

**Trois principes ergonomiques :**
1. **Contextuel avant tout.** L'accueil surface *ce qui compte maintenant* — « ta cellule commence,
   marque ta présence », « une annonce te concerne », « le sermon de dimanche t'attend ». Pas un flux
   à faire défiler sans fin.
2. **Faible friction.** Le code de séance façon Kahoot, les motifs d'absence à **taper** (jamais à
   rédiger), le QR mission, la carte biblique en un geste. Le pouce fait tout.
3. **Digne & sobre.** Réactions sans compteur, pas de « qui a vu », pas de mise en concurrence. Le
   fil est un **service**, pas une vitrine.

## 2. Identité (logo)
Rouge argile `#C0341C` → orange `#EF7E1B` → ambre `#F5A623`, sur fond chaud. Le **type porte la
couleur** (les annonces : deuil, joie, appel, prière…). Sémantique de soin distincte de l'accent.

## 3. Architecture d'information — la barre du pouce
```
Accueil        ← contextuel : l'action du moment + le fil (annonces + capsules)
Présence       ← se marquer présent · déclarer une absence
Missions       ← mon lien/QR, mes chercheurs, la carte biblique
Agenda         ← événements + mes rendez-vous
Moi            ← appartenances, compte, appareils, tier
```
5 onglets, pas plus. « Accueil » est l'écran d'atterrissage ; le reste est à un pouce.
*(Le pasteur / responsable retrouve ses outils de soin dans les mêmes écrans, révélés par son rôle.)*

---

## 4. Modules

Chaque module : **rôle**, **écrans**, **endpoints**. « Responsable » = capacités révélées par le rôle.

### 4.1 Entrée (Auth & Compte)
**Rôle** : s'inscrire (OTP SMS → PIN), se connecter (appareil de confiance ou OTP), gérer PIN/numéro.

| Méthode | Chemin | Objet |
|---|---|---|
| POST | `/auth/register` → `/auth/verify-registration` | Auto-inscription (OTP SMS) puis pose du PIN |
| POST | `/auth/login` → `/auth/verify-device` | Connexion ; nouvel appareil → OTP |
| POST | `/auth/refresh` | Rafraîchir la session |
| POST | `/account/change-password/request` · `/confirm` | Changer le PIN (OTP) |
| POST | `/account/change-phone/request` · `/confirm` | Changer de numéro (OTP) |

### 4.2 Accueil — Le Fil *(l'écran contextuel)*
**Rôle** : savoir. Une **carte « action du moment »** en tête si pertinent, puis le fil (annonces +
capsules du sermon), le type portant la couleur. Réactions légères, engagement (je viens/sers/porte).
**Non-exposition** : aucun compteur ; « ceci vous concerne » n'est visible que du sujet.

| Méthode | Chemin | Objet |
|---|---|---|
| GET | `/announcements/tenants/{tenant_id}/announcements` | Mon fil (Dorea + église + mes groupes), curseur |
| PUT · DELETE | `/announcements/{id}/reaction` | Réagir / retirer (emoji de la palette du type) |
| POST · DELETE | `/announcements/{id}/engage` | S'engager / se désengager (idempotent) |
| GET | `/announcements/{id}/consolation` | « N personnes vous portent » — **réservé au sujet** |
| POST | `/announcements/tenants/{tenant_id}/announcements` | Publier *(responsable/staff)* |
| GET · POST | `/announcements/{id}/responders` · `/archive` | Engagés / archiver *(responsable)* |

### 4.3 Présence *(la deuxième voix du membre)*
**Rôle** : dire « je suis là » (code de séance) ou « je ne serai pas là, et pourquoi » (motif à taper).
Hors-ligne d'abord (file rejouée). **Responsable** : ouvrir/animer la rencontre, roster, visiteurs.

| Méthode | Chemin | Objet |
|---|---|---|
| POST | `/attendance/self-check-in` | Taper le code de séance → présent (membre) |
| POST · GET · DELETE | `/attendance/tenants/{tenant_id}/absences[...]` | Déclarer / lister / annuler mon absence |
| POST | `/attendance/tenants/{tenant_id}/groups/{group_id}/gatherings` | Ouvrir une rencontre *(responsable)* |
| GET · PUT · DELETE | `/attendance/gatherings/{id}/roster` · `/present/{account_id}` | Roster · pointer *(responsable)* |
| POST | `/attendance/gatherings/{id}/close` | Clôturer la rencontre *(responsable)* |
| POST · GET · DELETE | `/attendance/gatherings/{id}/visitors[...]` · `/convert` | Visiteurs + conversion en membre *(responsable)* |

### 4.4 Soin & Intelligence *(pasteur / responsable, sur mobile)*
**Rôle** : comprendre avant de soigner — la care-list, la pulsation d'une cellule, la trajectoire d'un
membre, la santé et la tendance. **Jamais un jugement, toujours une invitation.** *(non-exposition)*

| Méthode | Chemin | Objet |
|---|---|---|
| GET | `/attendance/tenants/{tenant_id}/care-list` | Liste « à interpeller » (autorité pastorale) |
| GET | `/attendance/.../groups/{group_id}/pulse` · `/health` · `/trend` · `/effectif` · `/overview` | La cellule : pulsation, santé honnête, tendance, effectif réel |
| GET | `/attendance/.../groups/{group_id}/members/{account_id}/trajectory` | La frise & l'histoire d'un membre |

### 4.5 Le Compagnon & les Sermons
**Rôle** *(membre)* : vivre le compagnon — « as-tu vécu le culte ? » → consolider (oui) ou apprendre
l'essentiel (non). Conversation **guidée et privée**, pas un chat libre. *(pasteur)* : déposer un
sermon (texte / PDF / PPTX), approuver, publier.

| Méthode | Chemin | Objet |
|---|---|---|
| POST | `/sermons/{sermon_id}/companion` | Ouvrir/reprendre le compagnon (la question d'entrée) |
| POST | `/sermons/companion/{session_id}/attendance` | Répondre oui/non → consolidation ou enseignement |
| POST | `/sermons/companion/{session_id}/next` | Étape suivante (mot de clôture à la fin) |
| POST | `/sermons/tenants/{tenant_id}` · `/upload` | Déposer (texte / fichier PDF-PPTX) *(pasteur)* |
| POST | `/sermons/{sermon_id}/approve` · `/publish` | Approuver puis publier *(pasteur)* |
| GET | `/sermons/tenants/{tenant_id}` · `/sermons/{id}` | Lister / relire *(pasteur)* |

### 4.6 Missions *(la main tendue)*
**Rôle** : générer mon **lien/QR** personnel, créer une **carte biblique** (un verset flou → l'IA
retrouve la référence, la Bible donne le texte exact), suivre **mes chercheurs**, les accompagner/
intégrer. La carte publique s'ouvre **sans compte** (le code EST l'entrée).

| Méthode | Chemin | Objet |
|---|---|---|
| POST | `/mission/tenants/{tenant_id}/my-link` | Mon lien/QR personnel (idempotent) |
| POST | `/mission/generate-card` | Verset flou → carte designée (IA + Bible canonique) |
| GET | `/mission/tenants/{tenant_id}/my-seekers` | Mon fruit : les chercheurs amenés + réactions |
| POST | `/mission/seekers/{id}/accompany` · `/integrate` · `/close` | Relais humain / devenir membre / clôturer |
| POST | `/mission/tenants/{tenant_id}/groups/{group_id}/link` · `/links/{id}/revoke` | Lien de campagne de groupe *(responsable)* |
| GET · POST | `/api/mission/link/{code}` · `/accept` · `/react` | La **carte publique** (voir · accepter · réagir) |

### 4.7 Agenda — Événements & Rendez-vous
**Rôle** *(événements)* : le fil des événements qui m'atteignent (église/dénomination/plateforme),
réagir, confirmer ma présence, signaler ; publier (+ tableau de rayonnement pour l'organisateur).
*(rendez-vous)* : voir les créneaux, réserver, demander, suivre mes demandes.

| Méthode | Chemin | Objet |
|---|---|---|
| GET · POST | `/events/tenants/{tenant_id}` | Le fil des événements · publier |
| GET | `/events/{id}` · `/events/{id}/stats` | Détail · rayonnement *(organisateur)* |
| POST | `/events/{id}/react` · `/confirm` · `/withdraw` · `/view` · `/report` · `/cancel` | Gestes sur un événement |
| GET · POST | `/appointments/tenants/{tenant_id}/open-slots` · `/book` | Créneaux ouverts · réserver |
| POST · GET · POST | `/appointments/tenants/{tenant_id}` · `/mine` · `/{id}/cancel` | Demander · mes demandes · annuler |

### 4.8 Mes groupes
**Rôle** : rejoindre un groupe par code, quitter ; *(responsable)* générer/révoquer un lien d'invitation.

| Méthode | Chemin | Objet |
|---|---|---|
| POST | `/groups/join` | Rejoindre par code (onboarde l'église si besoin) |
| POST | `/groups/{group_id}/leave` | Quitter un groupe |
| POST | `/groups/tenants/{tenant_id}/groups/{group_id}/invitations` · `/invitations/{id}/revoke` | Lien d'invitation *(responsable)* |

### 4.9 Moi (Compte · Appartenances · Compte Business · Appareils)
**Rôle** : mes appartenances (découverte post-login), mon statut/rôles, activer le **compte Business**
(carte prépayée Visa), gérer les appareils push.

| Méthode | Chemin | Objet |
|---|---|---|
| GET | `/iam/me/memberships` · `/iam/me/tenants/{tenant_id}/membership` | Mes appartenances · statut & rôles |
| POST | `/iam/join-church` | Rejoindre une église par code |
| GET · POST | `/billing/status` · `/billing/card` · `/billing/card/remove` | Mon tier · activer/retirer le compte Business |
| GET · POST | `/notifications/devices` · `/devices/remove` | Mes appareils push (enregistrer / oublier) |
| PUT | `/media` | Téléverser une image (annonces, cartes) |

---

## 5. L'écran d'accueil contextuel *(le cœur ergonomique)*

Au lieu d'un flux social, l'accueil **compose ce qui compte maintenant** :

1. **La carte d'action du moment** (0 ou 1) — dérivée du contexte : une rencontre de ma cellule est
   ouverte (`self-check-in`), un sermon publié non encore vécu (`companion`), une annonce me concerne
   (`consolation`). Un seul appel à l'action, gros, au pouce.
2. **Le fil** — annonces + capsules, le type portant la couleur, réactions sans score.
3. **Rien de plus.** Pas de suggestions d'« amis », pas de tendances, pas de badge de non-lus anxiogène.

*L'app ne cherche pas à retenir. Elle rend service, puis se retire.*

---

## 6. Transverse (implémentation)

- **Auth** : JWT Bearer ; 429 (`AUTH_TOO_MANY_ATTEMPTS`) sur login → afficher le délai ; nouvel
  appareil → parcours OTP.
- **Hors-ligne d'abord** : la présence se met en file locale et se rejoue (saisie **idempotente** —
  marquer deux fois = pareil). Lecture du fil/agenda en cache tolérée.
- **Rôle** : l'UI adapte les capacités depuis `/iam/me/...` ; le backend reste l'arbitre.
- **Non-exposition** : jamais de compteur de réaction, jamais l'absence/note d'un autre, jamais la
  réponse intime au compagnon.
- **Erreurs** stables `{ error: { code, message, details } }` → messages qui expliquent et proposent.
- **Push** : enregistrer l'appareil au login ; best-effort côté serveur (une push ne bloque rien).

---

*Fichier vivant — régénérer la liste d'endpoints depuis `/openapi.json` à chaque évolution.*
