# Chantier bilingue — plan d'exécution arrêté le 16 août 2026

> **Nature :** plan d'exécution. Origine : *« il y a des églises anglophones même en Côte
> d'Ivoire »*. Ce document est ce qui sera **codé**, dans cet ordre.
>
> **Ce qu'il ajoute :** l'état réellement vérifié du dépôt — `tenants.language` existe depuis
> le M0 et **n'est lue par personne** —, la frontière entre ce que Dorea dit et ce que les
> humains écrivent, sept pièges relevés à la lecture, et un mur nommé sur Urim.
>
> **État au 16/08/2026 (soir) :** L-0, L-1, L-3, L-4, L-5, L-6 livrés. **L-2 reste**,
> bloqué par l'approbation Meta du modèle WhatsApp `dorea_otp` en anglais.

---

## 0. Le principe, et la frontière qu'il impose

> **Dorea traduit ce que Dorea dit. Dorea ne traduit jamais ce qu'un humain a écrit.**

Une annonce, un événement, un sermon, le mot du pasteur qui décline un rendez-vous : ce sont des
paroles d'église. L'église anglophone les écrit en anglais et personne ne les retouche. Ce qui
se traduit, c'est la **voix du produit** — « Rendez-vous confirmé », « Un retour ? », le code
de vérification.

Cette frontière n'est pas un confort de mise en œuvre : c'est ce qui empêche le chantier de
devenir sans fin. Sans elle, on finit par faire traduire par une machine le mot qu'un pasteur a
pesé, et Dorea se met à parler à la place de l'église.

**Deux corollaires, qui décident de toute l'architecture :**

- **Le serveur rend les push.** Une notification part vers un appareil éteint ; il n'y a aucun
  client pour la mettre en forme. Donc catalogue serveur, obligatoirement.
- **L'API rend des codes.** `ACCOUNT_NOT_FOUND` est déjà la règle du dépôt (2 seuls `detail`
  français sur toute la surface HTTP). On ne la casse pas : le client possède ses phrases.

---

## 1. État vérifié du dépôt (16 août 2026)

| Organe | État |
| :-- | :-- |
| `tenants.language`, défaut `'fr'` ([`models.py:45`](../app/contexts/tenant/infrastructure/persistence/models.py)) | **existe, stockée, recopiée dans 8 fichiers — lue par aucune logique** |
| `accounts.language` (la personne) | ~~n'existe pas~~ → **livré en L-0**, nullable, migration `a7c1e04b93d5` |
| `TemplateRef.language` ([`ports.py:25`](../app/contexts/messaging/application/ports.py)) | existe — le fournisseur Meta l'**impose** déjà |
| `whatsapp_otp_language` ([`config.py:98`](../app/core/config.py)) | existe, **valeur globale unique `"fr"`** |
| Corpus biblique multi-langues (`code`, `language`, `text_family`) | **schéma prêt**, aucune migration nécessaire pour accueillir une version anglaise |
| Erreurs HTTP en **codes** | déjà la règle — rien à faire |
| Catalogue de messages | ~~n'existe pas~~ → **livré en L-1**, `app/_shared/messages.py` |
| Push : 14 points d'appel, ~30 chaînes françaises en dur | **convertis en L-1** |
| ~~`PushNotification(title, body)`~~ | → `PushNotification(key, params)`, rendu au dispatch |
| ~~`scheduled_notifications.title` / `.body`~~ | → `message_key` + `params` (migration `b3d8f21a6c47`) ; les deux colonnes survivent nullables le temps que la file se draine |
| Prompts IA (Sermon, Mission, Urim) | Sermon **livré en L-3**, Mission **livré en L-4** (avec sa Bible), Urim hors périmètre (verrou D) |
| Bible | ~~LSG 1910 seule~~ → **WEB ajoutée en L-4** (`ScriptureLibrary`) ; dataset complet à construire, extrait dev en attendant |
| Jetons grec/hébreu d'Urim | **442 889, épinglés sur les `verse.id` de la LSG** |

**Le fait le plus important du tableau :** la fondation multilingue a été posée au M0 puis
laissée débranchée. On ne construit pas un étage neuf — on raccorde une colonne morte.

---

## 2. Les quatre verrous

