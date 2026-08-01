# Anniversaire et Restitution — spec d'exécution

> **Nature :** spec de deux briques issues de [Frontiere_IA_Scenarios.md](Frontiere_IA_Scenarios.md)
> (scènes 1, 3 et 6). La partie A spécifie l'**anniversaire** — premier cas d'usage du compagnon
> relationnel, le moins risqué. La partie B spécifie la **restitution pré-contact** — le seul
> usage de l'IA autorisé dans la Veille, et sa découverte principale : **le premier niveau n'a
> besoin d'aucune IA.**
>
> Les deux briques partagent trois propriétés : elles se calculent **à la lecture** (aucune
> dépendance au worker), elles n'écrivent **rien au ledger** (ce sont des affichages, pas des
> signaux), et le réglage du membre y est **absorbant**.
>
> Vérification préalable sur le dépôt : aucun champ de date de naissance n'existe aujourd'hui
> (l'`Account` IAM porte le téléphone et le nom) ; `CaseDTO` expose déjà `reason`, `annotations`
> et `previous_case_note`. Ce document part de cet état.

---

# PARTIE A — L'anniversaire

## A.1 Le principe

Une date déclarée par le membre, affichée au bon moment au cercle qu'il a choisi, pour provoquer
un geste humain. Rien d'autre. Pas de fait au ledger, pas de cas, pas d'entrée dans le plafond,
pas de notification push, pas de message automatique.

> **La ligne (scène 1) :** *Dorea rappelle aux humains d'aimer ; il n'aime jamais à leur place.*

## A.2 La donnée

Un champ de profil, côté IAM (le profil membre est propriété d'IAM ; emplacement exact à aligner
sur `M-Member_Mobile_Model.md`) :

```
birth_day        int  (1..31)      — requis si renseigné
birth_month      int  (1..12)      — requis si renseigné
birth_year       int | NULL        — optionnel, JAMAIS affiché
birthday_scope   enum              — le réglage de visibilité, absorbant
```

Quatre décisions dans ce schéma :

- **Jour + mois suffisent.** L'année est optionnelle et n'est **jamais** affichée nulle part —
  l'âge de quelqu'un n'est pas une donnée d'église. Elle n'existe que si le membre la donne, pour
  d'éventuels usages pastoraux futurs explicitement consentis (aucun en V1).
- **La visibilité est un enum fermé**, choisi par le membre :

  | `birthday_scope` | Qui voit l'encart |
  | :-- | :-- |
  | `GROUPS` *(défaut)* | les membres de ses groupes à politique d'alerte forte (cellules) |
  | `REFERENT_ONLY` | son référent seul |
  | `HIDDEN` | personne — absolu, y compris pour l'assistant et le pasteur |

- **Le défaut est `GROUPS`** parce que l'anniversaire est un rituel communautaire dans les églises
  cibles — mais le champ lui-même est optionnel : ne pas renseigner sa date équivaut à `HIDDEN`.
- **La saisie appartient au membre.** Un responsable ne renseigne pas la date d'un autre. (Le cas
  du membre sans smartphone passe par la saisie assistée déjà prévue à l'onboarding, avec son
  accord — même canal que le reste de son profil.)

## A.3 L'affichage

Calculé **à la lecture**, sans échéance ni worker : à l'ouverture de l'écran du groupe (ou de
l'accueil de l'app), une requête sur les dates du jour / du lendemain parmi les membres visibles.

| Qui | Quand | Quoi |
| :-- | :-- | :-- |
| le référent | J-1 et jour J | *« Demain : anniversaire d'Awa. »* / *« Aujourd'hui : anniversaire d'Awa. »* |
| les membres du cercle | jour J | *« Aujourd'hui : anniversaire d'Awa. »* |

Règles de forme, toutes trois non négociables :

- **Pas de push.** L'encart attend qu'on ouvre l'app. Un anniversaire poussé à 7 h du matin est le
  début d'une boucle d'habitude — et le contraire d'un geste.
- **Pas de bouton « souhaiter ».** Aucun message ne part de Dorea, ni au nom de Dorea, ni au nom
  de quiconque. L'encart peut porter le bouton d'appel standard (téléphone / WhatsApp), le même
  que partout ailleurs — Dorea fait sortir, comme toujours.
- **Pas d'agrégation rétrospective.** Aucun écran « anniversaires du mois », aucune liste
  exportable. La liste des dates de naissance d'un groupe est une donnée de fichier ; l'encart du
  jour est une attention. On livre la seconde.

## A.4 Le masquage est absolu (scène 6)

`HIDDEN` éteint tout : l'encart, la réponse de l'assistant, la visibilité pasteur. La réponse de
l'assistant est un **gabarit écrit**, pas un comportement émergent :

> *« Fatou n'a pas rendu cette information visible. »*

