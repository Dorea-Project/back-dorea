# Urim — spécification de renforcement

> **Origine.** Quatre documents pastoraux réels (3 sermons + 1 manuel liturgique), première
> donnée de terrain du projet. Voir `urim_grammaire_homiletique.md`.
>
> **Objet.** Ce que ces données obligent à changer dans l'architecture, avec les résultats
> attendus et les scénarios qui les prouvent.
>
> **Rattachement.** Extension de `urim_spec_architecture_v2.md` — §8 (sorties constatées) et §7
> (contrat de marqueurs) sont modifiés ; les autres sections restent intactes.

---

## 0. Les cinq renforcements

| # | Renforcement | Corrige | Priorité |
|---|---|---|---|
| **RF1** | Quatre gabarits homilétiques donnent un critère à `shape_homiletic` | Une faisabilité déclarée sans référentiel | 🔴 |
| **RF2** | Le proforma s'arrête là où les notes s'arrêtent | Un livrable que le pasteur n'écrit jamais lui-même | 🔴 |
| **RF3** | Le marqueur d'emplacement généralise le contrat `{{...}}` | Un proforma qui ne sait pas être incomplet volontairement | 🟠 |
| **RF4** | Le réservoir devient l'instrument du gabarit onomastique | Un réservoir aux contours vagues | 🟠 |
| **RF5** | Deux livrables dérivés : sujets de prière, pensée directrice | Une seule porte d'entrée par église | 🟢 |

Et une tension non résolue : **T1 — les crochets d'amplification** (§7).

---

## RF1 · Les gabarits homilétiques

### Le défaut corrigé

`shape_homiletic` déclare « faisable » sans référentiel. C'était le maillon mou : la sortie
`sermon` de §8 dépendait d'un jugement qu'aucun objet ne portait.

### Spécification

Quatre gabarits, tirés des documents réels :

| Gabarit | Déclencheur constatable | Ossature |
|---|---|---|
| `expositif` | une péricope bornée par `bound_pericope` | intro → A/B/C sur le mouvement du texte → bascule |
| `narratif_allegorise` | ≥ 3 groupes ou personnages distincts dans le récit | tension résolue → figures typées → application par figure |
| `lexical` | un terme original chargé, à traductions multiples | étude du mot → traductions → **le titre naît de la liste** |
| `onomastique` | un nom ou un motif récurrent ≥ 5 fois dans le canon | étymologie → dénombrement → thèse d'unité → traits |

**Nouvel objet.** `HomileticFit(gabarit, franchi: bool, motif: str)` — un par gabarit, toujours
les quatre, jamais filtrés. Même règle que les dix loci : on montre tout, on n'écarte rien.

### Résultats attendus

| # | Attendu | Interdit |
|---|---|---|
| RF1-A | La sortie `sermon` nomme le gabarit : *« ce texte se travaille bien en expositif »* | Offrir `sermon` en bloc, sans forme |
| RF1-B | Un texte qui ne porte **aucun** gabarit produit un refus **explicable** | « Non faisable » sans motif |
| RF1-C | Les quatre `HomileticFit` sont toujours rendus, franchis ou non | Ne rendre que le meilleur |
| RF1-D | Le gabarit est **proposé**, jamais imposé — le pasteur peut en choisir un autre | Verrouiller la forme |

### Scénario de vérification — **à faire cette semaine**

> **Test D1.** Faire descendre *Odyssée biblique du nom Joseph* dans le moteur.
>
> **Le piège :** ce sermon n'a **aucune péricope bornable** — le nom Joseph traverse la Genèse,
> Matthieu et les Actes. `bound_pericope` n'a rien à borner. Il est pourtant légitime, écrit
> par un pasteur en exercice, et bâti sur une méthode classique.
>
> **Attendu :** `onomastique` franchi, `expositif` non franchi, motif rendu pour chacun.
>
> **Si Urim refuse D1, ce n'est pas D1 le problème.** C'est le test le plus dur que le moteur
> ait rencontré, et il coûte une heure.

---

## RF2 · Le proforma s'arrête où les notes s'arrêtent

### L'observation

