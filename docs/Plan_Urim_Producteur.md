# Plan — retrait de `sermon`, Urim producteur

*Décidé le 05/08/2026. Complète `Plan_Implementation_Urim_Finance.md` (§4 Phase 2) et **révoque
D-B / S32**, qui organisaient une coexistence `urim` ↔ `sermon` devenue sans objet.*

---

## 1. La décision

> **Urim produit ce que le fidèle lit.** Le contexte `sermon` disparaît : il n'était qu'un
> producteur doublé d'une surface de réception, et son atelier est moins bien gardé que celui
> d'Urim.

L'argument décisif n'est pas l'économie de code, c'est **l'inversion des protections**. Aujourd'hui :

| | Politique sur un verset affiché | Qui lit le résultat |
| :-- | :-- | :-- |
| `urim` | aucun verset ne sort du modèle · `citation_check` · `textual_variant` · provenance | **un homme**, qui sait ce qu'il a dit |
| `sermon` | une phrase dans le prompt | **toute l'église** |

L'atelier rigoureux sert l'artefact que personne ne voit ; le digesteur sans garde alimente ce que
des centaines de gens lisent. Faire produire Urim **résout cette incohérence par construction** —
c'est le vrai gain du retrait.

### Deux choses que le retrait ne détruit pas, contrairement aux apparences

**La livraison existe déjà et ne bouge pas.** `AnnouncementCapsuleFeedAdapter` publie chaque capsule
comme une **annonce église-entière** de catégorie `sermon`. Le fil d'actualité est déjà la surface
de réception ; `sermon` n'est que ce qui l'alimente. On remplace le producteur, pas le tuyau.

**S-6 et `urim/capture` étaient le même travail.** Le lot « audio / speech-to-text » de `sermon`
n'a jamais été écrit ; la transcription du culte est la raison d'être de `urim/capture`. Le retrait
**supprime une duplication qui existait déjà** au lieu d'en créer une.

---

## 2. Le rayon d'explosion, mesuré

**23 fichiers · 89 occurrences · 3 tables · 10 routes · 2 fichiers de tests.**

| Ce qui disparaît | Détail |
| :-- | :-- |
| Contexte | `app/contexts/sermon/**` — 31 fichiers |
| Tables | `sermons` · `sermon_digests` · `companion_sessions` |
| Routes | 10, sous `/api/mobile/sermons` |
| Câblage | `app/api/router.py` · `migrations/env.py` |
| Tests | `tests/contexts/sermon/test_sermons.py` · `test_file_guards.py` |

### ⚠️ Trois orphelins que la démolition créerait — et c'est exactement la maladie qu'on vient de soigner

Le chantier du 05/08 a passé la journée à brancher des types qui existaient **sans émetteur**
(`GESTURE_DONE`, `record_gesture()`, `gestures_count`). Supprimer `sermon` sans relocaliser en
recréerait trois d'un coup :

| Orphelin | Son unique émetteur aujourd'hui | Conséquence si on démolit d'abord |
| :-- | :-- | :-- |
| `FactKind.GRATITUDE_DEPOSITED` + `GratitudeDepositedV1` + la source `COMPANION` | `sermon/application/commands/gratitude.py` | **La seule parole du membre qui dit que ça va** disparaît de la veille. L'interpreter reste enregistré et n'est plus jamais appelé |
| `AttendanceSource.DECLARED` | `sermon/infrastructure/culte_attendance.py` | La 3ᵉ voix de la présence perd son seul écrivain |
| `tests/test_model_output_is_untrusted.py` (DOREA-025) | importe `_from_json` du digesteur | Le garde « la sortie d'un modèle est une entrée non fiable » perd la moitié de son sujet |

**Règle du chantier : on relocalise avant de démolir.** Aucune suppression tant que R0-R3 ne sont
pas verts.

---

## 3. L'ordre — relocaliser, puis démolir

| Lot | Contenu | Fini quand |
| :-- | :-- | :-- |
| **R0** | **Gratitude → `watch`.** La route passe sous `/api/mobile/watch/…`. Aucun concept nouveau : `COMPANION` est **déjà** une source enregistrée de `watch`, et `watch` porte déjà la surface membre (inquiétude, geste, liens, react) | Un dépôt de reconnaissance entre au ledger sans passer par `sermon` |
| **R1** | **Présence déclarée → `attendance`.** L'adaptateur écrit déjà en direct dans les tables de Présence ; il change de maison, pas de comportement | Un « j'ai vécu le culte » pose une présence `declared` sans `sermon` |
| **R2** | **L'adaptateur de capsules devient un port d'Urim.** `CapsuleFeedPort` et son implémentation Annonces migrent ; la catégorie `sermon` du fil **survit** — c'est un type d'annonce, pas un contexte | Une capsule publiée depuis Urim apparaît dans le fil, à l'identique |
| **R3** | **Le compagnon : décision.** Voir §6 — recommandation : **retrait**, la branche perd son objet | Tranché et écrit |
| **R4** | **Démolition.** Contexte, tables (migration de suppression), routes, câblage, tests. DOREA-025 re-pointé sur le producteur d'Urim | `grep contexts.sermon` rend 0 · la suite complète est verte |

