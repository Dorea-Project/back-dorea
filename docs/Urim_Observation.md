# Urim — ce qu'il a le droit d'observer d'un pasteur

> **Nature :** liste fermée, à verrouiller avant construction. Elle répond à une question qui
> paraît technique et ne l'est pas : *que peut-on dire à quelqu'un sur sa propre manière de
> travailler, sans le juger, et sans devenir l'amplificateur de ses habitudes ?*
>
> **Ce n'est pas la veille.** La veille observe des membres, avec un plancher de cinq personnes
> gravé dans un `CHECK`. Ici le sujet est **n = 1 par construction** : un pasteur, son propre
> travail, montré à lui seul. Aucune des protections de la veille ne s'applique — il en faut
> d'autres.

---

## 1. Le piège, avant les règles

Reconnaître le style **pour le servir**, c'est amplifier l'habitude.

Un pasteur prêche thématique avec un risque de proof-texting élevé. Si Urim apprend qu'il
« préfère le thématique » et le lui propose en premier, Urim devient l'amplificateur exact de ce
contre quoi il est bâti. Un logiciel qui s'adapte à vous vous aplanit le chemin ; le métier
d'Urim est de mettre le texte qui résiste **en travers** de ce chemin.

> **Le style se reconnaît pour être nommé, jamais pour être servi.**

Le précédent est déjà dans le code : `recently_preached_axes` croise l'axe avec l'historique de
l'auteur **pour éviter la répétition**. Miroir, pas domestique. C'est le patron.

---

## 2. Les sept règles

**R1 — Cela ne se dit qu'à lui.** Aucune route, aucun agrégat, aucun écran de backoffice, aucune
remontée à l'église ni à la dénomination. Le sujet est n = 1 : il n'existe aucune façon de
l'agréger sans désigner quelqu'un. *« Votre pasteur n'a pas prêché l'Ancien Testament depuis huit
mois » dans une console d'église serait une arme.*

**R2 — On compte, on n'interprète pas.** *« Vous n'avez pas prêché l'Ancien Testament depuis huit
mois »* est un fait sur le registre. *« Vous évitez l'Ancien Testament »* est une affirmation sur
lui. *« Vous préférez le thématique »* est un trait de caractère. Seule la première est permise —
c'est S10 transposé : on nomme l'effet, jamais l'état de celui qui écrit.

**R3 — Toute observation doit être auditable.** Il doit pouvoir demander *« lesquels ? »* et
recevoir la liste des dimanches qui la fondent. Une observation qu'on ne peut pas vérifier est
une accusation. Conséquence d'implémentation : chaque observation transporte ses lignes.

**R4 — Ce qui n'est pas comptable ne s'observe pas.** Pas de score, pas de modèle, pas
d'inférence de style. Même verrou que le moteur de veille.

**R5 — Jamais de comparaison à d'autres.** Ni moyenne, ni classement, ni « les pasteurs comme
vous ». Un chiffre qui situe une personne par rapport à d'autres est un chiffre qui fait honte.
Il ne se compare qu'à **son propre registre**.

**R6 — Une observation se dit une fois.** Répétée chaque semaine, elle passe de miroir à
rengaine. Elle est donc datée et acquittée, et ne revient pas tant que le fait qui la fonde n'a
pas changé.

**R7 — Un socle de données, sinon rien.** Sous **huit** dimanches enregistrés, Urim n'observe
rien du tout. *« Vous n'avez jamais prêché l'eschatologie »* dit à quelqu'un qu'on connaît depuis
trois semaines n'est pas une observation, c'est une ignorance déguisée en constat.

---

## 3. La liste fermée

Huit observations. **Rien hors de cette liste ne s'affiche**, et toute addition future passe par
ce document — la même discipline que la liste blanche des huit types d'événements ecclésiaux,
qui est *fail closed* pour la même raison.

