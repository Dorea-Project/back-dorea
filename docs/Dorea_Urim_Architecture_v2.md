# DOREA URIM — Architecture consolidée

**Version 2 · 2 août 2026** — remplace `Urim_Architecture_2026-08-02.md`
**Statut :** spécification. Construction non autorisée (§11).

---

## 0. Corrections apportées à la version 1

| # | Version 1 (erronée) | Version 2 |
|---|---|---|
| 1 | Nom laissé ouvert, « Urim » seul | **« Dorea Urim »** — arrêté après refus d'« Urimium » (*Urim* est déjà un pluriel hébreu ; le suffixe latin *-ium* produit un hybride incohérent) |
| 2 | §4 : aucune donnée de La Veille ne traverse | **Règle réelle** : contexte d'assemblée **en recherche, jamais en génération**, seuil de cinq personnes (§4) |
| 3 | Homilétique implicitement traitée comme une liste plate de types | **Deux axes orthogonaux** — source du plan × matière du sujet (§6) |
| 4 | Marché supposé Afrique de l'Ouest francophone | **Toutes traditions, tous marchés.** Conséquences architecturales réelles (§9) |

---

## 1. Positionnement

Dorea Urim est le module d'étude biblique et de préparation de sermon.

**Métaphore de référence :** un pupitre. On y pose son texte, on y trouve ses outils, on y prépare — puis on monte prêcher, et le pupitre reste en bas. Urim ne rédige pas de sermon, ne produit pas d'application, n'entre pas dans l'herméneutique.

**Filtre produit :** est-ce que cela fait regarder un écran plus longtemps, ou est-ce que cela rend le pasteur plus libre devant son texte et son assemblée ?

---

## 2. Découpage du contexte `urim`

```
urim/
├── corpus/          GLOBAL · lecture seule · non tenant-scopé
│   ├── versions, verses, versification_map
│   ├── lemmas, morphology, strong
│   └── index_idf, index_trgm
├── resolution/      identification du passage
├── pericope/        bornage
├── doctrine/        axes + caveats curés
├── homiletics/      axes de plan · squelette de sermon
├── preparation/     TENANT-SCOPÉ + AUTEUR-SCOPÉ
├── deliverable/     diapositives · import · export · validation de sortie
├── archive/         prédications passées · couverture · distribution
└── calendar/        port d'entrée vers La Veille (ACL)
```

**`corpus` est immuable en production** — chargé par migration, jamais écrit par l'application. Seule donnée globale de tout Dorea : cache agressif possible, base de lecture séparable si la charge l'exige.

**`preparation` et `archive` appartiennent à leur auteur**, pas seulement à l'église. Un administrateur d'église ne voit pas la préparation d'un pasteur. Cohérence avec l'invisibilité des rendez-vous pastoraux aux responsables de cellule.

---

## 3. Le moteur — pipeline

Ordre contraignant. Chaque étage consomme le précédent.

> ⚠ **Correction 2026-08-05 (E2) — le pipeline compte HUIT étages (0→7).** Trois comptes coexistaient
> dans les documents : « 6 étages » (schéma `Structure §2`), les étages 0→6 énumérés ci-dessous, et
> les 8 de `PIPELINE`. **`ShapeHomiletic` EST un étage** — elle consomme les axes, rend un
> `StageResult` **motivé**, et peut `REFUSE` (`homiletic_feasibility.refusal_reason` est en base) :
> c'est la définition d'un étage. Elle s'insère en **6**, le thème passe en **7**.
> Les mentions « 6 étages » et l'arrêt au thème en étage 6 sont **périmées**.

### Étage 0 — Routage d'entrée
Trois portes : **référence** · **citation collée ou de mémoire** · **conviction thématique**.
La conviction entre par un chemin inversé (§7) et rejoint le pipeline à l'étage 2.

### Étage 1 — Résolution
**Objectif : identifier le passage, pas la version.** Le texte est ensuite resservi depuis les versions du corpus. La version d'origine est une information affichée, jamais bloquante — ce qui permet aussi de détecter qu'un texte ne correspond à aucune version indexée **sans posséder cette version**.

- Normalisation : casse, accents, apostrophes typographiques, numéros de versets, notes, ponctuation
- Ancres rares : IDF précalculé. Les mots rares survivent à la mémoire approximative ; les mots fréquents ne discriminent rien
- Similarité : `pg_trgm` + GIN + recherche plein texte. **Aucune infrastructure nouvelle** — ni Redis ni RabbitMQ
- Conflation de mémoire : deux versets fusionnés donnent un score médiocre partout. **C'est le signal, pas l'échec**
- Parseur de références multilingue (§9)

**Jamais de résolution silencieuse.** Sous seuil, les candidats s'affichent avec leur motif et le pasteur tranche.

