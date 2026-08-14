# Urim — la ligne d'arrivée

*Écrit le 14/08/2026, après une journée où douze commits sont partis et où la liste des dettes
n'a pas bougé d'une ligne.*

---

## 1. Pourquoi ce document existe

Urim s'améliore sans fin, et chaque amélioration se défend. L'hébreu manquait : il est semé.
Les mises en garde étaient vides : elles couvrent 96 % du corpus. Les traductions divergent :
un détecteur le montre. Un modèle se trompe : un contre-interrogatoire le reprend.

**Rien de tout cela ne dit qu'un pasteur peut s'en servir.**

Un produit sans minimum défini ne sort jamais, quelle que soit la qualité de chaque journée. Ce
document trace la ligne. Ce qui est dedans se finit ; ce qui est dehors attend, **et être
dehors ne veut pas dire mauvais** — la plupart des choses écartées ici sont bonnes, et
certaines sont déjà écrites.

---

## 2. Le critère, en une phrase vérifiable

> **Un pasteur d'une assemblée réelle crée son compte, prépare une prédication sur un texte
> qu'il choisit, repart avec un document, et paie.**
>
> **Et Urim lui dit honnêtement ce qui a été relu et ce qui ne l'a pas été.**

Tant que cette phrase est fausse, v1 n'est pas là. Quand elle est vraie, v1 est là — **même si
tout le reste de ce dépôt reste imparfait.**

---

## 3. Ce que v1 fait, et c'est presque tout construit

| | État |
| :-- | :--: |
| Ouvrir une préparation **sans église** — l'antichambre, rôle Dorea `null` | ✅ |
| Écrire n'importe quoi : référence, citation, conviction — sans onglet à choisir | ✅ |
| Lire la notation du pasteur : `Hb 2v29`, `Jn14v28`, `Eph 1v20-22` | ✅ |
| Proposer des passages quand la lettre ne trouve rien — plusieurs, jamais un | ✅ |
| Négocier les bornes : l'unité relue contre celles du pasteur | ✅ |
| Servir le texte, ses **mots d'origine** — grec et hébreu, 99,5 % de l'Écriture | ✅ |
| Peser les dix loci, y compris ce qui **résiste** | ✅ |
| Dire ce que le texte **ne dit pas** — les mises en garde | ✅ |
| Rendre les couples plan × matière, refusés compris | ✅ |
| Proposer un **thème**, jamais un titre | ✅ |
| Rendre chaque tour avec son motif — `turn`, sept blocs | ✅ |
| Écarter une option sans la perdre | ✅ |
| Ne jamais opposer un mur : `Null*`, dégradation, quota | ✅ |
| **Répondre à une question libre en cours de préparation** | ⏳ en vol |
| **Repartir avec un document** | ❌ |

---

## 4. Les quatre choses qui restent, dans l'ordre

### 4.1 — Les lacunes du noyau

`reset-secret-code`, `delete-account`, `devices`.

**Elles bloquent la publication sur les stores**, et personne ne les a jamais regardées. Ce
n'est pas d'Urim qu'il s'agit, c'est du compte : un utilisateur doit pouvoir récupérer son
accès et effacer ses données. Aucune boutique n'accepte une application qui ne le permet pas.

*C'est le premier travail, et c'est celui dont on a le moins parlé.*

### 4.2 — L'aiguilleur branché

La liaison est écrite, les deux répondeurs aussi, le tour part sur les sept routes. Il manque
le fil qui appelle l'aiguilleur quand la liaison rend la main. **Sans lui, la conversation
s'arrête au premier texte libre** que le pasteur écrit après l'ouverture.

*Chantier en vol.*

### 4.3 — Le livrable

Un `.docx` et un `.pptx`, **après validation et modification par le pasteur**. Un document
qu'on télécharge et qu'on lit en chaire tel quel ferait d'Urim une machine à sermons, ce que
toute sa conception refuse.

Le verrou actuel est délibéré : le livrable reste fermé tant qu'une citation projetée n'est pas
contrôlée. **Lever ce verrou fait partie de v1** — sans lui, le pasteur travaille et ne repart
avec rien.

*Note de conception en vol.*

### 4.4 — Le cycle de facturation

`business_accounts` n'a **aucun cycle**. Rien n'est encaissable aujourd'hui. Le quota est à 500
au lieu de 3 précisément parce qu'aucune sortie ne fonctionne.

---

## 5. Ce qui est dehors — et pourquoi ce n'est pas un reproche

| | Pourquoi dehors |
| :-- | :-- |
| La surface du relecteur | rend la relecture possible, ne livre rien au pasteur |
| Les collisions entre traductions | belle trouvaille, aucun pasteur ne l'attend |
| Les notes de contexte | 0,1 %, et un lot IA n'y est peut-être pas légitime |
| Le contre-interrogatoire, la file d'écarts | outils internes, pas du produit |
| La transcription audio | le vrai poste de coût, et rien ne le finance encore |
| Le choix de version par le pasteur | les quatre traductions servent le détecteur, pas l'écran |
| Le plafond d'église, l'abonnement de tenant | rien à plafonner tant que rien n'est facturé |

**Aucune de ces lignes n'est mauvaise.** Plusieurs sont déjà écrites et testées. Elles
attendent v2, et elles attendront mieux dans un produit qui vit que dans un dépôt qui grossit.

---

## 6. Les dettes qu'on assume, et ce qu'on en dit

Livrer avec des dettes connues est légitime **à condition de les nommer**. Voici ce qu'on
affiche.

**Aucune pesée n'a été relue par un humain — 0 sur 45 557.** La signature `ia-mistral` est
portée jusqu'à l'écran du pasteur, et la feuille qu'on lui donne le dit en toutes lettres :
*« ces notes ont été préparées avec l'aide d'une machine, et elles n'ont pas encore été relues
par un théologien. »*

C'est ce qui distingue Urim d'un outil qui répond à tout avec assurance. **Un pasteur à qui
l'on dit d'où vient chaque chose, et ce que personne n'a vérifié, fait plus confiance, pas
moins.**

**Les mises en garde confessionnelles sont quasi absentes** — 2 sur 2 392. Le modèle a refusé
la catégorie, et ce refus est juste : une machine ne doit pas arbitrer entre traditions.

**Les notes de contexte sont à 0,1 %.** Le champ existe, il est presque toujours vide, et le
contrat le dit plutôt que de le masquer.

---

## 7. Ce qu'on ne fait plus jusqu'à v1

Une règle, et elle vaut pour moi autant que pour quiconque :

> **Aucune dimension de corpus nouvelle. Aucun détecteur nouveau. Aucune traduction nouvelle.
> Aucun instrument nouveau.**

Ce qui est en vol se termine. On n'ouvre rien d'autre.

Une exception, une seule : **un défaut qui rendrait faux ce qu'un pasteur lit**. Celui-là se
répare toujours, immédiatement, parce que le corpus est le nerf du projet et qu'une ligne
fausse en chaire coûte plus que trois semaines de retard.

---

## 8. Comment on saura

La phrase du §2, éprouvée sur une personne réelle : **le Pasteur X prépare une prédication de
bout en bout, sur un texte qu'il choisit lui-même, et repart avec son document.**

Pas une démonstration. Pas un scénario écrit d'avance. Ses mots à lui — ceux qui ont déjà
appris à ce produit tout ce qu'il sait :

> *« Dieu est l'auteur et le consommateur de notre foi, sur l'autel Divin »*
> *« l'amour fraternel n'existe plus dans l'eglise »*
> *« les esclaves hebreux ne portaient pas de chaussures »*
> *« Hb 2v29 »*

S'il va au bout, v1 est là.