Sans détour, sans « demandez-lui directement », sans exception de bienveillance. Même mécanique
que `DO_NOT_CONTACT` : le réglage du membre absorbe, et aucune bonne intention ne le lève.

## A.5 Fichiers touchés

| Fichier | Modification |
| :-- | :-- |
| profil IAM (modèle + migration) | les quatre colonnes ; `birthday_scope` défaut `GROUPS` |
| surface mobile profil | saisie jour/mois (+ année optionnelle), sélecteur de visibilité, texte d'explication du réglage |
| écran groupe / accueil (Flutter) | l'encart, calculé à la lecture |
| requête côté `groups` ou `iam` | `birthdays_today(group_id)` — filtrée par `birthday_scope`, jamais d'année dans la réponse |
| assistant | le gabarit de refus |

## A.6 Tests

1. `HIDDEN` : aucun encart pour personne, et la réponse de l'assistant est le gabarit — y compris
   pour le pasteur.
2. `REFERENT_ONLY` : le référent voit, les membres du groupe ne voient pas.
3. L'année n'apparaît dans **aucun** DTO, aucune réponse, aucun log.
4. Aucun fait `birthday` n'existe au ledger ; aucun `FactKind` n'est ajouté (test négatif sur
   l'enum, même patron que les invariants existants).
5. Le 29 février s'affiche le 28 les années non bissextiles (le détail qui vexe s'il manque).

---

# PARTIE B — La restitution pré-contact

## B.1 Le principe, et la découverte

Avant d'appeler, Jean lit un résumé de six mois de lien — au lieu de relire onze entrées dans le
bus. La scène 3 posait quatre propriétés : que du déjà-écrit, servi à qui a déjà le droit de tout
lire, aucune conclusion, éphémère.

**La découverte en spécifiant : le premier niveau n'a besoin d'aucune IA.** Tout ce que le résumé
de la scène 3 contient est **déjà structuré** en base :

> *« Vous l'accompagnez depuis février (difficulté matérielle, résolue en mars). Épisode actuel :
> deuil de son père, annoncé le 12 avril. Dernier contact jeudi — vous aviez noté vouloir la
> rappeler aujourd'hui. En février, elle avait demandé qu'on n'évoque pas sa belle-famille. »*

Chaque segment vient d'un champ : `episode_id` + `occurrence_number` (les épisodes), `SignalOutcome`
(« difficulté matérielle, résolue »), la catégorie d'annonce et sa date (« deuil, annoncé le
12 avril »), `ContactAttempt.attempted_at` (« dernier contact jeudi »), et la note de
`watch_care_memory` (« elle avait demandé que… » — citée, pas résumée). La restitution se
construit donc en **deux niveaux**, et le premier se livre sans un token d'IA :

| Niveau | Contenu | Mécanique | Coût |
| :-- | :-- | :-- | :-- |
| **R1 — déterministe** | l'historique structuré : épisodes, issues, contacts, dates, catégories | **gabarits fermés** sur les champs — zéro IA | zéro |
| **R2 — résumé des notes** | condensé des notes libres quand elles sont longues ou nombreuses | appel IA, sous les garde-fous B.3 | par affichage, borné |

C'est le patron du sermon augmenté appliqué à la Veille : le déterministe d'abord, l'IA seulement
là où le texte libre la rend nécessaire — et le coût reste en O(consultations), jamais en
O(membres).

## B.2 R1 — la restitution déterministe

Un bloc en tête de l'écran du cas (`GET /my-cases` enrichi ou endpoint dédié
`GET /cases/{id}/context`), assemblé par gabarits depuis :

1. **L'épisode** : `occurrence_number > 1` → *« Cas précédent clos le {date} — {issue en langage
   pastoral}. »* (la phrase existe déjà dans la doctrine des épisodes ; on la place ici).
2. **Le lien** : première entrée de `watch_care_memory` → *« Vous l'accompagnez depuis {mois}. »*
3. **Le présent** : `reason` + `annotations` du cas (l'écart-à-soi-même s'y range déjà).
4. **Le dernier contact** : dernière `ContactAttempt` résolue → date, canal, résultat.
5. **Les notes récentes, verbatim** : les 2-3 dernières entrées de `watch_care_memory`,
   **citées telles quelles**, datées, attribuées. Citer n'est pas résumer — aucun risque.

Chaque segment est **dépliable vers sa source** (l'entrée de mémoire, le fait d'annonce). C'est la
traçabilité de la scène 3, gratuite en R1 puisque chaque phrase *est* un champ.

Le tout servi **uniquement** à travers `_OwnedCase._load` — le même contrôle d'autorité que le
reste de l'écran : le propriétaire du cas, personne d'autre. Rien de nouveau à sécuriser.

## B.3 R2 — le résumé IA des notes libres, et ses garde-fous

