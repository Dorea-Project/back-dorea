# Ce qui reste à écrire dans `back-dorea`

**Établi le 27 août 2026**, contre l'état réel des deux dépôts. Côté `urim`,
l'application est verte — 375 tests, analyse à zéro — et **tout ce qui reste est
côté serveur**.

Cinq chantiers, par coût croissant. Chacun porte ce qu'on écrit, ce qui est
interdit, le test qui le prouve, et le piège qui l'attend.

---

## 1. D57 — l'archivage ferme la préparation

**Une demi-heure.** Elle achève le sprint 6, dont toute la moitié application
est livrée.

### Pourquoi

« J'ai prêché celle-ci » écrit une ligne d'archive et laisse la préparation
`ouverte`. Le pasteur doit donc faire **deux gestes pour une seule réalité** :
dire qu'il a prêché, puis dire qu'il a terminé. Le fil montre « en cours » un
travail déjà en chaire.

### Ce qu'on écrit

`app/contexts/urim/application/archive_service.py`, dans `record_from_study`,
juste avant `reference = self._passage(record)` :

```python
if record.author_id == actor_account_id and record.status == "ouverte":
    record.status = "close"
    record.closed_at = self.clock()
    await self.studies.save(record)
```

### ⚠️ Le piège, et il n'est pas visible

Cette route appelle **`ensure_may_read`**, pas `ensure_may_prepare`. C'est
voulu : deux pasteurs d'une même église se relisent, et le second qui prêche
enregistre **sa** prédication — *« l'archive est celle de qui archive, c'est lui
qui est monté en chaire »*.

Fermer sans la garde `author_id == actor_account_id` clôturerait donc le travail
de l'auteur **parce qu'un confrère l'a prêché**. C'est exactement le dommage que
ce service existe pour empêcher : *« rien ne peut salir l'archive de quelqu'un
d'autre »*.

Et seulement depuis `ouverte` : une préparation **rangée** reste rangée, une
close l'est déjà.

### Le test qui compte

> *Un lecteur qui archive ne ferme pas la préparation de l'auteur.*

Sans lui, la garde disparaîtra au premier remaniement, et personne ne le verra —
la fermeture d'une préparation ne lève aucune erreur.

---

## 2. Sprint 4 — le bloc `trace`

**Le raisonnement à l'écran.** L'application a déjà tout, sauf la donnée.

### Pourquoi

`blockTrace` — « Comment j'en suis arrivé là » — est écrit dans les libellés de
l'application et **n'est utilisé nulle part** : le serveur ne sert aucun bloc de
ce type. Le pasteur voit ce qu'Urim conclut, jamais par où il est passé.

Sept `kind` existent dans `turn.py` : `chips`, `units`, `bounds`, `bearings`,
`feasibility`, `theme`, `actions`.

### Ce qu'on écrit

Un huitième, additif — rien de ce qui existe ne change :

```python
class TraceBlock(BaseModel):
    kind: Literal["trace"] = "trace"
    #: Les étages traversés, dans l'ordre où le pipeline les a joués.
    stages: list[TraceStageView]
```

Chaque étage porte son code, ce qu'il a **pesé**, et ce qu'il a **écarté avec
son motif**. La matière existe déjà : le pipeline la calcule pour décider, et la
jette.

### ⚠️ Interdits

- Le bloc **voyage replié**. L'application a `FoldedSection` pour ça (D43), et
  le décor déplié à chaque tour est ce que D42 a corrigé — onze écrans devenus
  trois.
- **Les écartés voyagent avec leurs motifs**, comme les couples refusés : les
  cacher laisserait croire qu'on n'y a pas pensé.
- Rien d'inventé. Un étage qui n'a rien pesé ne rend pas une phrase pour
  meubler.

### Le test

> *Un tour rend les étages dans l'ordre du pipeline, et chaque écarté porte son
> motif.*

---

