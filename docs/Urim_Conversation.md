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
      "origin": "locus", "selected": false }
  ] }
```

Source : `options[]`. `hint` est la glose courte (« Dieu », « le péché »). `origin` sert au
regroupement visuel — la maquette ne mélange jamais un locus et une proposition par le sens.

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

**Trou 1 — l'option ne dit pas sa dominance.** La maquette groupe les quatre unités en *« en
fait son sujet »* et *« le soutient »*. `OptionView` porte `code`, `label`, `rationale`, `origin`
— **et rien qui distingue les deux**. Le client ne peut pas fabriquer ce groupe ; il le devinerait
en lisant le texte du motif, ce qui marche jusqu'au jour où non. *Petit : un champ à ajouter.*

**Trou 2 — la question libre en cours de préparation n'existe pas.** Le tour 5 montre le pasteur
qui tape *« Quel plan je peux tenir sur ce texte ? »*. Or `raw_input` n'existe qu'à l'ouverture :
après, il n'y a que `POST /decisions` avec un code d'option. C'est le **prompt dynamique** (Lot E),
et c'est le geste le plus naturel une fois le texte sous les yeux. *Moyen, et c'est le vrai
chantier.*

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

## 7. Ordre de construction

1. **Trou 1** — la dominance sur l'option. Sans elle, le tour 2 n'est pas rendable.
2. **Le champ `turn`** sur les réponses existantes, avec les sept blocs.
3. **Trou 4**, version client : accepter `entry_origin=dictated` sur `POST /studies` (déjà le
   cas) et documenter la confirmation attendue.
4. **Trou 2** — la question libre. Il ouvre une surface neuve et mérite sa propre conception :
   *que peut-on demander en cours de préparation, et qu'est-ce que le moteur refuse de répondre ?*
5. **Trou 3** — pas avant le contrôle de citation.