Déclenché seulement quand R1 ne suffit plus : plus de `NOTES_SUMMARY_THRESHOLD` entrées de mémoire
(défaut : 5, au catalogue `WatchParam`). En dessous, les notes verbatim de R1 sont plus fiables
qu'un résumé.

Les garde-fous, chacun testable :

- **Entrée bornée** : le prompt ne reçoit que les notes de `watch_care_memory` du sujet, déjà
  lisibles par le demandeur. Jamais le contenu d'annonces, jamais les dépôts Compagnon, jamais
  les notes d'un autre membre.
- **Sortie contrainte au factuel** : l'instruction exige des faits datés et **interdit** toute
  appréciation d'état (« semble fragile », « ton en dégradation »), toute recommandation de
  posture, toute prédiction. Un post-traitement rejette les sorties contenant les marqueurs
  d'inférence (liste fermée de motifs, même mécanique que `FORBIDDEN_KIND_PATTERNS` — côté texte).
  Si la sortie est rejetée : repli silencieux sur R1. **Le repli est le comportement par défaut
  de toute erreur** — l'écran ne casse jamais pour cause d'IA.
- **Éphémère, structurellement** : généré à l'affichage, jamais écrit — ni en base, ni au ledger,
  ni en cache au-delà de la session d'écran. Un résumé stocké deviendrait une donnée sur Awa que
  personne n'a écrite ; l'éphémère n'est pas une optimisation, c'est la frontière.
- **Marqué comme machine** : le bloc R2 est visuellement distinct et titré *« Résumé automatique —
  vérifiez sur les notes »*, chaque note source dépliable en dessous. Jean fait confiance à ses
  notes ; le résumé lui fait gagner du temps, pas autorité.

## B.4 Ce que la restitution ne fera pas

À écrire dans la spec parce que la pression viendra : pas de restitution **agrégée** (« résumez-moi
ma cellule » — c'est l'écran de veille qui fait ça, en faits) ; pas de restitution pour un
**tiers** (le pasteur lit les notes auxquelles il a droit, il ne reçoit pas un digest d'un cas
qui ne lui est pas remonté) ; pas de **question libre sur une personne** (« comment va Awa
d'après ses notes ? » → gabarit de refus de la scène 4 — la restitution est un écran, pas un
oracle conversationnel).

## B.5 Fichiers touchés

| Fichier | Modification |
| :-- | :-- |
| `watch/application/my_cases.py` | `GetCaseContext` (R1) — assemblage par gabarits ; réutilise `_OwnedCase` |
| `watch/application/restitution.py` *(nouveau)* | gabarits R1 (jeu fermé, traduit) ; orchestration R2 + post-filtre + repli |
| `watch/application/ports.py` | `SummaryPort` (le port IA — l'adaptateur vit hors du contexte, comme pour le sermon) |
| `watch/domain/parameters.py` | `NOTES_SUMMARY_THRESHOLD = 5` |
| surface mobile | le bloc contexte en tête du cas, segments dépliables, style distinct pour R2 |

## B.6 Tests

1. R1 sur le fixture : chaque segment du bloc est traçable à un champ ; un cas sans historique
   n'affiche rien (pas de bloc vide).
2. Autorité : un non-propriétaire du cas reçoit la même erreur que sur `SeeCase`.
3. R2 : une sortie contenant un marqueur d'inférence est rejetée et l'écran sert R1 (test avec un
   faux `SummaryPort` qui renvoie « elle semble aller mal »).
4. Éphémère : aucune écriture en base pendant un affichage R2 (assertion sur la session).
5. Panne du port IA : l'écran sert R1, sans erreur visible.
6. Le résumé R2 d'un cas n'inclut jamais une note d'un autre sujet (test d'isolation du prompt).

---

## Ordre et rattachement

| Brique | Quand | Dépend de |
| :-- | :-- | :-- |
| **A — anniversaire** | livrable immédiatement | rien — ni worker, ni moteur |
| **B/R1 — restitution déterministe** | avec le pilote | l'écran `my-cases` (livré) |
| **B/R2 — résumé IA** | pendant le pilote, quand des mémoires longues existent réellement | R1 + un `SummaryPort` |

Ce séquencement **corrige** la note du §8 des scénarios (« après l'étage 05 ») : la restitution
n'a en réalité aucune dépendance à la notification — R1 est un enrichissement de lecture pur.
Elle entre donc dans le périmètre pilote, et c'est tant mieux : c'est l'écran qui fait dire à un
responsable « Dorea me connaît mieux que mon cahier ».

Hors périmètre de ce document : le parfum du groupe (`GROUP_TEMPERATURE`, spec propre), l'appel
fraternel en rencontre (`QUALIFICATION_SET`, spec propre — la prochaine à écrire), et tout usage
conversationnel de la restitution.
