# Urim — le contrat conversationnel

> **Nature :** contrat d'interface entre le moteur et le client Flutter. Il répond à une seule
> question, et elle décide de tout le reste : *qui écrit la phrase que le pasteur lit ?*
>
> Référence visuelle : `urim_conversation.html`. Les réponses de la maquette sont celles que le
> moteur a réellement rendues sur la saisie « l'amour fraternel ».

---

## 1. Le problème, en une ligne

`StudyView` rend un **état** — `outcome`, `options`, `bearings`, `couples`, `trace`. La maquette
montre une **conversation** — une phrase, son motif, et ce qu'on attend de vous.

Entre les deux, il faut décider quoi dire. Aujourd'hui, personne ne l'a décidé : si le client
s'en charge, alors *« Je lis une intention — et elle a le ton d'un constat sur une assemblée »*
est une chaîne de caractères écrite en Dart.

**Ce serait la pire place possible.** Cette phrase n'est pas de la présentation : elle applique
S19 — *un refus nomme ce qui manque au corpus, jamais ce qui manque au pasteur*. Elle applique
S10 — *on nomme l'effet d'une formulation, jamais l'état de celui qui écrit*. Ces règles ont
coûté des semaines de discussion, elles sont tenues par des tests côté serveur, et elles
dériveraient au premier écran ajouté un vendredi soir.

> **Décision : le serveur rend le tour. Le client rend des blocs. Le client n'écrit jamais une
> phrase que le pasteur lira.**

Corollaire pratique : un correctif de formulation est un déploiement serveur, pas une soumission
au store. Sur un produit dont l'ethos *est* la formulation, ça n'est pas un détail d'intendance.

---

## 2. Le contrat

`StudyView` **ne change pas** — il reste le contrat d'état, et les tests qui le tiennent restent
valides. Le tour vient **en plus**, dans le même corps de réponse :

```jsonc
{
  "id": "…", "outcome": "await_decision", /* …tout StudyView, inchangé… */

  "turn": {
    "say":   "Je lis une intention — et elle a le ton d'un constat sur une assemblée.",
    "why":   "Ni nom de livre, ni phrase des Écritures : une pensée que vous portez.",
    "ask":   "Sur quel axe prêchez-vous ?",
    "expects": "choice",
    "stage_code": "weigh_conviction",
    "signature": "ia-mistral",
    "blocks": [ { "kind": "chips", "…": "…" } ]
  }
}
```

| Champ | Rôle | Nul quand |
| :-- | :-- | :-- |
| `say` | La phrase principale. **Toujours présente.** | jamais |
| `why` | Le filet doré — le motif. | jamais (voir §5) |
| `ask` | La question posée, quand il y en a une. | le tour n'attend rien |
| `expects` | `choice` \| `text` \| `nothing` — ce que la barre de saisie doit permettre | jamais |
| `stage_code` | À renvoyer tel quel dans `POST /studies/{id}/decisions` | jamais |
| `signature` | `ia-mistral`, `relu`, ou `null` — le bandeau du bas | rien de curé n'est montré |
| `blocks` | Le contenu, typé. Liste ordonnée, à rendre de haut en bas. | jamais (peut être vide) |

**`why` n'est jamais nul, et c'est une règle du produit, pas une commodité.** *« Chaque réponse
porte son filet doré. C'est ce qui sépare un atelier d'un oracle. »* Un tour sans motif serait
une conclusion sans provenance — la seule chose qu'Urim s'interdit.

---

## 3. Le catalogue des blocs

Sept types, et **c'est une liste fermée**. Un client qui rencontre un `kind` inconnu affiche le
`say` et le `why`, et ignore le bloc : une version d'app plus ancienne dégrade proprement au
lieu de planter.

### `chips` — un choix qui se touche

```jsonc
{ "kind": "chips",
  "items": [
    { "code": "axe:ecclesiologie", "label": "Ecclésiologie", "hint": "l'Église",
      "origin": "locus", "selected": false, "signature": null }
  ] }
```

Source : `options[]`. `hint` est la glose courte (« Dieu », « le péché »). `origin` sert au
regroupement visuel — la maquette ne mélange jamais un locus et une proposition par le sens.

