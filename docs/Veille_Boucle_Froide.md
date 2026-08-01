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

Un **balayage borné**, pas un optimiseur : l'espace tient en trois entiers, et une descente de
gradient dessus serait de la mise en scène. Trois règles, dans cet ordre :

1. précision d'absence sous 50 % sur ≥ 5 cas → **monter** `ABSENCE_OCCURRENCES_THRESHOLD` ;
2. sinon, ≥ 5 inquiétudes confirmées → **descendre** le même seuil ;
3. sinon, plus d'un tiers de cas jamais ouverts → **descendre** `OPEN_CASES_CAP`.

> **Le contre-intuitif du module.** Si huit signaux arrivent par semaine pour une capacité de
> trois, le problème n'est pas que le plafond est trop bas : c'est que la détection est trop
> bavarde. On remonte le seuil. Remonter le plafond ferait disparaître l'indicateur en noyant le
> responsable — c'est-à-dire en supprimant exactement la protection dont l'indicateur signale le
> besoin. C'est pourquoi la règle 3 ne se déclenche que si la règle 1 ne s'est pas déclenchée.

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

Le **simulateur** (rejouer un ledger contre des seuils alternatifs pour chiffrer une proposition
avant de la poser) est reporté : il demande des stores en mémoire de qualité production, et le
`Proposer` est utile sans lui. Le lot 2 (`ReferenceReplay`) en est le prérequis, et il est livré.
