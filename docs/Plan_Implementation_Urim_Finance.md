# Plan d'implémentation — `urim` & `finance` dans `back-dorea`

**2026-08-03** — cadre l'exécution de `UrimEngine_Specs_Implementation.md` (2026-08-02) et
`Dorea_Finance_Decisions_et_Specs.md` (2026-08-02) **dans ce dépôt**.
**Statut :** plan. Rien ne commence avant le verrou (§1).

> Ce document ne réécrit pas les specs — il les **confronte au code existant**, corrige ce qui a
> changé, et donne l'ordre d'exécution. Les specs font foi sur le *quoi* ; ce plan sur le *où* et
> le *quand*.

---

## 1. Le verrou de séquencement — état réel

Les deux specs subordonnent tout à la même condition (Urim §9, Finance §12) :

| # | Condition | État vérifié dans le code (2026-08-03) |
| :-- | :-- | :-- |
| 1 | Écran de captation des présences, testé en réel | Contexte `attendance` **livré**, routes montées (`/api/mobile/attendance/*`, backoffice). **Front + dimanche réel : hors dépôt, non vérifiable ici** |
| 2 | Émetteur `CasePriority.ABSENCE` activé | ✅ **Levé.** Le doc de corrections constatait au 30/07 « la détection d'absence n'a pas d'émetteur » ; il en existe un aujourd'hui — `watch/application/interpreters/check_fired.py:118` émet `origin=CasePriority.ABSENCE` |
| 3 | Corrections `Moteur_Corrections_et_Regime_Hybride.md` appliquées | ✅ **Vraisemblablement levé.** Le doc est dans `docs/` et le chantier veille (6 lots) est marqué terminé le 01/08/2026 — cf. §0 du doc et l'émetteur ci-dessus. *À confirmer par l'auteur* |
| 4 | **Un dimanche réel, dans une église réelle** | ❌ **Non atteint** — **c'est le seul verrou qui reste** |

**Conclusion :** le code n'est pas le blocage ; l'usage réel l'est. **R1 (dispersion) reste le risque
dominant.** Ce plan existe pour être prêt, pas pour être lancé.

### 1bis. Documents — **complets depuis le 2026-08-03**

`Dorea_Urim_Architecture_v2.md` et `Dorea_Urim_Structure_et_Schema.md` ont été fournis et **copiés
dans `docs/`**. Le schéma du corpus est disponible : plus aucun blocage documentaire.

⚠️ **Mais Architecture v2 §11 est explicite : « Urim n'est pas autorisé à la construction. »**
L'ordre non négociable y est repris (présences → émetteur ABSENCE → corrections moteur → **dimanche
réel** → *alors seulement, réexamen d'Urim*). Les trois premières conditions sont levées ; **la
quatrième ne l'est pas**. Le socle du chantier 0 a été livré sur demande explicite de l'auteur ;
la suite (corpus, résolution, doctrine) reste subordonnée à ce §11.

---

## 2. Ce que le code dit — corrections aux specs

Points où la réalité du dépôt diffère de ce que les specs supposent. **À trancher avant le chantier 0.**

| # | Spec | Réalité du code | Impact |
| :-- | :-- | :-- | :-- |
| **C1** | Finance §13.1 « Le trésorier est-il un rôle IAM existant ? — à vérifier » | ✅ **OUI** : `RoleCode.TREASURER` existe **avec permissions** `VIEW_CONTRIBUTIONS` + `RECORD_CASH` (`iam/domain/permissions.py:131`), commentées « la comptabilité, pas la curiosité ». Il existe même une paire `(LAUNCH_COLLECTION, VIEW_CONTRIBUTIONS)` | **Point ouvert #1 CLOS.** Finance se greffe sur l'IAM existant, ne crée pas de rôle |
| **C2** | Specs : `CREATE SCHEMA finance` / `urim_corpus`, migrations `001…011` | Le dépôt n'utilise **aucun schéma Postgres** (tout en `public`), et Alembic a **une seule chaîne linéaire** de révisions (tête actuelle `e5f6a7b8c9d0`) | **Décision requise** : adopter les schémas dédiés (isolation forte, cohérent « couture d'extraction ») **ou** rester en `public` avec préfixes `urim_*`/`finance_*`. Les migrations devront s'insérer dans la chaîne existante, pas repartir de `001` |
| **C3** | Urim : étage `preached` / archive de prédication | Le contexte **`sermon` existe déjà** (S-0→S-5 : dépôt, digestion IA, capsules, compagnon, `preached_on`) | **Frontière à tracer** : `urim` = *préparer* (avant), `sermon` = *ce qui a été prêché et vit après*. `POST /urim/preached` **chevauche** `sermon`. Décider : Urim écrit-il dans `sermon` via un port, ou duplique-t-il une archive ? |
| **C4** | Finance §4.2 : devise portée par une table `finance.currency` | `tenants.currency` **existe déjà** (défaut `XOF`, ISO 4217, cf. M0 §2.2) | Réutiliser la devise du tenant comme défaut ; `finance.currency` reste la table d'exposants (XOF=0, EUR=2) |
| **C5** | Urim §10 / Structure §5 : « où vit le calendrier des rencontres ? — 10 min dans back-dorea » | Les rencontres vivent dans **`attendance`** (`gatherings`), les RDV dans **`appointments`**, les événements dans **`events`** — **hors `watch`** | ✅ **Vérification faite : hors `watch`.** Donc, par la spec, **l'adaptateur d'événements disparaît** ; seul `watch_aggregate_adapter` subsiste. Rien à extraire de `watch` au préalable |
| **C6** | Finance §13.2 : multi-sites, fonds par site ou par église ? | **Tranché depuis** : une annexe **est un tenant** (M0 §4.1, filiation plate) | → **fonds par `church_id` = par tenant**. Une annexe a ses propres fonds. Consolidation famille = lecture sur l'arbre `parent_id` (même brique que la taille-famille) |

---

## 3. Où ça vit — arborescence cible

Deux contextes bornés de plus, au même rang que les 16 existants :

```
app/contexts/
  finance/        domain · application · infrastructure · interface
  urim/
    engine/       outcomes.py · state.py · stage.py · stages/ · deps.py   (PUR)
    domain/ application/ infrastructure/ interface/
```

**Règles de frontière (non négociables, déjà la norme du dépôt) :**
- Aucune FK inter-contexte : `church_id`/`member_id` circulent en `uuid` nu.
- Un contexte n'en appelle un autre que par **port + adaptateur**.
- `urim/engine/` est **pur** : ni I/O, ni horloge, ni session — tout passe par `EngineDeps`.

---

## 4. Ordre d'exécution