⚠️ **`signature` dit qui a écrit le LIBELLÉ**, quand ce n'est pas le corpus — `ia-mistral`, le
mot du bandeau. Sur l'écran des dix loci, certains titres sont habillés dans la langue du
pasteur par un modèle (« L'effusion obligatoire » pour la pneumatologie) et les autres portent
celui de la dogmatique ; ils avaient exactement la même apparence. C'est §5.4 appliqué à
l'option — *pour que rien de généré ne se confonde avec une relecture*.

Ne pas la confondre avec `origin` : l'axe vient de la dogmatique dans les dix cas, seul son
habit est généré. Un client qui lirait la signature comme une origine annoncerait au pasteur que
l'axe lui-même est inventé.

> *Les pastilles sont des raccourcis, jamais des barreaux.* Le pasteur peut taper « Ecclésiologie »
> à la main : `expects` vaut `choice`, ce qui **autorise** le texte libre, jamais ne l'exclut.

### `units` — les unités relues, groupées par ce qu'elles font du sujet

```jsonc
{ "kind": "units",
  "groups": [
    { "role": "dominant", "heading": "En fait son sujet",
      "items": [ { "code": "texte:…", "label": "La charité sans hypocrisie",
                   "reference": "Romains 12:9-21", "rationale": "Toutes les injonctions…" } ] },
    { "role": "supporting", "heading": "Le soutient", "items": [ … ] }
  ] }
```

⚠️ **C'est ici qu'un champ manque aujourd'hui** — voir §6, trou 1.

### `bounds` — l'unité contre les bornes du pasteur

Même forme que `chips`, avec `selected` sur l'unité proposée et un `why` de conséquence :
*« Si vous gardez vos bornes, je ne pourrai plus vous alerter sur un risque de proof-texting. »*
C'est un `kind` distinct parce que la conséquence, elle, n'est pas optionnelle à l'affichage.

### `bearings` — ce que le texte porte, et ce qui lui résiste

```jsonc
{ "kind": "bearings",
  "carries": [ { "axis_code": "ecclesiologie", "label": "Ecclésiologie",
                 "dominant": true, "rationale": "…" } ],
  "resists": [ { "axis_code": "soteriologie", "label": "Sotériologie",
                 "rationale": "…", "reference": null } ] }
```

Source : `bearings[]` réparties par `strength` (`resiste` → `resists`), plus
`resisting_elsewhere[]` qui alimente `resists` avec sa `reference`.

**Les deux panneaux sont au même rang visuel.** Un texte qui complique un axe n'est pas un texte
qui s'en tait ; le reléguer en second ferait exactement ce que le produit existe pour empêcher.

### `feasibility` — les couples plan × matière

```jsonc
{ "kind": "feasibility",
  "items": [ { "plan_source": "expositif", "subject_matter": "ethique",
               "feasible": true, "risk": "faible", "rationale": "…" } ] }
```

Source : `couples[]`. **Les refusés voyagent avec les faisables** — les cacher laisserait croire
qu'on n'y a pas pensé.

### `theme` — la proposition, jamais un titre

```jsonc
{ "kind": "theme", "body": "L'amour sans masque — ce que l'Église se doit les uns aux autres" }
```

Le `why` qui l'accompagne dit la règle : *un thème, jamais un titre. Le titre, c'est votre voix.*

### `actions` — les sorties

```jsonc
{ "kind": "actions",
  "items": [ { "code": "elements", "label": "Écrire mes points", "enabled": true },
             { "code": "deck", "label": "PowerPoint", "enabled": false,
               "unavailable_reason": "Le livrable n'est pas ouvert : une citation projetée doit
                                      d'abord être contrôlée." } ] }
```

⚠️ `enabled: false` **porte toujours son motif**. Un bouton grisé muet est un mensonge poli — et
c'est la même règle que les versions indisponibles : *elle informe, elle ne rançonne pas.*

---

## 4. Les six tours de la maquette

| # | Le pasteur | `say` vient de | `blocks` |
| :-- | :-- | :-- | :-- |
| 1 | « L'amour fraternel » | `entry_mode=conviction` + `trace[route_entry]` | `chips` (10 loci) |
| 2 | « Ecclésiologie » | l'étage des unités | `units` |
| 3 | « …, Romains 12:9-21 » | l'étage de bornage | `bounds` |
| 4 | « L'unité » | `resolved` + `version` | `bearings` |
| 5 | « Quel plan… ? » | l'étage de faisabilité | `feasibility` |
| 6 | « Expositif » | l'étage du thème | `theme`, `actions` |

**Le tour 0 n'est pas dans la maquette et il existe :** l'ouverture d'une préparation sans
église (`POST /studies`). C'est le premier écran réel de l'antichambre.

---

## 5. Ce que le contrat garantit, et qu'aucun client ne peut casser

1. **Une ambiguïté revient en 200.** `await_decision` et `refuse` sont des issues, pas des
   erreurs HTTP. Un client qui traiterait `refuse` comme une panne effacerait ce que le produit
   veut montrer.
2. **`why` est toujours là.** Pas de conclusion sans provenance.
3. **`origin` ne se perd pas.** Deux options côte à côte ne valent pas la même chose ; le client
   les groupe, il ne les mélange jamais.
4. **La signature reste affichée.** *Pour que rien de généré ne se confonde avec une relecture.*
5. **Un `kind` inconnu dégrade, il ne plante pas.**

---

## 6. Les quatre trous — ce que la maquette promet et que le moteur ne sait pas encore faire

> **Le territoire est cartographié à côté.** `docs/Urim_Arbre_Conversationnel.md` liste les
> 13 cellules qui rendent un tour, ce que chacune affiche, et comment l'atteindre — et il porte
> les deux murs trouvés en la marchant : la liste épuisée, et le « voici » au-dessus de rien.
> Ce document-ci reste le contrat ; celui-là dit ce que le pasteur reçoit vraiment.

**Trou 1 — l'option ne dit pas sa dominance.** La maquette groupe les quatre unités en *« en
fait son sujet »* et *« le soutient »*. `OptionView` porte `code`, `label`, `rationale`, `origin`
— **et rien qui distingue les deux**. Le client ne peut pas fabriquer ce groupe ; il le devinerait
en lisant le texte du motif, ce qui marche jusqu'au jour où non. *Petit : un champ à ajouter.*

**Trou 2 — ~~la question libre en cours de préparation n'existe pas~~. Bouché.** Voir §9.
`POST /studies/{id}/turns` prend une phrase, et une seule — pas de `stage_code` : c'est ce qui
distingue *parler* de *répondre à un formulaire*.

**Trou 3 — le livrable est verrouillé, délibérément.** Les boutons PowerPoint et fiche de chaire
n'ont aucune route : les étapes 2 à 4 du chantier sont fermées tant qu'une citation projetée
n'est pas contrôlée. Le bloc `actions` les rend donc `enabled: false` **avec leur motif** — c'est
la seule façon honnête de les montrer. *Ne pas ouvrir sans le contrôle de citation.*

**Trou 4 — le micro n'a pas de transport.** `EntryOrigin.DICTATED` existe et sait déjà qu'une
dictée doit se faire **confirmer** là où une saisie tapée ne le fait pas (S36, le micro resté
ouvert sur « Ma voiture 406 »). Mais rien ne transporte de l'audio. Deux lectures possibles : le
client transcrit en local et poste du texte avec `entry_origin=dictated` — faisable tout de
suite — ou le serveur transcrit, ce qui est le chantier capture. *Le premier suffit pour la
maquette.*

---

## 7. Le vocabulaire d'intentions

L'aiguilleur ne rend **jamais de prose** : un code, d'une liste fermée, comme `axes()` et
`lever()` avant lui. Le vocabulaire fermé n'est pas seulement une garde anti-hallucination —
c'est un **clapet anti-retour** : le modèle n'ayant aucun canal de sortie en texte, rien de ce
que le pasteur confie ne peut ressortir par lui. C'est structurel, pas une politique.

### Ce que l'aiguilleur ne voit pas

**L'ouverture.** Le détecteur d'entrée fait mieux — il croise sur 31 170 versets, lit `Hb 2v29`
et recale « Actes des Apôtres ». L'aiguilleur n'existe qu'à partir du deuxième tour.

**Les réponses à une question posée.** « Ecclésiologie », « L'unité », « Expositif » sont des
**liaisons** vers une option offerte, résolues par comparaison de chaînes. Sur les six tours de
la maquette, **quatre sont des liaisons** : les deux tiers du fil ne coûtent rien et ne peuvent
pas se tromper.

> **La liaison consomme ce qu'elle reconnaît, l'aiguilleur reçoit le reste.** « Expositif.
> Propose-moi un thème. » porte deux gestes ; sans cette règle on en perd un, en silence.

**L'état.** Il ne reçoit que le texte. « Quel plan je peux tenir ? » posé avant qu'un texte soit
résolu part quand même en `interroger_travail`, et le répondeur dit la vérité. Aveugle, il reste
une fonction pure — testable hors rejeu, et sans confidence sur une assemblée.

### Les sept codes

| Code | Le répondeur | État |
| :-- | :-- | :-- |
| `preciser` | options `origin: entree` | ✅ |
| `interroger_texte` | concordance, notes de contexte, motif de l'unité, original | ✅ |
| `interroger_travail` | `couples`, `bearings`, `resisting_elsewhere` | ✅ |
| `demander_production` | thème ✅ / livrable ❌ verrouillé | ✅ |
| `changer_de_sujet` | **propose** une nouvelle préparation | ✅ |
| `hors_champ` | le tour qui redirige | ✅ |
| `indechiffrable` | le tour qui repose le fil | ✅ |

Les sept vivent dans `engine/repondeurs.py`, et trois réponses s'y ajoutent qui ne viennent
d'**aucune** intention — parce que les taire reviendrait à mentir :

| | Quand |
| :-- | :-- |
| `repondre_acquiescement` | « oui » sur une question posée — la liaison le consomme, sans appel |
| `repondre_sans_lecture` | aucun modèle branché : pas de clé, ou quota épuisé (S12/S37) |
| `repondre_panne` | 🔴 le modèle **n'a pas pu** répondre — voir §9 |
| `repondre_reference_introuvable` | le corpus refuse la référence, **avec ses mots à lui** |

La dernière est d'une autre espèce : elle ne dit pas ce qu'Urim est, elle **transporte le verdict
du corpus**. *« Hébreux 2 compte 18 versets »* n'est pas une phrase du produit, c'est une phrase
du texte — et à ce titre elle traverse intacte, comme le motif d'un étage.

**Une intention ne déclenche jamais un acte irréversible — elle propose.** Un aiguilleur
probabiliste n'a aucun pouvoir d'exécution.

**Pas de score de confiance.** Chaque tour montre déjà sa lecture et offre la correction. Et
comme les répondeurs sont déterministes, **une intention mal aiguillée donne une réponse hors
sujet, jamais une réponse fausse** : le mode d'échec est la non-pertinence, pas le mensonge.
C'est ce qui rend l'aiguillage probabiliste acceptable devant eux.

### Le banc — `scripts/urim_banc_aiguillage.py`

38 cas étiquetés, **avec leur provenance**. `reel` = écrit par un vrai pasteur ; `construit` =
écrit par moi. Le score est rendu séparément, et c'est ce qui rend le banc honnête : *nous
n'avons presque aucune saisie réelle de deuxième tour*, puisque tout ce que le Pasteur X a écrit
sont des **ouvertures**, que l'aiguilleur ne voit jamais.

**38/38 sur `mistral-small`.** Deux confusions que j'avais prédites ne se sont pas produites :
`interroger_texte` contre `interroger_travail` tient à 14/14, y compris sur le cas que j'avais
moi-même marqué ambigu.

**Ce que le banc a trouvé, et que je n'avais pas vu.** « Prie pour moi » partait en
`indechiffrable`. Répondre *« je n'ai pas su lire ça »* à un pasteur seul un samedi soir
traiterait une adresse réelle comme un parasite. J'ai élargi `hors_champ` — et le raté s'est
déplacé sur **le cas réel** du micro resté ouvert, que la nouvelle définition avalait.

Le bon partage n'est pas *« ai-je compris ? »* mais **« me parle-t-il ? »**. Une phrase
parfaitement claire sur une voiture à réparer est `indechiffrable` : elle a atterri là par
accident. « Prie pour moi » est `hors_champ` : il vous parle, et on ne sait pas répondre.

Sans la colonne `provenance`, 37/38 aurait ressemblé à un progrès — alors que j'échangeais un
cas inventé contre un cas attesté.

⚠️ **100 % est un avertissement, pas un résultat.** Un banc que son auteur réussit intégralement
est un banc trop facile. Il ne vaudra vraiment que le jour où il portera des dizaines de saisies
de deuxième tour venues de vrais pasteurs — et c'est la première chose à collecter dès qu'un fil
tourne.

---

## 8. Ordre de construction

1. ✅ **Les deux répondeurs manquants** — `hors_champ` et `indechiffrable`.
2. ✅ **Trou 1** — la dominance sur l'option. Sans elle, le tour 2 n'est pas rendable.
3. ✅ **Le champ `turn`** sur les réponses existantes, avec les sept blocs.
4. **Trou 4**, version client : accepter `entry_origin=dictated` sur `POST /studies` (déjà le
   cas) et documenter la confirmation attendue.
5. ✅ **Trou 2** — la question libre (§9).
6. **Trou 3** — pas avant le contrôle de citation.

---

## 9. Le tour de parole — `POST /studies/{id}/turns`

Un champ, `raw_input`, et rien d'autre. **Aucun `stage_code` :** c'est ce qui distingue *parler*
de *répondre à un formulaire*. L'étage, le serveur le connaît ; le faire renvoyer par le client
rendrait la phrase dépendante d'un état qu'il aurait pu manquer.

La réponse est un `StudyView` entier, comme partout. Quand le tour n'a conclu à aucun geste,
l'état n'a pas bougé — c'est `turn.say` qui porte la phrase du répondeur, et **`turn.why` reste
le motif du moteur**. Un tour aiguillé n'a fait avancer aucun étage ; réécrire le motif ferait
passer une réponse de répondeur pour un raisonnement.

### L'ordre, et il n'est pas négociable

    1. le controle de reference  le corpus refuse ? il le DIT — zero appel
    2. la liaison                exacte, deterministe, ZERO appel
    3. l'aiguilleur              un appel, sept codes — si la liaison rend la main
    4. le repondeur              deterministe, selon le code
    5. le tour                   comme partout

🔴 **Un tour qui atteint le modèle alors que la liaison pouvait répondre est un défaut, pas une
inefficacité.** Le scénario du 12/08 : trois refus successifs, neuf appels, dix secondes, rien
appris — et l'aiguilleur ne savait de toute façon pas *quelle* option était visée.

**Une cible sans geste n'est une décision que si le moteur attend une décision.** La liaison est
aveugle à l'issue ; c'est l'orchestration qui tranche, parce que c'est elle qui sait si une
question est posée. Les deux seuls gestes exécutés — décider, écarter — viennent d'elle, qui est
exacte. **Aucune intention n'exécute quoi que ce soit** : `changer_de_sujet` ne ferme pas la
préparation, `demander_production` ne fabrique rien.

### Les deux silences du modèle, qui ne se confondent pas

`MistralAssistant.echecs` est monotone : un 429 rend `None` **exactement** comme un tour non
classable. Servir alors *« je n'ai rien reçu qui concerne la préparation »* à un pasteur dont la
seule faute est d'avoir écrit pendant une coupure serait la seule fois où Urim reprocherait
quelque chose à quelqu'un qui n'a rien fait. On prend donc une photo du compteur avant, une
après — le même geste que le mémo des suggestions.

### Le banc — `scripts/urim_banc_tour.py`

Il mesure la **boucle**, pas l'aiguilleur seul, et rend deux chiffres qui doivent être zéro :

    liaisons manquees          0/21   ← une designation manquee fait agir sur le mauvais objet
    vraies saisies RENVOYEES   0/7    ← on lui dit qu'il n'a rien a faire ici

**Les quatre références attestées du Pasteur X ne coûtent plus un seul appel** : trois désignent
une option, `Hb 2v29` reçoit le verdict du corpus. Le total du banc est exactement son plancher —
un appel par cas d'aiguillage, zéro ailleurs.

Il charge le **vrai corpus** — en fabriquer trois formes de nom à la main ferait passer un banc
pour une preuve. Sans corpus, il le dit et laisse les cas de notation non mesurés plutôt que de
les compter réussis ou ratés.

Le reste est gênant, sans plus : une réponse **à côté** n'est pas un refus, puisque les
répondeurs sont déterministes. Séquentiel et cadencé, avec reprises — *une panne de débit
ressemble exactement à un refus*, et un banc sans cadence rend le verdict le plus flatteur.

**Ce que le banc a trouvé, et que trois relectures n'avaient pas vu.** Deux défauts de la
liaison, tous deux du genre *bon objet, mauvais geste* — le pire mode d'échec de cet étage :

1. **« La charité sans hypocrisie » s'écartait elle-même.** L'intitulé d'unité de la maquette
   contient « sans », un marqueur de retrait. Le geste se cherche désormais **hors de ce qui a
   été désigné** : les mots d'un intitulé appartiennent à l'intitulé.
2. **« un » était lu comme un rang.** Quatre saisies sur vingt et une décidaient une option en
   silence — *« je veux faire un culte sur l'adultère dans »*, *« Propose-moi un theme »*,
   *« y a un risque de proof texting »*, *« attends deux minutes »*. Les cardinaux écrits ont
   quitté la table des rangs ; les ordinaux et les chiffres restent lus.

### La notation du pasteur

`Hb 2v29`, `Jn14v28`, `Eph 1v20-22`, `jn 2:3` — **pas une de ses saisies attestées n'a la forme
`Livre chapitre:verset`**. Le lecteur qui les comprend existait depuis la chaîne de textes
d'appui (`reference_libre`) ; il ne parlait à personne dans le tour, si bien qu'une référence
*affichée à l'écran* partait quand même au modèle.

Il est branché. Reconnaître `Hb` demande les 357 formes du corpus, et la liaison est pure : elle
reçoit donc des `Reference` **déjà lues** et ne compare que des passages. La notation est
absorbée avant d'arriver.

Trois règles le rendent sûr, et chacune coûte des appels plutôt que des désignations inventées :

1. **Le nom de livre doit ouvrir la saisie.** Marc, Actes, Juges et Nombres sont des mots
   français avant d'être des livres : balayer la phrase entière rendrait « Marc a quitté
   l'église » équivalent à une référence. Seuls les **marqueurs de retrait** sont retirés en
   tête — un vocabulaire fermé, jamais de la prose — ce qui fait marcher « non, pas Jn14v28 »
   et pas « prends Jn14v28 ».
2. **Un nom de livre nu ne désigne rien.** `lire` rend volontiers un livre entier (S23), et
   c'est juste à la porte où le pasteur a *déclaré* saisir une référence. Ici, le chapitre est
   exigé — comme pour l'appariement par jetons.
3. **Une seule option visée, ou aucune.** `Jn` désigne quatre livres et `lire` les rend tous
   les quatre parce qu'il refuse de trancher (S24) : **c'est l'écran qui tranche**, et trois
   d'entre eux ne visent rien. Quand plusieurs options restent visées, la liaison rend la main.

Les versets se **recoupent** plutôt qu'ils ne s'égalent : `Ga 5v13` choisit l'unité qui contient
ce verset, là où « Ga 5 » désignerait les trois unités du chapitre et où l'appariement par
jetons prendrait la première.

### Le contrôle de référence

`Hb 2v29` et `Ph 28v9` sont dans les notes du Pasteur X. **Hébreux 2 compte 18 versets ;
Philippiens a quatre chapitres.** Urim savait le dire depuis le premier jour et ne le disait
qu'aux textes d'appui : au tour, la saisie repartait à l'aiguilleur, qui répondait à côté
*sans rien dire de l'erreur de référence*.

Le verdict du corpus est donc rendu au tour, et il passe **avant la liaison** — une référence
que le corpus rejette pourrait quand même désigner une option (`Hb 2v29` tombe dans une option
« Hébreux 2 » affichée en chapitre entier), et décider silencieusement cacherait la seule chose
utile de ce tour. Zéro appel : le corpus sait cela tout seul.

Le motif **traverse intact**, comme le filet doré du tour. *« Hébreux 2 compte 18 versets »* lui
apprend quelque chose ; *« référence invalide »* le laisse chercher — c'est S19, un refus nomme
ce qui manque au corpus, jamais ce qui manque au pasteur. Et *on ne corrige pas* : deviner qu'il
voulait 2:9 serait décider à sa place sur la foi d'une touche voisine.

Deux gardes l'encadrent, et elles disent la même chose de deux façons :

- **Le motif du lecteur n'est jamais rendu.** *« Je ne connais pas de livre nommé "bonjour" »*
  est juste, et absurde : toute phrase ordinaire le déclencherait. Seul le verdict du corpus sur
  un livre **déjà reconnu** sort d'ici.
- **La saisie doit être la référence, et rien d'autre.** « Nombres 500 personnes sont venues »
  est une phrase où un nom de livre passe par hasard ; lui répondre que le chapitre 500 n'existe
  pas serait répondre à une question qu'il n'a pas posée. Le surplus de mots interdit de
  *contredire* — pas de *désigner* : « Romains 12 s'il te plaît » vise bien une option.
  Désigner est réversible, contredire ne l'est pas.
