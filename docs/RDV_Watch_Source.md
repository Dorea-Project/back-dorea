# Rendez-vous → Veille — la main levée, et ce qui se passe après

**Statut :** blocs 1 à 4 livrés. Blocs 5 (routage/relais), 6 (cloisonnement) et 7 (second bouton
du Compagnon) à venir.
**Étend :** [RDV_Appointments.md](RDV_Appointments.md) — ne le remplace pas.
**Dépend de :** [Veille_Engine.md](Veille_Engine.md).

---

## 1. Le changement de nature

> **Un rendez-vous demandé est une main levée. L'agenda n'est que ce qui se passe après.**

Le module se terminait sur lui-même : une demande produisait un créneau, et rien d'autre. Les
chemins d'échec disparaissaient — or ce sont eux qui portent le plus d'information.

| Événement | Ce que ça dit | Effet de veille | Destinataire du cas |
|---|---|---|---|
| Demande | Quelqu'un a franchi le pas le plus coûteux | **fait au ledger, aucun cas** | — |
| **Annulé par le demandeur** | Il a demandé de l'aide, puis a reculé | cas ouvert, priorité maximale | **le pasteur du rendez-vous** |
| **Non honoré** | Idem, sans même prévenir | cas ouvert, priorité maximale | **le pasteur du rendez-vous** |
| **Décliné** | Il a demandé, on n'a pas pu. Notre dette | cas ouvert, motif porté | **qui a décliné**, à défaut qui tient l'agenda |
| **Réorienté** | Servi autrement | annoté, change de main | inchangé |
| Honoré | Le contact a eu lieu | annoté — **ne ferme rien** | inchangé |

L'annulation par le demandeur est probablement le signal le plus urgent que le produit sache
produire. Rien d'autre ne dit *quelqu'un a franchi le pas le plus difficile, puis a fait
demi-tour*.

