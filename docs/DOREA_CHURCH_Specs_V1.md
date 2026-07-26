# DOREA CHURCH — SPÉCIFICATIONS V1

**Version :** 1.0 — Pilote
**Date :** Juillet 2026
**Cadre :** 100 églises · 6 mois · gratuit · objectif 10 000 utilisateurs actifs
**Statut :** À valider — 4 décisions ouvertes (§12)

> Ce document remplace le CDC 1.0 **et** le document de référence V1 précédent.
> Il intègre le repositionnement « Dorea Church » et le cadrage pilote.

---

## 1. Positionnement

**Dorea Church permet à une communauté chrétienne de connaître réellement ses membres :
qui est actif, qui est malade, qui a voyagé, qui ne vient plus, qui a changé d'église.**

### 1.1. Le principe de non-surveillance — fondateur

> **Il n'y a PAS de QR code à l'entrée de l'église.**

Ce n'est pas un détail technique, c'est le positionnement. Un QR à l'entrée transforme Dorea en
**pointeuse** et détruit la confiance pastorale. La présence est captée **à l'intérieur de la
rencontre, par les pairs**, jamais à la porte.

### 1.2. L'absence n'est pas binaire

C'est la rupture centrale avec tous les outils existants. Une absence sans cause n'est **pas** un
signal exploitable. Dorea qualifie l'absence :

`Malade` · `En voyage` · `Excusé` · `A changé d'église` · `Sans nouvelles`

**Seul « Sans nouvelles » déclenche une attention fraternelle.** Tout le reste est une information,
pas une alerte. C'est ce qui évite le bruit qui tue le produit.

---

## 2. Objectifs du pilote et mesure du succès

| Objectif | Cible |
| :--- | :--- |
| Églises embarquées | 100 |
| Utilisateurs actifs | 10 000 (soit **100 par église**) |
| Durée | 6 mois, gratuit |

### 2.1. Le KPI qui décide de la V2

> **Nombre d'églises ayant tenu ≥ 8 semaines consécutives de présences validées.**

10 000 inscrits sans rétention est un échec déguisé : la V2 (billetterie, marketplace) n'aurait
personne à qui vendre. La rétention prime sur le volume.

| KPI | Définition |
| :--- | :--- |
| **Églises actives à 8 semaines** | ***Décide du passage en V2*** |
| Utilisateurs actifs hebdomadaires | Ouvrent l'app ≥ 1× / semaine |
| Rencontres avec présence validée / semaine | Cœur opérationnel |
| Taux de qualification des absences | *(absences qualifiées / total absences)* — mesure la valeur pastorale |
| Taux de visiteurs rappelés sous 48 h | Suivi de l'accueil |

### 2.2. La contrainte cachée du pilote

**100 utilisateurs actifs par église ne s'obtiennent pas avec une app qui sert à pointer.**
Personne n'installe une application pour être compté.

> **Le moteur d'adoption, ce sont les ANNONCES** (décès, naissances, convention).
> Les fidèles ouvrent Dorea pour **savoir**, et scannent leur présence **parce qu'ils sont déjà là**.

Conséquence structurelle : **le module Annonces est co-central avec la Présence.** Il n'est pas
périphérique. Sous-investir dessus fait échouer l'objectif des 10 000.

---

## 3. Périmètre

### 3.1. Inclus en V1

Église & annexes · Groupes · Rencontres · **Présence pair-à-pair** · **Qualification d'absence** ·
**Annonces multi-portées** · Accueil & Intégration · Alertes fraternelles · RDV Pasteur ·
Onboarding auto-servi.

### 3.2. Exclus — reportés V2

| Exclu | Raison |
| :--- | :--- |
| Events publics, billetterie, tickets | V2 — cœur du modèle économique |
| Marketplace | V2 |
| Sponsoring Dorea | V2 |
| **Liens de paiement dans les annonces** | = paiement → V2 (+ enjeu juridique : collecte de fonds religieux, KYC) |
| Abonnement premium | V1 = gratuit par définition |
| Fidèle vendant ses tickets | V2 — c'est un **pivot de business model**, pas une extension |
| Messagerie instantanée | V2 |
| Formations & parcours | V2 |
| Application native | PWA en V1 |