D3 s'achève sur « *Ton papa peut t'abandonner —* ». D4 s'achève sur une prière inachevée.
**Les deux s'arrêtent en pleine phrase.** L'atterrissage se fait à l'oral : le pasteur écrit
jusqu'à avoir de quoi partir, puis improvise la fin devant l'assemblée.

### Ce que ça change dans le débat rédiger / développer

Ce n'est plus une position doctrinale, c'est un **constat de pratique**. Le produit ne
s'aligne plus sur un principe défendable, il s'aligne sur ce que font les prédicateurs.

> **La règle.** Le proforma rédige **tout ce qui se rédige** — exégèse, contexte,
> circonstances, mouvements, points, applications. Il pose la **dernière bascule** (l'impératif
> de D1, la prière de D4) et **rend la main**. Il ne referme pas.

### Résultats attendus

| # | Attendu | Interdit |
|---|---|---|
| RF2-A | Le proforma se termine sur une **bascule ouverte**, pas une conclusion refermée | « En conclusion, retenons trois choses… » |
| RF2-B | La dernière section est marquée `a_completer_en_chaire` | Une fin silencieuse qui ressemble à une troncature |
| RF2-C | Le corps est **complet** : rien n'est esquissé sous prétexte d'ouverture | Un proforma maigre déguisé en respect du pasteur |
| RF2-D | Le pasteur peut demander explicitement une clôture rédigée | Lui refuser au nom de la doctrine |

⚠️ **RF2-C est le garde-fou.** Un développeur pourrait lire RF2 comme « écrire moins ». C'est
l'inverse : on rédige davantage, et on s'arrête au bon endroit.

---

## RF3 · Le marqueur d'emplacement

### L'observation

D3 contient « *Témoignage de Mariam — femme togolaise* ». Ce n'est pas du contenu : c'est un
**emplacement réservé à l'oral**.

### Spécification

Le contrat `{{...}}` se généralise à deux familles :

| Marqueur | Résolu par | Non résolu ⇒ |
|---|---|---|
| `{{Rm 8:1}}` | `serve_corpus` | refus visible dans le document |
| `{{témoignage}}`, `{{illustration}}`, `{{appel}}` | **personne — jamais** | un bloc vide **nommé**, attendu |

Le second est un **trou nommé**, pas un défaut. Il donne au proforma une façon d'être
incomplet **volontairement**, ce qui est exactement ce que RF2 demande.

### Résultats attendus

| # | Attendu | Interdit |
|---|---|---|
| RF3-A | Un marqueur d'emplacement rend un bloc vide nommé, visible | Le remplir par une illustration générée |
| RF3-B | Le modèle **peut poser** un emplacement, jamais le remplir | Fabriquer un témoignage plausible |
| RF3-C | Deux usages, un seul contrat | Deux mécanismes parallèles |

⚠️ **RF3-B est le contre-scénario critique.** Un modèle à qui on montre « Témoignage de Mariam,
femme togolaise » inventera une histoire de femme togolaise. Ce serait un faux témoignage
prononcé en chaire. **Contrainte, pas consigne.**

---

## RF4 · Le réservoir, instrument de l'onomastique

### Le recadrage

J'ai soutenu que la similarité cosinus ne détecte pas la contradiction. C'est vrai, et AS12
tombe pour cette raison. Mais D1 montre ce que le cosinus détecte **très bien** : la
**récurrence d'un motif à travers le canon**.

C'est un travail que ni le corpus curé ni Mistral ne font. Le réservoir cesse d'être un
enrichisseur vague des étages 2 et 3 : il devient l'**instrument** d'un gabarit précis.

### Résultats attendus

| # | Attendu | Interdit |
|---|---|---|
| RF4-A | Une requête onomastique rend les occurrences **et** les parallèles de motif | Une simple concordance lexicale |
| RF4-B | Les candidats arrivent **sans force** — `BearingSite` qualifie | Marquer `resiste` sur un score |
| RF4-C | Rejeu exact : même `embedding_ref` + `corpus_version` ⇒ même ordre | Index ANN |
| RF4-D | Réservoir éteint ⇒ `onomastique` non franchi, motif rendu | Un refus sec |