**Pourquoi la demande n'ouvre plus de cas** (30/07/2026). Elle en ouvrait un, sans destinataire —
donc résolu par la cascade du référent, donc le plus souvent le **responsable de cellule**, qui
lisait *« A demandé à rencontrer un pasteur. « … » »*, note comprise. Trois raisons d'y voir un
défaut et non un arbitrage : `RDV_Appointments.md` §1 promet que le sujet n'est visible que du
demandeur et des gardiens de l'agenda ; le cas d'usage le plus légitime était le pire (un membre
en conflit avec son responsable demande le pasteur, et c'est ce responsable qui reçoit le cas) ; et
la règle « un cas sans propriétaire est prenable » en faisait une porte ouverte à tout responsable
de la portée.

Le devoir de répondre à une demande était **déjà** tenu ailleurs — `relay_appointments.py` et
`WatchParam.RELAY_DELAY_HOURS`. Deux mécanismes pour une seule obligation, dont un qui fuitait. Le
fait, lui, reste au ledger : on ne perd ni l'antériorité, ni la narration d'épisode, ni le
déterminisme du rejeu.

Les trois issues d'échec, elles, **nomment leur destinataire** : le pasteur à qui la main avait été
tendue, ou celui qui a effectivement décliné. La source joint l'identité au fait ; l'interpreter
reste pur et ne renvoie qu'un titre de repli (`OwnerKind`), résolu à l'étage 02bis.

---

## 2. Aucun nouveau type de fait

`APPOINTMENT_REQUESTED` existait déjà au registre ; l'état voyage dans le payload. Le greffon le
plus lourd du produit se pose **sans rouvrir le contrat** — et c'est testé.

`fact_id` est dérivé de `(rendez-vous, état)` : rejouer une transition ne duplique rien.

**Le fait est émis à la demande, pas à la confirmation du créneau.** L'information de veille naît
quand quelqu'un demande ; l'enregistrer trois jours plus tard, c'est perdre l'antériorité — la
preuve que le produit a vu venir avant de calculer.

**Un walk-in n'émet rien.** Sans compte, il n'y a pas de sujet de veille. Le rendez-vous existe
quand même, il vit dans l'agenda.

**Poser un créneau ne dit rien au moteur.** C'est notre organisation, pas le mouvement de la
personne.

---

## 3. Ce qui ne ferme jamais un cas

> **Planifier n'est pas rencontrer. Rencontrer n'est pas résoudre.**

- `HONORED` **annote** ; un humain ferme
- `DECLINED` et `ORIENTED` ne ferment rien — ils changent de main
- l'annulation et le no-show **remontent** en priorité maximale

Sans cette règle on obtiendrait un excellent taux de résolution et personne de rencontré — la
même erreur que le retour qui fermait le deuil.

---

## 4. La troisième réponse

`ORIENTED` n'est pas un refus déguisé : *« le pasteur ne peut pas cette semaine, mais quelqu'un
te rappelle demain »*. Le cas reste ouvert et change de propriétaire.

Sans elle, la seule alternative à un créneau serait un « non » adressé à quelqu'un qui vient de
lever la main — et **un rendez-vous décliné est pire que pas de canal du tout**.

---

## 5. L'absence n'est pas un oubli

Deux mécanismes distincts, et les confondre coûte cher :

| | Nature | Traitement |
|---|---|---|
| **Absence** | Prévisible, déclarée | consultée **avant** l'assignation. Zéro attente |
| **Oubli** | Constaté après coup | relais après délai |

`pastor_unavailabilities` porte l'absence déclarée — à ne pas confondre avec `availability_rules`,
qui dit *quand il reçoit*. Sans cette distinction, un pasteur en voyage trois semaines ferait
attendre **chaque** demande le délai de relais complet, alors qu'on savait dès le premier jour
qu'il ne répondrait pas.

Le motif est court et **jamais exigé** : un pasteur n'a pas à justifier son absence pour que le
système sache l'anticiper.

---

## 6. Le pasteur assigné — dérivé, jamais stocké

Même nature que le référent, donc même mécanique. **Aucun champ `assigned_pastor_id`.**

```
override manuel  →  pasteur de la branche  →  pasteur de l'église  →  NULL
```

La branche se lit en remontant le **chemin matérialisé** du groupe primaire, du plus proche au
plus lointain : le pasteur d'annexe l'emporte sur celui de l'église. Le groupe primaire vient du
module Referent — une même personne ne peut pas avoir deux « groupes qui comptent » selon qu'on
cherche un référent ou un pasteur.

La disponibilité est consultée **à chaque étage**. Dans une église à un seul pasteur, la
dérivation renvoie toujours le même : c'est correct, pas dégradé — le mécanisme sert quand
l'église grandit, et il est là avant.

---

## 7. Le routage et le relais

Une demande est **adressée dès sa création**, à quelqu'un de réellement disponible : une absence
déclarée est connue d'avance, donc contournée tout de suite. Le délai de relais ne sert qu'à
constater un **oubli** — qui, lui, ne se déclare pas.

Le worker [relay_appointments.py](../scripts/relay_appointments.py) reprend ce qui attend :

| Situation | Ce qui se passe |
|---|---|
| Moins que le délai | rien — ce n'est pas encore un oubli |
| Un autre pasteur disponible | **relais nominatif**, motif stocké, le membre prévenu une fois |
| Personne, sous le seuil | la demande **reste en tête de file**, jamais silencieuse |
| Personne, au-delà de deux relais | **défaut de couverture** à l'admin — plus un problème de délai |
| Le demandeur s'est retiré du contact | close **en silence** (voir §9) |

Trois règles :

- **Nominatif.** On ne libère jamais une demande, on la transfère. Une demande sans destinataire
  est une demande que personne ne traite, et personne ne s'en aperçoit.
- **Motivé.** Le motif est stocké et voyage avec elle : un pasteur qui reçoit une demande sans
  savoir pourquoi elle lui arrive l'ignore.
- **Borné.** Deux relais infructueux ne sont pas une troisième relance : c'est que l'église n'a
  personne pour recevoir, et ça se dit à l'admin.

Le délai est un **paramètre par église** (`watch_parameters`), pas une constante. 48 h est long
dans une grande église ; dans une petite, deux jours de déplacement ne sont pas un oubli.

---

## 8. Le cloisonnement — ce qui rend le canal privé

| Objet | Visible par |
|---|---|
| La demande **et son motif** | le demandeur, et **le destinataire du routage** — personne d'autre |
| Le créneau confirmé | l'agenda, donc le secrétariat |
| Une demande déclinée ou réorientée | n'entre **jamais** dans l'agenda |

C'est appliqué par le **type de sortie**, pas par un filtrage conditionnel : le secrétariat
reçoit un `AgendaEntryDTO` qui ne **porte pas** `subject`, `note` ni `decision_note`. Un
filtrage s'oublie ; un champ absent ne peut pas fuir.

Et la file des demandes ne s'ouvre par **aucune permission d'église** : c'est le routage qui
décide. Un admin ne voit pas les demandes des autres du seul fait qu'il est admin — sinon le
cloisonnement ne serait qu'une convention.

> **Note de gouvernance.** Le cloisonnement change de fait qui *trie* les demandes : le
> secrétariat ne les voyant plus, il ne peut plus les décliner. Les commandes l'autorisent
> encore techniquement — la visibilité est ce qui applique la règle. Si vous voulez l'inscrire
> aussi dans l'autorité, c'est un prédicat à ajouter sur `decline` et `orient`.

---

## 9. `DO_NOT_CONTACT` — une veille dont on peut sortir

Une demande en attente d'une personne qui a demandé qu'on cesse de la contacter est **annulée
sans notification**. La prévenir serait précisément le contact qu'elle a refusé.

Elle est close sans `by_account_id` : ce n'est pas elle qui annule, donc **aucun fait de veille
n'est émis** — on n'ajoute pas un signal d'urgence à quelqu'un qui vient de demander le silence.

**Son retrait nous interdit d'aller vers elle ; il ne lui interdit pas de venir vers nous.** Une
nouvelle demande de sa part est son propre geste, et elle passe normalement.

---

## 10. Ce qui reste

| # | Bloc | État |
|---|---|---|
| 1 | `pastor_unavailabilities` + `is_available` | **livré** |
| 2 | `resolve_assigned_pastor` (avec `pastor_overrides` réels) | **livré** |
| 3 | États étendus : `ORIENTED`, `NO_SHOW`, annulation attribuée | **livré** |
| 4 | Émission des faits + `AppointmentRequestedV1` | **livré** |
| 5 | Routage, relais nominatif, défaut de couverture | **livré** |
| 6 | Cloisonnement demande / agenda | **livré** |
| 7 | Second bouton du Compagnon | bloqué (Compagnon non construit) |

**Il n'y a pas de surface pour désigner un pasteur.** `pastor_overrides` existe et la cascade le
consulte, mais aucune route ne le remplit. C'est l'écran naturel du défaut de couverture
« aucun relais pastoral disponible » : l'admin y répond en désignant quelqu'un.

**Le membre est prévenu du relais, mais rien ne lui affiche l'engagement de 48 h** au moment de
sa demande. L'engagement porte sur la **réponse**, pas sur le rendez-vous — c'est une phrase à
mettre dans l'écran mobile, pas du backend.