> **La migration de suppression n'est pas gratuite.** Les trois tables portent des données réelles
> dès qu'une église a déposé un sermon. Prévoir un export avant `DROP`, ou une fenêtre où la
> livraison est encore vide — c'est une décision d'exploitation, pas de code.

---

## 4. Ce que le retrait change **dans** Urim

Urim gagne une responsabilité qu'il n'a jamais eue : **publier**. Trois conséquences, et la
première casse un test au premier commit.

**① Le test de frontière va rougir, et il doit rougir délibérément.**
`test_urim_n_importe_rien_hors_de_lui_meme` interdit tout import hors-Urim en dehors de
`calendar/adapters/`. Le jour où Urim importe `announcements`, il casse. **C'est le bon
comportement** — le même patron que S28 : on étend la liste blanche par une décision nommée, jamais
par une exemption large.

```
_AUTORISE_DEPUIS_LES_ADAPTATEURS = (
    "app.contexts.watch.application.aggregates",     # S14 — lire, jamais écrire
    "app.contexts.announcements.…",                  # R2 — publier, jamais lire
)
```

**② Une règle à poser, sinon quelqu'un la déduira de travers.**

> **Publier n'est pas écrire dans la veille.** Le mur `urim → watch` ne bouge pas d'un pouce : une
> préparation ne crée toujours ni fait, ni cas, ni signal. Elle crée une **annonce**, que des
> membres liront — et ce sont *leurs* actes qui, ensuite, parlent à la veille.

**③ La chaîne transitive doit être nommée.** Après R0, la gratitude part de `watch`, donc la
chaîne `urim → annonce → membre → fait de veille` existe. Elle est **légitime** par symétrie avec
S11 (*le mur porte sur l'initiative de la machine, pas sur la parole de l'homme*) — mais aucun test
d'imports ne peut la voir, puisqu'elle traverse deux contextes. À écrire dans `ports.py`, là où on
la lira.

---

## 5. Les chantiers Urim

Ordre repris de la spec §8, **inchangé** — le retrait de `sermon` n'en déplace aucun. Il en ajoute
un à la fin.

| # | Chantier | Livre | État |
| :-- | :-- | :-- | :-- |
| **0** | Socle du moteur — contrat pur, 4 tests d'architecture | `StudyState`, `Outcome`, `EngineDeps`, `run()` rejouable | ✅ **livré** (13 tests) · `PIPELINE` **vide** |
| **0b** | Couche anticorruption | `EcclesialContextPort` AFFICHAGE SEUL, `NullEcclesialContext`, adaptateur d'agrégats | ✅ **livré** (26 tests) |
| **1** | **Corpus** | schémas `urim_corpus`, péricopes curées, `textual_variant`, `versification_map`, acquisition + apparat critique | ⛔ bloqué par **D-A** |
| **2** | **Livrable** | l'écran minimal : une entrée → un résultat motivé | dépend de 1 |
| **3** | Résolution | étages 0-1 : router l'entrée, résoudre la référence, **entrée hybride** (S16), normaliseur partagé (S21) | dépend de 1 |
| **4** | Bornage | étage 2 : coïncide / coupe / englobe (D-E, S8), contrainte négative (S18), hors-bornes (S19) | dépend de 3 |
| **5** | Doctrine | étages 3-5 : les **10 loci** semés, `doctrinal_bearing`, textes **résistants** (§7), caveats (D-F) | dépend de 1 |
| **6** | Moteur assemblé | les 8 étages branchés dans `PIPELINE` — les tests d'architecture cessent d'être vrais par vacuité | dépend de 3-5 |
| **7** | Homilétique | étages 6-7 : `homiletic_feasibility`, `proof_text_risk`, proposition de thème | dépend de 6 |
| **8** | Archive & dictée | `urim.preached` (clé `author_id`), la dictée | dépend de 6 |
| **9** | Plafond | `study_reservation.metered_at`, `usage_window`, repli LSG (S6) | dépend de 2 |
| **10** | **Capture** *(nouveau nom du lot S-6)* | fragments Opus, file de travaux, `TranscriptionPort`, deux détecteurs de versets, purge J+7 | ⛔ bloqué par **S31** |
| **11** | **Publication** *(nouveau — ce que `sermon` faisait)* | dépôt, digest **avec provenance**, approbation, capsules → fil | dépend de 6 et de R2 |

### Le chantier 11 en détail — parce que c'est lui qui remplace `sermon`

