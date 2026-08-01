# Dorea — Système de design & parcours de la veille

**Objet :** les lois d'interface du produit, et les écrans du **workflow de veille** — la chaîne
qui va d'un fait à un contact humain enregistré.
**Complète :** [Mobile_App.md](Mobile_App.md) et [Backoffice_PWA.md](Backoffice_PWA.md), qui
cataloguent les modules écran par écran. Ce document ne les répète pas : il donne le système qui
les gouverne, et décrit les surfaces que la chaîne de veille a rendues nécessaires.
**Dérive de :** [Veille_Engine.md](Veille_Engine.md) — chaque loi ci-dessous est la face visible
d'un invariant du moteur.

---

## 0. Le principe directeur

> **La file d'un responsable doit pouvoir atteindre zéro.**

Tout découle de là. Si Jean ne peut pas vider sa file, il cesse de fermer ; la file gonfle ;
l'outil est abandonné en six semaines — sans que personne ne s'en plaigne. C'est le mode d'échec
unique du produit, et il est silencieux.

Une interface qui donne envie de rester est donc un échec. **On ouvre Dorea pour savoir et agir,
puis on referme.** Le succès se mesure en secondes passées, à la baisse.

---

# PARTIE I — Les lois

Non négociables. Chacune est la contrepartie visuelle d'une garantie du moteur ; les violer en
interface annulerait ce que le code protège.

## L1 — Aucun compteur sur une personne

Jamais « Jean a traité 12 cas », jamais « Marie couvre 78 % », jamais un classement de
responsables. Le moteur refuse d'agréger les gestes par membre (`gestures_count` est **par
cas**) ; l'interface ne doit pas reconstituer ce qu'il s'interdit.

Corollaire : la carte du référent, côté membre, n'affiche **jamais** combien de personnes il
accompagne. Ce serait lui donner une charge à porter et au membre une place dans une file.

## L2 — La priorité vient de l'origine du dire, pas de la gravité

Le tri est : *déclaré > échéance > annonce > absence*, puis **fraîcheur du décrochage**. Jamais
« le plus grave d'abord » — à huit mois la personne est partie, à trois semaines elle se
rattrape.

**Conséquence de design, contre-intuitive et essentielle :** pas de rampe rouge/orange/vert. Une
échelle de sévérité colorée réintroduirait visuellement la gravité que le moteur refuse de
calculer. L'urgence s'encode par la **position dans la file** et par un marqueur d'origine
discret — jamais par la température d'une couleur.

## L3 — Le silence n'est jamais affiché comme une donnée

Aucun écran ne dit « n'a pas ouvert l'application », « n'a pas réagi », « ne dépose plus ».
Le registre de faits ne connaît pas ces formes ; l'interface non plus.

## L4 — « Rien à dire » est un écran légitime, et prioritaire

Une file vide est un **succès**. On l'affiche sobrement, sans suggestion d'autre chose à faire,
sans « pendant ce temps, vous pourriez… ». Un espace vide n'est pas un espace à remplir.

## L5 — La raison est une phrase, jamais un code d'état

Le moteur stocke la raison en clair à l'ouverture et ne la réécrit jamais. L'interface l'affiche
telle quelle. Un responsable lit *« Absente depuis 4 semaines. A annulé le rendez-vous qu'elle
avait demandé. »* — il ne lit pas `ABSENCE_DETECTED · APPOINTMENT_CANCELLED`.

## L6 — Le budget de parole

| Destinataire | Ce qu'il peut recevoir |
|---|---|
| Membre | 2 notifications/semaine max, liées à des **rencontres réelles**, plus les retours de dépôt (une fois, non rafraîchissable) |
| Responsable | Sa file, le rappel post-contact, la demande de retour d'appel — **seule notification autorisée à insister** |
| Pasteur | Un agrégé hebdomadaire, et les escalades |

Aucune relance vers un membre inactif. Jamais.

## L7 — Ce que le système retient, il ne le montre pas

Les cas `HELD` (retenus par le plafond) n'existent pas pour le responsable — c'est tout l'objet
du plafond. Pas même un « 3 autres cas en attente » : ce serait lui rendre la charge qu'on vient
de lui épargner. Ils remontent au pasteur, agrégés, comme mesure de sous-capacité.