**A. La langue vit à deux étages.** `tenants.language` = la langue de l'**église** (défaut, déjà
là). `accounts.language` **nullable** = le choix de la **personne**, qui gagne quand il est posé.
Résolution en un seul endroit : *personne → église → `fr`*.

> Pourquoi deux : à Abidjan, un membre anglophone dans une église francophone existe — et
> l'inverse aussi. Une langue par tenant seule ferait de ce membre un mal-servi permanent.
> `NULL` n'est pas un défaut : il veut dire *« je suis la langue de mon église »*, y compris
> quand elle change.

**B. Le serveur traduit ce qu'il pousse ; le client traduit ce qu'il affiche.** Voir §0.

**C. Le contenu humain n'est pas traduit.** Ni à l'écriture, ni au rendu, ni par l'IA.

**D. Urim reste francophone, et le dit.** Voir §5 — c'est un mur mesuré, pas un oubli.

*Ces quatre verrous sont ma recommandation, posée pour être contredite : le doc bouge avant
que le code ne bouge.*

---

## 3. Les sept lots, dans l'ordre

### L-0 — le porteur de la langue ✅ **livré (16/08/2026)**
`accounts.language` nullable (migration `a7c1e04b93d5`), l'objet-valeur
[`Locale`](../app/_shared/domain/locale.py) (`fr` | `en`, tolérant à l'entrée), le port
`LocaleResolver` et son unique adaptateur
[`SqlLocaleResolver`](../app/contexts/iam/infrastructure/persistence/locale_resolver.py).
Aucun texte n'a bougé.

**Trois choses décidées en écrivant, qui ne sont pas des détails :**

- **`parse_locale` rend `None`, pas le défaut**, quand la valeur n'est pas une langue que Dorea
  parle. Si une valeur illisible rendait déjà `fr`, la chaîne s'arrêterait au premier maillon et
  l'église ne serait **jamais** consultée : un compte portant `''` ou `'es'` tomberait en
  français au lieu d'hériter de son église anglophone. Le défaut n'est appliqué qu'au bout.
- **`resolve_many` est la méthode abstraite, `resolve` le confort.** Le fan-out d'une annonce
  à toute une église demande plusieurs centaines de langues d'un coup : rendre la méthode
  unitaire portante aurait rendu le N+1 possible. Une jointure externe, une requête.
- **Rien ne lève.** Compte inconnu, valeur illisible, personne sans église → `DEFAULT_LOCALE`.
  Le premier client est la notification, *best-effort et jamais bloquante* : une langue
  introuvable doit faire partir la push en français, pas l'empêcher de partir.

*Vérifié :* 26 tests dédiés, dont l'anglophone dans une église francophone, l'église quittée
qui cesse de parler pour lui, et le compte inconnu qui ne lève pas.

### L-1 — le catalogue ✅ **livré (16/08/2026)**
[`app/_shared/messages.py`](../app/_shared/messages.py) : 18 clés, 2 langues, une fonction
`render`. `PushNotification` porte désormais **une clé et des paramètres** ; le rendu descend
dans [`PushNotifier`](../app/contexts/notifications/application/push_notifier.py), une fois par
langue présente parmi les destinataires. `scheduled_notifications` stocke la clé
(migration `b3d8f21a6c47`). Les 14 points d'appel sont convertis.

**Quatre choses tranchées en écrivant :**

- **`tokens_for_accounts` → `tokens_by_account`.** Le dépôt rendait un sac de jetons anonymes ;
  impossible de savoir qui lit quoi. C'était *la* raison structurelle pour laquelle une push
  n'avait qu'un texte.
- **Deux clés là où une f-string suffisait.** `EVENT_TOMORROW` / `EVENT_TOMORROW_AT`, et
  `APPOINTMENT_DECLINED` / `..._WITH_NOTE`. Le tiret qui sépare un titre d'un lieu est de Dorea,
  pas de l'auteur : laissé au point d'appel, il aurait été introuvable en anglais. Même raison
  pour le défaut de refus, que le mot du pasteur remplace quand il en a écrit un.
- **Les lignes déjà en file ne sont pas perdues.** Elles portent leur phrase et aucune clé :
  plutôt que de la deviner par expression régulière, `title`/`body` deviennent nullables et le
  dispatcher sait lire les deux formes (`PushNotification.rendered`). La file se draine en 24 h
  au plus, après quoi une migration de nettoyage supprimera les deux colonnes.
- **Un paramètre manquant fait taire un groupe de langue, pas la publication.** Le rendu est
  sous la même garde best-effort que l'envoi ; c'est le test de structure du catalogue qui
  attrape la dérive en amont.

*Vérifié :* le cas fondateur (deux membres d'une même église, l'un `fr` l'autre `en`, une seule
notification, deux textes), le titre humain qui traverse les deux langues intact, un titre
contenant `{}` qui n'est pas réinterprété, la ligne d'avant le bilingue qui part avec son texte,
et [`tests/test_message_catalog.py`](../tests/test_message_catalog.py) qui refuse une clé
incomplète ou deux langues qui n'attendent pas les mêmes paramètres.

### L-2 — OTP & messagerie
Brancher `TemplateRef.language` sur la langue résolue ; `whatsapp_otp_language` cesse d'être un
réglage global. `_SUBJECT` / `_BODY` de [`otp_delivery.py`](../app/contexts/auth/infrastructure/otp_delivery.py)
et `_TEXT` de [`otp_sender.py`](../app/contexts/messaging/application/otp_sender.py) passent au
catalogue.

> ⚠️ **À lancer dès aujourd'hui, hors code :** un modèle WhatsApp est **approuvé par langue**
> chez Meta. Tant que `dorea_otp` n'est pas approuvé en `en`, ce lot n'a rien à servir. Le délai
> est fournisseur, pas développeur.

### L-3 — l'IA dans la langue du lecteur ✅ **livré (16/08/2026)**
Le digesteur de sermon porte **deux consignes système entières** (`_SYSTEM_BY_LOCALE`) au lieu
d'un prompt français où l'on aurait remplacé « en français ». La consigne est ce qui protège le
pasteur — *« n'invente aucune doctrine »* — et elle doit être lue dans la langue où le modèle
travaille, pas traduite au vol par lui.

**La règle de langue n'est pas celle des push, et c'est le cœur du lot.** Un digest est écrit
**une fois, gelé à l'approbation, lu par toute l'assemblée** : il n'a qu'une langue possible,
celle du culte qui a été prêché. D'où `LocaleResolver.resolve_tenant` — la langue de l'**église**,
jamais celle du pasteur. Un pasteur qui met son compte en anglais ne fait pas basculer en anglais
le résumé d'un culte tenu en français, pour tout le monde.

Le repli `KeywordSermonDigester` **n'était pas sans langue**, contrairement à ce que ce document
affirmait : il découpe le sermon (donc résumé et pastilles parlent déjà la langue du pasteur),
mais il pose une question de son cru — *« Qu'est-ce qui t'a le plus parlé dans ce message ? »*.
Elle est entrée au catalogue (`SERMON_FALLBACK_QUESTION`), pour que la règle reste vraie sans
exception : *aucune phrase de Dorea ne vit hors du catalogue*.

**Deux prompts, pas trois.**

- **Urim** est hors périmètre par le verrou D — le doc se contredisait en le listant ici.
- **Mission** ❌ **n'appartient pas à ce lot, et c'est un vrai constat, pas un report.** Son
  prompt dit *« Donne le nom du livre en français »*, mais ce n'est **pas** une langue
  d'interface : ce nom est la **clé de jointure** avec le dataset LSG
  (`VerseReference.key` → `normalize_book` → `{"Jean 3.16": …}`). Le résolveur ne produit
  aucune prose — l'IA retrouve une référence, la Bible donne le texte. Traduire ce prompt sans
  dataset anglais ferait résoudre « John 3:16 » puis échouer la recherche de texte :
  `VerseTextUnavailableError` là où l'anglophone recevait au moins une carte française.
  **Ce prompt bouge avec L-4, ou il ne bouge pas.**

*Vérifié :* le digest écrit dans la langue de l'église et non du pasteur, le montage sans
résolveur qui retombe au défaut sans lever, et le repli sans IA qui pose sa question en anglais
tout en rendant le sermon intact.

### L-4 — la Bible anglaise (Mission) ✅ **livré (16/08/2026)**
**World English Bible**, domaine public. Choix tranché contre la KJV : les deux sont libres, mais
la carte est le premier texte biblique que Dorea met sous les yeux de *quelqu'un du dehors*, et
l'anglais de 1611 met une distance là où l'on tendait la main. Basculer reste une ligne de
configuration.

**L'organe neuf est [`ScriptureLibrary`](../app/contexts/mission/application/ports.py)**, et il
existe pour empêcher un défaut précis : *un prompt anglais devant une Bible française*. Le nom de
livre que rend l'IA n'est pas un libellé, c'est la **clé** de recherche du texte — « John 3:16 »
cherché dans un index français ne trouve rien, et l'anglophone perdrait la carte française qu'il
avait avant le bilingue. `serving()` tranche donc **une** langue, et elle vaut pour le prompt
*et* pour la Bible. Elle n'est jamais devinée deux fois.

**Le repli est un service dégradé, pas une panne.** Une langue sans Bible retombe sur le
français — dès le prompt, pas après. La carte sort, dans la mauvaise langue, ce qui vaut mieux
qu'une erreur.

**La langue d'une carte est celle du membre qui invite.** Le chercheur n'a pas encore de compte
au moment où elle est composée : il n'y a personne d'autre à qui demander, et c'est de toute
façon l'inviteur qui sait à qui il tend la main.

⚠️ **Le dataset complet reste à construire** — `scripts/build_web_dataset.py` l'attend, comme
son jumeau français attend `data/ls1910_raw.json` :

```bash
curl -o data/web_raw.json https://api.getbible.net/v2/web.json && python scripts/build_web_dataset.py
```

Sans lui, `web_dataset_path` est vide et Mission sert l'**extrait dev de huit versets**. La carte
fonctionne ; sa couverture est celle d'un extrait, et rien ne le signale — d'où la règle : le
`data/web.json` produit **se versionne**, comme son jumeau français. Seule la source brute reste
hors dépôt (`data/*_raw.json` est déjà ignoré). Le script échoue bruyamment si la source renomme
un livre ou si le compte de chapitres bouge — même garde que côté français.

*Vérifié :* les deux Bibles qui ne répondent pas aux mêmes clés, la carte qui interroge la Bible
dans la langue de son prompt, la bascule qui se fait **avant** le résolveur, et une bibliothèque
sans langue de repli qui est refusée à la construction.

> Pourquoi domaine public, encore : c'est la raison exacte qui a fait choisir la LSG 1910
> ([`scripture_lsg.py:6`](../app/contexts/mission/infrastructure/scripture_lsg.py)) — les
> traductions modernes sont sous copyright, dans les deux langues.

### L-5 — la surface de choix ✅ **livré (16/08/2026)**
`PUT /me/language` — `{"language": "en"}`, `{"language": "fr"}`, ou `{"language": null}`. Et
`GET /me` rend désormais **deux** champs : `language` (mon réglage) et `resolved_language` (ce
que Dorea utilise réellement).

**Pourquoi deux champs et pas un.** Sans le premier, l'écran de réglage ne sait pas quelle case
cocher. Sans le second, *« je n'ai rien choisi »* se confond avec *« on m'a mis en français »* —
et un anglophone dont l'église vient de basculer en anglais ne comprendrait pas pourquoi
l'application a changé de langue toute seule.

🔴 **`null` est une réponse, pas un champ oublié.** C'est *« je suis la langue de mon église »*,
et il faut pouvoir y **revenir** après avoir choisi l'anglais. Un `COALESCE` bien intentionné
dans l'écriture, ou une écriture sautée quand la valeur est nulle, rendrait le premier choix
définitif — et personne ne s'en apercevrait avant qu'un membre demande pourquoi il ne peut plus
revenir en français. Le champ est donc obligatoire dans le corps, avec `null` permis.

Le service **refuse** deux choses, comme `SetMyBirthday` : poser la langue de quelqu'un d'autre,
et toucher `tenants.language` — changer la langue de l'église est un acte de gouvernance, sur une
autre surface.

*Vérifié :* le retour à `null` qui rend la parole à l'église, le réglage `null` qui suit l'église
**après coup** quand elle bascule, l'écriture qui ne touche ni l'église ni le compte du voisin,
et le profil qui rend les deux moitiés.

### L-6 — le libellé que Dorea écrivait **en base** ✅ **livré (16/08/2026)**
`title="Culte"` dans [`culte_attendance.py`](../app/contexts/sermon/infrastructure/culte_attendance.py) —
la seule voix de Dorea qui ne passait pas par une notification mais par une **ligne de table**.
Une église anglophone lisait « Culte » dans son historique de présence, et aucun rendu ne pouvait
le rattraper : la ligne existait déjà.

**La solution attendue n'était pas la bonne.** Ce document prévoyait d'y écrire une *clé de
catalogue* et de rendre à la lecture dans quatre chemins. En regardant, « Culte » n'était pas un
titre du tout : c'était **le mot français pour le type `service`**, que la ligne portait déjà.
Il n'y avait donc rien à traduire — seulement à cesser d'écrire deux fois la même chose.

`title` redevient ce qu'il est : **le nom qu'un humain donne lui-même** (« Culte de Pâques »,
« Cellule Bethel »). Une rencontre sans autre nom que son type porte `NULL`, et le client la
nomme dans la langue de son lecteur — exactement la règle du verrou B, celle des erreurs de
l'API. Aucun catalogue, aucune clé, aucun rendu serveur.

**Ce qui a vraiment bougé** : `type` voyage désormais **avec** `title` partout où le titre
voyage (`SelfCheckInDTO`, `TrajectoryPointDTO` et leurs schémas). Sans lui, un titre nul serait
une rencontre sans nom. Et la migration `c4e9a72b18f3` remet à `NULL` les lignes déjà écrites.

*Le contrat n'a pas changé* : `title` était **déjà** nullable et optionnel à la création — les
clients savent depuis toujours vivre sans.

*Vérifié :* contre une vraie base plutôt qu'un faux (un faux aurait accepté n'importe quel
titre) — la rencontre créée ne porte aucun mot d'aucune langue, et le get-or-create de
DOREA-009 tient toujours, le titre n'ayant jamais fait partie de sa clé.