| Étape | Ce qu'elle apporte | Ce qu'elle corrige par rapport à `sermon` |
| :-- | :-- | :-- |
| 11a | Entrée : texte, PDF, PPTX (l'extracteur de `sermon` est réutilisable tel quel) | rien — c'est un portage |
| 11b | **Digest avec provenance** : chaque capsule porte ses `segment_refs` dans le texte source | le digest actuel n'a **aucun** lien vers sa source |
| 11c | **Discipline des versets** : le modèle rend une *référence*, jamais un *texte* ; la Bible fournit le texte | patron **déjà écrit** dans `mission/verse_resolver.py` — à appliquer, pas à inventer |
| 11d | Approbation du pasteur, puis gel | inchangé — *rien de non approuvé n'atteint le membre* |
| 11e | Publication des capsules dans le fil | inchangé — l'adaptateur existe |

> **11c est le lot le plus rentable de tout le plan** : le patron existe, il est testé, et il
> protège ce que le plus grand nombre lit.

---

## 6. Le compagnon — la seule vraie perte, et pourquoi elle se défend

Le compagnon posait *« as-tu vécu le culte ? »* et branchait : **oui** → consolider, **non** →
enseigner. Sa valeur tenait à une chose : le sermon était un **artefact privé**, et celui qui avait
manqué le culte n'avait aucun autre moyen de le rattraper.

**Une fois les capsules dans le fil, la branche perd son objet** : tout le monde lit les mêmes
capsules, présent ou absent. Le compagnon devient une question dont la réponse ne change plus rien.

Recommandation : **retirer**, et laisser la capsule enseigner. Deux conséquences à assumer :

- la question *« as-tu vécu le culte ? »* disparaît, donc la présence `declared` perd son point
  d'entrée naturel. R1 la relocalise ; à l'église de décider si elle veut encore la demander ;
- `CompanionSession.attended = False` disparaît avec la table — et c'est un **bon débarras** : cette
  donnée disait *« cette personne a déclaré ne pas être venue »* et vivait dans un contexte sans
  frontière de transparence, sans `DO_NOT_CONTACT` et sans purge. Un écran *« qui n'a pas vécu le
  culte ? »* était à une requête de distance.

---

## 7. Les verrous — ce que ce plan **n'autorise pas** à démarrer

Aucun de ces verrous n'est technique. Ils tiennent tous.

| Verrou | Ce qu'il bloque | Ce qu'il faut pour le lever |
| :-- | :-- | :-- |
| **Architecture v2 §11** — *« Urim n'est PAS autorisé à la construction »* | tout Urim au-delà du socle | **un dimanche réel dans une église réelle** — 3 des 4 conditions levées, celle-ci non |
| **D-A** — schémas Postgres dédiés vs préfixes | chantier 1, donc 3-7 | une décision, une séance |
| **S31** — `Dorea_Urim_Capture_et_Retour.md` manquant | chantier 10 | le document : 4 tables référencées sans définition |
| **Capture §11** — étape 1 seule | la synthèse tirée du transcrit | **taux d'erreur mesuré dans 3 églises** |

> Ce dernier verrou touche directement ta phrase *« ce que le fidèle voit, c'est ce que le pasteur
> a prêché, transcrit »*. Elle deviendra vraie littéralement — mais **après** la mesure, pas avant.
> *« Une synthèse bâtie sur une transcription non mesurée est une invention présentée comme un
> souvenir. »* D'ici là, le chantier 11 prend le texte **déposé**, pas le transcrit.

---

## 8. L'ordre recommandé

```
R0 gratitude → watch          ─┐
R1 présence déclarée → attendance │ relocalisation — rien ne casse, rien ne se perd
R2 capsules → port d'Urim      ─┘
R3 compagnon : décision écrite
R4 démolition de `sermon`

           ↓  (le dépôt est propre, Urim est seul producteur)

D-A tranché  →  chantier 1 corpus  →  2 livrable  →  3-5  →  6 moteur assemblé
                                                              ↓
                                        11 publication (11c en premier)
                                                              ↓
                              §11 levé ?  →  7 homilétique · 8 archive · 9 plafond
                              S31 + 3 églises ?  →  10 capture
```

**R0 → R4 est faisable tout de suite** : aucun verrou ne les couvre, et le dépôt en sort plus
simple qu'avant. Tout ce qui suit attend une décision (D-A) ou un dimanche.

---

## 9. Ce qu'on perd, dit franchement

- **10 routes livrées et testées** disparaissent ; le fil, lui, garde ses capsules ;
- **le compagnon** — le seul objet du produit qui parlait à un membre en tête-à-tête d'un sermon ;
- **la question d'entrée** *« as-tu vécu le culte ? »*, et avec elle la manière la plus douce
  qu'avait Dorea de recueillir une présence sans demander un scan ;
- et une capacité qui n'existait qu'en théorie : `sermon` marchait **sans corpus**. Urim ne
  produira rien tant que le chantier 1 n'aura pas semé les péricopes curées. **Le retrait échange
  un producteur médiocre disponible aujourd'hui contre un producteur rigoureux disponible plus
  tard.** C'est un bon échange, à condition de le faire les yeux ouverts.
