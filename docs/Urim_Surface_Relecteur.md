# La surface du relecteur — rendre finissable le travail qu'un humain doit faire

**Statut :** livré le 2026-08-13. Contexte `urim`, surface **Plateforme**.
**Le chiffre qui commande tout :** **0 pesée relue par un humain, sur 45 557.**

---

## 1. Le constat de départ

`application/curation.py` promet que les pesées doctrinales et les mises en garde « restent à
quelqu'un qui répond de ce qu'il affirme ». Elles sont **toutes** signées `ia-mistral`. Ce n'est
pas une fonctionnalité manquante, c'est une **dette** — et elle ne diminue que du travail d'un
humain nommé.

Tout l'outillage pour rendre ce travail *fini* existait, et fonctionnait :

| Outil | Ce qu'il fait | État |
| :-- | :-- | :-- |
| `scripts/urim_ecarts.py` | cinq détecteurs, une file ordonnée du plus douteux au moins (~140 unités sur 4 561) | fonctionnait |
| `urim_corpus_review` | le registre des verdicts, avec `CHECK (reviewed_by <> 'ia-mistral')` en base | fonctionnait |
| `scripts/urim_verdict.py` | poser ou retirer un verdict, en ligne de commande | fonctionnait |

Et le compteur affichait zéro. **Le relecteur est un théologien, pas un développeur** : une
commande shell avec `--ref "Apocalypse 5:5-14" --portee D4` ne sera jamais tapée par la personne
dont on a besoin. C'est le seul défaut qu'il restait à corriger, et il n'était pas dans le code.

---

## 2. Les cinq décisions

### 2.1 Où elle vit — Plateforme, jamais mobile

Aucune table `urim_corpus_*` ne porte de `church_id` : le corpus est **global**. Une curation
change ce que *toutes* les églises lisent. Un pasteur ne peut donc pas curer — **pas par
défiance, mais parce que le geste n'a pas la bonne portée**.

Les routes vivent dans `interface/platform_router.py`, sous `/api/backoffice/platform/urim/…`,
derrière le jeton de service Plateforme. Les routes de lecture y sont comprises : la file dit
l'état d'avancement d'un produit, pas une donnée publique.

### 2.2 Qui signe — le nom cesse d'être une donnée d'entrée

`verifier_verdict()` faisait déjà tout ce qu'un validateur peut faire sur une chaîne : refuser le
vide, `semis-demo`, `ia-mistral`. Il n'a **jamais pu refuser le nom de quelqu'un d'autre** — et
c'est arrivé : un verdict d'essai posé au nom du propriétaire du dépôt, qu'il a fallu retirer
(d'où l'existence de `--retirer`).

> 🔴 Le défaut n'était pas dans le garde, il était en amont : **tant que le nom est une donnée
> d'entrée, aucune vérification ne le sauve.**

D'où le registre `urim_reviewer` :

```bash
python scripts/urim_relecteur.py --enroler kouassi --nom "Kouassi Jean"
#   X-Urim-Relecteur: kouassi:<secret affiché une seule fois>
```

- le porteur prouve un secret, la surface **rend** le nom correspondant ;
- **aucune route ne lit plus de `reviewed_by` dans un corps de requête** — le champ a disparu des
  sept schémas de curation, pas seulement de la nouvelle sous-surface ;
- le secret est haché en SHA-256 nu, parce qu'il est **tiré au sort** (32 octets) et non choisi :
  il n'existe pas de dictionnaire des tirages aléatoires ;
- `display_name` est unique — c'est lui qui atterrit dans `reviewed_by`, sous les yeux du pasteur ;
- révoquer **n'efface pas la ligne** : on retire le pouvoir de signer, pas la trace d'avoir signé.