| Code | Ce qui est compté | Moment |
| :-- | :-- | :-- |
| `testament_absent` | Aucun sermon d'un testament depuis N mois | ouverture |
| `livre_revisite` | Retour sur un livre déjà prêché cette année | ouverture |
| `axe_repete` | Même locus doctrinal N dimanches d'affilée | ouverture |
| `plan_repete` | Même source de plan N fois d'affilée | ouverture |
| `matiere_repetee` | Même matière N fois d'affilée | ouverture |
| `appuis_d_un_testament` | La chaîne convoquée ne puise que d'un côté | chaîne close |
| `appuis_d_un_auteur` | Tous les appuis du même auteur biblique | chaîne close |
| `references_introuvables` | Plusieurs références saisies ce mois n'existent pas | chaîne close |

Toutes sont des lectures pures de `urim_preached`, de `urim_preparation` et de
`urim_preparation_support` — **aucune colonne nouvelle**. L'index
`(author_id, book_id, start_ch)` existe déjà sur `urim_preached` et n'est lu par personne :
quelqu'un avait prévu la question sans jamais la poser.

**`references_introuvables` se dit des notes, pas de l'homme.** *« Vos notes portent trois
références que je n'ai pas trouvées »* — jamais *« vous vous trompez de références »*. Le fait est
le même ; l'un rend service, l'autre corrige un adulte.

---

## 4. Deux moments, et rien entre les deux

**`ouverture`** — avant qu'un texte soit retenu. C'est le seul instant où une observation peut
encore changer quelque chose.

**`chaîne close`** — quand il a fini de convoquer ses appuis. L'observation porte sur ce qu'il
vient de construire.

**Jamais pendant la préparation.** Un pasteur à 21 h un samedi ne veut pas savoir qu'il n'a pas
prêché l'Ancien Testament depuis huit mois : il veut son sermon. Une observation servie à ce
moment-là est du bruit, et au mieux un reproche.

---

## 5. Ce qu'Urim n'observera pas — et pourquoi

Cette liste vaut la première. Ce sont toutes des choses **mesurables**, dont plusieurs seraient
faciles, et qui sont refusées.

| Refusé | Raison |
| :-- | :-- |
| Le moment où il prépare (heure, jour, veille) | C'est sa vie, pas son travail |
| Le temps passé dans l'application | Compteur d'engagement — invariant déjà verrouillé |
| Le nombre de préparations abandonnées | Rendrait l'hésitation honteuse, alors qu'hésiter est le geste normal |
| Sa régularité, ses semaines sautées | Une absence de sermon a des causes qu'un logiciel ne connaît pas |
| Le contenu de ses points | C'est sa voix ; Urim met en forme, il ne lit pas |
| Toute progression, tout « vous vous améliorez » | Suppose une échelle de qualité qu'Urim n'a pas et ne veut pas |
| Toute comparaison à d'autres pasteurs | R5 |
| Une prédiction de ce qu'il prêchera | Observer le passé est un miroir ; prédire l'avenir est une assignation |

---

## 6. L'architecture, en une ligne

> **La mémoire nourrit les répondeurs, jamais l'aiguilleur.**

Les répondeurs sont déterministes : leur donner l'historique du pasteur est sans risque. Donner
ce même historique au modèle ferait sauter le clapet anti-retour — l'aiguilleur reste aveugle,
il voit une phrase et rend un code.

Le rejeu survit : ces observations sont relues à l'affichage, exactement comme l'horizon des axes
l'est déjà. Elles ne changent pas ce que le moteur calcule.

---

## 7. Ce qui reste à trancher

**Les seuils.** N mois pour `testament_absent`, N dimanches pour les répétitions. Trois d'affilée
est-il un motif, ou faut-il quatre ? Aucune donnée ne permet de trancher aujourd'hui — à poser
bas au début, et à corriger sur des registres réels plutôt que sur une intuition.

**L'acquittement.** R6 exige qu'une observation ne revienne pas. Faut-il un geste explicite du
pasteur (« vu »), ou l'affichage suffit-il à la marquer dite ? Le moteur de veille a déjà tranché
une question de cette forme — sa cadence à trois états, dont un acquitté hors dénominateur. La
même solution vaut sans doute ici.

**Le socle de huit dimanches** est un chiffre posé au jugé. Il ne coûte rien de le monter ; il
coûte cher de le descendre.