## L8 — Le cloisonnement est une propriété de l'interface, pas une politique d'accès

Le secrétariat voit un créneau à organiser. Il ne voit **jamais** une demande de rendez-vous en
attente ni son motif. Si *« on sait qu'il a demandé »* peut circuler dans l'église, le coût
social que le canal venait de supprimer revient par la porte administrative — et tout le
bénéfice est annulé.

---

# PARTIE II — Le système

## Couleur

L'identité est chaude et fixée : **rouge argile `#C0341C` → orange `#EF7E1B` → ambre `#F5A623`**.
Elle porte la marque et l'action principale — rien d'autre.

**Le soin a sa propre famille, froide et sourde, sans échelle de sévérité :**

| Rôle | Ton | Usage |
|---|---|---|
| `care/ink` | ardoise très sombre | texte des lignes de cas |
| `care/muted` | ardoise moyenne, biais bleu | ancienneté, métadonnées |
| `care/rule` | ardoise claire | filets, séparateurs |
| `care/declared` | vert-de-gris profond | marqueur d'origine « la personne a parlé » |
| `care/quiet` | ardoise pâle | fond des lignes, jamais d'alerte |

Le seul accent chaud dans la file est le **bouton d'action** — appeler, écrire. La liste elle-même
reste calme : elle décrit des personnes, pas des incidents.

**Le type d'annonce continue de porter sa couleur** (deuil, joie, appel, prière). C'est une
sémantique de fil, distincte de la sémantique de soin, et les deux ne coexistent jamais dans un
même écran.

## Typographie

Une seule famille humaniste, **système d'abord** — la cible est l'Android d'entrée de gamme en
connexion intermittente, et une police téléchargée qui échoue laisse un écran cassé. La hiérarchie
se fait par graisse et par échelle, pas par famille.

- **La raison** (la phrase du cas) est le texte le plus lisible de l'écran : corps confortable,
  graisse normale, pleine largeur. C'est ce qu'on vient lire.
- **Le nom** est au-dessus, en demi-gras, plus petit que la raison. On ne convoque pas quelqu'un
  par son nom en gros ; on lit ce qui lui arrive.
- **L'ancienneté** est en chiffres tabulaires, sourde, alignée à droite.

## Densité

Deux surfaces, deux régimes — et c'est délibéré :

- **Mobile** — surface de coup d'œil. Espacée, un geste par écran, le pouce fait tout.
- **Backoffice** — surface de travail : la secrétaire y passe des heures. Plus dense, tabulaire,
  raccourcis clavier, mais **jamais** au prix de la lisibilité de la raison.

## Composants propres à la veille

**La ligne de cas** — le composant central du produit.

```
┌────────────────────────────────────────────────────────────┐
│ ▍ Awa Traoré                                       3 sem.  │
│   Absente depuis 4 semaines. A déposé un sujet de          │
│   reconnaissance le 12 avril.                              │
│                                                            │
│   [ Appeler ]  [ WhatsApp ]  [ Qualifier ]            [⋯]  │
└────────────────────────────────────────────────────────────┘
```

- Le filet `▍` à gauche encode l'**origine** (déclaré / échéance / annonce / absence) — une teinte
  sourde, pas une alerte. Doublé d'une forme pour l'accessibilité, jamais couleur seule.
- La raison occupe deux lignes maximum. Au-delà, elle est tronquée — mais la troncature ne coupe
  **jamais** une annotation en son milieu : on affiche la raison d'origine, puis la plus récente.
- L'ancienneté est relative et arrondie (« 3 sem. »), jamais une date brute.
- `[⋯]` ouvre : transférer (nominatif), désigner un référent, fermer avec issue.

**Le chip d'issue** — à la fermeture, les sorties sont des choix côte à côte, de même poids
visuel. Aucune n'est mise en avant : si « la personne est revenue » était le bouton primaire, les
responsables cesseraient de fermer les autres cas, et la file ne se viderait plus.

**La carte du référent** — côté membre, sobre : visage, prénom, rôle, téléphone, « t'accompagne
depuis mars ». Aucune statistique. Aucun bouton d'évaluation. C'est **le seul écran du produit
dont la valeur est d'exister** : *si je disparais, c'est lui qui s'en aperçoit.*

