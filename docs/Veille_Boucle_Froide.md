# La boucle froide — lot 6 du chantier moteur de veille

> La boucle chaude décide — cinq étages, déterministes, inchangés.
> La boucle froide observe et calibre — elle ne produit que des propositions de `WatchParam`.

Livrée le 1ᵉʳ août 2026 sur `chantier/moteur-veille`. Paquet : `app/contexts/watch/calibration/`.

## Le problème qu'elle résout

Les seuils du moteur sont des paris — `app/contexts/watch/domain/parameters.py` le dit en toutes
lettres : *« les valeurs de départ sont des paris, pas des vérités »*. Rien ne les confrontait à ce
que les églises constatent réellement. Une valeur jamais mesurée finit par passer pour vraie parce
que personne ne l'a contredite.

## Ce qu'elle lit : la vérité terrain

`calibration/judge.py` — `OutcomeJudge` → `GroundTruth`.

| Ce qu'on observe | Ce que ça dit | Ce que ça décide |
| :-- | :-- | :-- |
| cas fermé sur « contact pris, rien à signaler » | la détection s'est **trompée** | seuil trop sensible |
| inquiétude d'un tiers **confirmée** | un humain a vu **avant** le moteur | seuil trop lent |
| cas jamais ouvert par son destinataire | il est **débordé**, pas indifférent | plafond trop haut |

Trois décisions à ne pas défaire :

1. **Seules les clôtures humaines comptent.** Une extinction système ferait noter la machine par
   la machine : un cas éteint par une annonce n'a été vérifié par personne, et le ranger d'un côté
   ou de l'autre bougerait la précision d'une église où pas un contact n'a eu lieu.
2. **`precision is None` sur zéro cas.** Zéro fermé ne veut pas dire zéro justesse ; rendre `0.0`
   déclencherait des propositions sur du vide.
3. **Le taux d'ignorés est le seul indicateur qui anticipe.** `first_contact_at` est la métrique
   reine mais elle est retardée. Le taux d'ignorés monte pendant que le délai de contact a encore
   l'air normal — parce que les cas traités le sont vite et que les autres ne sont jamais ouverts.

`MeasureConcernPrecision` (bloc 8 du signalement par un tiers) a été ramenée sur la **même requête
et le même filtre** : il n'existe plus qu'une source pour le mot « précision ». Deux nombres qui
portent le même nom et se contredisent finissent toujours par être arbitrés par celui qui arrange.
Le port `concern_outcomes` a disparu au profit de `closed_cases_since`.

## Ce qu'elle propose

`calibration/proposal.py` — `Proposer`, `CalibrationProposal`, `BOUNDS`, `ApplyProposal`.

Un **balayage borné**, pas un optimiseur : l'espace tient en deux entiers, et une descente de
gradient dessus serait de la mise en scène. Deux règles, dans cet ordre :

1. précision d'absence sous 50 % sur ≥ 5 cas → **monter** `ABSENCE_OCCURRENCES_THRESHOLD` ;
2. sinon, ≥ 5 inquiétudes confirmées → **descendre** le même seuil.

> **Le contre-intuitif du module.** Si huit signaux arrivent par semaine pour une capacité de
> trois, le problème n'est pas que le plafond est trop bas : c'est que la détection est trop
> bavarde. On remonte le seuil, et on ne touche pas au plafond.

**Il n'y a pas de troisième règle, et son absence est une décision (01/08/2026).** Le taux
d'ignorés proposait autrefois de baisser `OPEN_CASES_CAP`. Deux erreurs dans une :

- le plafond s'applique **par responsable**, le taux se mesure **à l'église** — un seul
  responsable noyé le faisait baisser pour tout le monde, y compris pour ceux qui ouvraient tout ;
- baisser le plafond ne répare rien : ça retient davantage de cas en amont pour que l'indicateur
  cesse de monter. Le symptôme s'efface, la personne qu'on n'appelle pas reste sans nouvelles.

`ignored_rate` reste **mesuré** — c'est la santé de l'église et une part de la clause d'arrêt de
cette boucle. Ce qui *agit* est passé dans la boucle chaude : `WatchForUnopenedCases` consigne un
`CoverageGap.CASES_NOT_OPENED` **sur le responsable**, formulé comme un besoin d'aide, et le
pasteur le lit sur son écran de couverture. Nommer quelqu'un doit déclencher une action sur lui,
jamais un réglage sur les autres — et c'est précisément parce que la boucle froide s'interdit les
noms qu'elle n'était pas le bon endroit.

`OPEN_CASES_CAP` garde sa borne dure dans `BOUNDS` alors qu'aucune règle ne le propose : la borne
dit ce qu'on **accepterait**, pas ce qu'on suggère. Le jour où un humain écrit 20 à la main,
`ApplyProposal` refuse.

Les **bornes sont dures** : hors bornes, une proposition n'est jamais appliquée seule, même
approuvée. Un humain peut toujours écrire la valeur à la main, mais il le fera en le sachant.

## Qui décide

| Régime | Ce qui se passe |
| :-- | :-- |
| `SHADOW` | la proposition est écrite et attend ; rien ne bouge |
| `ASSISTED` | idem ; une approbation l'applique |
| `STEADY` | dans les bornes, elle s'applique seule |

