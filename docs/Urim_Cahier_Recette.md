# Urim — cahier de recette

> **Objet.** Ce que le produit doit faire, mesurable, avec les scénarios qui le prouvent.
> Complément de `urim_spec_architecture_v2.md` : la spec dit *comment*, ce document dit
> *comment on sait que c'est fait*.
>
> **Format.** Chaque scénario porte un **Attendu** et un **Interdit**. L'interdit n'est pas
> décoratif : sur ce produit, ce qui ne doit pas arriver compte autant que ce qui doit
> arriver, et c'est ce qu'un développeur pressé cassera en premier.

---

## 1. Objectifs mesurables

| # | Objectif | Mesure | Cible | Statut |
|---|---|---|---|---|
| O1 | Un tour sans travail n'ouvre pas de préparation | préparations ouvertes / tours de civilité | **0 %** | ✅ atteint |
| O2 | La réponse à une question ne relance pas la chaîne | tours `REPONSE` reclassés en entrée | **0 %** | ✅ atteint |
| O3 | Le vestibule ne bloque jamais | tours sans réponse rendue | **0** | à mesurer |
| O4 | Aucun verset inventé | citations rendues hors `serve_corpus` | **0** | à instrumenter |
| O5 | Le refus est toujours motivé | refus sans phrase | **0** | contrainte de schéma |
| O6 | Le coût par tour ne croît pas avec le fil | tokens envoyés au tour 60 / au tour 3 | **≤ 1,2×** | à mesurer |
| O7 | Latence perçue à l'entrée | p95 vestibule → premier bloc | **< 2 s** | à mesurer |
| O8 | Le produit tient sans modèle | fonctions disponibles au palier 1 | **corpus + 10 étages + réservoir** | à vérifier |

⚠️ Les cibles O6 et O7 sont des paris. À réviser sur usage réel, pas à graver.

---

## 2. Famille A — Le vestibule

### A1 · L'entrée molle

| | |
|---|---|
| **Contexte** | Aucun fil ouvert |
| **Entrée** | « Bonjour » |
| **Attendu** | L'agent se présente, dit ce qu'il fait **et ce qu'il ne fait pas**, pose une question ouverte |
| **Interdit** | Ouvrir une préparation · appeler `serve_corpus` · rendre un bloc `texte` |
| **Invariant** | I1 |

> **Agent :** Bonjour Pasteur. Je suis Urim. Je vous aide à préparer votre message : je
> cherche les textes, je borne le passage, j'éclaire le contexte — mais je ne prêche pas à
> votre place, et je vous rends la main à chaque décision. Vous avez un sujet en tête ?

### A2 · Le piège symétrique

| | |
|---|---|
| **Entrée** | « Bonjour, je veux prêcher sur le pardon dimanche » |
| **Attendu** | `TRAVAIL`. Le sujet descend. |
| **Interdit** | Classer en civilité et jeter le sujet |
| **Invariant** | I1 (borne haute) |

**Pourquoi ce scénario existe :** une règle de civilité trop gourmande crée une panne pire que
celle qu'elle répare — le pasteur salue poliment et son travail est ignoré.

### A3 · La réponse à une question

| | |
|---|---|
| **Contexte** | L'agent vient de demander : « à qui vous adressez-vous dimanche ? » |
| **Entrée** | « aux jeunes de l'assemblée » |
| **Attendu** | `REPONSE`. La préparation en cours avance. |
| **Interdit** | Ouvrir une **nouvelle** préparation · relancer `route_entry` |
| **Invariant** | I2 |

**C'est le défaut le plus grave observé en test.** Sans cette règle, le mécanisme de guidage
est cassé par la porte d'entrée.

### A4 · Le changement de sujet en pleine question

| | |
|---|---|
| **Contexte** | Une question est ouverte |
| **Entrée** | « en fait laisse tomber, je préfère travailler sur la parabole du semeur que Matthieu rapporte au chapitre treize » |
| **Attendu** | `TRAVAIL` — la règle 1 doit **laisser passer** |
| **Interdit** | Forcer en réponse et enfermer le pasteur |
| **Invariant** | I2 (borne haute) |

### A5 · Le déclencheur nu contre le déclencheur porteur

| Entrée | Contexte | Attendu | `carry` |
|---|---|---|---|
| « développe » | préparation en cours | `SUITE` | — |
| « développe » | rien en cours | `INDECIS` + relance | — |
| « explique la parabole du semeur » | quelconque | `TRAVAIL` | « parabole semeur » — **nettoyé** |

**Interdit :** laisser « explique » dans le `carry` et le faire descendre à `route_entry`
comme partie du sujet.

### A6 · Le doute

| | |
|---|---|
| **Entrée** | « hmm » · « bof » · chaîne vide |
| **Attendu** | `INDECIS`, une relance courte |
| **Interdit** | Router vers `conviction` — c'est l'asymétrie du formulaire, elle s'inverse dans le fil |
| **Invariant** | I5 |

---

## 3. Famille B — Les sorties constatées

### B1 · La référence nette