**Ce que ça garantit :** on ne signe que d'un nom **dont on détient le secret**, et ce nom se
**révoque**. **Ce que ça ne garantit pas :** que la personne soit bien celle qu'elle dit — il n'y
a pas d'identité authentifiée dans ce produit avant la console d'administration Dorea
(`Dorea_Platform_Admin.md` : comptes staff nominatifs, mot de passe + OTP, journal d'audit).
C'est un cran, pas la fin. Le jour où la console existe, **seule `exiger_relecteur` change de
source** ; les routes n'en sauront rien.

Effet de bord voulu : **plus rien de généré ne peut entrer par HTTP.** `ia-mistral` reste une
signature légitime sur le découpage littéraire, mais elle n'est écrivable que par le lot hors
ligne, qui passe par SQLAlchemy en direct. La frontière humaine et la frontière machine ne sont
plus la même porte. `scripts/urim_verdict.py` a été aligné : il demande un identifiant et un
secret, parce qu'une garantie que la surface tient et qu'un script d'à-côté contourne n'est pas
une garantie.

### 2.3 L'empreinte — calculée au moment du verdict

`judged_fingerprint` périme le verdict quand la curation jugée change : *une décision ne vaut que
sur l'objet qu'elle a regardé.* La surface la calcule sur ce que la base contient **au moment où
l'on signe**, jamais sur ce que le balayage avait vu.

### 2.4 `corrige` doit permettre de corriger — et l'ordre se garde tout seul

Le verdict seul ne répare rien. Les routes de curation existantes (`set_bearings`, `add_caveat`,
`add_context`, `set_feasibility`, `PATCH`) sont donc **branchées sur la même identité** : elles
écrivent la signature du relecteur authentifié. Aucune duplication de logique.

> ⚠️ **On corrige d'abord, on signe ensuite**, et ce n'est pas une convention.
> Signer `corrige` avant de réparer figerait la décision sur la curation fautive ; la réparation
> périmerait aussitôt cette signature, et l'unité reviendrait en file. **Le mécanisme se garde
> lui-même** — c'est pourquoi il n'y a *aucun* contrôle supplémentaire sur l'ordre des gestes.
> On aurait pu exiger qu'un `corrige` soit accompagné d'une correction : un contrôle de plus,
> contournable, et qui aurait fait porter au produit un jugement sur le travail du relecteur.

### 2.5 Le compteur — alimenté, jamais contourné

`GET /urim/relecture/compteur` rend :

| Champ | Ce qu'il dit |
| :-- | :-- |
| `unites` / `unites_signalees` / `unites_relues` | 4 561 · ~140 · **0** au premier jour |
| `lignes` / `lignes_humaines` / `part_relue` | 45 557 · **0** · 0,0 |
| `signalements` / `signalements_tranches` | la file, et ce qu'elle a perdu |
| `derniere_analyse` | ⚠️ **quand la file a été calculée** |

`lignes_humaines` compte les **signatures**, pas les verdicts : un `accepte` laisse la ligne
signée `ia-mistral`, et c'est juste — le relecteur a validé une ligne générée, il ne l'a pas
écrite. Compter les verdicts ici gonflerait le seul chiffre qui doive rester sévère.

`derniere_analyse` n'est pas décoratif : les détecteurs tournent hors ligne, et **une file dont
on ne sait pas l'âge ment**.

---

## 3. La file, matérialisée

D2 (le gabarit) mesure la fréquence d'une tournure sur **tout** le corpus : rien de global ne se
recalcule dans le temps d'une requête HTTP. Le détecteur écrit donc sa file dans
`urim_corpus_signal` :

```bash
python scripts/urim_ecarts.py --materialiser
```

- **le sens de la flèche compte** : le détecteur produit, la surface lit. Aucune route ne peut
  écrire dans cette table — faute de quoi le produit pourrait un jour se signaler lui-même comme
  relu ;
- **c'est une photographie, pas un journal** : chaque balayage remplace le contenu en bloc. Un
  signalement qu'aucun détecteur ne retrouve n'a pas à survivre à sa propre disparition ;
- ce sont les écarts **bruts** qui sont écrits ; le filtrage par verdict se fait à la lecture,
  contre l'empreinte courante — c'est ce qui fait revenir en file une unité dont les pesées ont
  été régénérées.

`verdict_couvre()` vit dans `application/curation.py` parce que **deux** lecteurs en dépendent :
le détecteur, qui décide ce qu'il remet en file, et la surface, qui décide ce qu'elle affiche.
Recopiée, la règle aurait divergé, et les deux moitiés du produit n'auraient plus dit la même
chose sur *ce qui reste à faire*.

---

## 4. Ce que la surface ne fait pas

**Elle ne trie pas à la place du relecteur.** L'ordre est la gravité posée par les détecteurs,
rien d'autre. Aucun score, aucun pré-verdict, aucun modèle. Les détecteurs signalent, ils ne
jugent pas — ils savent qu'une ligne est incohérente, formulaire, aberrante ou qu'elle cite un
texte absent du passage ; aucun ne sait si une pesée est théologiquement **juste**.

**Elle ne masque pas ce que l'IA a écrit.** `signature` sur l'unité, `signee_par` et `generee`
sur chaque ligne, `lignes_generees` sur le dossier : rien de généré ne doit se confondre avec une
relecture, pas même par inattention.

**Elle ne fait pas disparaître ce qu'on reprochait.** `accepte` n'est pas « c'est bien » : c'est
*« l'écart est réel et la curation est juste quand même »*. Apocalypse 5 porte réellement huit
loci ; le détecteur a raison de la trouver inhabituelle et tort d'en faire un défaut. Ce qui sort
de la file est l'unité, pas la trace du signalement.

---

## 5. Les routes

```
GET    /api/backoffice/platform/urim/relecture/compteur              (jeton)
GET    …/relecture/file?limite&decalage                              (jeton)
GET    …/relecture/unites/{id}                                       (jeton)
POST   …/relecture/unites/{id}/verdict                               (jeton + relecteur)
DELETE …/relecture/unites/{id}/verdict/{portee}                      (jeton + relecteur)
```

Le **dossier** rend, dans cet ordre : le passage (version `LSG`, celle contre laquelle la
curation a été écrite), la curation ligne par ligne avec ses signatures, puis les signalements.
*Juger une pesée sans lire le passage qu'elle pèse n'est pas une relecture, c'est une signature.*

Le décalage porte sur la file **brute** : une unité tranchée laisse un trou dans la page plutôt
que de décaler les suivantes. Descendre la file en sautant des entrées serait la seule façon de
manquer quelque chose sans le savoir.

---

## 6. Ce qui reste

| # | Ce qui manque | Où ça se règle |
| :-- | :-- | :-- |
| R1 | **Qui a effacé ?** `delete_pericope` exige un relecteur sans l'enregistrer. | journal d'audit de la console (dette **R6** de `Security_Audit.md`) |
| R2 | **Identité réelle** : le secret prouve la détention, pas la personne. | `Dorea_Platform_Admin.md` — `exiger_relecteur` change de source |
| R3 | **Le client.** Cette note décrit l'API ; l'écran qui la descend reste à faire (backoffice PWA). | `Backoffice_PWA.md` |
| R4 | **Le sixième détecteur** — repasser la ligne au modèle en lui demandant de la réfuter. Coûte un appel par unité suspecte. | `urim_ecarts.py` |
| R5 | **La révision `e6f708192a3b` n'a pas été posée par Alembic** sur la base de dev : celle-ci est estampillée `c7d8e9f0a1b2`, une révision d'une autre worktree, absente de cette chaîne. Les deux tables ont été créées depuis les modèles ; `alembic_version` n'a pas été touché. À réconcilier au moment de la fusion des branches. | `migrations/` |

---

## 7. Le premier balayage matérialisé — 2026-08-14

```
4 561 unités, 47 960 lignes de curation examinées
  D2 gabarit        43 lignes / 43 unités
  D3 forme interdite 6 lignes /  6 unités
  D4 aberration     89 lignes / 89 unités
  D5 citation fantôme 1 ligne /  1 unité
  → 139 unités à relire sur 4 561 (3,0 %)
```

Et le compteur, le même jour : **0 unité relue en entier**, **38 lignes humaines sur 47 960**
— soit **0,079 %**. C'est le chiffre qu'il s'agit de faire monter, et il est désormais lisible
par une route plutôt que par un script.

⚠️ **D1 n'a rien signalé** (aucune mise en garde sur un locus déclaré `absent`) et D5 une seule
fois. Ce n'est pas la preuve que le corpus est sain : c'est la mesure de ce que **ces
détecteurs-là** savent voir. Les 139 unités sont un plancher, jamais un total.

---

*Chantier livré : `application/relecture.py`, `infrastructure/persistence/relecture_repository.py`,
`interface/relecture_schemas.py`, `interface/platform_router.py`, `scripts/urim_relecteur.py`,
migration `e6f708192a3b`. 33 tests, `tests/contexts/urim/test_relecture*.py`.*