## Motion

Minimale et fonctionnelle : transitions de navigation, retour tactile sur les gestes coûteux.

**Interdit explicite : aucune animation de célébration à la fermeture d'un cas.** Fermer un cas
n'est pas un accomplissement de jeu — c'est parfois constater que quelqu'un a changé d'église.
Une confettis-animation transformerait le soin en score.

`prefers-reduced-motion` respecté partout sur le PWA.

## États vides — les écrans les plus importants

| Écran | Ce qu'on montre |
|---|---|
| File de veille vide | Une phrase sobre. **Rien d'autre.** Pas de suggestion, pas d'illustration festive |
| Aucune annonce | Le fil est calme, c'est normal |
| Pas de référent (membre) | La carte d'accueil ou du pasteur, présentée comme un contact — jamais « vous n'avez personne » |
| Couverture parfaite (pasteur) | « Tout le monde est sous le regard de quelqu'un. » Point |

## Micro-copie — le vocabulaire

| ❌ Jamais | ✅ Toujours |
|---|---|
| « membre inactif », « à risque », « dormant » | « sans nouvelles depuis 4 semaines » |
| « score », « taux », « performance » | rien — on ne le montre pas |
| « relancer », « traiter le dossier » | « prendre de ses nouvelles », « aller vers elle » |
| « tu nous as manqué », « on ne t'a pas vu » | « voici ce qui a été partagé dimanche » |
| « demande rejetée » | « le pasteur ne peut pas cette semaine, mais quelqu'un te rappelle » |
| « 0 cas — bravo ! » | « Rien à signaler cette semaine. » |

Règle générale : **on parle de personnes, jamais de dossiers.** Le mot « cas » n'apparaît pas dans
l'interface — il est un terme de code, pas de produit.

---

# PARTIE III — Le workflow, écran par écran

La chaîne du moteur, et la surface de chaque étage. Ce qui n'a **pas** de surface est dit.

```
CAPTER ──► INTERPRÉTER ──► ARBITRER ──► MATÉRIALISER ──► NOTIFIER ──► CONTACTER ──► RÉSOUDRE
  │                                          │              │            │            │
 mobile                                  (invisible)     budget      boomerang     issues
 membre                                                  de parole
```

## 1. Capter — là où le membre parle

Quatre gestes produisent un fait, tous **explicites**, tous côté membre :

| Geste | Écran | Surface |
|---|---|---|
| Se marquer présent | Présence — code de séance | Mobile |
| Déclarer une absence | Présence — motifs à **taper**, jamais à rédiger | Mobile |
| Demander un rendez-vous | Agenda — aucun motif exigé | Mobile |
| Accepter d'être nommé | Notification de consentement | Mobile |

**L'écran de consentement** est le plus délicat du produit. Une annonce nomme quelqu'un comme
malade ; elle n'existe pour personne tant qu'il n'a pas répondu.

```
┌──────────────────────────────────────────┐
│  Une annonce vous concerne               │
│                                          │
│  Votre cellule souhaite porter votre     │
│  santé dans la prière cette semaine.     │
│                                          │
│  Elle ne sera visible qu'après votre     │
│  accord.                                 │
│                                          │
│      [ J'accepte ]    [ Je préfère non ] │
└──────────────────────────────────────────┘
```

Les deux boutons ont le **même poids visuel**. « Je préfère non » n'est pas un lien discret en bas
de page : refuser doit coûter aussi peu qu'accepter, sinon le consentement n'en est pas un. Et le
refus n'est jamais expliqué à l'auteur — il verra l'annonce non publiée, rien de plus.

## 2 & 3. Interpréter et arbitrer — **aucune surface, et c'est voulu**

Personne ne voit les propositions d'effet, ni ce que l'arbitrage écarte. Exposer « le système a
envisagé d'ouvrir un cas mais ne l'a pas fait » transformerait chaque écran en explication de
soi-même, et rendrait discutable ce qui doit être fiable.

**Seule exception, obligatoire :** ce que le plafond retient remonte au pasteur, **agrégé**, comme
mesure de sous-capacité — « Béthel : 7 situations détectées, 5 transmises. » Jamais au responsable
concerné (L7), jamais nominativement.