---

## 4. Le catalogue — inventaire exhaustif

18 clés à l'origine, 19 depuis L-3 ; ~30 chaînes. Le contenu **humain** reste en paramètre, jamais concaténé dans la phrase.

| Clé | fr (existant) | paramètres |
| :-- | :-- | :-- |
| `announcement.targeted.body` | Une annonce vous concerne. | — *(le titre est celui de l'annonce)* |
| `announcement.broadcast.title` | Nouvelle annonce | — |
| `announcement.consent.title` / `.body` | Une annonce vous concerne / Acceptez-vous qu'elle soit publiée ? | — |
| `appointment.confirmed.title` / `.body` | Rendez-vous confirmé / Votre rendez-vous a été confirmé. | — |
| `appointment.reminder.title` / `.body` | Rappel de rendez-vous / Votre rendez-vous approche. | — |
| `appointment.declined.title` / `.body_default` | Rendez-vous / Votre demande n'a pas été retenue. | — |
| `appointment.relay.title` / `.body` | Rendez-vous / C'est un autre pasteur qui te recevra. | — |
| `appointment.recall.body` | Quelqu'un vous rappelle très vite. | — |
| `event.tomorrow.title` / `.body` | C'est demain / « {title} »{where}. | `title`, `where` |
| `event.participant.title` / `.body` | Nouvelle présence confirmée / Quelqu'un sera présent à « {title} ». | `title` |
| `event.published.title` / `.body` | Nouvel événement / « {title} » | `title` |
| `event.cancelled.title` / `.body` | Événement annulé / « {title} » a été annulé. | `title` |
| `event.removed.title` / `.body` | Événement retiré / Votre événement a été retiré par la modération. | — |
| `mission.card.accepted.title` / `.body` | Une invitation acceptée / {name} a répondu à ton invitation. | `name` |
| `watch.contact_return.title` / `.body` | Un retour ? / As-tu pu joindre {label} ? | `label` |
| `watch.shadow_digest.title` / `.body` | Dorea observe / {count} situation(s) auraient été signalées… | `count` |
| `otp.email.subject` / `.body` — `otp.sms.text` | Votre code Dorea / … est : {code} | `code` — **L-2** |
| ~~`gathering.service`~~ | ~~Culte~~ | **jamais créée** — L-6 a montré qu'aucune clé n'était nécessaire (§L-6) |

Les charges utiles `data` sont **déjà** des codes — `{"type": "appointment"}`,
`{"actions": "reached,not_reached,postponed"}`. Elles ne bougent pas : le client les traduit.

---

## 5. Le mur d'Urim — nommé, pas contourné

Les 442 889 jetons grec/hébreu du corpus sont épinglés sur les `verse.id` de la **LSG**, et
`SCHEMA_DE_REFERENCE = "LSG"` ([`index.py:65`](../app/contexts/urim/infrastructure/corpus/index.py))
sert de **repli increvable** — la garantie qu'aucun pasteur ne tombe sur un mur un vendredi soir.

Une version anglaise crée de **nouvelles lignes de versets sans jetons** : Strong et morphologie
tomberaient à vide, et le repli désignerait une version qui ne porte pas le lexique. Un Urim
anglophone livré dans cet état n'est pas un Urim traduit — c'est un Urim amputé.

**Décision : Urim reste francophone, et l'écran le dit.** Le rendre bilingue demande une table
de correspondance LSG ↔ KJV sur la versification — le schéma
(`CorpusVersificationMapModel`) l'attend déjà, mais c'est un chantier à lui seul, pas un lot
d'ici.

*Mission, Sermon, la Présence, la Veille, les Annonces, les Événements, les Rendez-vous : tout
le reste passe en bilingue.*

---

## 6. Les sept pièges relevés à la lecture

**1. L'outbox fige la phrase.** `scheduled_notifications` stocke `title` et `body` **rendus**.
Un rappel de rendez-vous est planifié des semaines à l'avance — et surtout planifié **avant**
qu'on sache dans quelle langue le lire. La clé va en base ; la phrase naît au dispatch.

**2. Le fan-out est mono-texte.** `Notifier.notify(account_ids, PushNotification)` — un texte,
N destinataires. C'est la signature qui est monolingue, pas les chaînes. Elle doit regrouper par
langue avant de rendre.

**3. Le corps qui mélange deux voix.** `body=f"« {event.title} »"` : la coquille est de Dorea
(traduite), le titre est de l'humain (jamais traduit), et ils sont **collés dans la même
f-string**. Le catalogue prend des paramètres — il ne concatène pas.

**4. Le mot du pasteur, et le défaut de Dorea.** `appointment.decision_note or "Votre demande
n'a pas été retenue."` ([`manage.py`](../app/contexts/appointments/application/commands/manage.py)) :
la note du pasteur passe telle quelle, seul le **défaut** entre au catalogue. Traduire la note
serait franchir la frontière du §0.

**5. ✅ Un libellé français est écrit *en base*.** *(corrigé en L-6 — et pas comme prévu : ce
n'était pas un titre mais le mot français d'un type déjà porté par la ligne.)* `title="Culte"`
([`culte_attendance.py:89`](../app/contexts/sermon/infrastructure/culte_attendance.py)) — un
`Gathering` créé par le code. Ça ne se rattrape pas au rendu : la ligne existe déjà. Proposition :
y écrire une **clé** et rendre à la lecture. C'est le seul endroit trouvé où le produit écrit sa
propre voix dans la base ; à re-vérifier avant L-1.

**6. `whatsapp_otp_language` est un réglage global.** Une seule valeur pour toute la plateforme.
Il devra devenir une **résolution**, et le modèle `dorea_otp` être approuvé en `en` chez Meta
(§L-2) — délai fournisseur.

**7. ~~Le dépôt a cinq têtes Alembic.~~** ❌ **Faux — relevé erroné, corrigé au moment de coder
L-0.** Le comptage avait lu les `down_revision` un par un et ignoré ceux écrits en **tuple**
(les migrations de fusion), ce qui faisait passer quatre révisions déjà absorbées pour des têtes.
Le dépôt a **une seule tête**, `0be963a24a19` — et la base de dev y était bien. Rien à trancher,
rien à fusionner.

---

## 7. Ce qui n'est **pas** dans ce chantier

- Traduire du contenu écrit par des humains (§0).
- Traduire les réponses de l'API (verrou B — elles sont déjà des codes).
- Une troisième langue. Le catalogue est indexé par langue, donc l'ajout est ouvert ; il n'est
  pas visé.
- Les docstrings et commentaires français du code. C'est la prose du dépôt, pas une interface.
- Urim (§5).