---

## 4. Structure ecclésiale

### 4.1. Le modèle hiérarchique

```
DÉNOMINATION        (ex : Assemblées de Dieu)      — portée d'annonce nationale/régionale
   └── ÉGLISE        (indépendante OU principale)  — TENANT · a un Owner
         ├── ANNEXE  (son pasteur, ses membres, son admin)
         └── ANNEXE
               └── GROUPES (cellule, département, association…)
```

### 4.2. Règle de modélisation — importante

> **La hiérarchie existe dans le SCHÉMA dès la V1** (`église.parent_id` nullable,
> `annonce.portée` ∈ {nationale, régionale, église, annexe, groupe}),
> **mais l'UI ne couvre que le cas simple** (église indépendante) au lancement.

*Raison :* si le recrutement des 100 églises passe par **une dénomination**, tu ne fais pas 100 ventes
mais **une seule** — c'est de loin le canal d'acquisition le plus rapide. Le coût de prévoir la
hiérarchie aujourd'hui est faible ; après, il est prohibitif. *(Voir §12.1.)*

### 4.3. Le tenant

- **Le TENANT est l'Église** (indépendante ou principale). Elle a **un Owner**.
- **L'annexe est un sous-espace du tenant** : son propre pasteur, ses propres membres, sa propre
  administration — mais **pas** son propre Owner.
- **Cloisonnement :** une annexe ne voit **jamais** les données d'une autre annexe.
  L'église principale voit l'agrégat.

---

## 5. IAM — modèle de domaine

### 5.1. Les trois notions

| Notion | Définition | Propriétaire |
| :--- | :--- | :--- |
| **Compte** | Identité de la personne. **Globale.** Clé = **téléphone** | La personne |
| **Appartenance** | Lien Compte ↔ Église/Annexe. Porte le **statut** | L'église |
| **Attribution de rôle** | Permission accordée dans une **portée** | L'église |

**Une église ne possède jamais un Compte.** Elle ne peut que **clôturer une Appartenance**.
C'est ce qui rend possible « qui a changé d'église » (§1) — et ce qui prépare la V2 sans migration.

### 5.2. Agrégats