## 4. Matérialiser → 5. Notifier

Le responsable reçoit **sa file**, pas une notification par cas. Une notification par cas
transformerait la veille en flux d'alertes, et le plafond n'y suffirait pas.

## 6. Contacter — l'écran Veille et la boucle boomerang

**L'écran Veille est l'écran d'accueil du responsable, pas un onglet.** Sur mobile, il remplace la
carte d'action contextuelle quand il y a quelque chose ; sur le backoffice, il ouvre le rail.

```
┌─ Veille ──────────────────────────────────────────────┐
│                                                       │
│  ▍ Awa Traoré                                 3 sem.  │
│    Absente depuis 4 semaines. A déposé un sujet de    │
│    reconnaissance le 12 avril.                        │
│    [ Appeler ] [ WhatsApp ] [ Qualifier ]        [⋯]  │
│                                                       │
│  ▍ Koffi N'Da                                 5 j.    │
│    A demandé qu'on l'appelle.                         │
│    [ Appeler ] [ WhatsApp ]                      [⋯]  │
│                                                       │
│  … 3 lignes au plus                                   │
└───────────────────────────────────────────────────────┘
```

Cinq lignes maximum. Pas de pagination, pas de « voir tout » : ce qui n'est pas là n'est pas à
faire aujourd'hui.

**La boucle boomerang** — le mécanisme le plus sous-estimé du produit. Dorea n'héberge pas le
contact : on sort vers WhatsApp ou le téléphone, et on ne revient pas. Le signal reste ouvert, le
taux d'ignorés explose — non parce que personne n'a appelé, mais parce que **personne n'est revenu
le dire**. C'est le pire des faux négatifs : celui qui invalide un succès réel.

Trois parades, indissociables :

1. **L'intention s'enregistre au départ.** Au tap sur `[Appeler]`, la tentative est écrite *avant*
   que l'application passe en arrière-plan. La trace de l'effort existe même si le responsable ne
   revient jamais.
2. **Le rappel de retour**, trois heures plus tard : « As-tu pu joindre Awa ? » avec les réponses
   dans la notification — *joint · pas joint · plus tard*. Répondre sans ouvrir l'application.
   C'est la seule notification du produit autorisée à insister.
3. **La reprise au premier plan** : à la réouverture, une invite unique pour les tentatives en
   attente. **Un tap, puis on n'insiste plus de la session** — un rappel qui se répète devient un
   rappel qu'on désapprend.

## 7. Résoudre — les sorties non-succès sont la clé

```
┌─ Comment cela s'est-il terminé ? ─────────────────────┐
│                                                       │
│  [ Repris contact ]      [ Suivie par quelqu'un ]     │
│  [ A changé d'église ]   [ Injoignable ]              │
│  [ Ne souhaite plus être contactée ]                  │
│                                                       │
└───────────────────────────────────────────────────────┘
```

Toutes de même poids. Si le seul moyen de fermer était « la personne est revenue », les
responsables cesseraient de fermer — et la file ne se viderait plus.

« Ne souhaite plus être contactée » mérite d'être visible et facile : **une veille dont on ne peut
pas sortir est un fichage.** C'est ce qui sépare la veille fraternelle de la surveillance.

Fermer est **toujours un acte humain**. Le système ne ferme que deux choses tout seul : ce qu'une
annonce explique, et le retrait d'une personne décédée.

---

## Les surfaces du référent et de la couverture

**Côté membre — la carte.** Visible en permanence dans « Moi ». Elle ne demande rien. Elle
matérialise la promesse : *si je disparais, c'est lui qui s'en aperçoit.*

**Côté pasteur — la couverture, en zones d'aveuglement :**

```
┌─ Qui n'est sous le regard de personne ────────────────┐
│                                                       │
│  23 personnes                                         │
│                                                       │
│  Béthel — 7 personnes, depuis 4 mois                  │
│  Cette cellule n'a pas de responsable actif.          │
│  → [ Nommer un responsable ]                          │
│                                                       │
│  9 personnes sans groupe de suivi                     │
│  → [ Attribuer des référents ]                        │
└───────────────────────────────────────────────────────┘
```

Trois règles :
- **Jamais agrégée par responsable.** « 23 personnes ne sont sous le regard de personne » — jamais
  « Jean couvre 78 % ».