---

## RF5 · Les deux livrables dérivés

### L'observation

Le manuel liturgique (D2) formule deux demandes explicites, **récurrentes chaque semaine** :

- *« Sujets de prière **formulés en rapport avec le message donné** »* — deux fois dans le
  document.
- *« Lire un texte biblique et en tirer une **pensée** autour de laquelle se déroulera la
  rencontre. Le dirigeant devra rappeler cette pensée tout le long. »*

### Pourquoi c'est stratégique et pas seulement utile

La **pensée directrice** sert le *dirigeant de réunion*, pas le prédicateur. C'est une seconde
porte d'entrée individuelle dans la même église, gratuite, sans passer par le pasteur.

La slide 2 dit que Dorea ne s'achète pas seul, faute de pouvoir entrer sans décision
collective. Voici un **second compte flottant** qui s'installe seul, sur un besoin
hebdomadaire, chez un utilisateur différent.

### Résultats attendus

| # | Attendu | Interdit |
|---|---|---|
| RF5-A | Les sujets de prière **dérivent** du proforma, jamais générés à part | Une liste générique de prières |
| RF5-B | La pensée directrice tient en **une phrase** | Un paragraphe |
| RF5-C | Les deux sont disponibles au **palier 1** — ils dérivent de l'état établi | Les rendre dépendants du modèle |
| RF5-D | Le dirigeant de réunion accède à la pensée **sans compte pasteur** | Exiger une préparation partagée |

---

## T1 · La tension non résolue — les crochets d'amplification

### Le fait

D3 et D4 citent avec des gloses **dans le verset** :

- *« sauve-nous **[de la mort]** »*
- *« Je ne vous laisserai pas orphelins **[sans confort, dans le deuil, et sans défense]** »*
- *« Je suis le **[seul]** chemin, la **[véritable]** vérité »*

Ce n'est pas la Louis Segond 1910. Ces pasteurs lisent un texte **amplifié**.

### La tension

| Position | Argument | Coût |
|---|---|---|
| **L'amplification reste en note** | `serve_corpus` demeure la seule source du texte servi ; le verset n'est jamais réécrit | Le proforma sera plus **sec** que ce que ces pasteurs utilisent déjà |
| **L'amplification entre dans le verset** | La forme correspond à leur pratique observée | `serve_corpus` n'est plus la seule source ; l'invariant I13 s'affaiblit |

### Piste de sortie

Une **troisième forme** : le texte servi reste la LSG nue, et l'amplification s'affiche **au
survol ou en incise typographiée**, tirée des `ContextNote` curées. Visuellement au plus près
du verset, structurellement à côté.

Ce n'est pas une esquive : c'est exactement ce que produit `load_context`, présenté autrement.

> ⚠️ **Décision doctrinale — non déléguable.** C'est le seul point où les données de terrain
> poussent contre l'architecture. À trancher avant le lot 6.

---

## Traçabilité et séquence

| Renforcement | Touche | Lot | Effort |
|---|---|---|---|
| RF1 | `shape_homiletic`, §8 | nouveau lot 8 | 3 j |
| RF2 | rédaction du proforma | lot 6 | inclus |
| RF3 | contrat de marqueurs, §7 | lot 6 | +1 j |
| RF4 | réservoir | lot 5 | inclus |
| RF5 | livrables dérivés | nouveau lot 9 | 2 j |
| T1 | décision fondateur | — | avant lot 6 |

**Nouveaux invariants** (suite de §12) :

| # | Invariant |
|---|---|
| I19 | Les quatre `HomileticFit` sont toujours rendus, franchis ou non |
| I20 | Un marqueur d'emplacement n'est **jamais** rempli par le modèle |
| I21 | Le proforma ne referme pas ; sa dernière section est marquée `a_completer_en_chaire` |
| I22 | Sujets de prière et pensée directrice sont disponibles au palier 1 |

---

## Le premier pas

**Faire descendre D1 dans le moteur.** Une heure. C'est le seul point de ce document qui soit
une vérification plutôt qu'une décision, et il conditionne RF1 tout entier.