- **Compte** *(racine)* — global, credentials **optionnelles** (le visiteur existe avant l'app)
- **Appartenance** *(racine)* — statut + historique + **attributions de rôle** (entités internes)
  → la rétrogradation **révoque les rôles dans la même transaction** (cascade atomique)

### 5.3. Chaîne d'autorité

```
PLATEFORME → provisionne le tenant → crée le compte OWNER
   OWNER    → enregistre les PASTEUR(S) et les GESTIONNAIRES (Admin)
   ADMIN    → crée les GROUPES et désigne les RESPONSABLES
   RESPO    → enregistre les MEMBRES du groupe (formulaire ou lien)
```

### 5.4. Règle de bootstrap

> **L'enrôlement par l'Owner confère directement le statut *Membre confirmé*.**

Sans cette règle, l'invariant « un rôle exige Membre confirmé » rend la création d'église
impossible (personne n'est membre, personne ne peut confirmer). Paradoxe résolu.

### 5.5. Statuts

**Chaîne de progression :** `Invité → Visiteur → Sympathisant → Nouveau → Membre confirmé`
**Statut parallèle :** `Participant externe` *(hors chaîne)*
**Sortie :** `Appartenance clôturée` *(le Compte survit)*

| Transition | Déclencheur |
| :--- | :--- |
| *(néant)* → Membre confirmé | **Owner seul** (bootstrap) |
| Invité → Visiteur | **Automatique** — 1ʳᵉ présence captée |
| Visiteur → Sympathisant → Nouveau | Intégration |
| Nouveau → Membre confirmé | Admin **ou** Intégration |
| Rétrogradation / clôture | **Admin seul** — révoque tous les rôles |

*Fast-track Invité → Membre : **interdit en V1**.*

### 5.6. Rôles

| Rôle | Portée | Enregistré par |
| :--- | :--- | :--- |
| **Owner** | Tenant | Plateforme |
| **Pasteur** *(pluriel)* | Église / Annexe — **lecture seule** | Owner |
| **Admin / Gestionnaire** | Église / Annexe | Owner |
| **Responsable de groupe** | **Groupe** — 1 à 6 | Admin |
| **Accueil** | Église / Annexe | Admin |
| **Intégration** | Église / Annexe | Admin |
| *Fidèle* | — | *Capacité de base, pas un rôle* |

**Modèle de permission — RBAC borné par la propriété :**

> Un acteur peut faire A **si** un rôle accorde A **ET** que la ressource tombe dans sa portée.
> *Le rôle donne le verbe. La propriété donne le périmètre.*

Une attribution de rôle de portée groupe **porte obligatoirement l'ID du groupe**.
« Responsable » seul ne donne aucun droit.

---

## 6. Groupes

### 6.1. Règles

- **Un groupe n'existe que par validation de l'église.** Un fidèle ne peut **jamais** créer un groupe.
- Types : **cellule · département · association** *(+ ministère, équipe, commission)*
- **1 ≤ responsables ≤ 6.** Le minimum de 1 est un invariant dur : un groupe sans responsable
  produit des alertes **sans destinataire**.
- Le groupe porte : horaires de rencontre, membres, annonces, événements internes.
- **Enregistrement des membres** par le/les admins du groupe : **formulaire** ou **lien d'invitation**.

### 6.2. Le type de groupe porte une POLITIQUE, pas une étiquette

> Une absence en **cellule** a un poids pastoral fort.
> Une absence en **commission technique** ou en **association** n'en a aucun.

Si le type ne pilote pas le moteur d'alertes, le worker génère du **bruit** → les responsables
**cessent de lire les alertes** → le produit perd sa raison d'être.

| Type | Alertes d'absence | Seuil par défaut |
| :--- | :--- | :--- |
| Cellule | **Oui — suivi fort** | 3 absences consécutives |
| Département · Ministère · Équipe | Oui — modéré | 4 |
| Association · Commission · Temporaire | **Non** | — |

*Seuils surchargeables par l'Admin.*

### 6.3. Assignation des alertes

> **Une alerte de groupe est assignée AU GROUPE, pas à un responsable nommé.**

Avec jusqu'à 6 responsables égaux, il n'y a pas de destinataire par défaut. N'importe lequel peut
prendre l'alerte en charge. Robuste au turnover. *(Voir §12.2.)*

---

## 7. PRÉSENCES — le cœur

### 7.1. Le mécanisme pair-à-pair

**Principe :** pendant la rencontre, chaque personne déjà validée devient un **point de scan** pour
son voisin. Le téléphone du responsable ne circule pas.

```
1. Le responsable ouvre la rencontre → son QR devient actif
2. Un membre scanne le QR du responsable → il est présent
3. Ce membre devient à son tour scannable
4. Chaîne de propagation dans la salle
```

**Aucun QR à l'entrée. Aucune file. Aucune surveillance.**

### 7.2. Le QR tournant

> Le QR d'un participant est **actif pendant une fenêtre courte (30–60 s), puis se régénère.**

C'est le mécanisme TOTP. Il rend l'envoi d'une capture d'écran à un absent très contraignant.

**Modèle de menace assumé :** un présent peut screenshoter son QR et l'envoyer par WhatsApp à un
absent qui scanne dans la fenêtre. **On ne cherche pas à l'empêcher cryptographiquement** — personne
ne gagne rien à se faire marquer présent à une cellule.

**Mais le risque est réel et il est pastoral :** un membre qui s'éloigne apparaît présent →
**aucune alerte ne se déclenche** → Dorea rate exactement ce pour quoi il existe (**faux négatif**).

**Deux garde-fous, suffisants :**
1. **Rotation courte** (30–60 s)
2. **Traçabilité de la chaîne** — on enregistre **qui a scanné le QR de qui**. La dissuasion est
   sociale, pas technique. Une chaîne anormale est détectable a posteriori.

### 7.3. Les membres sans smartphone

> **Liste de présence manuelle**, validée par un responsable.

Non négociable : dans une église, une part significative des membres (souvent les plus âgés, souvent
les plus fidèles) n'a pas de smartphone. Un système qui les rend invisibles produit des alertes
d'absence **sur les personnes les plus présentes**. Ce serait un échec absolu.

### 7.4. Hiérarchie de confiance

| Mode | Niveau |
| :--- | :--- |
| Scan par un responsable | **Très fort** |
| Scan pair-à-pair (chaîne validée) | Fort |
| Liste manuelle validée par un responsable | Fort |
| Ajout manuel a posteriori | Moyen |
| Signalement par un fidèle | **Faible — à confirmer** |

**Résolution de conflit :** une présence *Très fort* ne peut pas être écrasée par un niveau
inférieur — seulement confirmée. Historique conservé.

### 7.5. Statuts de présence

`Présent validé` · `Présence signalée (en attente)` · `Absent` · **`Absent qualifié`** *(§8)*

### 7.6. Mode hors ligne — contrainte forte

Le réseau est faible dans beaucoup d'églises. **Les scans sont mis en file locale et rejoués à la
reconnexion.**

⚠️ **Risque identifié (R1) :** un scan rejoué **après** le passage du worker d'alertes crée une
**alerte d'absence à tort**.
**Mitigation :** le worker n'évalue une rencontre qu'après une **fenêtre de grâce** (voir §12.3).

---

## 8. QUALIFICATION D'ABSENCE — la valeur pastorale

C'est ce qui distingue Dorea de tout logiciel de gestion d'église.

### 8.1. Les qualifications

| Qualification | Déclenche une alerte ? | Posé par |
| :--- | :--- | :--- |
| **Malade** | Non — déclenche une **visite de soutien** | Responsable, Fidèle *(pour lui-même)* |
| **En voyage** | Non — suspend le compteur d'absence | Responsable, Fidèle |
| **Excusé** | Non | Responsable, Fidèle |
| **A changé d'église** | Non — propose la **clôture d'appartenance** | Admin, Intégration |
| **Sans nouvelles** | **OUI — attention fraternelle** | *(défaut si non qualifié)* |

### 8.2. Règles

- **Toute absence non qualifiée est « Sans nouvelles » par défaut.** C'est le seul état qui alerte.
- **Le fidèle peut se qualifier lui-même à l'avance** (« je serai en voyage 3 semaines »)
  → **suspend le compteur**. Résout la faiblesse R2b.
- La qualification est **une donnée pastorale, jamais un jugement**.

### 8.3. Ce que ça change

Sans qualification, l'alerte d'absence est du **bruit** : elle ne distingue pas un malade d'un
membre qui décroche. Avec elle, chaque alerte est **actionnable**. C'est la condition de survie du
module 6.

---

## 9. ANNONCES — moteur d'adoption (co-central)

### 9.1. Portées

`Nationale` · `Régionale` · `Église` · `Annexe` · `Groupe`

*(Les portées nationale/régionale supposent la couche dénomination — §4.2.)*

### 9.2. Tags

`Décès` · `Naissance` · `Fête` · `Convention` · `Mariage` · `Baptême` · `Prière` · `Général`

### 9.3. Contenu

Texte · **image** · **GIF** · **vidéo** · liens
*(**Liens de paiement : V2** — §3.2.)*

### 9.4. Émetteurs

Owner · Admin · Pasteur · Responsable de groupe *(portée groupe uniquement)*

### 9.5. Contrainte forte — non-exposition

> **Le fidèle ne voit JAMAIS :** les absences des autres · les alertes pastorales ·
> les notes de suivi · les statistiques privées · les commentaires internes.

*Le fidèle voit ce qui l'aide à participer, pas ce qui expose les autres.*

---

## 10. RDV PASTEUR

Module léger, **fort levier d'adoption** (raison personnelle d'ouvrir l'app).

- Le fidèle demande un RDV : motif *(optionnel, confidentiel)*, créneaux souhaités
- Le pasteur *(ou son secrétariat)* accepte, propose un autre créneau, ou refuse
- **Confidentialité :** visible uniquement du demandeur et du pasteur concerné
- **Hors périmètre V1 :** agenda partagé, récurrence, visio

---

## 11. MODULES DE DÉVELOPPEMENT

> **Rappel (voir §14) :** un **seul backend FastAPI**. La colonne **Surface** indique quel front
> consomme le module — **backoffice** (`/api/backoffice/*`, PWA Next.js), **mobile**
> (`/api/mobile/*`, Flutter), **les deux**, ou **worker** (tâche de fond, sans surface HTTP).
> Il n'y a **aucun** service séparé ; tout est dans ce monolithe.

### 11.1. Socle — rien ne démarre sans

| Module | Contenu | Surface |
| :--- | :--- | :--- |
| **M0 · Tenant, Owner & Hiérarchie** | Provisionnement, Owner, `parent_id`, annexes | backoffice |
| **M1 · IAM** | Compte · Appartenance · Statuts · Rôles · portées · cascade | backoffice (écritures) + mobile (lecture) |
| **M2 · Auth 2 canaux** | JWT mobile + session backoffice, **même hash** (deux canaux, un backend) | les deux |
| **M3 · Onboarding auto-servi** | ⚠️ **Conditionne tout le pilote** — voir §11.4 | backoffice |

### 11.2. Cœur

| Module | Contenu | Surface |
| :--- | :--- | :--- |
| **M4 · Groupes** | Types + **politique de suivi**, 1–6 responsables, formulaire/lien | backoffice (+ lecture mobile) |
| **M5 · Rencontres** | Horaires, occurrences, **définition du « membre attendu »** *(§12.4)* | les deux |
| **M6 · Présences** | **QR tournant, chaîne pair-à-pair, liste manuelle, file offline** | **mobile** |
| **M7 · Qualification d'absence** | Les 5 qualifications, auto-déclaration, suspension de compteur | les deux |
| **M8 · Annonces & Fil** | **Co-central** — portées, tags, médias | les deux |
| **M9 · Worker d'alertes** | 6 règles, fenêtre de grâce, assignation au groupe | worker |

### 11.3. Périphérie

| Module | Contenu | Surface |
| :--- | :--- | :--- |
| **M10 · Accueil & Intégration** | Visiteur sans app, suivi 48 h | backoffice |
| **M11 · RDV Pasteur** | Prise de rendez-vous, vue pasteur (lecture seule) | les deux |
| **M12 · Dashboard & KPI** | Indicateurs owner / admin | backoffice |
| **M13 · Exports** | Table `jobs` (pas de Redis) | backoffice + worker |

### 11.4. Le module que personne n'avait listé

> **M3 · Onboarding auto-servi.**
> 100 églises en pilote gratuit = **aucun support manuel possible**.
> Création d'église, import des membres, premier groupe : **< 15 minutes, sans intervention humaine.**

C'est le module qui décide si le pilote est opérable. Il n'est dans aucune version antérieure du CDC.

### 11.5. Chemin critique

```
M0 → M1 → M2 → M4 → M5 → M6 → M7 → M9
                              ↘ M8  (parallélisable, mais NE PAS sous-investir)
M3 (onboarding) — parallèle, mais BLOQUANT pour le lancement pilote
```

⚠️ **M9 porte la valeur du produit mais est le dernier testable** — il lui faut des semaines de
données réelles. **Prévoir un mode simulation**, sinon les faux positifs se découvrent en production.

---

## 12. DÉCISIONS OUVERTES

| # | Décision | Recommandation |
| :--- | :--- | :--- |
| **12.1** | **Recrutement des 100 églises : par une dénomination, ou one-to-one ?** Détermine si l'UI hiérarchique est V1 ou V2. | Schéma hiérarchique **dès maintenant**, UI **seulement si dénomination** |
| **12.2** | **Alerte assignée au groupe, ou responsable principal réintroduit ?** *(Ton dernier message réintroduit un « responsable principal », ce qui contredit les 6 responsables égaux.)* | **Au groupe** — 6 égaux |
| **12.3** | **Fenêtre de grâce du worker** avant évaluation d'une rencontre *(gère le rejeu offline — R1)* | **24 h** après la fin de la rencontre |
| **12.4** | **Définition de « membre attendu ».** L'alerte d'absence n'a pas de dénominateur sans elle. Un membre est-il attendu à **toutes** les rencontres de son groupe ? | **Oui par défaut**, sauf qualification d'absence active |

---

## 13. FAIBLESSES RÉSIDUELLES

| # | Faiblesse | Risque |
| :--- | :--- | :--- |
| **R1** | **Rejeu offline après passage du worker** → alerte d'absence à tort | Mitigé par la fenêtre de grâce (§12.3) — **à valider en pilote** |
| **R2** | **Screenshot du QR envoyé à un absent** → faux négatif pastoral | Mitigé (rotation + traçabilité), **assumé** |
| **R3** | **Unicité par téléphone** : un couple partageant un numéro = un seul Compte | Moyen — non résolu |
| **R4** | **RGPD / suppression.** Le Compte est global. Qui peut le supprimer ? Rétention des présences ? | **Élevé — juridique, non traité** |
| **R5** | ~~Cohérence du hash d'auth entre FastAPI et NestJS~~ — **caduc** (pivot monolithe, §14) : un seul backend, un seul hasher | **Résolu par l'architecture** |
| **R6** | **Aucun audit trail IAM.** Qui a rétrogradé qui, quand ? Sujet sensible en contexte pastoral | Moyen |
| **R7** | **Owner unique = point de défaillance.** S'il perd son accès, le tenant est bloqué | Moyen |

---

## 14. ARCHITECTURE (rappel — verrouillée)

> **⚠️ Correction (2026-07) — pivot monolithe.** La V1 de cette spec décrivait deux backends
> (FastAPI mobile + NestJS backoffice, ce dernier « propriétaire unique du schéma »). **C'était une
> erreur.** L'architecture réelle est **un seul backend** : ce **monolithe FastAPI**, qui **possède le
> schéma et les migrations** et sert **les deux surfaces**. NestJS n'existe pas. Les deux « fronts »
> (PWA Next.js/React et Flutter) sont des **clients**.

| Composant | Choix |
| :--- | :--- |
| **Backend (unique)** | **FastAPI monolithe** — propriétaire du schéma & des migrations, expose `/api/backoffice/*` + `/api/mobile/*` |
| Front backoffice | **PWA Next.js / React** (gestion tenant & owner) → `/api/backoffice/*` |
| Front mobile | **Flutter** (le membre) → `/api/mobile/*` |
| Base | **PostgreSQL** — propriété du backend FastAPI |
| Migrations | **Alembic**, dans ce repo (`migrations/`, autogenerate) ; `dev_bootstrap` = dépannage local |
| Broker | **Aucun** — les 6 alertes sont des **non-événements** |
| Cache / jobs | **Aucun** — table `jobs` |

> **Règle :** le schéma et les migrations vivent **dans ce backend FastAPI**, source de vérité unique.
> La faiblesse **R5** (cohérence du hash entre deux services) **disparaît** : il n'y a qu'un service.

---

**Fin des spécifications V1.**

*Les §12 et §13 doivent être traités avant le démarrage du développement.*