- **La sortie est une désignation, pas un contact.** Un défaut de couverture ne se résout pas en
  appelant : il se résout en nommant quelqu'un. Les boutons le disent.
- **Les trous sont datés.** « Sans référent » n'est pas actionnable ; « depuis 4 mois » l'est, et
  c'est ce qui trie la liste.

## Le rendez-vous — la troisième réponse

Côté gardien de l'agenda, une demande offre **trois** issues, pas deux :

```
[ Proposer un créneau ]   [ Quelqu'un te rappelle ]   [ Décliner ]
```

`Quelqu'un te rappelle` n'est pas un refus déguisé : la demande est **servie autrement**, le cas
reste ouvert et change de main. Sans cette troisième porte, la seule alternative à un créneau
serait un « non » adressé à quelqu'un qui vient de lever la main — et un rendez-vous décliné est
pire que pas de canal du tout.

`Décliner` est en dernier recours, exige un mot, et prévient le référent.

**L'engagement affiché au membre porte sur la réponse, pas sur le rendez-vous :**

> *Quelqu'un te répond sous 48 h* — jamais *le pasteur te reçoit*.

Tenable, honnête, et ne s'effondre pas quand le volume monte.

---

# PARTIE IV — Qui voit quoi

| Objet | Membre concerné | Référent | Responsable de cellule | Secrétariat | Pasteur / Admin |
|---|---|---|---|---|---|
| Sa propre carte de référent | ✅ | — | — | — | — |
| Ce que le moteur sait de lui | ✅ | — | — | — | — |
| Ligne de cas (raison, ancienneté) | ❌ | ✅ | ✅ si propriétaire | ❌ | ✅ escalades |
| Cas retenus par le plafond | ❌ | ❌ | ❌ | ❌ | ✅ **agrégé** |
| Couverture (zones d'aveuglement) | ❌ | ❌ | ❌ | ❌ | ✅ |
| Demande de RDV en attente | ✅ la sienne | ❌ | ❌ | ❌ | ✅ assigné seul |
| Motif écrit par le membre | ✅ | ❌ | ❌ | ❌ | ✅ assigné seul |
| Créneau confirmé | ✅ | ❌ | ❌ | ✅ | ✅ |
| Demande déclinée ou réorientée | ✅ | ✅ notifié | ❌ | ❌ | ✅ |
| Qui a signalé un tiers | ❌ | ❌ | ❌ | ❌ | ❌ **personne** |

La dernière ligne est structurelle : le déclarant n'est jamais joint au cas, dans aucune
projection. Une passation qui laisse une trace de son auteur devient une dénonciation.

---

# PARTIE V — Ce qui n'a pas encore de surface

Honnêteté sur l'état réel : le moteur est en avance sur les écrans.

| Écran décrit ici | État du backend |
|---|---|
| Écran Veille (la file) | Le `Signal` existe ; **aucune route HTTP** dans `watch` |
| Carte du référent | La résolution existe ; aucune route |
| Couverture / zones d'aveuglement | Les trous datés existent ; agrégation par groupe à faire |
| Boucle boomerang | **Rien** — ni `ContactAttempt`, ni rappel de retour |
| Écran de consentement | Route existante (`POST /announcements/{id}/consent`) |
| Trois réponses du RDV | `orient` et `no_show` livrés ; **routage et relais absents** |
| Cloisonnement demande / agenda | **Non implémenté** — le secrétariat voit encore les demandes |
| Compagnon | Non construit, et **ne doit pas l'être** avant que l'escalade fonctionne |

Deux d'entre eux sont des risques produit, pas des manques :

**Le cloisonnement du RDV.** Tant qu'il n'est pas fait, le canal privé ne l'est pas. C'est le seul
point de cette liste qui peut faire du tort à quelqu'un.

**La boucle boomerang.** Sans elle, les métriques mesurent la mémoire des responsables et non la
santé de la veille — et le produit conclura à un échec là où le contact humain a réellement eu
lieu.

---

## En une phrase

**Une interface qui décrit des personnes, jamais des dossiers ; qui propose une action, jamais un
score ; et dont le meilleur écran est celui qui n'a rien à dire.**
