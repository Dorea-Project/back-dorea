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
| 2 | Émetteur `CasePriority.ABSENCE` activé | `CasePriority.ABSENCE` **existe** et est émis par `watch/application/interpreters/check_fired.py:118`. Contexte `watch` livré (bloc 1) |
| 3 | Corrections `Moteur_Corrections_et_Regime_Hybride.md` appliquées | **Doc absent de `docs/`** — à fournir/vérifier avant démarrage |
| 4 | **Un dimanche réel, dans une église réelle** | ❌ **Non atteint** — c'est le vrai verrou |

**Conclusion :** le code n'est pas le blocage ; l'usage réel l'est. **R1 (dispersion) reste le risque
dominant.** Ce plan existe pour être prêt, pas pour être lancé.

---

## 2. Ce que le code dit — corrections aux specs

Points où la réalité du dépôt diffère de ce que les specs supposent. **À trancher avant le chantier 0.**

| # | Spec | Réalité du code | Impact |
| :-- | :-- | :-- | :-- |
| **C1** | Finance §13.1 « Le trésorier est-il un rôle IAM existant ? — à vérifier » | ✅ **OUI** : `RoleCode.TREASURER` existe **avec permissions** `VIEW_CONTRIBUTIONS` + `RECORD_CASH` (`iam/domain/permissions.py:131`), commentées « la comptabilité, pas la curiosité ». Il existe même une paire `(LAUNCH_COLLECTION, VIEW_CONTRIBUTIONS)` | **Point ouvert #1 CLOS.** Finance se greffe sur l'IAM existant, ne crée pas de rôle |
| **C2** | Specs : `CREATE SCHEMA finance` / `urim_corpus`, migrations `001…011` | Le dépôt n'utilise **aucun schéma Postgres** (tout en `public`), et Alembic a **une seule chaîne linéaire** de révisions (tête actuelle `e5f6a7b8c9d0`) | **Décision requise** : adopter les schémas dédiés (isolation forte, cohérent « couture d'extraction ») **ou** rester en `public` avec préfixes `urim_*`/`finance_*`. Les migrations devront s'insérer dans la chaîne existante, pas repartir de `001` |
| **C3** | Urim : étage `preached` / archive de prédication | Le contexte **`sermon` existe déjà** (S-0→S-5 : dépôt, digestion IA, capsules, compagnon, `preached_on`) | **Frontière à tracer** : `urim` = *préparer* (avant), `sermon` = *ce qui a été prêché et vit après*. `POST /urim/preached` **chevauche** `sermon`. Décider : Urim écrit-il dans `sermon` via un port, ou duplique-t-il une archive ? |
| **C4** | Finance §4.2 : devise portée par une table `finance.currency` | `tenants.currency` **existe déjà** (défaut `XOF`, ISO 4217, cf. M0 §2.2) | Réutiliser la devise du tenant comme défaut ; `finance.currency` reste la table d'exposants (XOF=0, EUR=2) |
| **C5** | Urim §10 : « où vit le calendrier des rencontres ? — 10 min dans back-dorea » | Les rencontres vivent dans **`attendance`** (`gatherings`) et les RDV dans **`appointments`** — **hors `watch`** | ✅ **Réponse : hors `watch`.** Donc, par la spec, **l'adaptateur d'événements disparaît** ; seul l'adaptateur d'agrégats subsiste |
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

**Les 4 tests d'architecture (chantier 0, rouges d'abord) :**
- `test_urim_n_importe_rien_hors_de_lui_meme`
- **`test_aucun_etage_ne_lit_le_contexte_ecclesial`** ← *le plus important du dépôt* : interdit **par
  programme** que les agrégats de veille atteignent une proposition de thème (AFFICHAGE SEUL)
- `test_determinisme` (100×, même `corpus_snapshot`)
- `test_tout_resultat_porte_un_motif`

**Invariants à ne pas négocier :** `rationale` jamais vide · `AWAIT` = état normal, pas une erreur ·
`DEGRADE` ne coupe jamais (« aucun mur un vendredi soir ») · `run()` pure · réservation vérifiée
**à l'ouverture seulement**.

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
| **D-A** | Schémas Postgres dédiés (`finance`, `urim`, `urim_corpus`) ou préfixes en `public` ? | **Schémas dédiés** — cohérent avec « la couture d'extraction », et Finance sortira en premier |
| **D-B** | `POST /urim/preached` vs contexte `sermon` existant | **Urim prépare, `sermon` publie** : Urim écrit dans `sermon` via un port, pas de seconde archive |
| **D-C** | Séquence de reçus : par exercice ou continue | **Par exercice** (recommandation de la spec, #4) |
| **D-D** | Fonds en multi-sites | **Par tenant** (une annexe = un tenant, C6) |

---

*Plan — fait foi sur l'ordre et l'ancrage dans ce dépôt. Les deux specs sources font foi sur le
contenu. Rien ne démarre avant §1.*