## 3. Sprint 4 — `theme_label`, sans toucher au gabarit

**Petit, et le piège est le plus dangereux du lot.**

### Pourquoi

Le thème s'affiche `theologie_propre, en textuel doctrinal`. C'est du
vocabulaire de schéma, montré à un prédicateur.

### 🔴 Ce qu'il ne faut surtout pas faire

Rendre le gabarit lisible. `propose_theme.theme_propose()` compose
`f"{axis}{forme}"` **et son propre docstring dit pourquoi il est ainsi** :

> *« Le gabarit étant déterministe, comparer le thème enregistré à ce qu'il
> rendrait dit si le pasteur l'a réécrit ou s'il a laissé la proposition. »*

C'est une **empreinte**. La changer fait cesser de correspondre **tous les
thèmes déjà en base**, et le système conclut que chaque pasteur a réécrit le
sien. La régression est **silencieuse** : rien ne lève, une phrase du moteur
passe pour une phrase d'homme.

### Ce qu'on écrit

Un champ **en plus** sur `StudyView` :

```python
theme: str | None          # inchangé — l'empreinte
theme_label: str | None    # les libellés humains, pour l'écran
```

`urim_corpus_doctrinal_axis` porte déjà `code` **et** `label`. À vérifier avant
de coder : d'où viennent les libellés de `plan_source` et `subject_matter` —
« textuel », « doctrinal » — car ils ne sont pas dans cette table.

### Le test

> *Réécrire le libellé ne change pas l'empreinte : `theme` reste identique
> pendant que `theme_label` devient lisible.*

---

## 4. D55 — le plan rédigé

**Deux à trois jours, et c'est le seul qui change le produit.**

### Pourquoi

Le fondateur l'a vu sur un téléphone : *« il ne faut pas donner du boulot en
supplément »*. L'étage 6 propose trois couples `plan × matière` avec, pour tout
motif, un niveau de risque — « faible », « moyen », « élevé ». Trois défauts :

- **du vocabulaire d'exégète**, pas de prédicateur : un pasteur ne choisit pas
  entre « textuel » et « thématique », il veut un plan ;
- **un adjectif sans motif** : les couples **écartés** sont argumentés — *« l'unité
  ne met en scène aucun personnage : Nicodème a quitté le dialogue »* — les
  couples **retenus** ne le sont pas. On explique pourquoi on refuse, jamais
  pourquoi on accepte ;
- **le travail reporté** sur le pasteur au moment où il vient chercher de l'aide.

### Ce qu'on écrit

Dans `engine/stages/shape_homiletic.py`, où `execute` rend aujourd'hui
`options=tuple(_option(couple, …) for couple in faisables)` :

1. **Trancher** — retenir le faisable au risque le plus bas au lieu de les
   offrir.
2. **Dire pourquoi** — `_motif_du_risque` existe et compose déjà la phrase. Elle
   passe du décor à l'**obligation**.
3. **Rédiger** — déplacer `PlanSuggestion(body, transition, model)` en amont,
   appelée sur le couple retenu, pour produire les points.
4. **Changer la question** — de « Lequel voulez-vous suivre ? » à « Vous changez
   quoi ? ». Les couples refusés continuent de voyager avec leur motif.

### ⚠️ Interdits

- **Un plan rédigé sans son motif est un oracle.** Le filet doré existe pour
  l'empêcher : *« chaque réponse porte son filet doré ; c'est ce qui sépare un
  atelier d'un oracle »*. Trancher sans dire pourquoi trahit cette règle plus
  gravement que l'ancien écran.
- Le moteur **n'écrit jamais une division** à la place du pasteur. Il propose
  des points ; c'est un geste explicite qui les reprend, comme les articulations
  (verrou du 22/08).

### ⚠️ Le piège de coordination

