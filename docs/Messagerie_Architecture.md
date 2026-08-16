# Messagerie — architecture

Statut : **proposition à valider**. Rien n'est écrit tant que M1 et M3 n'ont pas
de réponse.

Périmètre arrêté : **deux appelants, pas un de plus** — le contexte `events`
pour l'invitation à un happening publié, et `auth` pour l'OTP. Tout le reste
(annonces, rendez-vous, veille) attendra d'avoir une raison écrite.

## 1. Ce qui existe déjà, et qu'on ne refait pas

| Brique | Ce qu'elle fait | Où |
|---|---|---|
| `notifications` | Push vers un **appareil** (jeton FCM), outbox `ScheduledNotification`, dispatch par cron externe | `contexts/notifications` |
| `auth` | Port `OtpSender` + adaptateurs SMTP et SMS HTTP, aiguillés par canal, avec interdiction du repli journal hors `local` | `contexts/auth/infrastructure/otp_delivery.py` |
| `events` | Le happening publié, sa portée (`church` en E-0), les réactions et les RSVP | `contexts/events` |

Trois choses à retenir : l'**outbox + cron** est le patron d'asynchrone maison
(pas de Celery), le port `OtpSender` est déjà la bonne abstraction, et le numéro
de téléphone ne va jamais dans les journaux (DOREA-027).

**Pas de bus.** La spec §14 l'a tranché : les faits métier sont tirés par la
couche application, jamais publiés. `messaging` ne s'abonne donc à rien — il est
**appelé**, comme `notifications` l'est déjà par les annonces.

## 2. La frontière : un contexte `messaging`, deux portes

**Ce qu'il possède** : les canaux opérateur (WhatsApp, SMS, e-mail), les modèles
approuvés, l'état d'acheminement de chaque envoi, le consentement par canal, les
webhooks entrants.

**Ce qu'il ne possède pas** : la raison d'écrire. Un événement reste un
événement, un OTP reste une preuve de possession.

```
events  ──►  MemberMessenger (port)  ──┐
                                       ├──►  messaging  ──►  WhatsApp / SMS / e-mail
auth    ──►  OtpSender (port existant) ─┘        │
                                                └──►  webhooks entrants (statuts, réponses, STOP)
```

Les deux portes sont des **ports déclarés côté `messaging`**, injectés dans les
appelants — exactement comme `Notifier` l'est aujourd'hui dans
`publish_announcement`. Un contexte appelant ne connaît jamais WhatsApp.

**Pourquoi pas dans `notifications`.** Un jeton FCM est une adresse d'appareil,
révocable, gratuite, sans réglementation. Un numéro WhatsApp est une identité de
personne, avec un consentement, un coût par conversation, une fenêtre de 24 h et
une note de qualité. Les mélanger obligerait le même agrégat à porter deux
mondes qui n'ont en commun que le verbe « envoyer ».

## 3. Le modèle

- **`MessagingProfile`** — pour une personne : les adresses connues par canal,
  l'opt-in (quand, comment, prouvé par quoi), le canal préféré, et la date du
  dernier message **entrant** — c'est elle qui ouvre la fenêtre de service.
- **`Template`** — un modèle approuvé côté opérateur, sa catégorie
  (`authentication`, `utility`, `marketing`), ses variables. Hors fenêtre de
  24 h, **rien ne part sans modèle approuvé** : ce n'est pas notre règle, c'est
  celle de WhatsApp.