`calibration/review.py` — `RunCalibrationPass`, `ListProposals`, `DecideOnProposal`. Autorité
`MANAGE_STAFF`, la même que « laissez Dorea parler » : changer un seuil de détection engage
l'église entière, ce n'est pas une lecture pastorale.

**Un refus vaut autant qu'une acceptation** : il est enregistré, daté, signé, et la proposition ne
revient pas. Une proposition rejetée qui se represente chaque nuit est du harcèlement, et le
pasteur apprend à tout accepter pour que ça s'arrête. Une seule proposition en attente par
`(église, paramètre)`, pour la même raison.

## Ce qu'une proposition coûterait

`calibration/simulator.py` — `Simulator`, `SimulationResult`.

> *« À 4 rencontres, 19 des 31 cas ne se seraient pas ouverts : 5 des 6 fermés sur "rien à
> signaler" — et 1 qui s'est confirmé. »*

Une proposition qui ne dit que ce qu'elle fait gagner est une publicité. La phrase **finit** par
ce qu'on perd, parce que l'ordre d'une phrase est ce qu'on en retient. Un seuil plus haut fait
toujours moins de bruit ; la vraie question est qui on ne va plus voir, et personne ne peut y
répondre à la place du pasteur.

**Le simulateur lourd n'a pas été nécessaire.** Le plan prévoyait de rejouer le journal contre des
seuils alternatifs, avec des dépôts en mémoire de qualité production. Inutile : `CheckFiredV1`
écrit `occurrences` et `threshold` **dans le payload du fait**, précisément pour rester pur et
déterministe. Le contrefactuel se lit donc dans le journal, sans rejouer quoi que ce soit — la
discipline d'un interpreter sans I/O a payé une seconde fois, là où on ne l'attendait pas.

| Sens | Ce qu'on peut dire |
| :-- | :-- |
| seuil **plus haut** | **exact** — sous-ensemble de ce qui s'est ouvert, et pour ceux-là on sait qu'aucune neutralisation ne courait |
| seuil **plus bas** | **une borne haute** — certains auraient été étouffés par un deuil ou un voyage, que le payload ne porte pas |

Le champ `exact` porte cette différence jusqu'à l'écran : un nombre dont on ne sait plus s'il est
une mesure ou une estimation finit toujours par être lu comme une mesure.

**Le simulateur ne choisit pas.** Il chiffre ; les trois règles du `Proposer` sont inchangées, et
un test le verrouille — la proposition reste `+1` même quand la simulation dit qu'elle coûterait
vingt vrais cas. Le laisser choisir en ferait un optimiseur, et un optimiseur arbitrerait en
silence « moins de bruit contre des gens qu'on ne voit plus », un compromis qui n'est pas le sien.

Seul le seuil d'absence se simule : le plafond de débit n'a pas de contrefactuel lisible — il
n'aurait pas empêché des cas d'exister, seulement retardé leur sortie — et on n'invente pas une
phrase pour faire symétrique.

## Les quatre interdits — structurels, pas des consignes

`tests/contexts/watch/test_calibration.py` les lit **dans le paquet** :

1. **Aucun objet ne porte l'identifiant d'une personne observée.** La frontière est entre l'auteur
   et le sujet : `decided_by_account_id` signe une décision et ne porte aucun nombre. Le test
   n'autorise que trois champs d'identifiant dans tout le paquet — `tenant_id`, `id`,
   `decided_by_account_id`.
2. **La boucle froide ne peut pas écrire un effet.** Un test parcourt les imports en AST et refuse
   `materialization`, `projections`, `intake`, `ledger`, `arbitration`, `owner_assignment`,
   `case_acts`, `fire_checks`.
3. **Aucun fait inféré n'entre au ledger.** Les propositions vivent dans leur propre table
   (`watch_calibration_proposals`, migration `d3fd0c1d2e3f`), hors du journal : aucun rejeu ne les
   relit, aucun interpreter ne peut les transformer en effet.
4. **Pas de score par personne**, visible ou non — corollaire testé du premier.

Son unique pouvoir d'écriture tient dans une signature : `WatchParameterWriter.set_int`, un entier
pour une église, jamais la ligne du défaut produit.

## Surfaces

- `POST /api/platform/watch/calibrate` — la passe, mensuelle, cadence dans le cron ;
- `GET /api/backoffice/tenants/{id}/watch/calibration/proposals` — ce qui attend le pasteur ;
- `POST .../proposals/{proposal_id}` — accepter ou refuser (`{"accept": bool}`, sans défaut).

## Sa propre clause d'arrêt

La précision des cas ouverts, église par église, doit monter d'un mois sur l'autre. Si elle ne
monte pas, la boucle froide n'apprend rien et on la coupe — même exigence que pour tout le reste
du produit.

## Ce qui reste

Rien du lot 6. Le simulateur, dernier point ouvert, est livré — et sous une forme plus légère que
prévue : le contrefactuel se lisait déjà dans le journal.

Le seul prolongement identifié n'est pas un manque mais une décision à prendre au pilote : le
`Proposer` ne balaie aujourd'hui qu'un seul candidat (`±1`). Élargir le balayage à toute la plage
des `BOUNDS` et présenter deux ou trois options chiffrées au pasteur serait possible — mais c'est
un choix de produit (offrir un curseur plutôt qu'une proposition), pas une dette technique.