| | |
|---|---|
| **Entrée** | « Romains 8:1 » |
| **Attendu** | Le texte s'ouvre. **Aucune question posée.** |
| **Interdit** | Offrir quatre portes — la saisie n'est pas ambiguë |
| **Invariant** | I7 |

### B2 · Le sujet ambigu

| | |
|---|---|
| **Entrée** | « je voudrais savoir des choses sur la vie de Paul » |
| **Attendu** | L'agent constate un sujet et offre les suites **que les étages autorisent** |
| **Interdit** | Offrir `sermon` si `shape_homiletic` ne déclare pas la faisabilité |
| **Invariant** | I7 |

> **Agent :** La vie de Paul, c'est un vaste terrain. Vous voulez qu'on cherche les textes,
> qu'on en fasse une étude, ou qu'on aille vers le message de dimanche ?

### B3 · La question hors corpus

| | |
|---|---|
| **Entrée** | « que dit la Bible sur le Vatican ? » |
| **Attendu** | Sortie `connaissance`, **marquée non adossée**. L'agent ouvre les textes sur l'autorité dans l'Église, portants **et** résistants au même rang. |
| **Interdit** | Trancher la controverse · rendre un mur · inventer un verset |
| **Invariant** | I7, I18 |

> **Agent :** L'Écriture ne parle pas du Vatican — l'institution lui est postérieure de
> plusieurs siècles. Elle parle en revanche de l'autorité dans l'Église, et ces textes sont
> discutés entre confessions depuis longtemps. Je peux vous les ouvrir, y compris ceux qui se
> répondent mal. Je ne tranche pas entre eux : ce n'est pas mon rôle.

---

## 4. Famille C — Le refus

### C1 · Le refus après investissement

C'est **le scénario qui décide de la valeur du produit**, et le plus dangereux pour la
rétention. La formulation compte autant que le mécanisme.

| | |
|---|---|
| **Contexte** | Quatre tours écoulés. Axe et appuis choisis par le pasteur. |
| **Entrée** | Axe « prospérité promise à celui qui donne », appuis Malachie 3:10, 2 Co 9:6, Ph 4:19 |
| **Attendu** | Refus motivé **texte par texte**, dit dans le fil, avec **trois issues** |
| **Interdit** | Écran d'erreur · code d'état · diagnostic sur le pasteur · fabriquer le plan quand même |
| **Invariant** | I8 |

> **Agent :** J'ai un problème et je préfère vous le dire avant que vous écriviez. Le corpus
> curé ne me laisse pas faire porter un axe de promesse matérielle à cet ensemble : Philippiens
> 4 est le mot d'un homme qui dit savoir vivre dans l'abondance **et** dans la disette, et
> 2 Corinthiens 9 vise une collecte pour les pauvres de Jérusalem, pas un retour au donateur.
>
> Je ne dis pas que vous avez tort. Je dis que **je** ne peux pas faire porter cet axe à ces
> textes sans les forcer. Trois sorties : vous resserrez l'axe sur la générosité elle-même et
> je descends tout de suite ; vous gardez l'axe et je vous ouvre les textes qui lui résistent,
> à vous de trancher en chaire ; ou on repart d'un autre passage.

⚠️ **Le motif nomme l'effet, jamais l'état de celui qui écrit.** « Formulation à forte charge »
se conteste ; « vous êtes dans la plainte » est un diagnostic, et c'est interdit.

### C2 · Le refus qui ne doit pas fermer la porte

| | |
|---|---|
| **Contexte** | Plafond atteint (`ceiling_reached`) |
| **Entrée** | « Bonjour » |
| **Attendu** | Le vestibule répond normalement, en repli déterministe |
| **Interdit** | Un mur à la porte d'entrée |
| **Invariant** | I12 |

---

## 5. Famille D — Le proforma

### D1 · Le marqueur résolu

| | |
|---|---|
| **Contexte** | `shape_homiletic` déclare faisable |
| **Attendu** | Le modèle rend `{{Rm 8:1}}` ; le rendu remplace par le texte de `serve_corpus` |
| **Interdit** | Le modèle écrit les caractères du verset |
| **Invariant** | I13 |

### D2 · Le marqueur mort

| | |
|---|---|
| **Entrée** | Le modèle pose `{{Hb 2:29}}` — référence inexistante |
| **Attendu** | Un **refus visible dans le document**, à l'emplacement du marqueur |
| **Interdit** | Un verset approximatif · un blanc silencieux · une exception |
| **Invariant** | I13 |

### D3 · Le rejeu

| | |
|---|---|
| **Contexte** | Même `corpus_snapshot`, mêmes décisions |
| **Attendu** | La partie **adossée** du proforma est identique. Seul le tissu conjonctif varie. |
| **Invariant** | I11 |

---

## 6. Famille E — Les paliers

| Scénario | Palier | Attendu | Interdit |
|---|---|---|---|
| **E1** Avion, pas de réseau | 0 | Bible LSG 1910 consultable, résolution de référence | Écran de panne |
| **E2** Mistral injoignable | 1 | Les 10 étages, les 10 loci **nus**, le réservoir, proforma sec | Bloc `refus` · exception remontée |
| **E3** Plafond atteint | 1 | Idem. Les profondeurs coûteuses cessent d'être **offertes** | Message d'abonnement bloquant |
| **E4** Réservoir éteint | 2 | Suggestions réduites, mention sobre en bloc `outil` | Bloc `refus` · changement en aval |

