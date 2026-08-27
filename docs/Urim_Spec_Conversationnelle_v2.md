# Urim — spécification d'architecture conversationnelle · **v2**

> **Portée.** Comment un fil de conversation se raccorde aux dix étages sans les modifier, où
> Mistral intervient exactement, ce que le réservoir sémantique ajoute, et ce que chaque
> partie a le droit de décider.
>
> **Ce qui ne change pas.** Les dix étages, de `route_entry` à `shape_homiletic`. Écrits,
> testés, fusionnés. Tout ce qui suit se pose **en amont** de `route_entry` ou **en lecture**
> de ce que les étages ont établi. Aucun étage n'apprend l'existence du fil.

---

## 0. Révisions depuis la v1

| # | Change | Motif |
|---|---|---|
| R1 | `weigh_conviction` requalifié en **étage 1-bis** | Le code le dit : chemin inversé, s'efface dès que `resolved` est posé. La v1 le plaçait en fin de chaîne. |
| R2 | §5 aligné sur `route_turn.py` **codé et testé** | 50 tests verts. L'algorithme cite désormais l'API réelle, plus du pseudo-code. |
| R3 | Le **réservoir sémantique** intégré en §9 | Il touche trois étages ; le laisser en document séparé faisait diverger deux sources de vérité. |
| R4 | **Segond 21 → Louis Segond 1910** | La LSG est le corpus chargé (31 170 versets) et elle est dans le domaine public. La Segond 21 est sous droits. |
| R5 | **AS12 supprimée** | La similarité cosinus ne détecte pas la contradiction — deux textes qui s'opposent sont sémantiquement *proches*. La résistance vient de `BearingSite`, curée. |
| R6 | Embedding **local sur CPU** | Rend le réservoir disponible au **palier 1**, sans modèle de langue ni coût marginal. La v1 du réservoir ne disait pas d'où venait le vecteur de la requête. |
| R7 | **Scan exact, pas d'index ANN** | Un index approché ne garantit pas le même ordre — l'invariant de rejeu était infaisable tel qu'écrit. |
| R8 | Seuil de similarité **relatif**, plus absolu | Un seuil de 0,7 ne veut pas la même chose d'un modèle d'embedding à l'autre, or `embedding_ref` prévoit qu'il change. |
| R9 | Additivité portée sur le **vivier**, pas sur l'affichage | 4 à 6 candidats Mistral + le réservoir = douze options. Choisir devient plus dur, pas plus facile. |
| R10 | Les invariants passent de **§10 à §12** | Renumérotation due à R3. Le plan de délégation référence désormais §12. |

---

## 1. Correction de placement — `weigh_conviction`

Ce n'est **pas** l'étage du refus. C'est l'**étage 1-bis, le chemin inversé** :