### Phase 0 — Décisions (aucun code)
Trancher **C2** (schémas vs préfixes) et **C3** (frontière urim/sermon). Fournir le doc
`Moteur_Corrections_et_Regime_Hybride.md` (verrou #3). ~1 séance.

### Phase 1 — FINANCE (Registre V1) — *démarre en premier*

**Pourquoi Finance avant Urim :** valeur seule dès la première semaine (« remplace le cahier du
trésorier »), aucune dépendance au corpus ni à l'IA, rôle IAM **déjà là** (C1), et c'est le contexte
« qui sortira en premier si quelque chose sort » (Finance §10). Urim est plus lourd (corpus,
déterminisme, doctrine) et sa valeur arrive plus tard.

| Lot | Contenu | Fini quand |
| :-- | :-- | :-- |
| **F0** | Socle : contexte `finance`, tables `currency`/`fund`/`period`/`entry`, **trigger d'immuabilité**, migration | Un `UPDATE` sur `entry` **échoue en base** |
| **F1** | Journal : écriture entrée/sortie, **collecte anonyme** (`donor_id` NULL = normal), **comptage à deux** (`counted_by[]` + `variance_minor`) | Une offrande de panier s'enregistre **sans donateur** |
| **F2** | Contre-passation + exercices : `reverses_id`, clôture de période, refus d'écriture sur période close | Aucune correction ne modifie une ligne |
| **F3** | Reçus : séquence **sans trou** par (église, exercice), allouée **à la validation** ; annulé reste dans la série | L'index unique tient sous concurrence |
| **F4** | Fonds & transferts : soldes, transfert **avec motif obligatoire** | Un transfert sans motif est refusé |
| **F5** | Visibilité : trésorier = tout ; membre = le sien ; **pasteur = soldes/rapports, jamais le nominatif** ; responsable = rien | Les 3 tests de frontière (§10 spec) passent |
| **F6** | Engagements (`pledge`) : **aucune colonne d'état, aucun signal, aucune relance** | Un test prouve qu'aucun fait de veille n'est émis |
| **F7** | Projets & rapport d'assemblée **figé** (`payload jsonb`) | Un rapport se réaffiche à l'identique après contre-passation |

**Les 3 tests de frontière (à écrire en F0, rouges d'abord) :**
`test_watch_n_importe_jamais_finance` · `test_finance_n_emet_aucun_fait_de_veille` ·
`test_aucune_lecture_de_contribution_hors_tresorier`.

### Phase 2 — URIM (le moteur)

Ordre des chantiers **repris de la spec** (§8), avec sa justification propre — livrable en 2 parce
qu'il ne dépend que du corpus :

`0` socle + les 4 tests → `1` corpus → **`2` livrable** → `3` résolution → `4` bornage →
`5` doctrine → `6` moteur assemblé → `7` homilétique → `8` archive/dictée → `9` plafond.

> **Chantier 0 — socle du moteur : LIVRÉ le 2026-08-03** (`app/contexts/urim/engine/`, 13 tests).
> Contrat complet et **pur** : `errors.py` · `state.py` (`StudyState` immuable, `with_`, `trace`) ·
> `outcomes.py` (`Outcome`, `Option`, `StageResult` + invariants) · `deps.py` (ports + `EngineDeps`,
> `FORBIDDEN_FOR_STAGES`) · `stage.py` (Protocol) · `pipeline.py` (`UrimEngine.run/resume`, `EngineRun`).
> **`PIPELINE` est vide** : les 8 étages dépendent du schéma corpus (§1bis) et viennent aux chantiers 1→7.
> Les tests qui itèrent `PIPELINE` sont donc vrais par vacuité — c'est pourquoi chacun est **doublé
> d'une preuve sur un étage-témoin fautif** : c'est le *détecteur* qui est testé, pas le vide.

**Les 4 tests d'architecture (chantier 0, rouges d'abord) :**
- `test_urim_n_importe_rien_hors_de_lui_meme`
- **`test_aucun_etage_ne_lit_le_contexte_ecclesial`** ← *le plus important du dépôt* : interdit **par
  programme** que les agrégats de veille atteignent une proposition de thème (AFFICHAGE SEUL)
- `test_determinisme` (100×, même `corpus_snapshot`)
- `test_tout_resultat_porte_un_motif`

**Invariants à ne pas négocier :** `rationale` jamais vide · `AWAIT` = état normal, pas une erreur ·
`DEGRADE` ne coupe jamais (« aucun mur un vendredi soir ») · `run()` pure · réservation vérifiée
**à l'ouverture seulement**.

> **Le schéma : LIVRÉ le 2026-08-06** — migration `a1b2c3d4e5f7`, **33 tables**, préfixes D-A.
> `app/contexts/urim/infrastructure/persistence/` : `corpus_models.py` (18 tables, global immuable)
> et `models.py` (15 tables, tenant + auteur, capture et Retour compris). Appliquée, aller-retour
> `downgrade`/`upgrade` vérifié, `alembic check` propre.
>
> **Semé dans la migration :** les dix `doctrinal_axis`, les trois `plan_source`, les six
> `subject_matter` — dix-neuf codes de référence que la spec fixe littéralement et vers lesquels
> trois tables pointent. **Rien d'autre** : péricopes, pesées, caveats, notes de contexte et
> faisabilités portent `reviewed_by NOT NULL`, et une migration ne signe pas à la place d'un
> relecteur. Ces tables sont donc **vides**, et les étages travaillent contre des ports sans
> adaptateur : c'est le chantier 1 (corpus) qui reste, et il est **éditorial avant d'être
> technique**.
>
> **Six règles produit sont désormais dans la base**, et `tests/contexts/urim/test_schema_urim.py`
> prouve que chacune mord — chaque cas présente le couple : la ligne légitime que la base accepte,
> sa jumelle fautive qu'elle refuse. Une contrainte qui rejette tout ne prouve rien.
>
> **Trois écarts assumés au DDL de la spec**, tous documentés dans les modules :
> 1. `preparation.bounds_override int4range` → **quatre colonnes** `override_start_ch/_v`,
>    `override_end_ch/_v`. Un intervalle d'entiers ne peut pas exprimer un empan chapitre+verset :
>    Galates 5:16 → 6:2 n'est pas un intervalle. `pericope` et `preached` utilisent déjà quatre
>    colonnes dans la même spec ;
> 2. **les index trigrammes et plein-texte ne sont pas dans cette migration.** `gin_trgm_ops` et
>    `to_tsvector` exigent `pg_trgm` et une expression que SQLite ne lit pas — or la base de test
>    se construit depuis les modèles. Ils appartiennent au chargement du corpus, avec les millions
>    de lignes qui les justifient ;
> 3. **les FK internes à `urim` restent** là où la spec les déclare (elles portent un
>    `ON DELETE CASCADE`, un comportement et pas seulement une garantie) ; les tables de la capture
>    font exception, leur propre spec ayant choisi l'intégrité applicative partout.
>
> **Ce que la migration a appris.** `confessionnel_borne` mordait en Postgres et **passait en
> SQLite** : le type `JSON` — variante de `text[]` pour les tests — sérialise `None` en chaîne
> `null`, qui n'est pas `NULL` pour SQL. Corrigé par `none_as_null=True`. C'est exactement le mode
> de panne que `test_schema_integrity.py` raconte dans son en-tête : une garde qui n'existe que là
> où personne ne la vérifie. Elle a été trouvée parce que le test exige le **couple** accepté/refusé.

---

## 5. Ce qui peut avancer **sans** attendre le verrou

Sans écrire une ligne de code produit :
- **Finance** : instruction réglementaire mobile money, échanges PSP, conservation légale (point
  ouvert #5), format d'export comptable (#3). *Délais externes non compressibles.*
- **Urim** : acquisition/vérification du corpus (LSG 1910, Darby, SBLGNT, Strong — licences), et
  les **40 péricopes doctrinales** à semer (chantier 5) — travail éditorial, pas technique.
- **Les deux** : trancher C2/C3 (Phase 0).

---

## 6. Risques

| # | Risque | Mitigation |
| :-- | :-- | :-- |
| **R1** | **Dispersion** — deux gros contextes ouverts avant qu'un dimanche réel ait eu lieu | Le verrou §1. Ne pas ouvrir Urim tant que Finance F0–F3 n'est pas livré |
| **R2** | Frontière veille↔finance franchie par confort produit (« montrer qui ne donne plus ») | Les 3 tests de frontière, écrits **avant** le code |
| **R3** | Doublon `urim`/`sermon` (C3) non tranché → deux archives de prédication | Phase 0 obligatoire |
| **R4** | Migrations : specs numérotées `001…011` vs chaîne Alembic existante | Insérer dans la chaîne (`down_revision` = tête courante), jamais repartir de zéro |
| **R5** | Immuabilité contournée par une migration maladroite | Trigger **en base** (pas applicatif) dès F0 |

---

## 7. Décisions attendues (Phase 0)

| # | Question | Recommandation |
| :-- | :-- | :-- |
| **D-A** | Schémas Postgres dédiés (`finance`, `urim`, `urim_corpus`) ou préfixes en `public` ? | ✅ **Tranché par les specs elles-mêmes** : `CREATE SCHEMA urim_corpus;`, `CREATE SCHEMA urim;`, `CREATE SCHEMA finance;`. Le dépôt n'en utilisait aucun — ces trois contextes inaugurent la pratique |
| **D-B** | `urim.preached` vs contexte `sermon` existant | ✅ **Tranché 2026-08-04 : « Urim prépare, `sermon` publie »** — les deux coexistent, reliés par un **port** unidirectionnel. Détail ci-dessous |

**Correction que la spec s'applique à elle-même (Structure §3.9)** — à ne pas rater à l'écriture des
migrations : **aucune FK de `urim` vers `urim_corpus`**. Les `REFERENCES urim_corpus.*` des §3.4/§3.5
doivent être **retirées** (uuid nu, intégrité applicative) — le corpus est destiné à migrer vers une
base de lecture séparée, et une FK inter-bases n'existe pas.
| **D-C** | Séquence de reçus : par exercice ou continue | **Par exercice** (recommandation de la spec, #4) |
| **D-D** | Fonds en multi-sites | **Par tenant** (une annexe = un tenant, C6) |
| **D-E** | Étage 2 (bornage) : `AWAIT` systématique ou conditionnel ? | ✅ **Tranché 2026-08-03 : `AWAIT` uniquement quand la demande COUPE une unité.** Si les bornes demandées coïncident avec la péricope curée → `CONTINUE` sans interrompre. On ne fatigue pas un pasteur qui a déjà visé juste ; on ne le laisse pas prêcher un texte amputé sans l'avoir dit |
| **D-F** | Mise en garde **confessionnelle** : s'affiche-t-elle si la tradition de l'église est inconnue ? | ✅ **Tranché 2026-08-03 : OUI, elle s'affiche toujours** — voir la note ci-dessous (formulation « les traditions divergent », pas « votre tradition dit ») |

### D-E — le bornage n'interrompt que s'il y a quelque chose à dire

```
bornes_demandées == péricope curée   → CONTINUE (motif tout de même tracé)
bornes_demandées ⊂ ou ⊄ péricope     → AWAIT + deux options :
                                         · la péricope (motif curé, source_ref)
                                         · la demande telle quelle (bounds_overridden = true)
```
Cas d'école : `Rom 1:16` **coupe** `Rom 1.16-17` (le v.17 fonde le v.16 par γάρ) → `AWAIT`.
Mais `Rom 1:16-17` → `CONTINUE` : rien à arbitrer.

### Constats des simulations à blanc (2026-08-03)

Trois essais sur papier — `Rom 1:16` (référence), une **citation fusionnée**, une **conviction** — ont
fait remonter ceci **avant** qu'une ligne d'étage soit écrite :

| # | Constat | Statut |
| :-- | :-- | :-- |
| **S1** | **Le schéma ne pouvait pas exprimer « résiste ».** `doctrinal_bearing.strength` n'acceptait que `dominant/porte/absent`. Or §7 exige d'afficher les textes **résistants** au même rang que les portants. `absent` (ne dit rien) ≠ `resiste` (complique ou contredit) — seule la seconde protège du proof-texting. **Le mode conviction était inconstructible.** | ✅ **Corrigé (confirmé)** : `'resiste'` ajouté au CHECK, cf. `Structure_et_Schema.md §3.2`. Additif, aucune reprise |
| **S2** | **« Aucun candidat » viole un invariant du moteur.** `StageResult` refuse un `AWAIT` sans options. Si une citation ne matche rien — ou si une conviction ne touche aucune péricope curée — l'étage **ne peut pas** rendre `AWAIT`. | ✅ **Tranché 2026-08-04 : `REFUSE` motivé** — voir ci-dessous |
| **S3** | **La conviction est le seul chemin où le corpus curé est un plafond dur.** En référence/citation, un texte non curé se sert quand même (le corpus est complet, seule la doctrine est curée). En conviction on **part** de la doctrine : hors des 40 péricopes semées, il n'y a littéralement rien à proposer. | ⏳ **À dire au pasteur sans détour**, plutôt qu'une liste maigre sans explication. Question de formulation, pas de schéma |

Deux essais de plus — **le livrable** (une diapositive retapée) et **le plafond** (un vendredi soir) :

| # | Constat | Statut |
| :-- | :-- | :-- |
| **S4** | **La validation de sortie confondait troncature et altération.** Couper la fin d'un verset pour l'écran est légitime et universel ; un booléen `matches_corpus` rejette la troncature au même titre qu'un mot changé → le pasteur contourne la validation, **et le garde-fou meurt de son excès de zèle**. | ✅ **Corrigé** : `verdict IN ('exact','extrait','altere')` remplace le booléen (`Structure §3.6`). Règle : **sous-chaîne contiguë** du corpus après normalisation ; `…` autorise plusieurs fragments contigus, dans l'ordre, sans chevauchement |
| **S5** | **`citation_check` comparait des références brutes.** Selon que le titre du psaume est compté, « Psaume 51:12 » désigne deux versets différents → faux rejets, ou pire, validation du mauvais verset. | ✅ **Corrigé** : la comparaison porte sur la référence **traduite via `versification_map`** (`Structure §3.6`). Code, pas schéma |
| **S6** | **Réserver ≠ consommer.** La réservation était posée à l'ouverture, où l'on ignore encore si la préparation touchera une ressource facturée. Compter là faisait **mentir §13** (« un pasteur sur Segond 1910 ne rencontre jamais aucune limite »). | ✅ **Corrigé** : colonne `study_reservation.metered_at` (NULL = n'a rien coûté) ; `metered_units` ne s'incrémente qu'au **premier service `metered`**, via un `UPDATE … WHERE metered_units < ceiling` **atomique** (règle aussi la course à `ceiling-1`). La règle §6 se reformule : **vérification à la première consommation, puis droit acquis** pour la durée de la réservation — l'intention (« une préparation commencée va jusqu'au bout ») est préservée, ancrée au bon endroit |

> **S6 était le plus grave** : une promesse produit que le mécanisme ne tenait pas. Découvert sur
> papier, il coûte une colonne ; découvert en production, c'est un pasteur facturé pour du domaine
> public. **Les trois corrections sont additives et gratuites — aucune table urim n'existe encore.**

Quatre essais de plus — **Col 1:27** · **Galates 5** (un chapitre) · une **conviction de détresse** ·
**la veille annonce 30 décisions** :

| # | Constat | Statut |
| :-- | :-- | :-- |
| **S7** | `Reference.verse_start` était **obligatoire** → « Galates 5 » (chapitre entier) inexprimable. Défaut du socle, pas de la spec | ✅ **Corrigé dans le code** : `verse_start: int \| None` + propriété `is_whole_chapter` (+ test) |
| **S8** | **D-E ne couvrait que « la demande coupe ».** Une demande peut aussi **englober** plusieurs unités (Gal 5 = 5:1-12 · 5:13-15 · 5:16-26) | ✅ **Tranché 2026-08-04 : `AWAIT` à N+1 options** — règle complète de bornage ci-dessous |
| **S9** | **`pericope_key` calculée sur l'entrée brute, avant l'affinage du bornage** → ouvrir large puis resserrer crée une **2ᵉ réservation** → double comptage. Touche aussi `Rom 1:16` | ✅ **Corrigé (spec §3.7)** : clé **provisoire** à l'ouverture, **re-clée** sur la péricope résolue (UPDATE, jamais INSERT) ; si une réservation active existe déjà, on libère la provisoire |
| **S10** | **Une conviction est souvent une plainte, pas un thème.** « trop de malades, malgré les prières rien ne va » : sujet apparent = *guérison*, sujet réel = *prière sans réponse / lamentation*. Un mapping naïf produit un sermon qui **blesse des malades** (« ayez plus de foi ») | ✅ **Tranché 2026-08-04 : proposer les deux axes** — voir ci-dessous |
| **S11** | **`AFFICHAGE SEUL` porte sur l'initiative de la MACHINE, pas sur la parole du pasteur.** Il peut porter lui-même la situation de son église dans sa conviction — c'est légitime. Ce qui est interdit : que le moteur aille **corroborer** cette conviction dans les agrégats | ✅ **Tranché 2026-08-04** : écrit dans `urim/calendar/domain/ports.py` — le mur porte sur l'initiative de **la machine**, pas sur la parole du pasteur |
| **S12** | **Si `conviction → axes` est une étape modèle**, elle est `metered` → au plafond elle se désactive (§13) → **le mode conviction perd sa porte d'entrée**, « aucun mur » devient faux pour ce chemin | ✅ **Tranché 2026-08-04 : repli manuel sur les axes curés** — voir ci-dessous |
| **S13** | **Le cas « 30 décisions » est le test le plus dur d'`AFFICHAGE SEUL`** : la tentation y est maximale parce que l'usage serait *bon*. À documenter comme cas d'école — c'est lui qui justifie le test bytecode auprès de qui n'a pas lu la spec | ✅ **Tranché 2026-08-04** : le cas « 30 décisions » est documenté comme cas d'école dans `ports.py` — c'est lui qui justifie le test bytecode auprès de qui n'a pas lu la spec |
| **S14** | **`watch` n'exposait aucun agrégat non nominatif.** Les 30 décisions y vivent comme **30 `Signal` nominatifs** (écrits par `mission`). `watch_aggregate_adapter` n'avait rien à appeler | ✅ **LIVRÉ 2026-08-04** — read-model construit, détail ci-dessous |
| **S15** | **« Évangélisation / campagne » n'est pas dans la liste blanche** des 7 types. L'événement est **invisible par défaut** — comportement voulu (*fail closed*), mais qui demande une décision explicite | ✅ **Tranché 2026-08-04** : `EVANGELISM` **ajouté** à la liste blanche (codes en anglais comme les 7 autres ; seul l'affichage est traduit). Enum, test de liste close et `CHECK` du schéma mis à jour |

> **S14 corrige une conclusion trop rapide de C5.** J'avais écrit « le calendrier est hors `watch` ⇒
> l'adaptateur d'événements disparaît, seul l'adaptateur d'agrégats subsiste ». Or l'adaptateur
> d'agrégats **n'a pas de source**. En l'état, la couche anticorruption n'a **aucun adaptateur
> fonctionnel** — `NullEcclesialContext` est la seule réalité. Cohérent et sans danger, mais à savoir.

> **La formulation que la porte 9 a produite**, et qui vaut d'être gravée telle quelle :
> > **Le signal informe l'homme. L'homme commande la machine. Jamais le signal ne commande la machine.**
>
> Le mur ne rend pas l'information inutile — il rend le pasteur **responsable de ce qu'il en fait**.

Dernier essai — **`Rom 8:1` + sa citation** (entrée **hybride**), sur le verset le plus piégeux du NT :

| # | Constat | Statut |
| :-- | :-- | :-- |
| **S16** | **L'entrée hybride (référence + citation) n'est pas modélisée** — l'étage 0 route vers trois portes **exclusives**. Or deux sources qui se corroborent sont un **cadeau**, pas un conflit | ⏳ **Règle à ajouter** : résoudre sur la **référence**, **vérifier** par la citation, n'interrompre **que si elles divergent** (« vous citez Rm 8:1 mais votre texte est Rm 8:34 » — erreur de mémoire fréquente que seule la double entrée attrape) |
| **S17** | **Aucune table pour les variantes textuelles.** `doctrinal_caveat` ne convient ni par son `kind` (une variante n'est ni exégétique ni confessionnelle : c'est ce que le texte **est**) ni par sa clé (un verset ≠ péricope + axe) | ✅ **Corrigé** : table `urim_corpus.textual_variant` ajoutée (`Structure §3.1`), migration **003**. `doctrinal_weight IN ('nul','notable','majeur')` fait le tri de l'affichage |

> **Pourquoi Rm 8:1 est le cas d'école.** Le Texte Reçu ajoute « qui ne marchent point selon la chair,
> mais selon l'esprit » (assimilé depuis 8:4) ; les textes critiques l'omettent — LSG 1910 et Darby
> aussi, Ostervald non.
> **Sans la clause : « aucune condamnation » est inconditionnel. Avec : c'est une condition morale.**
> Deux sermons opposés sur la même référence. La version détectée n'est donc **pas** une information
> cosmétique — et c'est précisément pourquoi la spec dit « identifier le passage, **pas** la version ».

Dernier essai (pasteur Venance) — **« 1 Cor 5:17 ou 2 Cor 5:17, mais je veux pas d'une créature
en Christ »** : deux références dont **une n'existe pas**, plus une contrainte **négative**.

| # | Constat | Statut |
| :-- | :-- | :-- |
| **S18** | **Une conviction NÉGATIVE rétrécit le bornage — elle ne refuse pas le texte.** D-E et S8 ne connaissaient que des contraintes *positives*. Ici le seul verset valide (`2 Cor 5:17`) porte **exactement** l'axe refusé. Refuser serait décider à la place du pasteur ; ignorer lui donnerait le sermon qu'il ne veut pas. La bonne issue : **borner ailleurs dans la même péricope** — `2 Cor 5:18-21` (réconciliation, ambassade, substitution) satisfait son refus **sans quitter son texte** | ⏳ **Règle à écrire** + ⚠️ **dépendance à contre-courant** (ci-dessous) |
| **S19** | **Une référence hors bornes est une information, pas un arbitrage.** `1 Corinthiens 5` compte 13 versets : `1 Cor 5:17` n'existe pas. Le moteur l'apprend du corpus (table des versets), écarte le candidat **avec son motif**, et **continue sans interrompre** — il n'y a rien à trancher. Cohérent avec D-E : on n'interrompt que devant un vrai choix | ✅ **Tranché 2026-08-04** : règle complète écrite au § bornage (étage 1) |

> ✅ **Tranché le 2026-08-04 : l'étage 2 lit les axes** (`deps.doctrine`).
>
> **Et ce n'est pas une entorse à l'ordre du pipeline** — la nuance vaut d'être écrite, sinon
> quelqu'un « corrigera » cela dans six mois : `deps.doctrine` est un **port de lecture** sur le
> corpus curé, **pas la sortie de l'étage 5**. L'étage 2 ne consomme donc aucun étage postérieur ;
> il lit la même donnée immuable. **L'ordre contraint le flux d'état (`StudyState`), pas l'accès
> aux ports.** L'étage 5 reste seul à *interpréter* ces axes et à porter les mises en garde.
>
> Deux conséquences à tenir :
> - **Dégradation silencieuse** : hors des péricopes curées (40 semées), il n'y a aucun signal pour
>   ordonner. Le bornage rend alors ses options **sans ordre** — jamais une erreur.
> - **Le refus doit voyager dans l'état** → champ `StudyState.refused_axes` (ajouté au socle).
>   ⚠️ Mais traduire « je ne veux pas d'une créature en Christ » en **code d'axe** est le même
>   problème que **S12** (texte libre → axes) : si c'est une étape modèle, elle est `metered` et
>   se désactive au plafond. **Même repli : le pasteur désigne l'axe refusé dans la liste curée.**

### S14 — la lecture non nominative de la veille (LIVRÉ 2026-08-04)

**Le principe : rendre la fuite structurellement impossible, pas seulement interdite.**

| Pièce | Rôle |
| :-- | :-- |
| `watch/application/aggregates.py` | `TopicCount(topic, headcount, window_days)` — **aucun champ d'identité** — + port `AggregateReader` |
| `watch/infrastructure/persistence/aggregate_reader.py` | `SELECT origin, count(*) … GROUP BY origin HAVING count(*) >= 5` |
| `urim/calendar/adapters/watch_aggregate_adapter.py` | traduit en `AggregateSignal`, libellés en français |

**Trois gardes indépendantes**, plutôt qu'une convention :
1. **Le type n'a nulle part où mettre un nom.** Une implémentation pressée *ne peut pas* fuiter.
2. **Le seuil est dans le `HAVING`** : un groupe sous cinq ne quitte pas la base — il n'est pas
   filtré après coup, il n'est **jamais lu**.
3. **`AggregateSignal.__post_init__`** refuse à son tour tout compte sous le seuil, côté Urim.

**Et deux tests qui tiennent la propriété** (dans l'esprit du test bytecode) : le type de sortie
**n'a aucun champ UUID** (introspection), et le **SQL compilé** ne mentionne ni `subject_id` ni
`owner_account_id`. Plus un test de cohérence : le seuil vaut cinq **des deux côtés** de la
frontière (les contextes ne partageant rien, la constante est écrite deux fois).

> **Premier franchissement réel de la frontière.** L'adaptateur est le premier fichier d'Urim à
> importer hors d'Urim — depuis `calendar/adapters/`, la **seule** zone exemptée. Le test de
> frontière l'accepte : la règle d'architecture est désormais éprouvée sur un cas réel, plus
> seulement sur un témoin.
>
> **Correction de C5 par la même occasion** : l'adaptateur **d'événements** reste inutile (le
> calendrier vit dans `attendance`/`events`, hors `watch`) — `events_between` rend `()`.

### S2 — « aucun candidat » : `REFUSE` motivé (tranché 2026-08-04)

**Pourquoi pas `DEGRADE`.** `DEGRADE` veut dire « repli, **la préparation continue** » — et il ne le
dit que parce qu'un **substitut** existe (LSG 1910 à la place de la Segond 21). Ici il n'y a pas de
substitut : sans texte, il n'y a pas de pipeline. Rendre `DEGRADE` ferait **mentir la promesse** que
`DEGRADE` porte. `REFUSE` est honnête : le moteur dit qu'il ne peut pas aider **avec cette entrée**.

**Le motif fait tout le travail** — un refus qui n'oriente pas est une porte fermée :
- citation → *« Aucun texte du corpus ne porte cette formulation. Vérifiez la citation, ou entrez une référence. »*
- conviction → *« Aucune péricope curée ne porte cet axe »* — dit franchement (c'est la réponse à **S3**).

> ⚠️ **La frontière à ne pas rater : `REFUSE` seulement si l'ensemble des candidats est VIDE.**
> Un candidat **faible reste un candidat**. La « conflation de mémoire » — deux versets fusionnés,
> score médiocre **partout** — produit justement des candidats faibles : c'est un `AWAIT` avec le
> diagnostic, **jamais** un refus. Confondre les deux ferait perdre le plus beau mécanisme du moteur.

### D-B — « Urim prépare, `sermon` publie » (tranché 2026-08-04)

Les deux **coexistent** : ce ne sont pas deux archives, ce sont deux **objets différents**, et ils
n'appartiennent pas à la même personne.

| | `urim.preached` | contexte `sermon` |
| :-- | :-- | :-- |
| Quoi | ce que **j'ai prêché** — passage, axe, date | ce que **l'église reçoit** — texte, capsules, compagnon |
| À qui | l'**auteur** (`author_id`) | l'**église** (`tenant_id`) |
| Sert | couverture du canon · distribution doctrinale | fil d'actualité · résonance · présence déclarée |
| Survit | **oui** — `exportable_until NULL`, résilie ou pas | à la vie de l'église |

**Le sens du flux : `urim` → `sermon`, jamais l'inverse.** Un port de publication ; aucune FK (§3.9) ;
`sermon` n'a **rien** à connaître d'Urim.

**Publier est facultatif.** Une préparation peut être prêchée sans jamais être publiée à l'église —
l'archive de l'auteur se remplit quand même. Réciproquement, `preached.preparation_id` est nullable :
on peut **importer** un sermon d'avant Dorea. **L'archive ne dépend donc pas du moteur.**

> **La conséquence la plus juste** : le jour où un pasteur **change d'église**, son archive le suit
> (elle est clée sur `author_id`) et les sermons publiés restent à l'église (clés sur `tenant_id`).
> Son travail lui appartient ; ce qu'il a donné à l'assemblée lui reste. **La frontière était déjà
> écrite dans les clés** — il fallait seulement ne pas fusionner les deux tables.

### Règle complète du bornage (étage 2) — consolidée le 2026-08-04

D-E, S8, S18 et S19 se répondent ; les voici en un seul endroit, pour le chantier 4.

**Trois relations entre ce qui est demandé et l'unité curée — et une seule question à chaque fois :
« y a-t-il quelque chose à arbitrer ? »**

| Relation | Exemple | Issue |
| :-- | :-- | :-- |
| **coïncide** | `Rom 1:16-17` | `CONTINUE` — rien à trancher (motif tracé quand même) |
| **coupe** (⊂) | `Rom 1:16` dans `1.16-17` | `AWAIT` à **2 options** : la péricope · la demande telle quelle (`bounds_overridden`) |
| **englobe** (⊃) | `Galates 5` = 3 unités | `AWAIT` à **N+1 options** : chaque unité avec son motif · le tout en **un seul sermon expositif** |

**Ordre des options** — si `refused_axes` n'est pas vide (S18), on présente **en tête** les bornes
dont l'axe dominant n'est pas refusé. Hors péricopes curées : aucun ordre, jamais d'erreur.

**Hors bornes** (S19, tranché 2026-08-04) — règle de l'**étage 1** :

```
pour chaque référence saisie :
    livre inconnu            → candidat écarté, motif « livre non reconnu »
    chapitre hors du livre   → candidat écarté, motif « ce livre compte N chapitres »
    verset hors du chapitre  → candidat écarté, motif « ce chapitre compte N versets »
                                 (1 Cor 5:17 → « 1 Corinthiens 5 compte 13 versets »)
puis :
    ≥ 1 candidat valide  → CONTINUE, le motif dit ce qui a été écarté et pourquoi
    0 candidat valide    → REFUSE motivé (S2)
```

**Le moteur n'interrompt jamais pour un fait.** Une référence qui n'existe pas n'est pas une
ambiguïté à arbitrer : c'est une information à donner. On la donne, et on continue — sinon on
fatigue le pasteur avec des questions dont la réponse ne dépend pas de lui.

⚠️ **Le motif n'est pas facultatif ici non plus.** Écarter en silence, c'est laisser un homme se
demander pendant vingt minutes pourquoi « son » verset a disparu.

**La série n'est pas modélisée** — et c'est assumé : `1 preparation = 1 sermon`. Prêcher Galates 5
en trois dimanches, ce sont **trois préparations**, donc trois unités facturées — ce qui est juste,
puisque ce sont trois sermons.

> **Et cela marche déjà sous S9.** Ouvrir « Gal 5 », retenir `5:16-26` → la réservation se **re-clé**
> sur cette péricope. Rouvrir « Gal 5 » la semaine suivante pour `5:1-12` crée une **nouvelle**
> réservation provisoire, qui se re-clé à son tour : pas de collision, pas de double comptage sur la
> même unité. Le re-clage de S9 sert la série sans qu'on ait rien à ajouter.

### S26 · S27 — le temple, les cotisations, la motivation (2026-08-05, porte 15)

**Entrée** (pasteur Cédric) : *« s'inspire de la veille, construction du temple, les cotisations et
la motivation »*. Elle enchaîne **trois choses que Dorea sépare volontairement** : la veille, la
chaire, l'argent.

**Ce que le moteur fait** : « s'inspire de la veille » est **légitime** — E1 le confirme, le pasteur
porte lui-meme ce qu'il a vu, le moteur **ne verifie pas** dans les agregats. Les axes montrent que
le motif « temple » est **transversal** : ecclesiologie dominante, theologie propre et anthropologie
portees — et **christologie/pneumatologie** portees *si* l'on va vers Jn 2:19 ou 1 Co 6:19 (*le vrai
temple*). Le bornage decide donc de la doctrine, encore une fois (S18).

**Les resistants, ici, protegent l'assemblee de la collecte** : Ex 36:5-7 (le peuple donne **tant**
que Moise doit **le faire cesser**) · 2 Co 9:7 (« ni avec tristesse, ni par contrainte ») ·
Mc 12:41-44 (la veuve et ses deux pites) · Ac 5:1-11 (Ananias : donner sous le regard) · Mt 23:23 ·
Jn 2:13-16. **Ex 36:5-7 est le texte que ce pasteur doit voir** : un sermon de collecte y trouve son
contraire exact — la generosite libre deborde au point qu'il faut l'arreter, aucune motivation n'y
est necessaire.

| # | Constat | Statut |
| :-- | :-- | :-- |
| **S26** | **« Motivation » n'est pas un axe, c'est une INTENTION.** L'entree mele un motif biblique (le temple), une pratique (les cotisations) et un **but** (motiver). S10 et S20 distinguaient *sujet apparent / posture reelle* ; ici c'est **sujet ↔ intention**. Declarer « je veux motiver » n'ajoute **aucun axe** — cela **change le risque** : c'est annoncer un sermon persuasif sur l'argent | ⏳ Doit **relever `proof_text_risk`** et **appeler les resistants sur la contrainte**. Ne jamais refuser : motiver n'est pas une faute, c'est une intention qui demande des garde-fous |
| **S27** | 🔴 **Le mur `finance → urim` n'est ecrit nulle part.** Finance §2.1 interdit `finance → watch`. Urim §4.3 interdit `watch → moteur`. **Personne n'a ecrit `finance → urim`** — et la tentation y est identique : *« le projet toiture est a 40 %, proposons un sermon sur la generosite »* | ⏳ **Frontiere a ecrire.** Regle proposee, **plus stricte que pour la veille** : la veille peut au moins **s'afficher** a cote du texte ; l'etat financier ne doit **meme pas s'afficher** dans l'atelier de preparation |

> **S27 est la trouvaille de cette porte.** Deux murs etaient batis sur **trois** cotes. Le troisieme
> est le plus dangereux, parce que le lien y parait le plus innocent — et parce que l'argent est le
> seul domaine ou le benefice de la transgression est **immediatement mesurable**.
>
> **Un pasteur qui prepare son sermon n'a pas a voir le solde du fonds.**

### S29 · S30 · S31 — la capture, le retour, et le quatrieme mur (2026-08-05)

`Dorea_Urim_Architecture_Transcription.md` (module `urim/capture/`) **ferme la boucle** :
preparer *(le moteur)* -> precher *(la capture)* -> revoir *(le retour)*. Copie dans `docs/`.

**Il confirme trois patrons deja eprouves ailleurs** — et la spec en nomme un elle-meme :

| Patron | Instances |
| :-- | :-- |
| **Provenance obligatoire** | `rationale` (StageResult) · `reviewed_by NOT NULL` (corpus) · **`segment_refs` non vide** (synthese) |
| **Filtrer avant d'ecrire** | `HAVING >= 5` (S14) · **voix ecartees avant ecriture**, « jamais stockees puis filtrees » (§7) |
| **Rien plutot qu'une vraisemblance** | texte non cure -> rien · **couverture < seuil => aucune synthese**, le transcript brut reste (§10.5) |

| # | Constat | Statut |
| :-- | :-- | :-- |
| **S29** | 🔴 **Un QUATRIEME mur, interne a Urim** : §10.1 — « **le modele ne voit jamais la preparation** ». S'il recoit le plan, il **fabrique la conformite** et detruit ce que le Retour existe pour montrer. La comparaison prepare/preche est **deterministe**, calculee par difference sur des faits (versets cites, horodatages, ancres) | ⏳ **A rendre executable**, comme `deps.context`. ⚠️ **Distinguer deux choses qu'on confondra** : le **module** lit la preparation (§6, alignement deterministe sur les versets d'ancrage — **legitime**) ; seul le **modele** ne doit pas la voir. **Parallele exact de S11** : le mur porte sur *l'entree du modele*, pas sur *l'acces du module* |
| **S30** | **Le resolveur de l'etage 1 sert un TROISIEME flux** (ecrit -> personnage S24 -> **audio**, §5.2 : « le moteur de resolution de l'etage 1, applique a un autre flux d'entree »). Mais §5.1 demande une **machinerie neuve** : **analyseur de nombres en toutes lettres** (« Romains chapitre huit, verset quinze » — `book_name.abbreviations` n'y sert a rien) + **references relatives** (« au verset dix-sept ») heritant du dernier livre/chapitre cite | ⏳ Conception. **Rend S21 critique** : trois entrees dependent du normaliseur partage |
| **S31** | 🔴 **`Dorea_Urim_Capture_et_Retour.md` manquant.** Quatre tables referencees sans etre definies : **`urim.capture`** (FK de `capture_job`), **`transcript_segment`**, **`cited_verse`** (§5.3, §10.4), **`urim.reflection`** (§10.6 l'`ALTER`, personne ne la `CREATE`). Aucune dans `Structure §3` | ⏳ **Bloque `urim/capture/`** — meme situation que le schema corpus au 03/08 |

> **S29 est la plus belle regle du document, et la plus fragile** : elle sera « corrigee » par le
> premier developpeur qui trouvera utile de donner le plan au modele « pour qu'il comprenne mieux ».
> **Elle doit etre un test, pas une phrase.**

> ⚠️ **Second verrou de sequencement, interne au module** (§11) : **etape 1 seule** — capture,
> transport, transcript brut **non exploite** — jusqu'a mesure du taux d'erreur dans **trois eglises
> reelles**. La synthese est **quatrieme et derniere**. « Une synthese batie sur une transcription
> non mesuree est une invention presentee comme un souvenir. »

### Les trois murs — matrice complete (2026-08-05, S27 + S28)

`finance`, `watch` et `urim` sont **mutuellement cloisonnes**. Six directions, aucune laissee
au hasard :

| Direction | Regle | Ou elle tient |
| :-- | :-- | :-- |
| `finance -> watch` | ⛔ « aucune donnee financiere n'entre dans le moteur de veille » (Finance §2.1) | Spec Finance §10 — `test_finance_n_emet_aucun_fait_de_veille` *(a ecrire avec le contexte)* |
| `watch -> finance` | ⛔ « un membre qui ne donne plus n'apparait **jamais** dans La Veille » | Spec Finance §10 — `INTERDIT_DANS_WATCH` *(a ecrire avec le contexte)* |
| `watch -> urim` | ⛔ **AFFICHAGE SEUL** — agregats non nominatifs ≥ 5, via l'ACL, jamais dans un etage | ✅ **teste** — test bytecode + test d'imports |
| `urim -> watch` | ⛔ « aucun retour : une preparation ne cree ni fait, ni cas, ni signal » (Structure §2) | ✅ **teste (S28)** — liste blanche : seuls les **agregats** sont importables |
| `finance -> urim` | ⛔ l'etat financier n'entre **meme pas** dans l'atelier | ✅ **teste (S27)** — scanne tout Urim, exemption comprise |
| `urim -> finance` | ⛔ idem | ✅ **teste (S27)** — meme test |

**S28 — le trou que S27 a fait apparaitre.** L'exemption de `calendar/adapters/` ouvrait **tout**
`watch` : `SignalStore`, `Intake`, les stores de contact. Lire les agregats est permis ; **ecrire**
ne l'est pas, et ce n'etait garanti que par la bonne volonte. Ferme par une **liste blanche** —
`app.contexts.watch.application.aggregates` et rien d'autre. *Une liste blanche tient mieux qu'une
liste noire : ce qui n'est pas nomme est refuse par defaut.*

> **Ce que la matrice rend visible** : les deux murs deja ecrits protegeaient chacun **un** couple.
> Les regarder tous les six d'un coup a fait apparaitre **deux directions non gardees** — et c'est
> exactement pour cela qu'un tableau vaut mieux qu'une regle enoncee au fil de l'eau.
>
> ⚠️ Les deux premieres lignes sont **specifiees mais pas encore executables** : le contexte
> `finance` n'existe pas. **A ecrire en F0**, rouges d'abord.

### S32 — `sermon` ↔ `urim` : **pas un mur, un pont** (tranché 2026-08-05)

La matrice des six directions ne concerne que `finance`, `watch` et `urim`. **`sermon` n'y figure
pas, et c'est volontaire : il n'y a aucun mur à bâtir de ce côté.** Le « quatrième mur » évoqué en
S29-S31 est **interne** au module — §10.1, *« le modèle ne voit jamais la préparation »* — c'est
`plan ↮ modèle`, pas `sermon ↮ urim`. La confusion valait d'être écrite : elle a failli faire
poser une cloison là où il fallait une porte.

**La règle existait déjà — c'est `D-B`, tranché le 2026-08-04** : *« Urim prépare, `sermon`
publie »*, flux **`urim → sermon` uniquement**, via un **port** de publication, **aucune FK**, et
`sermon` n'a rien à connaître d'Urim. Elle n'a pas bougé. Ce qui suit ne la remplace pas : la
**capture** (spec du 2026-08-05) fait apparaître un **troisième artefact** que D-B ne connaissait
pas, et la question est de savoir si la règle tient encore sur lui.

| # | Constat | Statut |
| :-- | :-- | :-- |
| **S32** | **La capture ajoute un producteur que D-B n'avait pas.** D-B arbitrait entre `urim.preached` (l'**archive** du prédicateur, clée `author_id`) et `sermon` (ce que **l'église reçoit**, clé `tenant_id`). Le transcript est un **troisième** objet : le texte de ce qui a été **réellement dit**. Si rien ne tranche, un membre peut recevoir des capsules issues du plan **déposé** pendant que le Retour montre au pasteur qu'il a prêché autre chose | ✅ **Tranché 2026-08-05 : D-B s'étend au transcript sans changer** |

**La règle, inchangée et étendue :**

> **Urim prépare, prêche et transcrit. `sermon` publie.**
> Ce qui a été réellement prêché **remonte** vers `sermon`, seul propriétaire de l'artefact publié
> et des capsules. **Urim ne publie jamais rien au membre** — ni son plan, ni son transcript.

```
préparer (urim/engine)
    ↓
prêcher → capture (urim/capture)          ← transcript + versets extraits
    ↓
  SERMON  ← propriétaire unique de l'artefact publié
    ↓
capsules → compagnon → membre
```

**Trois raisons, et les deux premières sont déjà écrites dans les specs :**

- la synthèse de capture est *« une proposition, pas un compte rendu »* (§10.6) et **aucun verset
  ne sort du modèle** (§10.4) : ce n'est pas un artefact publiable en l'état. Le publier
  reviendrait à présenter une reconstruction comme une parole ;
- `sermon` porte déjà l'approbation du pasteur — *rien de non approuvé n'atteint le membre*. Un
  second chemin de publication contournerait cette onction, et c'est exactement ce que D-B
  protégeait en refusant une seconde archive ;
- le Retour existe pour montrer au pasteur **l'écart** entre ce qu'il avait préparé et ce qu'il a
  dit. Un écart n'a de sens que si les deux restent distincts : fusionner les artefacts détruirait
  précisément ce que le module existe pour révéler.

**Les trois objets, et à qui ils appartiennent** — c'est la grille de D-B, avec le transcript ajouté :

| Objet | Clé | À qui | Publié au membre |
| :-- | :-- | :-- | :-- |
| `urim.preparation` | `author_id` | le prédicateur | ⛔ jamais |
| `urim.transcript` | `author_id` | le prédicateur | ⛔ jamais |
| `urim.preached` (archive) | `author_id` | le prédicateur — **le suit s'il change d'église** | ⛔ jamais |
| `sermon` | `tenant_id` | l'église — **y reste** | ✅ le seul |

> La conséquence la plus juste de D-B, qui vaut d'être relue ici : **son travail lui appartient, ce
> qu'il a donné à l'assemblée lui reste.**

**Ce que ça n'autorise pas.** Le pont ne rouvre aucune des six directions gardées : une capture ne
crée ni fait, ni cas, ni signal de veille, et `AFFICHAGE SEUL` tient inchangé.

> ⏳ **Rien n'est écrit** : `urim/capture/` est bloqué par S31 (`Dorea_Urim_Capture_et_Retour.md`
> manquant, quatre tables référencées sans être définies), et le verrou de séquencement interne
> impose l'**étape 1 seule** — transcript brut non exploité — jusqu'à mesure du taux d'erreur dans
> trois églises réelles. Le sens du flux est tranché **avant** d'avoir quoi que ce soit à faire
> couler : c'est le bon ordre, et c'est ce qui évite qu'un développeur pressé branche la capture
> sur le compagnon parce que « c'est le plus court ».

### D-A — ✅ **préfixes, pas de schémas Postgres dédiés** (tranché 2026-08-06)

La spec écrit `CREATE SCHEMA urim_corpus;` et `CREATE SCHEMA urim;`. Le dépôt, lui, n'utilise
**aucun** schéma : quatorze contextes vivent dans `public`. La décision est de **suivre le dépôt**.

| | Retenu |
| :-- | :-- |
| Corpus | `urim_corpus_version`, `urim_corpus_verse`, `urim_corpus_pericope`, … |
| Préparation | `urim_preparation`, `urim_preached`, `urim_deliverable`, … |

**L'argument qui tranche n'est pas l'uniformité, c'est la collision.** Les tables du corpus
s'appellent `version`, `language`, `book`, `verse`, `token`, `lemma`, `idf`. Ce sont exactement les
noms qu'un autre contexte réclamera un jour — et dans `public` sans préfixe, c'est un champ de
mines. Le préfixe n'est pas une convention cosmétique ici : **il est ce qui rend ces noms
utilisables**.

**Trois conséquences, et aucune ne dégrade ce qui était acquis :**

1. **La couture tient inchangée.** §3.9 interdit toute FK de `urim` vers `urim_corpus` parce que le
   corpus migrera vers une base de lecture séparée. Ce motif ne dépend pas du schéma Postgres — il
   dépend de la **base**. La règle survit telle quelle : `pericope_id uuid NOT NULL`, jamais
   `REFERENCES`.
2. **Les migrations se simplifient.** Aucun `CREATE SCHEMA`, aucun `search_path` à poser, rien à
   ajouter dans `migrations/env.py`.
3. **Le critère d'extraction ne bouge pas** — « quand les requêtes de résolution dégradent
   mesurablement le transactionnel ». Un préfixe s'extrait aussi bien qu'un schéma.

> ⚠️ **Le DDL de `Dorea_Urim_Structure_et_Schema.md` §3.1 et §3.4 est donc à lire avec deux
> corrections, pas une** : retirer les `CREATE SCHEMA` **et** retirer les `REFERENCES urim_corpus.*`
> (§3.9). Qui copie ce SQL tel quel se trompe deux fois.

**Le chantier 1 est débloqué.**

### S33 — le **détecteur d'entrée** : l'étage 0 ne fait plus confiance à l'onglet (2026-08-06)

L'étage 0 routait vers trois portes **d'après le mode déclaré**. Or les entrées réelles qui traînent
déjà dans ces constats ne respectent aucun onglet :

| Constat | Ce que le pasteur a tapé | Pourquoi le mode déclaré est faux |
| :-- | :-- | :-- |
| S23 | « l'histoire de Jézabel » | saisi en *référence* — aucun parseur n'en tire un livre |
| S24 | « 1 Roi ou 2 Roi, il s'agit de Jézabel la femme du Roi » | une hésitation, pas une référence |
| S21 | « nexiiste », « leglise » | tapé sur une tablette un vendredi soir |
| S16 | `Rom 8:1` **avec** sa citation | deux portes à la fois |

| # | Constat | Statut |
| :-- | :-- | :-- |
| **S33** | **Les trois onglets sont une fiction d'interface.** Une conviction saisie dans le champ *référence* fausse tout le pipeline en aval — et rien ne le rattrape | ✅ **Tranché 2026-08-06 : détecteur déterministe qui propose, jamais qui reclasse** |

**La règle**, et c'est celle du dépôt entier — *le calcul propose, la personne dispose* :

> Le détecteur **ne route pas** : il propose une route, et le motif est tracé.
> Reclasser en silence ferait décider la machine à la place du pasteur — ce que S10 interdit.
> Exiger qu'il ait choisi le bon onglet, c'est refuser le terrain.

**Quatre issues, dans le vocabulaire qui existe déjà** (l'étage 0 est un `Stage` comme les autres) :

| Ce que le détecteur voit | Issue | Ce que le pasteur lit |
| :-- | :-- | :-- |
| signal **univoque**, conforme au mode saisi | `CONTINUE` | rien — *on ne fatigue pas quelqu'un qui a visé juste* (règle de D-E, appliquée en amont) |
| signal qui **contredit** le mode saisi | `AWAIT` à 2 options | « je peux lire ceci comme une référence, ou comme une intention. Laquelle ? » |
| **deux signaux qui se corroborent** | `CONTINUE` en `reference` | **c'est ici que S16 se résout** — résoudre sur la référence, vérifier par la citation |
| **rien de lisible** | `REFUSE` motivé | voir ci-dessous |

**Le détecteur doit être déterministe — et il peut l'être.** S'il était une étape modèle, il serait
`metered` : au plafond, **la porte d'entrée elle-même disparaîtrait**, et « aucun mur » deviendrait
faux au tout premier étage — pire que le problème que S12 a résolu. Or les trois modes ont des
signatures de surface lisibles dans le corpus, sans aucun modèle :

| Signal | Lu où |
| :-- | :-- |
| un nom ou une abréviation de livre | `book_name.abbreviations` — la table, jamais une regex |
| un recouvrement fort avec le texte biblique | `verse.body_norm`, trigrammes + ancres `idf` |
| du français lisible, sans les deux précédents | `idf` sert de **lexique** — c'est une table `(langue, token, idf)` |

> **Un nom de livre reconnu suffit à faire une référence** — sans exiger de chiffres. C'est S23 :
> « 1 Rois » seul est une entrée réelle, pas une saisie incomplète.

**Le charabia, et l'asymétrie qui compte.**

> **En cas de doute, on route vers `conviction` — jamais vers charabia.**

Dire à un pasteur que sa phrase est incompréhensible alors qu'elle ne l'est pas est la pire erreur
possible à la porte d'entrée. Mieux vaut accepter une conviction faible : le plafond du corpus curé
produira plus loin un `REFUSE` franc (S3). Même asymétrie que S2 — *un candidat faible reste un
candidat*.

Et le motif ne renvoie **jamais** le verdict du corpus : un clavier malheureux n'est pas
« aucune péricope ne porte cet axe ». Il attire à la correction :

> *« Je n'arrive pas à lire ceci — ni une référence, ni une phrase des Écritures, ni une
> intention. Vous vouliez peut-être dire… ? »*

La saisie est **conservée** (`resolution_attempt.candidates`) : jamais de champ vidé.

**Trois conséquences de mise en œuvre :**

1. **Aucune migration.** `preparation.entry_mode` stocke désormais le mode **retenu** ; la `trace`
   porte la divergence — elle est faite pour ça. Le mode saisi devient un **indice**, pas un ordre.
2. **L'étage 0 dépend du chantier 1.** Il lit `book_name`, `verse.body_norm` et `idf` : le routage
   n'est plus gratuit, on ne peut pas le construire en premier contre une chaîne nue.
3. **Le normaliseur partagé (S21) passe de « à extraire » à prérequis.** Le détecteur en a besoin
   *avant* de router quoi que ce soit.

### Porte 16 — le micro resté ouvert : S34 · S35 · S36 · S37 (2026-08-06)

Simulation à blanc sur le détecteur à peine écrit. Pasteur Cédric, saisie brute :

> « Ma voiture 406, a besoin de reparation , jefgf Paradis »

L'hypothèse qui explique tout : **`jefgf` n'est pas une faute de frappe** — aucun doigt ne produit
ça. C'est une mauvaise transcription. Le sujet décousu, le mélange voiture / réparation / Paradis,
l'absence de structure : un **micro ouvert** a ramassé ce qui passait.

Trois hypothèses du détecteur sont tombées, et une quatrième décision est née de la discussion.

| # | Constat | Statut |
| :-- | :-- | :-- |
| **S34** | **`idf` n'est pas un lexique du français, c'est celui du corpus biblique.** Deux mots retirés suffisaient à faire déclarer illisible une phrase parfaitement française — et le vocabulaire qui souffre est exactement celui d'une conviction sur l'église d'aujourd'hui : *voiture*, *réseaux*, *chômage*, *quartier* | ✅ **Tranché — lexique de la LANGUE, et un décompte** |
| **S35** | **Un nom de livre reconnu ne suffit pas.** `Job`, `Juges`, `Nombres`, `Actes`, `Rois` sont des mots français courants — « il y a trop de **juges** dans cette assemblée » est même l'accusation de S20. Et **exiger un chiffre ne sauve rien** : « Ma voiture **406** » en contient un | ✅ **Tranché — l'empan contigu** |
| **S36** | **Le vrai défaut n'était pas la détection.** Rien ne disait au moteur d'où venait le texte, alors que le système le sait : le module de capture stocke déjà son `provider` | ✅ **Tranché — la provenance, puis la confirmation** |
| **S37** | La charge émotionnelle d'une conviction : peut-on la lire sans franchir l'interdit ? | ✅ **Tranché — elle relève le RISQUE, elle ne choisit jamais le TEXTE** |

**S34 — un décompte, pas une proportion.** La question n'est pas *« quelle proportion de ces mots
est du français ? »* mais **« y a-t-il quelque chose de reconnaissable là-dedans ? »**. Un seul mot
reconnu ouvre la conviction ; on ne refuse que ce qui n'a *rien*. Un token pourri sur neuf cesse de
peser. ⚠️ **Conséquence chantier 1** : il faut un lexique de la langue — `idf`, bâti sur l'Écriture,
ne convient pas.

**S35 — la contiguïté est le seul juge.** Deux formes acceptées : le nom **suivi de chiffres
contigus** (`Romains 8:10`, `Job 38`), ou le nom qui **couvre toute la saisie** (`1 Rois`, le livre
entier de S23). Tout le reste est un mot français qui se trouve être un nom de livre. Le port cesse
de rendre un code et rend un **empan** — c'est l'étage qui tranche.

**S36 — la provenance plutôt que la divination.** Une dictée qui ne produit pas un signal univoque
**se fait confirmer**, avec ce qui a été entendu rendu tel quel :

> *« J'ai entendu : "Ma voiture 406, a besoin de reparation , jefgf Paradis". C'est bien ce que
> vous vouliez ? »* — Ce n'est pas ça · Une intention

Le micro ouvert se referme en un tap, **et aucune analyse n'a eu lieu**. Une saisie tapée, elle, ne
demande rien : quelqu'un qui tape ces mots les a voulus.

**S37 — la charge émotionnelle relève le risque, elle ne choisit jamais le texte.**
La demande initiale était de détecter le sentiment pour router. Refusée : S10 démontre qu'une
lecture émotionnelle **juste** (« détresse → réconfort → guérison ») produit un sermon qui blesse
des malades. Ce qui protège n'est pas la justesse du sentiment, ce sont les **textes résistants**.

Mais la distinction posée par l'auteur — *l'émotion a sa place dans la conviction, jamais dans le
texte biblique* — rouvre une voie, et c'est **exactement le patron de S26** (« motiver » n'est pas
un axe, c'est une intention : ça ne change pas l'axe, ça change le **risque**). D'où la règle :

| Le détecteur se trompe | Conséquence |
| :-- | :-- |
| faux positif | des textes résistants **en plus** — inoffensif |
| faux négatif | le comportement d'aujourd'hui |
| modèle absent / plafond | idem — rien ne casse |

> **Un signal qui ne peut qu'ajouter de la protection ne peut pas nuire en se trompant.**

Modèle **optionnel** (S12), et une règle de formulation non négociable : *le motif nomme l'effet,
jamais l'état de celui qui écrit*. « Formulation à forte charge — davantage de textes qui résistent
sont affichés » se vérifie et se conteste ; « vous êtes dans la plainte » est un diagnostic.

⚠️ **Et la ligne qui n'a pas bougé** : sur un **produit de la veille**, on agrège ce qui a été
**déclaré** (des actes comptés, non nominatifs, ≥ 5) — on n'infère jamais un état par personne pour
l'agréger ensuite. *On compte ce qui a été dit, on ne devine pas ce qui a été tu.*

### S38 · S39 · S40 — les ajustements du pipeline complet (2026-08-06)

Trois constats apparus en écrivant les huit étages, puis en décrivant ce que « curer » veut dire.

| # | Constat | Statut |
| :-- | :-- | :-- |
| **S38** | **Une ligne de pesée absente et une pesée `absent` sont des choses opposées** — « personne n'a regardé » contre « quelqu'un a regardé, et le texte n'en dit rien ». L'étage 5 les confondait : il affirmait qu'une unité *« a été relue et ne porte aucun des dix axes »* alors que rien n'avait été relu | ✅ **Corrigé dans le code + `absent` doit être SAISI** |
| **S39** | **`homiletic_feasibility` n'a pas de `reviewed_by`**, contrairement aux quatre autres tables curées. Or `refusal_reason` s'affiche au pasteur : un refus lui est opposé sans que personne n'en réponde | ✅ **Corrigé 2026-08-06** — `reviewed_by` + `reviewed_at` ajoutés (§3.3) |
| **S40** | **`ContextNote` n'a aucune table.** L'étage 4 travaille contre un port dont rien ne définit la forme — même situation que les quatre tables de la capture (S31) | ✅ **Corrigé 2026-08-06** — `urim_corpus_context_note` définie (§3.2bis) |

**S39 — pourquoi c'était le pire endroit où une signature pouvait manquer.** Les quatre autres
tables curées portent une **information** : ce que le texte dit, ce qu'il ne dit pas, où l'unité
commence. Celle-ci porte un **refus** — et un refus est précisément ce qu'il faut pouvoir
contester. « Ce passage ne porte aucun personnage » opposé à un pasteur sans que personne n'en
réponde est une décision anonyme prise contre quelqu'un. `proof_text_risk` relève du même
raisonnement : c'est un jugement porté sur le risque du travail de quelqu'un.

**S40 — la table suit le patron, avec deux choix explicites.** `context_kind` sépare
l'**historique** (qui situe) du **littéraire** (qui explique la construction), parce qu'ils ne se
lisent pas au même moment ; et `ordinal` donne l'ordre de lecture au curateur plutôt qu'à un tri
par identifiant — même raison que `doctrinal_axis.ordinal`.

> **Au passage, une phrase du schéma qui mentait.** §3.2 affirmait que `reviewed_by` était
> `NOT NULL` « sur les **trois** tables ». Elles étaient déjà quatre depuis `textual_variant`, et
> six désormais. Le compte a été retiré : la règle porte sur une **propriété** — *ce contenu
> atteint-il le pasteur ?* — pas sur une liste qu'il faut penser à tenir à jour.

**S38 mérite d'être développé, parce qu'il inverse une règle du produit.**

Partout ailleurs dans Dorea, **le silence n'est rien** — c'est l'asymétrie fondatrice de la veille,
et aucun type de fait ne décrit une omission. Ici, c'est l'inverse : le silence d'une pesée doit
porter une information, sinon une curation à moitié faite **ressemble à une curation finie**.

> Une ligne absente ne dit pas « ce texte ne parle pas d'angélologie ».
> Elle dit « personne n'a encore regardé ».

Avec `reviewed_by NOT NULL` sur la ligne, un `absent` **saisi** prouve que quelqu'un a examiné.
Une ligne manquante ne prouve rien. D'où la règle de curation : **les dix loci sont saisis pour
chaque péricope, absents compris** — cent lignes pour dix péricopes, et c'est le prix de la
distinction.

Le code porte désormais les deux cas séparément : aucune pesée → *« aucune pesée doctrinale n'a
encore été relue »* ; des pesées toutes `absent` → *« relue, ne porte aucun des dix axes »*.

### Le quatrième mur rendu exécutable (S29 — 2026-08-06)

S29 disait : *« elle doit être un test, pas une phrase »*. C'est fait, **avant** le module qu'elle
garde — `app/contexts/urim/capture/__init__.py` ne contient rien d'autre que
`FORBIDDEN_IN_MODEL_PROMPT`, le pendant exact de `EngineDeps.FORBIDDEN_FOR_STAGES`.

Le test balaiera `urim/capture/` dès qu'il existera. En attendant il serait **vrai par vacuité** —
et on connaît maintenant le prix de cette vacuité, puisque le premier étage réel a exposé un bug
dormant dans le test le plus important du dépôt. D'où la parade du socle, reprise telle quelle :
un **témoin volontairement fautif** qui prouve que la sonde fonctionne.

Le témoin n'est pas caricatural, et c'est le point : il fait exactement ce qui *paraît utile*.
C'est pour ça qu'une phrase dans une spec n'aurait pas suffi.

### Les dix axes doctrinaux — ce sont les **loci de la théologie systématique** (2026-08-05)

Le schéma dit « 10 catégories, données et non enum de code » sans les nommer. **Ce sont les dix
loci classiques** — le nombre fixe aurait dû le faire deviner. Donnée de départ du **chantier 5**,
à semer dans `urim_corpus.doctrinal_axis` :

| Code | Locus |
| :-- | :-- |
| `theologie_propre` | Dieu |
| `christologie` | Jésus-Christ |
| `pneumatologie` | le Saint-Esprit |
| `anthropologie` | l'homme |
| `hamartiologie` | le péché |
| `soteriologie` | le salut |
| `ecclesiologie` | l'Église |
| `angelologie` | les anges |
| `demonologie` | Satan et les démons |
| `eschatologie` | les derniers temps |

**Ce que ça change concrètement** : le thème (étage 7) se dérive du locus **`dominant`**, soutenu
par les `porte`, en évitant ce qui `resiste` ; un locus `absent` n'affiche **rien** — et **aucun plan
ne se construit sur un locus absent**.

> **Démonstration de S18 par l'exemple.** Sur `Jn 3:16-21` : sotériologie **dominante** ; théologie
> propre, christologie, hamartiologie, eschatologie **portées** ; **pneumatologie absente**. Mais
> borner `Jn 3:1-21` la rend **portée** (« naître d'eau et d'Esprit », v. 5-8). **Deux bornages
> voisins ne portent pas la même doctrine** — c'est précisément pourquoi l'étage 2 doit lire
> `deps.doctrine`.

⚠️ Rappel qui vaut pour toute pesée : ces forces viennent de `doctrinal_bearing`, **curées et
relues** (`reviewed_by NOT NULL`). Une pesée improvisée — fût-elle plausible — est exactement ce que
la contrainte interdit.

### S22 · S23 · S24 — le nominal, et la recherche par personnage (2026-08-04, portes 13-14)

**Porte 13 — `Jean 3:16`**, le cas le plus nominal qui soit. Il **passe sans accroc**, et c'est
la bonne nouvelle : après douze portes d'exceptions, le chemin simple reste fluide. Deux
confirmations au passage — `textual_variant` **reste silencieuse** (ce verset n'en porte pas de
notable : rien à montrer, rien de montré) et **D-F joue pour de vrai** sur « le monde » (κόσμος),
formulé en **divergence nommée**. Et une élégance : le **bornage choisi change les couples
faisables** — `3:1-21` ouvre le plan `biographique` (Nicodème est un personnage), `3:16-21` le
refuse (c'est une proposition, pas un récit). Le schéma le porte déjà, `homiletic_feasibility`
étant clée sur `pericope_id`.

**Porte 14 — « 1 Roi ou 2 Roi, il s'agit de Jézabel la femme du Roi »**. Le pasteur hésite, et il
a **raison deux fois** : Jézabel traverse les deux livres (1 R 16:31 le mariage · 1 R 18-19 les
prophètes de Baal · 1 R 21 la vigne de Naboth · 2 R 9:30-37 sa mort). Sa question est mal posée,
pas fausse — le moteur ne répond pas « c'est 1 Rois », il répond **« lequel de ces quatre
moments ? »**. Son indice « la femme du Roi » travaille : il existe **une autre Jézabel** (Ap 2:20,
la prophétesse de Thyatire), et les livres nommés servent de **filtre** — la règle hybride S16
généralisée : *ce qui est nommé contraint, le reste vérifie.*

| # | Constat | Statut |
| :-- | :-- | :-- |
| **S22** | **`bounds_overridden` laisse l'étage 6 sans données.** D-E autorise le pasteur à **forcer ses bornes** ; or `homiletic_feasibility` est clée sur `pericope_id` : des bornes libres n'ont **aucune ligne**. Ni faisabilité, ni refus motivé, ni `proof_text_risk` | ⏳ **Issue : `DEGRADE`, jamais `REFUSE`** — il a fait un choix légitime, on ne le punit pas ; et on ne **devine** pas une faisabilité qui n'a pas été relue : *« vous avez retenu vos propres bornes ; la faisabilité est établie sur les unités curées, je ne peux pas vous avertir ici »*. Accorder une liberté crée toujours une zone hors garde-fous — il faut le dire à celui qui l'exerce |
| **S23** | **`Reference.chapter` doit aussi être optionnel.** S7 avait libéré `verse_start` pour « Galates 5 » ; ici même le **chapitre** est inconnu — « 1 Rois », « l'histoire de Jézabel ». Une référence **au livre seul** est une entrée réelle | ⏳ Défaut du socle (second du même ordre) |
| **S24** | **Les candidats d'une recherche par personnage ne sont pas des versets, ce sont des SCÈNES.** Pour une citation : *quel verset vouliez-vous*. Pour un personnage : *quel épisode* → candidats **groupés par péricope**, pas listés par verset. Trente versets contenant « Jézabel », c'est une **concordance** ; quatre scènes, c'est une **aide à la prédication** | ⏳ Conception (étage 1 → présentation) |

> **Ce que la porte 14 confirme du design** : « Jézabel » est un **nom propre**, donc l'ancre IDF
> idéale. Le résolveur de citation (trigramme + plein texte + ancres rares) sert la recherche par
> personnage **sans machinerie nouvelle**. Le mécanisme est le bon ; c'est la **forme du résultat**
> qui doit changer selon ce qu'on cherchait.

### S20 — la conviction qui ACCUSE (2026-08-04, porte 12)

**Entrée** (pasteur Cédric) : *« l'amour fraternel nexiiste plus dans leglise »*.

**S10 traitait la plainte** — « malgré les prières rien ne va » : le pasteur **souffre**, et le
danger était de blesser des malades en leur prêchant plus de foi. **Ici il juge son assemblée.**
Le danger est inverse et au moins aussi grave : le sermon devient un **règlement de comptes depuis
la chaire**, et **ceux qui aiment encore le prennent aussi**.

**La règle** : quand la conviction est une **accusation portée sur l'assemblée**, les textes
résistants doivent inclure ceux qui **se retournent vers le prédicateur** —

| Portants | Résistants ⚠️ *même rang* |
| :-- | :-- |
| Jn 13:34-35 · He 13:1 · 1 Jn 4:20 · Rm 12:9-10 | **1 Co 13:1** (« si je n'ai pas l'amour, je suis un airain qui résonne » — le prédicateur est **dans** le texte) · **Mt 7:3-5** (la poutre avant la paille) · **Ga 6:1** (« redressez-le avec douceur, **prenant garde à toi-même** ») · **Ap 2:2-5** |

**Ce n'est pas pour le faire taire.** Un pasteur peut, et doit parfois, reprendre son Église. C'est
pour qu'il le fasse **après s'être vu dans le texte**.

> **Ap 2:2-5 est le cas remarquable** : à la fois le plus **portant** (une Église qui a perdu son
> premier amour — exactement le constat de Cédric) et le plus **résistant**, parce que c'est **le
> Seigneur** qui le dit, et qu'il **loue d'abord** (« je connais tes œuvres, ton travail, ta
> persévérance ») avant de reprendre. Le diagnostic est légitime ; il n'appartient simplement pas au
> prédicateur de le porter sans avoir vu **ce qui tient encore**.

**S20 complète S10, ne le remplace pas.** Deux formes de conviction, deux dangers opposés : la
plainte blesse en culpabilisant les affligés, l'accusation blesse en condamnant l'assemblée. Même
mécanique de protection — les textes résistants — mais **pas les mêmes textes**.

### S21 — le normaliseur doit être partagé (2026-08-04)

« nexiiste », « leglise ». L'étage 1 possède un **normaliseur** (casse, accents, apostrophes
typographiques, ponctuation) — mais la **conviction saute l'étage 1** (§7, chemin inversé). Si le
mapping conviction → axes lit le **texte brut**, « leglise » ne rencontre jamais « église », et une
conviction mal orthographiée ne touche aucun axe.

⇒ Le normaliseur est un **utilitaire de domaine partagé**, pas une étape de l'étage 1. Les deux
portes d'entrée (citation, conviction) l'appellent. *Rappel : le pasteur tape sur une tablette, un
vendredi soir. Exiger l'orthographe, c'est refuser le terrain.*

### S10 — proposer les deux axes, et ne jamais interpréter le pasteur (tranché 2026-08-04)

**La règle** : une conviction rend **plusieurs** axes candidats, chacun avec son motif — jamais un
seul « meilleur ». C'est un `AWAIT` ordinaire (le contrat l'exige déjà : `AWAIT` sans options est
refusé). Le pasteur choisit.

**Ce que le moteur ne fait à aucun prix** : diagnostiquer celui qui écrit. Il ne dit pas « vous êtes
dans la plainte », il ne classe pas un axe « apparent » et l'autre « réel ». Les axes sont présentés
**au même rang**, nommés, motivés :

> *« Votre formulation touche deux axes : **guérison et maladie** · **la prière sans réponse, la
> lamentation**. Lequel prêchez-vous ? »*

La nuance n'est pas cosmétique. Ordonner les axes en « ce que vous avez dit » / « ce que vous vouliez
dire » serait une interprétation du for intérieur du pasteur — le moteur n'a rien à y faire. **Nommer
les deux suffit :** un homme qui a écrit « malgré les prières rien ne va » et qui voit s'afficher
*lamentation* comprend seul.

**Le filet ne dépend pas de son choix.** Même s'il retient *guérison*, les **textes résistants** de
§7 s'affichent au même rang que les portants : 2 Co 12:7-10 (Dieu dit non trois fois), 2 Tm 4:20
(Trophime laissé malade), Jn 9:1-3 (ni lui ni ses parents n'ont péché), Ps 88. **La protection est
dans les textes résistants, pas dans la justesse du choix d'axe.** C'est ce qui rend S10 tenable :
on ne mise pas sur le fait que le pasteur choisisse bien.

**Repli** : identique à S12 — sans modèle, le pasteur désigne lui-même ses axes dans la liste curée.

### S12 + S18b — le repli manuel, et ce qu'il rend possible (tranché 2026-08-04)

**La règle** : partout où du **texte libre doit devenir un axe** — l'entrée `conviction` (S12) comme
la contrainte négative (S18) — le pasteur peut **désigner l'axe lui-même** dans la liste des 10
catégories curées. L'étape modèle ne fait que **pré-remplir un choix qu'il pouvait déjà faire**.

**La conséquence, plus grande qu'il n'y paraît** : le mode conviction devient **model-optional**.
Le modèle n'est plus une dépendance du chemin critique, c'est un **accélérateur**. Trois gains :

1. **« Aucun mur » redevient vrai** sur ce chemin — au plafond, la porte d'entrée reste ouverte.
2. **Urim est livrable sans aucun modèle branché** — cohérent avec Architecture v2 §10 (« la V1 est
   intégralement utilisable hors ligne sur le domaine public »). Le terrain — tablette, connexion
   irrégulière — est servi par défaut, pas par exception.
3. **Le sélecteur d'axes n'est pas un écran de secours** : c'est l'écran **de base**, que le modèle
   pré-remplit quand il est disponible. Rien à construire « en plus pour le cas dégradé ».

**Le patron existe déjà dans le dépôt** — c'est celui du module Sermon (S-1) : `MistralSermonDigester`
avec `KeywordSermonDigester` en repli déterministe sans clé, choisis par `build_sermon_digester`.
Urim ne l'invente pas, il l'applique.

> Et la posture produit reste la même que partout ailleurs dans Dorea : **l'IA propose, l'homme
> dispose.** Ici elle ne fait même pas ça — elle pré-coche.

---

## 7ter. Les écarts — spec écrite ↔ décisions prises

Tableau de contrôle. **Trois familles**, et seule la première demande encore un arbitrage.

### A · Contradictions **internes aux specs** — ✅ tranchées le 2026-08-05

| # | Écart | Issues |
| :-- | :-- | :-- |
| **E1** | **§3 étage 6** : le thème « croise l'axe retenu, **le calendrier ecclésial**, l'historique » ⟷ **§4.3/§4.5** : `ACL → moteur` **interdit** | ✅ **Tranché 2026-08-05 — (a) : §4 gagne.** Le thème croise **l'axe retenu et l'historique** (`preached`, donnée d'Urim), **jamais le calendrier ecclésial**. Celui-ci s'**affiche à côté** du texte ; le pasteur en tient compte lui-même. **§3 étage 6 est corrigé sur ce point** — le test bytecode reste la règle |
| **E2** | **Nombre d'étages divergent** : **6** (mermaid `Structure §2`) · **7** (Architecture §3, 0→6) · **8** (`PIPELINE`) | ✅ **Tranché 2026-08-05 — (a) : HUIT étages.** `ShapeHomiletic` **est** un étage : elle consomme les axes, rend un `StageResult` **motivé** (`refusal_reason` est en base) et peut `REFUSE` — c'est la définition d'un étage. Les mentions « 6 étages » et l'arrêt à l'étage 6 sont **périmées** |

### B · Nos décisions qui **surchargent** la spec — déjà tranchées

| # | La spec disait | Nous avons décidé |
| :-- | :-- | :-- |
| **E3** | §5 : caveat confessionnel « ne s'affiche que dans la **tradition configurée** » ; §4 : « ne fuit pas hors de sa tradition » | **D-F** — il s'affiche **toujours**, formulé en **divergence nommée**. La surcharge touche **deux** endroits de la spec |
| **E4** | §6 : plafond vérifié « **à l'ouverture**, jamais en cours de route » | **S6** — à la **première consommation**, puis droit acquis (+72 h). L'intention est préservée, ancrée au bon endroit |
| **E5** | §3.6 : `matches_corpus boolean` | **S4** — `verdict IN ('exact','extrait','altere')` : troncature ≠ altération |
| **E6** | §3.2 : `strength IN ('dominant','porte','absent')` | **S1** — `'resiste'` ajouté, sans quoi le mode conviction est inconstructible |
| **E7** | §6 : `pericope_key` calculée à l'ouverture | **S9** — clé **provisoire**, re-clée sur la péricope résolue |
| **E8** | §3.8 : liste blanche de **7** types | **S15** — **8** avec `EVANGELISM` |
| **E9** | *(rien)* | **S17** — table `textual_variant` ajoutée : les variantes n'avaient nulle part où vivre |
| **E10** | §3 étage 2 : « unité littéraire réelle + motif » | **D-E · S8 · S18 · S19** — règle complète : 3 relations, ordre par `refused_axes`, hors-bornes à l'étage 1 |
| **E11** | *(rien)* | **S2** — `REFUSE` motivé quand l'ensemble des candidats est **vide** |
| **E12** | *(rien)* | **S12** — repli **manuel** sur les axes curés ⇒ le mode conviction devient *model-optional* |
| **E13** | §3.2 : `doctrinal_axis (code, label)` | **+ `ordinal`** et les **dix loci** semés (2026-08-05) |

### C · Écarts **spec ↔ dépôt réel** — déjà résolus

| # | Écart | Résolution |
| :-- | :-- | :-- |
| **E14** | La spec prescrit `CREATE SCHEMA` ; le dépôt n'utilise **aucun** schéma Postgres | **D-A** — on adopte les schémas dédiés ; ces contextes inaugurent la pratique |
| **E15** | La spec prévoit un `program_adapter` | **C5** — le calendrier vit hors `watch` ⇒ l'adaptateur d'événements **disparaît** |
| **E16** | `watch_aggregate_adapter` n'avait **rien à appeler** | **S14** — read-model non nominatif **construit** |
| **E17** | `urim.preached` chevauche le contexte `sermon` | **D-B** — « Urim prépare, `sermon` publie », par un port, sans FK |
| **E18** | Finance : « le trésorier est-il un rôle IAM ? » | **C1** — `RoleCode.TREASURER` existe **avec** ses permissions |
| **E19** | Finance : fonds par site ou par église ? | **C6** — par **tenant** (une annexe **est** un tenant) |

> **Restent ouverts par ailleurs** (constats, pas écarts) : **S20** (la conviction qui accuse) ·
> **S21** (normaliseur partagé) · **S22** (`bounds_overridden` sans faisabilité) · **S24** (candidats
> groupés par scène).

---

## 7bis. Impact des 21 constats sur la mise en place

L'architecture ne bouge pas. **Le contenu de quatre chantiers change, et un prérequis apparaît hors Urim :**

| Chantier | Ce qui change |
| :-- | :-- |
| **0 — Socle** | ✅ une seule correction, faite : `Reference.verse_start` optionnel (S7) |
| **1 — Corpus** | **+ table `textual_variant`** (S17), migration 003. Et **l'acquisition doit inclure un apparat critique**, pas seulement des textes |
| **2 — Livrable** | `verdict` remplace `matches_corpus` (S4) · comparaison via `versification_map` (S5) |
| **3 — Résolution** | **+ entrée hybride** (S16) · la **détection de version devient porteuse de sens** (S17) · **+ validation des bornes de verset** (S19) · **+ normaliseur extrait en utilitaire partagé** (S21) — la conviction saute l'étage 1 mais en a besoin |
| **4 — Bornage** | ✅ **règle complète consolidée** (§ ci-dessus) : 3 relations — coïncide/coupe/englobe — + ordre par `refused_axes` + série non modélisée. Lit `deps.doctrine` (tranché) |
| **5 — Doctrine** | **`'resiste'`** (S1) · caveats **toujours affichés**, formulés en divergence (D-F) · **+ textes résistants qui se retournent vers le prédicateur** quand la conviction accuse (S20) |
| **7 — Homilétique** | inchangé |
| **9 — Plafond** | `metered_at` (S6) · **re-clage** de la réservation (S9) · repli conviction ✅ **résolu** (S12 : sélecteur d'axes manuel, écran **de base** que le modèle pré-remplit) |
| **hors Urim** | ✅ **read-model d'agrégats non nominatifs dans `watch`** (S14) — **livré** ; la couche anticorruption a enfin une source |

**Ce qui n'a pas bougé** : le contrat du moteur, les 4 tests d'architecture, la frontière `AFFICHAGE
SEUL`, l'ordre des chantiers — et le **§11 qui gèle toujours la construction**.

> **Les 21 constats ont coûté zéro.** Sept corrections de schéma/code sur des tables qui n'existent
> pas encore. Le même travail après le chantier 1 aurait été une reprise de données ; après la mise
> en service, un incident.

> **Ce que la simulation de la citation fusionnée confirme** : « deux versets fusionnés donnent un score
> médiocre partout — c'est le signal, pas l'échec » (§3, étage 1). Le mode de défaillance **est** le
> diagnostic : le moteur ne rend pas « introuvable », il rend « votre mémoire a fusionné deux textes,
> les voici ». Un moteur ordinaire aurait servi le meilleur des deux — et le pasteur aurait prêché une
> phrase qui n'existe dans aucune Bible.

### D-F — le caveat confessionnel s'affiche, mais comme une **divergence**

⚠️ **Frottement assumé avec la règle §4 du schéma** (« un caveat confessionnel ne fuit pas hors de
sa tradition »). Il est levé par la **formulation**, pas par le filtrage :

- ❌ *« Votre tradition enseigne que la justice de Dieu est attribuée. »* → imposerait une confession
- ✅ *« Ici les traditions divergent (réformée / catholique / …) : le texte ne tranche pas. »* → avertit

Ce que la règle voulait empêcher, c'est qu'**une** confession soit servie comme le sens évident du
texte. Nommer la divergence fait l'inverse : c'est de l'humilité, pas une fuite. Le `tradition_scope`
du caveat reste `NOT NULL` (contrainte inchangée) — il sert désormais à **nommer** les traditions
concernées à l'écran, non à filtrer l'affichage.

**Conséquence heureuse** : le champ « tradition » manquant sur `Tenant` **n'est plus bloquant**
(`denomination` reste un texte libre, descriptif). À rouvrir seulement si un jour on veut *filtrer*
par tradition — ce qui exigerait alors une tradition **déclarée et normalisée** sur le tenant.

---

*Plan — fait foi sur l'ordre et l'ancrage dans ce dépôt. Les deux specs sources font foi sur le
contenu. Rien ne démarre avant §1.*