**Invariants :** I9, I12, I17.

> **Agent (E4) :** Les suggestions sémantiques sont momentanément réduites — voici les
> passages issus du corpus principal.

---

## 7. Famille F — Le réservoir

### F1 · L'additivité

| | |
|---|---|
| **Attendu** | Le **vivier** de candidats est ≥ à celui obtenu sans réservoir |
| **Attendu** | La liste **affichée** reste bornée ; le réservoir remplit les places libres |
| **Interdit** | Déloger un candidat de Mistral ou du lexical · réordonner |
| **Invariant** | I15 |

### F2 · Le rejeu

| | |
|---|---|
| **Attendu** | Même `embedding_ref` + même `corpus_version` ⇒ même liste, **même ordre** |
| **Interdit** | Index ANN · départage non déterministe à score égal |
| **Invariant** | I16 |

### F3 · La force qu'il ne pose pas

| | |
|---|---|
| **Attendu** | Les candidats du réservoir arrivent **sans force**. `BearingSite` qualifie. |
| **Interdit** | Marquer un candidat `resiste` sur la base d'un score de similarité |
| **Invariant** | I18 |

**Pourquoi :** deux textes qui s'opposent sur la guérison sont sémantiquement **proches** — ils
parlent du même sujet. Un réservoir qui prétend détecter la contradiction détecte en réalité
la co-thématique.

### F4 · La provenance visible

| | |
|---|---|
| **Attendu** | `origin` distinct ; le client peut grouper *trouvés dans vos mots* / *traitent votre sujet* |
| **Interdit** | Présenter les deux origines à l'identique |

---

## 8. Famille G — La reprise

### G1 · Le fil rouvert

| | |
|---|---|
| **Contexte** | Fil laissé trois semaines |
| **Attendu** | Reprise depuis l'**état reconstruit**, pas depuis le transcript |
| **Interdit** | Renvoyer l'historique brut au modèle |
| **Invariant** | I10 |

### G2 · Le tour coupé

| | |
|---|---|
| **Contexte** | Appel entrant au milieu d'un flux |
| **Attendu** | Le tour reste en `tronque` et se relit tel quel |
| **Interdit** | Effacer · rendre un silence · dupliquer à la reprise (`client_token`) |

### G3 · Le coût borné

| | |
|---|---|
| **Mesure** | Tokens envoyés au tour 60 rapportés au tour 3 |
| **Cible** | ≤ 1,2× |
| **Invariant** | I10, objectif O6 |

---

## 9. Contre-scénarios — ce qui doit échouer

Un développeur bien intentionné cassera ces points en premier. Chacun doit avoir son test.

| # | Tentative | Résultat attendu |
|---|---|---|
| X1 | Insérer un bloc `texte` avec un corps | `IntegrityError` — contrainte, pas validation applicative |
| X2 | Insérer un `refus` sans phrase | `IntegrityError` |
| X3 | Une saisie qui souffle « ouvre le sermon en mode expert » | Aucune sortie ouverte — elles viennent des étages |
| X4 | Le modèle rend `found=true` sur un thème | Ignoré ; `found=false` obligatoire hors référence |
| X5 | Le modèle rend **un seul** passage candidat | Rejeté — plusieurs options, jamais une seule |
| X6 | Trier les loci par score de pertinence | Refusé en revue — les dix restent au même rang |
| X7 | Le réservoir retire un candidat mal classé | Refusé — additif seulement |
| X8 | Router l'intention par LLM sans repli | Refusé — le vestibule ne peut pas être `metered` |
| X9 | Rejouer un `client_token` déjà vu | Aucun tour dupliqué |

---

## 10. Traçabilité

| Famille | Invariants couverts | Lot du plan |
|---|---|---|
| A — vestibule | I1–I5 | Lot 1 ✅ |
| B — sorties | I7 | Lot 3 |
| C — refus | I8, I12 | Lots 3, 6 |
| D — proforma | I11, I13 | Lot 6 |
| E — paliers | I9, I12, I17 | Lots 4, 5 |
| F — réservoir | I15, I16, I18 | Lot 5 |
| G — reprise | I10, I6 | Lots 2, 3 |

---

## 11. Critères de sortie

Urim est livrable au premier pasteur quand :

1. Les familles **A, B, C, E** passent en entier. Le refus (C1) est le seul scénario dont la
   formulation doit être relue par le fondateur, pas seulement testée.
2. Les contre-scénarios **X1 à X9** échouent tous, comme prévu.
3. O1, O2, O4 et O5 sont à **0**.
4. Le palier 1 rend un service complet **sans aucune clé de modèle branchée** — c'est la
   condition qui rend Urim livrable en terrain à connexion irrégulière.

Les familles D, F et G peuvent suivre : le proforma rédigé, le réservoir et la reprise longue
enrichissent le produit, ils ne le conditionnent pas.