- Ne s'applique que si `entry_mode is CONVICTION` **et** `resolved is None`.
- Deux temps, deux `AWAIT` : *quel axe* (les dix loci, toujours les dix), puis *quel texte*
  (les unités qui disent quelque chose de l'axe — portantes **et résistantes, au même rang**).
- Dès que `resolved` est posé, **il s'efface** ; le pipeline reprend au bornage sans qu'aucun
  étage aval n'ait à savoir par où c'est entré.

Sa protection a une propriété rare : *elle ne dépend pas de la justesse de l'axe choisi*. Un
pasteur qui retient « guérison » verra quand même les textes qui la compliquent.

---

## 2. Les trois zones

| Zone | Contenu | Appelle un modèle ? | Rejouable ? |
|---|---|:---:|:---:|
| **Vestibule** | `route_turn`, reconstruction d'état | oui, **avec repli déterministe** | non |
| **Escalier** | les 10 étages | **jamais** | oui |
| **Application** | `study_service`, réservoir | oui, 6 points | partiellement |

> **Règle de séparation.** Le moteur ne parle à personne. C'est ce qui le rend déterministe à
> corpus constant, et ce qui permet de ne persister que les décisions — la trace se rejoue.

---

## 3. Partage d'autorité

> **Le modèle formule, le moteur dispose.**

| Décision | Modèle | Réservoir | Moteur |
|---|:---:|:---:|:---:|
| Écrire la phrase de l'agent | ✅ | — | — |
| Extraire le sujet d'un tour bavard | propose | — | valide |
| Reconnaître une référence | propose | — | tranche |
| Annoter les loci | propose | ajoute | n'écarte jamais |
| Proposer des passages candidats | propose | ajoute | borne la liste |
| **Qualifier une force** (porte / résiste) | — | **jamais** | ✅ seul |
| **Ouvrir une sortie** | — | — | ✅ seul |
| **Servir un verset au pasteur** | jamais | jamais | ✅ seul |
| **Refuser, et le motiver** | — | — | ✅ seul |

**Propriété de sûreté (S37).** Un port qui pourrait *retirer* une option pourrait nuire en se
trompant ; un port qui ne peut qu'*ajouter* ne le peut pas. Tous les appels externes sont
additifs. Une intention hallucinée — ou soufflée par une saisie malveillante — n'ouvre donc
rien : la sortie vient d'un étage franchi, jamais d'une chaîne de caractères.

---

## 4. L'état du fil

> **On ne renvoie jamais l'historique brut au modèle. On reconstruit un état.**

```
EtatFil
  preparation_id      UUID | None      # nul tant qu'aucun travail n'a commencé
  question_ouverte    OpenQuestion|None
  profondeur_atteinte str | None       # dernier étage franchi
  sujet               str | None
  decisions           dict             # ce que le pasteur a tranché, par étage
  corpus_snapshot     str
  embedding_ref       str | None
```

Trois gains pour un mécanisme : le coût par tour cesse de croître avec la longueur du fil ; le
tour redevient rejouable ; un fil repris trois semaines plus tard repart d'un état propre.

---

## 5. Algorithme du tour

**Implémenté** : `app/contexts/urim/conversation/route_turn.py`, 50 tests verts.

```python
def tour(fil, saisie):
    etat = reconstruire(fil)                       # § 4

    # ── Vestibule déterministe — aucun modèle, jamais metered
    lu = lire_tour(saisie, etat)                   # → TurnReading

    # ── Mistral affine, il ne décide pas (point 5, § 6)
    if modele_joignable() and lu.kind in (TurnKind.TRAVAIL, TurnKind.INDECIS):
        affine = modele.vestibule(saisie, etat, lu)
        lu = affine or lu                          # panne ⇒ on garde le déterministe

    if lu.kind in (CIVILITE, META, INDECIS):
        return [bloc_parole(...), bloc_question(...)]     # rien ne s'ouvre

    if lu.kind is COMMANDE:
        return livrable(etat, lu)

    descente = moteur.descendre(etat, lu.carry, jusqu_a=profondeur(lu))
    offres = capacites_constatees(descente)        # § 8
    return blocs(descente) + question_si_ambigu(offres)
```

### Les sept règles de `lire_tour`, dans l'ordre

| # | Règle | Sortie |
|---|---|---|
| 1 | Une question de l'agent est ouverte | `REPONSE` |
| 2 | ≤ 4 mots, tous de politesse | `CIVILITE` |
| 3 | Question sur l'outil lui-même | `META` |
| 4 | Verbe **et** objet livrable | `COMMANDE` |
| 5 | Déclencheur de suite, < 2 mots de fond derrière | `SUITE` |
| 6 | ≥ 3 mots reconnus | `TRAVAIL` |
| 7 | Sinon | `INDECIS` |

**La règle 1 est celle qui rapporte le plus, et elle est gratuite.** Sans elle, « aux jeunes de
l'assemblée » redevient une conviction et relance la chaîne entière.

**L'asymétrie s'inverse par rapport au formulaire.** `route_entry` : en cas de doute →
`conviction`. Le fil : en cas de doute → **on demande**. Ce n'est pas un reniement — dans un
formulaire il n'y avait pas de tour suivant pour se rattraper.

**Deux seuils sont des paris**, à régler sur des saisies réelles et non à l'intuition :
`MOTS_DE_FOND_MINIMUM = 2` et la limite de 8 mots qui distingue une réponse brève d'un
changement de sujet.

**JSON et streaming sont incompatibles.** Un objet ne s'affiche pas mot à mot avant d'être
clos. Sans gravité : `reply` fait deux phrases. Le streaming ne sert qu'au point 6.

---

## 6. Les six points Mistral

Aucun étage n'appelle Mistral. Les quatre appels existants partent tous de `study_service.py`.

### Existants

| # | Ligne | Invite | Reçoit | Rend | Taille | Panne |
|---|---|---|---|---|---|---|
| 1 | 839 | `_SYSTEME_REFERENCE` | la saisie brute | `{found, book, chapter, verse}` | petit | `NullVerseResolver` |
| 2 | 725 | `_SYSTEME_PASSAGES` | le thème | 4 à 6 candidats — **jamais un seul** | moyen | les loci seuls |
| 3 | 872 | `_SYSTEME_AXES` | l'intention | loci annotés | moyen | les 10 loci nus |
| 4 | 873 | `_SYSTEME_RISQUE` | l'intention | marques de forme | petit | pas de marque |

Points 3 et 4 en parallèle. **Aucun ne reçoit de texte biblique** — une phrase française entre,
du JSON sort, `temperature=0`.

⚠️ Le point 4 nomme **l'effet, jamais l'état de celui qui écrit** (S10). *« Formulation à forte
charge — davantage de textes qui résistent sont affichés »* se vérifie et se conteste ; *« vous
êtes dans la plainte »* est un diagnostic, et c'est interdit.

### À créer

| # | Où | Reçoit | Rend | Taille | Metered |
|---|---|---|---|---|---|
| 5 | vestibule, **après** `lire_tour` | saisie + `EtatFil` + `TurnReading` | `{reply, carry, exit}` | petit | ❌ **jamais** |
| 6 | rédaction, après `shape_homiletic` | l'état établi + la péricope | le proforma, **en flux** | grand | ✅ |

⚠️ **Le point 5 ne doit jamais être `metered`.** L'argument de `route_entry` vaut mot pour mot :
*si c'était une étape modèle, au plafond la porte d'entrée elle-même disparaîtrait.* Il
**affine** une lecture déterministe déjà obtenue ; il ne la produit pas.

### Cascade

Un seul `self._model` aujourd'hui. `demander()` prend déjà l'invite en paramètre.

- **Petit** : 1, 4, 5 — fréquents, courts. Le coût dominant est là.
- **Moyen** : 2, 3 — annotation contrainte.
- **Grand** : 6 — rare, cher, et c'est ce que le pasteur vient chercher.

---

## 7. Contrat de marqueurs — rédaction du proforma

Le proforma est **rédigé complet**. Pour développer Romains 8, le modèle doit lire Romains 8 :
la règle « le modèle ne voit jamais l'Écriture » ne survit pas, et il ne sert à rien de faire
semblant. Ce qui survit est plus étroit et plus utile :

> **Le modèle lit le texte. Il ne le restitue pas.**

| Étape | Qui | Quoi |
|---|---|---|
| 1 | Corpus | la péricope entre **en lecture** dans le contexte de rédaction |
| 2 | Modèle | rédige ; pour citer, pose `{{Rm 8:1}}` |
| 3 | Rendu | chaque marqueur est résolu par `serve_corpus` |
| 4 | Rendu | un marqueur non résolu devient un **refus visible dans le document** |

**Provenance au paragraphe.** Chaque bloc porte l'élément du moteur qui l'adosse
(`ContextNote`, `AxisBearing`, `VariantSeen`) ou rien. Ce n'est pas un jugement de qualité :
c'est ce qui permet à la comparaison prêché ↔ préparé de ne comparer que ce qui était adossé
ou validé par le pasteur.

---

## 8. Les sorties constatées

Une sortie n'existe **que** si l'étage qui l'autorise a été franchi.

| Sortie | Condition | Le pasteur reçoit |
|---|---|---|
| `connaissance` | aucun locus ne s'accroche | réponse brève, **marquée non adossée** |
| `recherche` | `resolve_passage` a résolu | le texte, servi par le corpus |
| `etude` | `bound_pericope` a borné | contexte, circonstances, loci, variantes |
| `sermon` | `shape_homiletic` déclare faisable | le proforma complet |

**La porte du sermon ne se ferme jamais ; son aboutissement n'est jamais garanti.** Une porte
fermée ne donne aucun motif ; un chemin qui s'arrête en donne un.

- **Une porte offerte doit s'ouvrir.** Jamais `sermon` sans faisabilité constatée.
- **On n'offre que sur ambiguïté réelle.** `Romains 8:1` n'est pas ambigu — on ouvre le texte.

---

## 9. Le réservoir sémantique

> **Il ne sait pas ce qui est vrai. Il sait ce qui se ressemble.**

Index des péricopes (unités de 3 à 5 versets) sur **pgvector**, consultatif et additif.

### Ce qu'il n'est pas

- **Pas un remplaçant de `serve_corpus`** — il ne contient que métadonnées et vecteurs.
- **Pas un juge de pertinence** — il ordonne par similarité, ce qui n'est pas une évaluation
  théologique.
- **Pas un qualificateur de force** *(R5)*. La similarité cosinus ne détecte pas la
  contradiction : deux textes qui s'opposent sur la guérison sont sémantiquement **proches**,
  ils parlent du même sujet. Le réservoir propose des candidats **sans force** ; c'est
  `BearingSite` — curé, déterministe — qui dit `dominant / porte / resiste / absent`.
- **Pas un diagnostiqueur** — aucun effet, aucune mise en garde.

### Points d'insertion

| Où | Rôle |
|---|---|
| Vestibule | jusqu'à 3 sujets probables, pour aider l'agent à formuler une relance ouverte |
| Étage 2 — `passages` | ajoute des candidats au **vivier** |
| Étage 3 — `axes` | ajoute tags et parallèles ; complète les loci manquants |
| Point 6 — rédaction | parallèles et illustrations, en lecture seule |

### Décisions techniques *(R6–R9)*

| Décision | Motif |
|---|---|
| **Embedding local CPU** (`bge-small`, ~130 Mo) | Vectoriser la requête est en soi un appel modèle. En local, le réservoir devient disponible au **palier 1** — quand Mistral est injoignable ou le plafond atteint. |
| **Scan exact, pas d'index ANN** | ~8 000 péricopes : balayage cosinus sous la milliseconde. Un index approché ne rend pas le même ordre, et casserait le rejeu. |
| **Départage déterministe sur la référence** | À score égal, sinon l'ordre dépend du plan d'exécution Postgres. |
| **Seuil relatif** (les k premiers + écart au suivant) | Un seuil absolu ne veut pas la même chose d'un modèle d'embedding à l'autre, or `embedding_ref` prévoit qu'il change. |
| **Additivité sur le vivier, pas sur l'affichage** | 4 à 6 candidats Mistral + réservoir = douze options. Le réservoir ne remplit que les places libres et ne déloge jamais un candidat d'un autre canal. |
| `embedding_ref` + `corpus_version` persistés | Un fil ouvert ne change jamais de classement. Migration asynchrone, non rétroactive. |

⚠️ **À mesurer avant de graver le modèle d'embedding.** La LSG 1910 est archaïsante ; les
modèles sont entraînés sur du français contemporain. Un pasteur qui tape « burn-out des
responsables » cherche dans un espace où ces mots n'existent pas. **Piste :** vectoriser aussi
les **annotations curées** — thèmes, tags, notes de contexte — qui sont en français moderne.

### Gouvernance

- Aucune colonne `eglise_id` / `tenant_id`. Les notes personnelles sont liées à `author_id` :
  un pasteur qui change d'église **emporte ses notes**.
- Transfert entre pasteurs : explicite, tracé, jamais automatique.
- Agrégats anonymes seulement, seuil de 5, aucune liste nominative.
- Les notes pastorales **ne sont pas vectorisées** — recherche plein texte séparée.
- Les sermons publiés **n'alimentent pas** le réservoir : *un sermon publié est un acte du
  prédicateur, pas une donnée d'entraînement*.

### Provenance

Les candidats du réservoir portent `origin` distinct. Le champ **existe déjà** sur `Option` :
*deux options côte à côte ne valent pas la même chose — « partage 1 des mots rares » et
« traite votre sujet » ne sont pas trouvées de la même façon.*

---

## 10. Paliers de dégradation

Tout passe par le réseau **sauf la Bible**.

| Palier | Condition | Ce qui fonctionne |
|---|---|---|
| **0** | hors ligne | corpus LSG 1910, lecture, résolution de référence |
| **1** | serveur, sans modèle de langue | les 10 étages · les 10 loci nus · **le réservoir** · proforma sec |
| **2** | Mistral joignable | vestibule affiné, relances, rédaction |

Le palier 1 est un produit **sans coût marginal** qui rend déjà l'essentiel — et c'est là que
retombe `ceiling_reached` : au lieu de bloquer, les profondeurs coûteuses cessent d'être
offertes. *(R6 fait entrer le réservoir dans ce palier.)*

---

## 11. Persistance du fil

- `urim_thread` — `preparation_id` **nullable** : le pasteur parle avant de savoir sur quoi il
  travaille.
- `urim_thread_turn` — `state ∈ {en_cours, complet, tronque}` ; `client_token` unique.
- `urim_thread_block` — `kind ∈ {parole, question, texte, refus, outil}` :
  - `CHECK (kind <> 'texte' OR (reference IS NOT NULL AND body IS NULL))` — **le proof-texting
    devient inécrivable**, pas déconseillé.
  - `CHECK (kind <> 'refus' OR body IS NOT NULL)` — jamais un code d'état.
  - `stage` nul ⇒ le bloc vient du modèle. La provenance se lit sans jointure.

---

## 12. Invariants testables

*(Anciennement §10. Le plan de délégation référence cette section.)*

| # | Invariant | Statut |
|---|---|---|
| I1 | `bonjour` n'ouvre aucune préparation et ne touche pas le corpus | ✅ testé |
| I2 | Le tour suivant une question ne crée jamais une entrée | ✅ testé |
| I3 | Seuls `TRAVAIL` et `REPONSE` portent un `carry` | ✅ testé |
| I4 | Le motif n'est jamais vide | ✅ testé |
| I5 | La lecture du vestibule est déterministe et rejouable | ✅ testé |
| I6 | Aucun bloc `texte` ne porte de corps — contrainte de schéma | à écrire |
| I7 | Aucune sortie offerte sans l'étage correspondant franchi | à écrire |
| I8 | Un refus est toujours dit dans le fil, motivé | à écrire |
| I9 | Modèle injoignable ⇒ le fil dégrade, il ne tombe pas | à écrire |
| I10 | Le contexte envoyé au modèle ne croît pas avec la longueur du fil | à écrire |
| I11 | À corpus et décisions constants, la partie adossée d'un proforma est identique | à écrire |
| I12 | Le vestibule n'est jamais `metered` | à écrire |
| I13 | Tout marqueur `{{...}}` non résolu apparaît comme refus visible | à écrire |
| I14 | `weigh_conviction` s'efface dès que `resolved` est posé | à écrire |
| I15 | Le réservoir ne retire **jamais** un candidat d'un autre canal | à écrire |
| I16 | Deux recherches identiques (`embedding_ref`, `corpus_version`) rendent la même liste **dans le même ordre** | à écrire |
| I17 | Une panne du réservoir ne produit aucun bloc `refus` ni changement en aval | à écrire |
| I18 | Le réservoir ne pose jamais de force (`porte` / `resiste`) sur un candidat | à écrire |

---

## 13. Ouvert

- **La controverse confessionnelle.** Il manque une règle au rang de *« il n'écrit pas le
  sermon »* : **Urim ne tranche pas une controverse entre confessions.** Sans elle, le modèle
  tranchera — c'est ce que fait un modèle à qui on pose une question fermée.
- **Le contenu de `weigh_conviction`** — ce qu'il pèse, et ce qui se passe quand la pesée
  penche contre l'axe du pasteur.
- **La carte de style** depuis les transcriptions : mesures de forme uniquement, robustes à un
  taux d'erreur de 25 %, injectées comme contrainte au point 6. Bloquée par le verrou de
  séquencement (trois églises réelles).
- **Rétention audio** — 7 jours ferme la piste des extraits en langue locale. À trancher
  pendant que l'étape 4 est verrouillée.