- **`Message`** — l'unité : un destinataire, un canal, un contenu, un état.
- **`Broadcast`** — une diffusion. Elle **matérialise** ses destinataires à la
  création (photo de l'assemblée), puis engendre N `Message`. Résoudre
  l'audience au moment de l'envoi la ferait varier pendant que la diffusion
  part. En E-0, un seul producteur : l'invitation d'un `Event` de portée
  `church`.

État d'un message :

```
queued ──► dispatched ──► sent ──► delivered ──► read
   │                        └──► failed(raison)
   └──► skipped(sans opt-in | hors fenêtre | numéro invalide)
```

`skipped` n'est pas un échec : c'est un refus **avant** de dépenser une
conversation, et il se compte à part — un taux qui monte signale un problème de
consentement, pas de réseau.

## 4. Deux voies, et c'est la décision centrale

| | Transactionnelle | Diffusion |
|---|---|---|
| Qui | OTP | Invitation à un événement |
| Attente acceptable | quelques secondes | quelques minutes |
| File | immédiate, priorité haute | par lots, étalée |
| Débit | réservé | ce qui reste |
| En cas de surcharge | jamais retardée | ralentie |

Elles partagent les adaptateurs, **jamais la file ni le budget de débit**. Sans
cette séparation, l'invitation à une convention envoyée un dimanche matin
retarderait les codes de connexion de ceux qui ouvrent l'application pendant le
culte — et l'utilisateur n'a aucun moyen de comprendre pourquoi son code
n'arrive pas.

C'est aussi ce qui protège la note de qualité du numéro : trop de blocages sur
une invitation fait chuter le débit autorisé, et ce sont les OTP qui en
souffrent en premier.

## 5. Les ports

```python
# Vers l'extérieur — ce que les appelants connaissent.
class MemberMessenger(ABC):
    """Écrire à des membres. Ne dit ni par quel canal, ni quand."""
    async def broadcast(self, request: BroadcastRequest) -> BroadcastId: ...

class OtpSender(ABC):   # déjà dans auth, inchangé
    async def send(self, *, channel, target, code, purpose) -> None: ...

# Vers l'intérieur — ce que messaging branche.
class MessageChannel(ABC):
    async def send(self, message: OutboundMessage) -> ProviderReceipt: ...

class TemplateCatalog(ABC):
    """Les modèles approuvés, et leur catégorie."""
```

Adaptateurs : `WhatsAppCloudChannel`, `HttpSmsChannel` (celui d'aujourd'hui,
déplacé), `SmtpEmailChannel`. Le repli journal reste, avec la même interdiction
hors `local` que pour l'OTP.

## 6. Les deux flux

**OTP.** `auth` continue d'appeler son port — il ne change pas. Un adaptateur
`MessagingOtpSender` le branche sur la voie transactionnelle, avec un modèle de
catégorie `authentication`. Repli SMS si WhatsApp échoue ou si le numéro n'a pas
de compte : un code qui n'arrive pas est un compte inaccessible.

**Invitation.** L'`Event` publié appelle `MemberMessenger.broadcast` : audience
figée (les membres de l'église, portée `church`), messages en file de diffusion,
dispatcher par lots sous un seau à jetons — le débit est une propriété du numéro
émetteur, pas du serveur. Chaque message porte une clé d'idempotence
`(broadcast_id, recipient)` : un redémarrage en cours d'envoi ne doit pas doubler
la facture.

Un point à assumer dès maintenant : **une invitation est un modèle `marketing`**
au sens de WhatsApp — la catégorie la plus chère, et celle qui exige l'opt-in le
plus explicite. Un rappel de RSVP à quelqu'un qui a déjà répondu peut passer en
`utility`, moins cher. La différence se joue sur ce que dit le modèle, pas sur
notre intention.

## 7. Ce que WhatsApp impose, et qui ne se négocie pas

- **La fenêtre de 24 h.** Hors d'elle, seuls les modèles approuvés partent. Une
  invitation libre vers des gens qui n'ont jamais écrit est impossible, quelle
  que soit l'architecture.
- **La facturation par conversation**, selon la catégorie du modèle.
- **La note de qualité du numéro.** Trop de blocages fait chuter le débit
  autorisé — et ce sont les OTP qui en souffrent en premier.
- **L'opt-in prouvable.** Il ne suffit pas de l'avoir : il faut pouvoir dire
  quand et comment il a été donné.

Conséquence pour le produit : quand la portée des événements s'élargira
(`denomination`, `platform`, tier Business), le volume et le coût suivront la
même courbe. Le gratuit local reste gratuit ; le rayonnement large a un prix
d'opérateur en plus du prix institutionnel déjà décidé.

## 8. Ce que ça change dans l'existant

| Fichier | Changement |
|---|---|
| `auth/infrastructure/otp_delivery.py` | `build_otp_sender` route vers `messaging` ; les adaptateurs SMTP/SMS déménagent, le port ne bouge pas |
| `events/application/commands/…` | Reçoit un `MemberMessenger` optionnel, comme `publish_announcement` reçoit son `Notifier` |
| `notifications`, `announcements` | Rien |
| `core/config.py` | Clés WhatsApp (identifiant de numéro, jeton, secret de webhook) ; les clés SMS existantes restent |

## 9. Ce qui est tranché

### M1 — un seul numéro, celui de Dorea

Un numéro par église coûterait un provisionnement, une vérification Meta et un
jeu de modèles à faire approuver **par église**. On commence avec un numéro
unique. Quatre conséquences, dont trois à traiter dans le code dès la première
étape :

1. **C'est Dorea qui parle, pas l'église.** Le membre voit « Dorea » comme
   expéditeur. Le nom de son église doit donc être une **variable du modèle**,
   et apparaître dans la première phrase — sans quoi celui qui fréquente deux
   assemblées ne sait pas laquelle lui écrit.
2. **La note de qualité est commune.** Une église qui écrit trop, ou mal, fait
   chuter le débit de tout le monde — OTP compris. D'où un **quota par église**
   sur la voie de diffusion, et la possibilité de suspendre les diffusions d'un
   tenant sans toucher à la voie transactionnelle.
3. **Un blocage est global, et c'est le vrai danger.** Un membre agacé qui
   bloque le numéro Dorea ne reçoit plus ses **codes de connexion** : il perd
   l'accès à son compte, pas seulement les invitations. Le repli SMS de l'OTP
   (M5) cesse d'être un confort — il devient la seule porte de secours.
4. **Un seul jeu de modèles à faire approuver**, et une fenêtre de 24 h
   partagée : deux églises qui écrivent au même membre le même jour peuvent
   tomber dans la même conversation facturée. C'est le gain, et il est réel.

Le jour où une église voudra son propre numéro, `MessagingProfile` et
`Broadcast` ne changent pas : seul l'émetteur devient un attribut du tenant
plutôt qu'une constante de la plateforme.

## 10. Questions restantes

| # | Question | Recommandation |
|---|---|---|
| M3 | **Cloud API Meta en direct**, ou agrégateur (Twilio, 360dialog, Infobip) ? | **En direct.** L'intérêt d'un agrégateur est le provisionnement de nombreux numéros et une facture unique — précisément ce que M1 reporte. Le SMS de repli passe déjà par un fournisseur HTTP générique. |
| M5 | Le **repli SMS** est-il automatique ? Il est payant. | **Oui pour l'OTP**, et ce n'est plus discutable depuis M1 : un numéro bloqué ne doit pas enfermer quelqu'un dehors. Jamais pour une invitation. |
| M6 | Combien de temps conserve-t-on le **contenu** des messages ? | Le minimum : l'état et l'horodatage longtemps, le corps peu — c'est une donnée personnelle. |
| M7 | Le **STOP** vaut-il pour une église ou pour Dorea entier ? | Avec un numéro unique, le membre ne peut pas viser une église : son STOP arrive à Dorea. On l'enregistre donc **global sur la diffusion**, jamais sur l'OTP, et l'application propose de le régler par église. |

*(M2 — messagerie à deux voies — et M4 — quotas et facturation — sont hors
périmètre tant que les deux seuls appelants sont `events` et `auth`.)*

## 11. Ordre de livraison

### Étape 1 — socle, WhatsApp, OTP · **faite**

`contexts/messaging` avec le port `MessageChannel`, l'adaptateur Infobip
(WhatsApp par modèle, SMS en repli) et `MessagingOtpSender` branché dans
`build_otp_sender`. Le port `OtpSender` d'`auth` n'a pas bougé.

Vérifiée par un envoi réel : `python scripts/messaging_smoke.py --to +225…`.

Deux propriétés que les tests tiennent :

- `OutboundMessage` porte le modèle **et** le texte. Le repli ne reconstruit
  rien, donc il ne peut pas dire autre chose que le message d'origine.
- Deux erreurs distinctes : `ChannelUnavailableError` se rejoue et se replie,
  `MessageRejectedError` non. Un HTTP 200 portant un statut mort (`groupId` 2,
  4, 5) est un refus, pas un succès.

### Étape 2 — webhooks · **faite**

Deux routes publiques, `POST /api/webhooks/infobip/reports` et `/inbound`, plus
deux tables : `messaging_deliveries` (le sort d'un message, **sans numéro ni
contenu**) et `messaging_opt_outs` (qui a dit stop, avec le numéro — c'est la
clé de vérification et la preuve du refus).

**Ce qui garde ces routes, et ce que ça vaut.** Infobip ne signe pas ses appels :
pas de HMAC, rien qui prouve l'origine. Un secret partagé en en-tête
(`X-Dorea-Webhook-Token`) est la seule barrière praticable. Quelqu'un qui le
connaîtrait pourrait donc nous raconter qu'un message a été remis. D'où la
règle : **aucune décision de sécurité ne dépend de ces routes** — elles
renseignent un journal et enregistrent des refus, elles n'ouvrent aucun accès et
ne valident aucun code.

Deux pièges du format Infobip, tenus par des tests :

- leur bloc `error` est **toujours** présent, `NO_ERROR` compris. Le lire comme
  un échec ferait passer chaque message réussi pour un problème ;
- un message entrant sans texte (image, audio, position) n'est pas une parole :
  on ne fabrique pas un message vide qui pourrait passer pour un « stop ».

**Ce qui reste pour fermer la boucle** : dire à Infobip où appeler. Soit dans
leur portail, soit en posant `notifyUrl` à l'envoi. Tant que ce n'est pas fait,
les routes existent mais personne ne les appelle — et l'on continue d'envoyer à
l'aveugle.

**Ce que l'opt-out ne fait pas encore** : il est enregistré, pas appliqué. Rien
ne le consulte, parce que rien ne diffuse. Il sera vérifié à l'étape 3 — et
**jamais** pour l'OTP : un code est demandé par celui qui le reçoit, il ne
relève pas du consentement de diffusion.

### Étape 3 — diffusion · à venir

Audience figée, lots, débit, idempotence, opt-out appliqué — branchée sur
l'invitation d'un `Event`.