Cet étage a un jumeau côté application : **le décor cliquable**. Les pastilles
d'axes portent `decide_stage: "bear_axes"` et restent touchables pendant qu'un
autre étage pose sa question. Toucher un axe poste sur un étage déjà tranché, le
pipeline rejoue, et la même question revient — *c'est le défaut que le fondateur
a signalé.*

**Le moteur et l'écran partent ensemble**, sinon on remplace un défaut par le
même.

### Le test

> *Le tour rend un plan rédigé, son motif, et une seule question.*
> *Aucun plan retenu ne sort sans motif.*

---

## 5. Sprint 7 — la route de capture et son travailleur

**Le plus gros, et l'application l'attend déjà.**

### Ce que le client envoie

L'étage 1 est livré côté appareil. Le contrat qu'il attend :

```dart
Future<bool> send({
  required String captureId,
  required int index,
  required List<int> bytes,
});
```

- Des fragments **PCM 16 kHz mono, 30 s**, soit 960 000 octets pleins ; le
  dernier est plus court.
- Numérotés, envoyés **dans l'ordre**, à partir d'une marque haute conservée sur
  l'appareil.
- Un `false` arrête la file sans sauter le fragment ; le passage suivant
  reprend là.

### Ce qu'on écrit

- `POST /urim/captures/{capture_id}/fragments/{index}` — les octets, et un
  accusé.
- Un travailleur qui consomme `CaptureJob`. Le domaine modélise déjà le retry et
  le backoff ; **personne ne les exécute**.
- `JobKind.TRANSCRIRE` **change de sens** : le transcript se fabrique sur
  l'appareil (D52). Le travail serveur devient *recevoir* un transcript, non le
  produire.

### ⚠️ Interdits

- **La capture n'est jamais refusée.** Plafond atteint, l'enregistrement a lieu
  quand même — c'est la transcription qui est différée. La route ne rend donc
  jamais un refus qui ferait perdre un fragment.
- **Le même fragment peut arriver deux fois.** La marque haute s'écrit *après*
  l'accusé : une application tuée entre les deux renverra le dernier. Le serveur
  doit l'absorber — *il sait absorber un doublon, il ne sait pas deviner un
  trou* (I24).
- **Un travail abandonné laisse le transcript en `partielle`, jamais un
  silence.**

### La décision à porter dans la route

**D56 — l'audio ne monte que pendant la campagne de mesure.** Avec le transcript
fabriqué sur le téléphone, l'audio n'a plus de raison technique de partir ; la
seule qui reste est de comparer à une référence humaine, et elle est datée. La
route doit donc être **explicitement activable**, et se couper quand le verdict
tombe — sinon on la gardera par inertie, et elle coûtera des mégaoctets sur
chaque forfait.

---

## Ce qui n'entre dans aucun de ces cinq

**La migration `a1c7d3e50b94`** — titre et rangement — n'est pas appliquée. La
base a **23 divergences préexistantes** avec les modèles et **sept têtes
Alembic** ; `alembic upgrade heads` appliquerait bien plus que ce changement.
C'est un appel du fondateur, pas une tâche.

**`capture/quality.py` n'existe pas.** La spec *T-Rec v1.1* le déclare
« implémenté et testé, 12 tests verts » ; vérification faite le 26/08, il n'est
ni dans l'arbre, ni dans un commit, ni sur aucune des trente branches.
L'en-tête est à corriger. Le module lui-même appartient au sprint 9, après la
mesure — et deux choses manquent à sa spec : **le relecteur ne peut pas être
celui qui a prêché** (il lit à travers les erreurs, il sait ce qu'il a dit), et
**l'avis doit s'ancrer sur des fragments identifiés**, sinon il ne se rejoue pas
plus fin qu'un culte entier.

**Des modifications non commitées du fondateur** vivent dans `back-dorea` —
`mistral.py`, `engine/*`, `conversation.py`. Le titre, le rangement et la
migration viennent de la session du 26. Il faudra trier avant de commiter.