### Étage 2 — Bornage
Unité littéraire réelle + **motif affiché**. Le pasteur peut forcer d'autres bornes en connaissance de cause.

### Étage 3 — Corpus
Versions parallèles, lemme, morphologie, champ sémantique, concordance **par auteur d'abord**.

### Étage 4 — Contexte
**Sourcé ou absent.** Aucune génération. Un contexte historique plausible mais inventé produit un pasteur qui affirme une chose fausse en chaire.

### Étage 5 — Axes doctrinaux
Les dix catégories, avec pour chacune : porté / non porté / mise en garde.

### Étage 6 — Thème
Croise l'axe retenu et l'historique (`preached`, l'archive de l'auteur). **Affiche toujours son motif.**

> ⚠ **Correction 2026-08-05 (E1) — le calendrier ecclésial est RETIRÉ de cet étage.** La rédaction
> initiale (« croise l'axe retenu, **le calendrier ecclésial**, l'historique ») contredisait §4.3 et
> §4.5 : `ACL → moteur` est **interdit**, et le garde-fou exécutable rejette tout étage qui lit le
> port de contexte. Les deux ne pouvaient pas tenir. **§4 l'emporte** : le calendrier s'**affiche à
> côté** du texte, le pasteur en tient compte lui-même.
>
> *L'historique ne pose aucun problème : c'est `urim.preached`, la donnée d'Urim, pas la veille.*
>
> Le motif du refus vaut d'être gardé : « un baptême dimanche, c'est légitime » vaudrait demain pour
> « douze malades ce mois-ci ». **Le signal informe l'homme ; l'homme commande la machine.**

---

## 4. Interopérabilité avec La Veille

### 4.1 Le port

```
EcclesialContextPort
    upcoming_events(church_id, window) -> list[EcclesialEvent]
    aggregate_context(church_id, window) -> list[AggregateSignal]
```

`EcclesialEvent` et `AggregateSignal` sont des objets du domaine Urim. **Aucun identifiant de personne, jamais.**

### 4.2 Ce qui traverse

**Calendrier ecclésial** — événements déclarés et publics, que l'assemblée connaît déjà.

```
EcclesialEventKind = { WEDDING, BAPTISM, SPECIAL_SERVICE,
                       WORSHIP_NIGHT, FAST, MEMORIAL_SERVICE, CONVENTION }
```

**Liste blanche, jamais liste noire.** Tout type ajouté un jour dans `watch` est invisible d'Urim par défaut. C'est le seul dispositif qui résiste à six mois de développement par quelqu'un qui n'a pas lu ce document.

**Contexte d'assemblée agrégé** — seuil minimum **cinq personnes**, jamais nominatif, jamais un cas.

### 4.3 La règle décisive

> **Recherche : oui. Génération : non.**

Un agrégat peut s'afficher **à côté** du texte, comme un fait parmi d'autres. Il n'est **jamais transmis au modèle** ni intégré à une proposition de thème.

*Forme autorisée :* « douze passages traitent du deuil » et « trente-quatre personnes en ont vécu un cette année » — deux faits côte à côte, le pasteur fait le lien lui-même.

*Forme interdite :* « prêche sur la consolation, trois membres sont en deuil ». Le dimanche, trois personnes savent que le sermon parle d'elles, et le pasteur ignore que la machine a pensé à elles.

### 4.4 Ce qui ne traverse jamais
`Case`, `Fact`, `CasePriority`, `FactKind`, `owner_account_id`, tout identifiant de membre, tout agrégat sous le seuil, toute donnée financière.

**`MEMORIAL_SERVICE` est le point de vigilance** : culte d'hommage inscrit au programme, jamais deuil ouvert dans La Veille. La distinction est dans la source, pas dans le type.

### 4.5 Garde-fou exécutable
Test d'architecture : **aucun module sous `urim/` n'importe le domaine `watch`**, hors `urim/calendar/adapters/`. Un test qui casse la CI, pas une convention documentaire.

### 4.6 Adaptateur nul
`NullContextAdapter` — une église sans Veille utilise Urim normalement. Ce n'est pas un bouchon de test : c'est le mode nominal d'un client qui n'a acheté qu'Urim.

---

## 5. Mises en garde doctrinales — données curées

```
DoctrinalCaveat
    pericope_range, axis, caveat_text, source_ref,
    tradition_scope, reviewed_by, reviewed_at
```

Une mise en garde générée à la volée varie d'un vendredi à l'autre et n'est contestable par personne. **Ce qui corrige un pasteur doit pouvoir être examiné par un pasteur.**

Conséquence assumée : **couverture partielle à l'ouverture**. Un texte sans caveat relu n'affiche rien plutôt qu'une improvisation. Le corpus se constitue en commençant par les péricopes les plus prêchées.

`tradition_scope` distingue les mises en garde **exégétiques** (valables partout — « la chair n'est pas le corps ») des mises en garde **confessionnelles**, qui ne s'affichent que dans la tradition configurée.

---

## 6. Homilétique — deux axes orthogonaux

**Correction de la v1.** Il n'existe pas de liste plate de types de sermon. La tradition classique (Broadus, Kuen) croise deux axes indépendants.

### Axe A — Source du plan
Où le plan est-il puisé ?

| | Description |
|---|---|
| **Textuel** | Les divisions sortent du texte lui-même, dans son ordre |
| **Expositif** | Textuel étendu à une péricope large ; le texte gouverne tout le mouvement |
| **Thématique** | Les divisions sortent du sujet ; les textes sont convoqués |

### Axe B — Matière du sujet
De quoi le sermon traite-t-il ?

`BIOGRAPHIQUE` · `DOCTRINAL` · `ÉTHIQUE` · `HISTORIQUE` · `TYPOLOGIQUE` · `PROPHÉTIQUE`

### Le croisement produit la structure
Un sermon est un couple `(source_plan, matière)`. Textuel × doctrinal ne se construit pas comme thématique × biographique.

**Combinaisons impossibles signalées, jamais fabriquées.** Romains 8.9-17 ne porte aucun personnage : `× BIOGRAPHIQUE` ne produit pas un plan, il produit un refus motivé. Urim ne fabrique pas un personnage pour satisfaire une case.

**Le risque de proof-texting est indexé sur l'axe A.** Il est structurellement plus élevé en thématique — les textes sont convoqués pour confirmer. Le mode conviction (§7) hérite de cette alerte.

### Squelette d'archive
La structure canonique en dix éléments (Braga) sert de squelette au stockage : titre, introduction, proposition, phrase interrogative, phrase de transition, divisions principales, subdivisions, illustrations, application, conclusion.

**Squelette, pas gabarit imposé.** Les champs vides restent vides. Une prédication archivée n'est pas rejetée parce qu'il lui manque des éléments.

### La frontière
```
Exégèse  →  [ Herméneutique ]  →  Homilétique
              Urim n'entre pas
```
Ce que le texte dit — Urim outille. Ce que le texte signifie — les traditions divergent, Urim s'abstient. Comment on le prêche — Urim outille la structure, pas le contenu.

---

## 7. Mode conviction — chemin inversé

```
thème → axes doctrinaux → textes candidats (portants ET résistants)
      → sélection → RETOUR À L'ÉTAGE 2
```

Aucun raccourci : bornage, versions, original, concordance et contexte s'appliquent intégralement.

**Les textes résistants s'affichent au même rang que les textes portants.** C'est ce qui distingue Urim d'un moteur de proof-texting — risque documenté dans la littérature homilétique que les utilisateurs ont eux-mêmes étudiée.

---

## 8. Livrable — diapositives

Fonction hebdomadaire, **sans IA**. Import d'un document existant, export de diapositives.

### Trois contraintes

**Validation de sortie.** Toute citation projetée est confrontée au corpus, caractère par caractère, et rejetée si elle diffère. Un verset inventé sur écran est fatal — mais il est détectable par programme, donc il doit l'être.

**Table de versification.** Les traductions ne numérotent pas identiquement (Psaumes avec ou sans titre compté, découpages divergents). `versification_map` traduit entre schémas. Sans elle, l'écran projette le mauvais verset.

**Aucune image générée.** Les visuels viennent de la bibliothèque du pasteur, ou de rien.

### Capture
La dictée après le culte est la seule entrée réaliste de l'archive. **Personne ne tapera sa prédication.** Sans capture, l'archive n'existe pas — et sans archive, ni la couverture du canon ni la distribution doctrinale n'existent.

---

## 9. Internationalisation — conséquences architecturales

Dorea vise toutes les traditions et tous les marchés. Ce n'est pas une phrase de positionnement, c'est une contrainte de schéma.

| Domaine | Règle |
|---|---|
| **Vocabulaire d'école** | Aucun terme confessionnel en dur. Les libellés de tradition, de rôle et de plan sont des données, pas des `enum` de code |
| **Corpus** | Multilingue par conception. Un corpus au lancement, N ensuite — le schéma ne change pas |
| **Références** | Parseur par langue : Rom/Rm/Ro/Romains, Rom/Röm, Rom/Rm/Romanos. Table d'abréviations, pas de regex codée |
| **Monnaie** | Champ devise + décimales. Le FCFA n'a pas de décimales, l'euro en a deux |
| **Fuseau** | Les dates de prédication sont locales à l'église. Un dimanche n'est pas un instant UTC |
| **Versification** | Schémas multiples dès le départ (§8) |

**Séquence de lancement inchangée : un corpus, une langue.** Ce qui doit être juste au premier jour, c'est le schéma — pas le catalogue.

---

## 10. Licences textuelles

**Libre de droits (V1)** — Louis Segond 1910, Darby, Ostervald · SBLGNT, Westcott-Hort · Strong, BDB.

**Sous licence** — Segond 21 et NEG (Société Biblique de Genève, présente en Côte d'Ivoire) · Semeur (Biblica) · NBS et TOB (Alliance Biblique Française) · Nestle-Aland. Voie alternative : licence individuelle par traduction via API.Bible, à partir de 10 $/mois, avec suivi d'usage imposé.

**Piège documenté :** la clause de citation de la S21 (500 versets, pas un livre complet, pas plus de 50 % de l'œuvre) vise les **citations non commerciales** dans des publications d'Églises et d'instituts. Urim sert du texte à la demande dans un produit payant : **c'est de la distribution, pas de la citation.** La clause ne couvre rien.

**Conséquence produit :** le suivi d'usage impose des appels serveur. **La V1 est intégralement utilisable hors ligne** sur le domaine public ; les versions sous licence sont un enrichissement en ligne, jamais une dépendance du chemin critique. Cohérent avec le terrain — tablette IDINO, connexion irrégulière.

---

## 11. Séquencement

**Urim n'est pas autorisé à la construction.**

R1 — dispersion — reste le risque dominant. Ordre non négociable :

1. Écran de captation des présences, testé en conditions réelles
2. Émetteur `CasePriority.ABSENCE` activé
3. Corrections du `Moteur_Corrections_et_Regime_Hybride.md` appliquées
4. **Un dimanche réel, dans une église réelle**
5. Alors seulement — réexamen d'Urim

---

## 13. Plafond anti-abus

**Principe : ce qui ne coûte rien à servir n'est jamais plafonné.** Corpus du domaine public, résolution, bornage, concordance, caveats — illimités, définitivement. Le plafond ne porte que sur les ressources **facturées à l'usage** : appels aux versions sous licence, et toute étape adossée à un modèle.

Conséquence directe : un pasteur qui travaille sur Segond 1910 ne rencontre jamais aucune limite, quel qu'en soit le volume.

### Ce qu'on plafonne — le motif, pas le volume

Un quota mensuel d'« études » punit l'intensité légitime : semaine d'école biblique, préparation d'une série, convention. **Le volume ne distingue pas l'abus ; le motif oui.** Trois vecteurs réels :

| Vecteur | Détection | Réponse |
|---|---|---|
| Script / aspiration du corpus | Cadence, régularité machine | Limitation technique par siège, invisible |
| Partage de compte entre pasteurs | Sessions simultanées, dispersion des appareils, péricopes parallèles distinctes | **Signal commercial, jamais blocage** |
| Revente de préparation | Volume + dispersion d'églises | Conversation, pas sanction |

**Le partage de compte n'est pas traité comme une fraude.** Dans le marché visé, partager est un réflexe culturel normal. La détection alimente la vente — ajouter un siège doit être plus simple que partager — et jamais l'exécution d'une sanction.

### Mutualisation
Le plafond est **mutualisé au niveau de l'église**, pas par siège. Une église à cinq sièges où un seul pasteur prêche l'essentiel ne doit pas voir son prédicateur principal limité pendant que quatre compteurs dorment.

### Dégradation, jamais blocage

> **Aucun mur un vendredi soir.**

Plafond atteint = les versions sous licence retombent sur Segond 1910, les étapes modèle se désactivent. **La préparation reste entièrement possible.** Le pasteur termine son sermon.

### Invisibilité
**Aucun compteur affiché.** Un compteur visible fait rationner : le pasteur hésite avant d'ouvrir un texte, ce qui est l'inverse exact du but. Rien ne s'affiche jusqu'à la dégradation, et la dégradation s'explique en une ligne, sans reproche.

---

## 12. Points ouverts

| # | Question | État |
|---|---|---|
| 1 | ~~Tarification~~ | **VERROUILLÉ — Urim est inclus dans l'abonnement Dorea, sans supplément ni comptage.** Trois corollaires obligatoires : (a) plafond anti-abus invisible, jamais présenté comme une limite commerciale ; (b) versions sous licence ouvertes aux sièges prédicateurs seulement, jamais à tous les sièges (§10) ; (c) **l'archive personnelle reste accessible et exportable après résiliation** — le travail du pasteur ne peut pas être pris en otage par le non-renouvellement de son église (§2) |
| 2 | Urim = contexte dans `back-dorea` ou service séparé | Non tranché. Le corpus global et immuable plaide pour une base de lecture séparable, pas nécessairement un service |
| 3 | Où vit le calendrier ecclésial aujourd'hui — `watch` ou contexte distinct | **À vérifier dans le code** avant d'écrire l'adaptateur |
| 4 | Qui relit les caveats doctrinaux | Non tranché — question théologique avant d'être technique |
| 5 | Volumétrie du corpus, coût des index trigrammes | Non instruit |
