# S-6 — La transcription audio : la dictée et le dimanche (note de conception)

**2026-08-13** — dernier pilier non livré du Compagnon (`docs/Sermon_Companion.md`, S-0→S-5 livrés)
et porte d'entrée vocale d'Urim.
**Statut :** note de conception. **Aucune ligne de code applicatif.** Ce qu'elle appelle à
construire est nommé au §9, et elle s'arrête là.

> ⚠️ **§2.2bis et §5.3 ont été réécrits le jour même**, sur relevé des poids ouverts. La première
> version de cette note disait *« Dorea transcrit le français ; on ne promet pas le dioula »* — et
> c'était vrai quand la spec de capture a été écrite. Ça ne l'est plus : **le dioula et le baoulé
> sont couverts, sous licence Apache 2.0.** La conclusion économique du §2.2 s'en trouve renversée
> à l'échelle. C'est laissé visible plutôt que réécrit en silence : *la mesure tranche, l'opinion
> précédente ne se cache pas.*

> Deux usages partagent un microphone et rien d'autre. L'un coûte des secondes, l'autre des heures.
> Les concevoir ensemble sans le dire, c'est facturer le second au tarif du premier — ou refuser
> le premier au motif du second.

⚠️ **Prémisse à vérifier avant de lire le reste.** Cette note est demandée sous le nom « S-6, le
dernier pilier du Compagnon ». Or `docs/Plan_Urim_Producteur.md` (05/08/2026) **décide le retrait
du contexte `sermon`**, révoque **D-B / S32**, et note en une ligne ce que le §8 développe :
*« S-6 et `urim/capture` étaient le même travail »*. Le contexte `sermon` **existe toujours**
(R0→R4 non démarrés). Les décisions D1→D14 ci-dessous sont **indépendantes de cet arbitrage** —
elles portent sur l'argent, le port, l'audio, la langue et la relecture, qui ne changent pas selon
le contexte qui héberge le transcripteur. **Seul le §8 en dépend**, et il ne recommande pas de
construire S-6 là où il est aujourd'hui.

---

## 1. Deux usages, deux produits

| | **Dictée** (préparation, `urim`) | **Dépôt du culte** (`sermon`, S-6) |
| :-- | :-- | :-- |
| Ce que c'est | *« je veux prêcher sur le pardon mais l'assemblée est dure »* | l'enregistrement de la prédication |
| Durée | 10 à 40 secondes | **30 à 60 minutes** |
| Ce que ça remplace | un champ de saisie sur une tablette, un vendredi soir | rien — c'est un usage neuf |
| Ce que ça alimente | le détecteur d'entrée (étage 0), **exactement comme du texte tapé** | la digestion S-1 → capsules → compagnon |
| Si ça échoue | le pasteur tape | le pasteur colle son texte (S-0) ou dépose un PDF (S-5) |
| Confidentialité | **privée** — c'est une intention, pas une parole publique | parole publique… *prononcée dans une salle qui contient d'autres voix* |
| Coût par acte | ≈ celui d'une ouverture d'étude | **100 à 700 fois** une ouverture d'étude |

**Ce que le dépôt sait déjà faire, et qu'il faut ne pas redécouvrir :**

- côté Urim, `EntryOrigin.DICTATED` **existe** (`engine/state.py`), l'étage 0 s'en sert (S36 : une
  dictée non univoque **se fait confirmer** avec ce qui a été entendu rendu tel quel), et
  `interface/schemas.py` l'expose déjà sur la route d'ouverture. **Aucun appelant ne le pose
  jamais** — parce que rien ne produit de dictée ;
- côté Sermon, S-5 a posé le port unique `SermonTextExtractor` et `source_kind` accepte déjà
  `audio` ; l'extracteur rend `UnsupportedSermonFormatError` sur ce format, en attendant S-6.

> Le chantier n'est donc pas *« ajouter la voix »*. Il est **de brancher une source de texte sur
> deux contrats qui l'attendent** — et de décider ce que ça coûte avant de le brancher.

---

## 2. Le modèle économique — d'abord, parce qu'il décide de la technique

### 2.1 L'étalon existe, et il a été mesuré

`da4d2ef` (11/08/2026), sur les saisies réelles du Pasteur X, `mistral-small`, instrumenté par
invite (`urim_mistral_usage`) :

| Acte | Coût |
| :-- | --: |
| Ouverture en **conviction** (3 appels : axes · risque · passages) | **0,050 ¢** |
| Ouverture en **référence** (1 appel) | 0,007 ¢ |
| 10 000 pasteurs × 20 ouvertures/mois | **≈ 92 €/mois** |

Conclusion tirée alors, et qui tient : *« il n'y a rien à rationner ; la réputation perdue à faire
sentir une limite coûterait davantage que les 92 € qu'elle économise. »*

⚠️ **Le message de ce commit avait déjà nommé le poste suivant** : *« la dépense à venir est la
capture audio (…). `urim_usage_window` a été bâti pour la bonne raison et braqué sur la mauvaise
ressource. Sa cible réelle est l'audio du dimanche — côté église, donc côté payant. Le texte reste
gratuit. »* **La présente note ne décide pas cette dégradation : elle la chiffre.**

### 2.2 Ce que coûte une heure d'audio

⚠️ **Tarifs en dur et datés (août 2026), non lisibles par l'API — à revérifier sur les pages de
facturation avant d'en refonder une décision.** C'est la discipline que
`scripts/urim_mesure_cout.py` s'impose déjà à lui-même ; elle vaut ici davantage encore, les
tarifs STT ayant baissé d'un facteur dix en deux ans.

| Voie | Tarif | € / heure d'audio | Remarque |
| :-- | :-- | --: | :-- |
| **API « historique »** (Whisper `whisper-1`) | $0,006 / min | **0,33 €** | la référence de qualité, la plus chère |
| **API récente** (classe *Voxtral-mini-transcribe*, Deepgram *Nova*) | $0,001 à 0,0043 / min | **0,05 à 0,24 €** | même famille de modèles, tarifs de 2026 |
| **Cloud généraliste** (Google / Azure STT) | ≈ $1,00 à 1,44 / h | 0,92 à 1,32 € | **hors sujet** : trois fois le prix du plus cher |
| **Poids ouverts, auto-hébergés** | 400 à 1 100 €/mois **par GPU** | voir ci-dessous | licence permissive, **aucun octet ne sort** |

**Les poids ouverts changent l'arithmétique, et pas qu'un peu** (§2.2bis). Ce n'est plus un GPU
contre un tarif : c'est un GPU contre un tarif **et une capacité qui dépend de l'architecture du
décodeur** :

| Modèle auto-hébergé | Facteur temps réel | Capacité / GPU | Ce qu'il faut pour 10 000 églises (43 300 h/mois) |
| :-- | --: | --: | :-- |
| `omniASR-CTC-7B` (~15 GiB) | RTF 0,006 ≈ **167×** | ≈ 120 000 h/mois | **un seul GPU**, utilisé à 36 % |
| `omniASR-LLM-7B` (~17 GiB) | RTF 0,092 ≈ **11×** | ≈ 7 800 h/mois | ≈ 6 GPU |

**Le seuil de bascule, exprimé en heures d'audio** — il ne dépend d'aucun tarif de GPU, seulement
du coût fixe rapporté au prix de l'API. Une église type consomme 4,33 h/mois (un culte de 60 min
par semaine) :

```
un GPU (400 à 1 100 €/mois)  vs  API chère (0,33 €/h)      →  1 200 à  3 300 h/mois  =   280 à   770 églises
un GPU (400 à 1 100 €/mois)  vs  API bon marché (0,055 €/h) →  7 300 à 20 000 h/mois  = 1 680 à 4 600 églises
```

> **Verdict inchangé au pilote, renversé à l'échelle.** En dessous de ~300 églises, auto-héberger
> revient à payer un GPU pour en économiser dix euros — **l'API, et le port qui rend la bascule
> gratuite** (**D5**). Mais au-delà, la bascule n'est plus un compromis : avec un décodeur CTC,
> **un GPU couvre les dix mille églises** et le coût marginal de la onze-millième est nul. ⚠️ Un
> GPU reste exactement l'infrastructure que l'architecture de la capture refuse par écrit
> (*« aucune infrastructure nouvelle. Ni Redis, ni RabbitMQ »*) — c'est une décision d'exploitation
> à prendre les yeux ouverts, pas un détail de déploiement.

⚠️ **Les RTF ci-dessus sont ceux des fiches de modèle** — mesurés sur A100, BF16, lot de 1, audio
de 30 s. Le lot améliore, un GPU moins cher dégrade. **À remesurer sur la machine retenue**, comme
les tarifs.

### 2.2bis — Ce que les poids ouverts changent (relevé le 13/08/2026)

Trois faits, et le troisième est le plus important pour Dorea :

1. **La licence n'est plus un obstacle.** `Omnilingual ASR` (Meta, nov. 2025) est publié en
   **Apache 2.0**, modèles *et* code — pas de clause non-commerciale, contrairement à ce que
   traînaient MMS et SeamlessM4T. Whisper est MIT, `Voxtral Mini Realtime` (Mistral, fév. 2026)
   Apache 2.0, `Parakeet` CC-BY-4.0 (attribution requise). **Rien à négocier avec personne** ;
2. **la famille est graduée** — de 300 M (≈ 5 GiB de VRAM, pour l'appareil ou la dictée) à 7 B
   (≈ 15-17 GiB, pour le culte) — donc le même choix de modèle sert les deux usages du §1 ;
3. **et surtout : les langues locales sont dedans.** Voir §5, qui s'en trouve entièrement réécrit.

> **Conséquence sur Q1 (souveraineté) : la réponse n'est plus « payer plus ».** Elle est « payer
> un GPU » — et à partir de quelques centaines d'églises, ce GPU est de toute façon moins cher que
> l'API. **L'option souveraine et l'option économique cessent d'être en conflit.**

### 2.3 Par église et par mois — la seule échelle qui décide

| | Par culte | Par église / mois | **En part de l'offre Standard** (12 500 FCFA ≈ 19,06 €) | 10 000 églises |
| :-- | --: | --: | --: | --: |
| API chère | 0,33 € | 1,43 € (941 FCFA) | **7,5 %** | 14 335 €/mois |
| API bon marché | 0,055 € | 0,24 € (156 FCFA) | **1,3 %** | 2 382 €/mois |
| Auto-hébergé (CTC) | — | ≈ 0,04 à 0,11 € | 0,2 à 0,6 % | **400 à 1 100 €/mois — un seul GPU** |

Deux mises en regard qui valent mieux qu'un discours :

- **la transcription coûte ≈ 100 fois sa propre digestion.** Digérer un transcript de 60 min
  (≈ 13 000 jetons d'entrée) en un appel `mistral-small` : **0,35 ¢**. Le transcrire : 6 à 36 ¢.
  *Le texte n'a jamais été le poste. L'audio l'est en entier ;*
- **S-6 ne change pas la classe de coût du Compagnon, il en change le coefficient.** S-1 a gravé
  `O(sermons)`, jamais `O(membres × interactions)` — c'est toujours vrai. Mais le coefficient
  passe de *quelques centimes par semaine et par église* à **environ six cents fois ça**.

> **Le rapport à l'étalon, honnêtement :** **entre 120 et 720 fois par acte** (deux à trois ordres
> de grandeur, comme pressenti), mais seulement **entre 26 et 156 fois par mois et par église** —
> parce qu'un pasteur ouvre vingt préparations et ne prêche que quatre fois. Les deux chiffres sont
> vrais ; c'est le second qui décide, puisque c'est lui qu'on facture.

### 2.4 La dictée ne coûte rien — **si on ne la construit pas côté serveur**

C'est la trouvaille de cette note, et elle est déjà à moitié dans le dépôt.

`entry_origin` est un **champ de la requête d'ouverture**. Le client peut donc poster du texte en
déclarant qu'il vient d'un micro — et l'étage 0 fait déjà tout ce qu'il faut de cette provenance
(S36). **La dictée de préparation ne demande aucun octet d'audio sur le serveur** : la reconnaissance
du clavier Android / iOS / Web Speech la produit sur l'appareil, gratuitement.

⚠️ **Vérifié le 13/08, et c'est plus complet que « le champ existe »** : la chaîne est entière,
route → service → base → rejeu. `mobile_router.py:54` et `:249` passent `payload.entry_origin` au
service, qui le **persiste** (`study_service.py:336`) et le **relit** à la reprise (`:978`, défaut
`TYPED`). Une préparation ouverte à la voix rouvre donc à la voix, et la confirmation S36 se
redéclenche à l'identique — **la provenance survit au rejeu**, ce qui est exactement ce qu'un moteur
déterministe exige d'elle. Côté serveur, il n'y a **rien à écrire**.

| Voie | Coût par dictée de 30 s | 10 000 pasteurs × 10 dictées/mois | Effet sur la facture texte (92 €) |
| :-- | --: | --: | :-- |
| **Sur l'appareil** (clavier du système) | **0 ¢** | **0 €** | aucun |
| API bon marché | 0,05 ¢ | 46 €/mois | +50 % |
| API chère | 0,30 ¢ | 276 €/mois | **×4** |

⚠️ **Deux réserves à ne pas taire.** La dictée du système exige les services Google sur Android et
**envoie l'audio chez Google** — la question de souveraineté (**Q1**) n'est pas résolue, elle est
déplacée et sa facture passe à quelqu'un d'autre. Et sur la tablette de référence de la spec de
capture (IDINO NOTEBOOK-10, Android 8.1), la disponibilité hors ligne est incertaine.

> ✅ **D1 — la dictée se fait sur l'appareil par défaut ; le transcripteur serveur est le *repli*
> du repli.** Même s'il sert dans tous les cas, il reste dans la bande *« erreur d'arrondi »* :
> 46 à 276 €/mois à dix mille pasteurs, contre 92 € pour tout le texte. **Rien à rationner ici non
> plus.** La dictée est **gratuite pour le pasteur**, quel que soit le chemin.

### 2.5 Le dimanche — ce que le coût impose, et à partir de quand

Il ne se dégrade pas aujourd'hui, et c'est ce qu'il faut dire :

- **au pilote** (une poignée d'églises) : 5 églises × 1,43 € = **7 €/mois** au tarif le plus cher.
  Le débat n'existe pas ;
- **le blocage n'est pas le prix unitaire, c'est l'absence de recette en face.** 7,5 % de l'offre
  Standard est parfaitement absorbable — mais `docs/Tenant_Subscription.md` est une **note de
  design non implémentée**. Aujourd'hui, chaque culte transcrit est une dépense sans contrepartie.

> ✅ **D2 — la transcription du culte est un service de l'abonnement d'ÉGLISE, pas du palier
> gratuit.** Le texte reste gratuit et généreux (position acquise le 11/08) ; l'audio du dimanche
> est le premier service qui a une facture à l'unité, et il rejoint le tenant qui la paie.
> **Ce n'est pas le compte Business d'une personne** (`docs/Business_Account.md`, qui ouvre les
> portées d'Event) : le culte appartient à l'église.

> ✅ **D3 — jusqu'à ce que l'abonnement existe, S-6 s'ouvre par configuration, église par église.**
> Un drapeau et une liste, comme `push_provider_url` ou `mistral_api_key` ouvrent leurs services.
> À l'échelle du pilote, la dépense est une erreur d'arrondi ; à l'échelle de mille églises sans
> abonnement, c'est **14 000 €/mois pour un produit gratuit**, et personne ne l'aurait décidé.

> ✅ **D4 — le plafond a déjà sa table, et elle a déjà été braquée sur la mauvaise ressource.**
> `urim_usage_window` (mutualisé par église, `metered_units < ceiling` atomique) **est lu et n'a
> jamais été écrit** — ⚠️ vérifié le 13/08 : le seul usage dans tout le code est un `select`
> (`study_repository.py:484`), **aucun `INSERT`, aucun `UPDATE`**. Il n'y a donc jamais de ligne, et
> le chemin réellement emprunté est le repli — `row is None → ceiling_reached=False`, commenté
> *« l'absence de configuration ne doit jamais dégrader le service »*. **Le plafond d'église n'est
> pas mal réglé : il n'existe pas.** Sa cible réelle est ici. **L'unité est la
> capture, pas la minute** : le pasteur comprend « quatre cultes par mois », pas « 240 minutes ».
> Et la règle de la spec de capture ne bouge pas — **plafond atteint, l'enregistrement a lieu
> quand même, la transcription est différée** (`transcription_deferred`), *« ce qui n'est pas
> capté dimanche est perdu pour toujours ; un transcript peut attendre lundi »*.

---

## 3. Le port, et son adaptateur nul

Patron tenu quatre fois — `OtpSender`, `PushSender`, `MistralSermonDigester`/`KeywordSermonDigester`,
`build_verse_resolver` : **un port, un adaptateur réel qui s'active par configuration, un repli sûr
qui ne casse rien.**

### 3.1 Un seul port, et il existe déjà sur le papier

`Dorea_Urim_Architecture_Transcription.md` §4 définit `TranscriptionPort.transcribe(chunks,
language_hints) -> TranscriptResult` (segments texte + ms + confiance, `provider`, `model_ref`).

> ✅ **D5 — c'est ce port-là, sous le nom de `Transcriber`, et il n'y en a pas deux.** Les trois
> usages — dictée de quelques secondes, fichier déposé, fragments captés en direct — diffèrent par
> la *forme de l'entrée*, pas par le contrat. **Le ré-assemblage des fragments appartient au module
> de capture**, pas au port : on lui passe un bloc ou une séquence, il rend des segments.
>
> ⚠️ **Un seul port, quel que soit le contexte qui l'héberge** (§8). Là où un dépôt de fichier
> existe, le transcripteur est **le maillon amont d'une chaîne d'extraction déjà bâtie** — le patron
> de S-5, où PDF et PPTX sont des adaptateurs derrière un port unique et où *l'IA ne voit que du
> texte*. Ce patron survit au retrait de `sermon` : il décrit une extraction, pas un contexte.

`provider` et `model_ref` sont **stockés par transcript**, pas journalisés : sans eux, on ne saura
jamais pourquoi certains dimanches sont mauvais. Même raison que `model` sur `urim_model_suggestion`.

### 3.2 `NullTranscriber` — et **deux règles opposées** selon ce qui est perdu

Une panne de transcription n'est **jamais** une panne d'Urim ni du dépôt de sermon. Mais la bonne
manière d'échouer n'est pas la même des deux côtés, et les confondre serait une faute :

| Situation | Comportement | Pourquoi |
| :-- | :-- | :-- |
| **Dictée**, pas de transcripteur | le bouton micro **n'est pas offert** ; le champ texte est là, il l'a toujours été | S12 : *« le sélecteur n'est pas un écran de secours, c'est l'écran de base »*. Rien à construire pour le cas dégradé |
| **Dépôt d'un fichier audio**, pas de transcripteur / quota épuisé | ⛔ **refus franc et immédiat**, avant tout octet stocké : *« le dépôt audio n'est pas disponible ; collez votre texte ou déposez un PDF »* | **le fichier est encore sur son téléphone.** Il n'y a rien à sauver, et accepter un dépôt qu'on ne saura pas traiter, c'est promettre |
| **Capture en direct d'un culte** (`urim/capture`, à venir) | ✅ **jamais de refus** — on enregistre, on diffère | *« ce qui n'est pas capté dimanche est perdu pour toujours »* |

> ✅ **D6 — la règle « on ne refuse jamais » porte sur l'IRRÉVERSIBLE, pas sur l'audio.**
> C'est la distinction que S-6 doit tenir : un culte en train de se dérouler ne se rejoue pas, un
> fichier déposé se redépose. Les traiter pareil ferait stocker des heures d'audio qu'on ne saura
> peut-être jamais transcrire — un coût, un risque de confidentialité, et une attente déçue.

---

## 4. Le stockage de l'audio, et sa durée de vie

### 4.1 Le port de rangement, oui — le validateur d'images, non

Le contexte `media` fournit exactement ce qu'il faut : `MediaStore.put(content, content_type) → URL`,
`LocalMediaStore` en dev, `S3MediaStore` (MinIO) en prod par `s3_endpoint_url`, corps brut sans
multipart, et le contrôle des **octets contre le type déclaré** (`_MAGIC`, DOREA-024).

> ✅ **D7 — S-6 réutilise le port `MediaStore` et **pas** `validate_upload`.** Les bornes de `media`
> sont celles d'une image d'annonce : 5 Mo, `media_allowed_types`. L'audio a ses propres bornes, son
> propre plafond, sa propre liste de types.

⚠️ **Vérifié dans le code le 13/08 — et le dépôt en sait plus que ce paragraphe ne supposait.**
Le chemin de dépôt d'un fichier de sermon **existe déjà et a déjà son plafond** :

```python
# sermon/interface/mobile_router.py:81
data = await read_body_capped(request, max_bytes=settings.sermon_max_bytes)   # 15 Mo
```

Deux conséquences, et la seconde est un trou :

1. **15 Mo est déjà la bonne borne — mais seulement pour de l'audio bien encodé.** Un culte de
   60 min pèse **6,5 Mo** en Opus 20 kbit/s (spec capture §2.2) et passe largement ; le même culte
   en AAC 128 kbit/s — ce que produit un téléphone qu'on n'a pas configuré — pèse **≈ 57 Mo** et
   sera **refusé**. Ce n'est pas un bug : c'est une contrainte qui pousse à l'encodage que la spec
   de capture prescrit déjà. **Mais elle doit être dite au client**, sinon le pasteur voit son
   dépôt échouer sans savoir pourquoi ;
2. 🔴 **ce chemin ne valide ni le type déclaré ni les octets.** Contrairement à `media`, il n'appelle
   ni `validate_upload` ni `_looks_like` : il borne la taille et passe les octets à l'extracteur,
   qui aiguille sur le `kind` **déclaré en query**. Pour PDF/PPTX c'est tolérable — `pypdf` et
   `python-pptx` échouent d'eux-mêmes sur du n'importe quoi, et l'échec est gratuit. **Pour l'audio,
   il ne l'est plus** : voir **D8**.

### 4.2 **La durée est la facture** — et c'est ce qui décide de la liste des formats

Le contexte `media` a déjà rencontré ce problème et l'a tranché pour la vidéo, dans
`application/video.py` : *« un format qu'on ne sait pas mesurer est un format qu'on refuse »*,
la durée se lit dans l'en-tête `mvhd` et ne se croit jamais sur déclaration.

Le même raisonnement mord ici **beaucoup plus fort**, parce que ce n'est plus une règle de confort :

> **La transcription est facturée à la minute. Un plafond en octets ne borne donc pas la facture** —
> soixante minutes pèsent 6 Mo ou 60 selon l'encodeur. **On ne transcrit jamais un fichier dont on
> n'a pas lu la durée**, sans quoi on découvre le prix après l'avoir payé.

> ✅ **D8 — formats acceptés = ceux dont on sait lire la durée.** `m4a`/`mp4` d'abord, et c'est
> gratuit : un `.m4a` **est** un conteneur ISO-BMFF, `mp4_duration_seconds` y trouve son `mvhd`
> sans une ligne nouvelle — vérifié, le scan de boîtes ne présume aucune marque, et le contrôle
> d'octets de `media` teste `content[4:8] == b"ftyp"`, donc agnostique lui aussi. Tout autre
> conteneur (ogg/opus, mp3) s'ajoute **le jour où son lecteur de durée est écrit**, jamais avant.
> Durée illisible ⇒ refus, comme `VideoTooLongError` traite déjà *« je ne sais pas »* à l'égal de
> *« trop longue »*.

> 🔴 **D8bis — et sur le chemin de dépôt, ce contrôle est le SEUL qui existe.** Le point 2 de
> **D7** le montre : rien ne vérifie aujourd'hui que les octets sont ce que le `kind` prétend. Tant
> que l'extracteur ne sert que PDF et PPTX, une déclaration fausse coûte une exception. **Le jour
> où `kind=audio` appelle un service facturé à la minute, elle coûte de l'argent** — et le chemin
> le plus court pour vider un solde est d'envoyer n'importe quoi en déclarant que c'est un sermon.
>
> **Lire la durée n'est donc pas seulement savoir ce qu'on va payer : c'est la porte.** Un fichier
> dont on ne lit pas une durée plausible ne part pas à la transcription — refus avant appel, avant
> stockage, avant tout. C'est le même raisonnement que `_looks_like` côté `media` (DOREA-024,
> *« ce que le fichier est, pas ce qu'il prétend être »*), appliqué là où l'erreur se facture.

### 4.3 Combien de temps on garde — **deux régimes, et ils sont opposés**

| Objet | Audio conservé | Texte conservé | Pourquoi |
| :-- | :-- | :-- | :-- |
| **Dictée de préparation** | ⛔ **jamais écrit sur disque** | oui (`preparation`, saisie conservée) | c'est un substitut de clavier. Personne ne garde un journal de frappe |
| **Culte déposé / capturé** | **J+7**, puis purge planifiée | oui, indéfiniment | la spec de capture l'a déjà tranché (§8) — un travail planifié, `audio_purged_at` daté, qui **échoue bruyamment** |

**La dictée ne touche pas le `MediaStore`.** Tampon en mémoire, transcription, rejet. Deux motifs,
et le second est le vrai :

1. l'audio n'a plus aucun usage une fois le texte rendu — il n'y a rien à en faire ;
2. **une conviction dictée contient des noms.** *« l'amour fraternel n'existe plus dans l'église »*
   est une saisie réelle du dépôt ; sa cousine *« depuis que Untel est parti »* l'est tout autant.
   La préparation est privée par conception, et c'est un des cinq piliers du Compagnon (n° 4 :
   *le privé produit la vérité*). Un fichier audio de vingt secondes est **la pire forme** sous
   laquelle cette phrase puisse survivre : intégrale, avec le ton.

⚠️ **Si un fournisseur exige un dépôt de fichier plutôt qu'un flux, alors l'audio quitte
l'infrastructure — et cette phrase-là doit être écrite dans le produit, pas découverte.** → **Q1**.

**J+7 pour le culte, et pourquoi pas plus.** Le seul motif légitime de garder l'audio est de
retranscrire un jour avec un meilleur modèle. Il ne pèse pas assez : la valeur de l'audio décroît
avec la semaine, son risque ne décroît jamais — *« un micro capte la salle »* (spec capture §7), et
un témoignage donné au micro du prédicateur peut s'y trouver. Une meilleure transcription se
demande par un **nouveau dépôt**, geste explicite de celui qui en porte la responsabilité.

---

## 5. La langue — français ivoirien, code-switching, langues locales

### 5.1 Le mode de panne n'est pas le silence, c'est **l'invention** — et il vient du DÉCODEUR

C'est le fait technique le plus important de cette note, et il entre en collision frontale avec un
patron du dépôt.

Les modèles de la famille Whisper **n'échouent pas en s'arrêtant**. Sur un silence, un bruit, ou une
langue hors distribution, ils produisent du français **fluide, confiant et jamais prononcé** —
souvent une phrase apprise du corpus d'entraînement.

> Et *« une synthèse bâtie sur une transcription non mesurée est une invention présentée comme un
> souvenir »* (spec capture §10.7) devient, ici, littéral : **l'invention est déjà dans le
> transcript**, avant même qu'un modèle la résume.

**Mais ce n'est pas une propriété de la reconnaissance vocale — c'est une propriété du décodeur
autorégressif.** Whisper prédit le mot suivant sachant les précédents : privé de signal, il continue
la phrase, parce que c'est exactement ce pour quoi il a été entraîné. Un décodeur **CTC** n'a pas de
boucle de langage : privé de signal, il rend des caractères décousus. Les deux échouent ; **un seul
échoue de façon visible.**

| Décodeur | Ce qu'il rend sur un signal absent ou hors distribution | Détectable à l'œil ? |
| :-- | :-- | :-- |
| **Autorégressif** (Whisper, `omniASR-LLM`, Voxtral) | une phrase française **fluide et fausse** | ⛔ non |
| **CTC** (`omniASR-CTC`, Parakeet) | des caractères décousus, une bouillie | ✅ **oui** |

> ✅ **D17 — pour le culte, un décodeur CTC, et c'est un choix d'architecture, pas de performance.**
> Le CTC a un taux d'erreur un peu plus élevé que la variante autorégressive du même modèle. Il le
> paie en visibilité, et c'est le bon échange pour ce dépôt : **une bouillie se voit et se marque
> non reconnue (D11) ; une phrase inventée se croit.** C'est la même règle que partout ailleurs
> ici — *rien plutôt qu'une vraisemblance* — appliquée au niveau où elle se décide vraiment.
>
> Et l'échange est doublement bon : le CTC est aussi **le variant rapide** (RTF 0,006 contre 0,092),
> donc celui qui rend un seul GPU suffisant à l'échelle (§2.2). **La sûreté et le prix vont dans le
> même sens.**

### 5.2 Trois décisions qui en découlent

> ✅ **D9 — la langue est DÉCLARÉE, jamais devinée.** Les modèles retenus acceptent un code de
> langue explicite (`fra_Latn`, `dyu_Latn`, …), et le port l'a prévu depuis le premier jour :
> `language_hints: Sequence[str]  # ['fra'] + langues déclarées par l'église` (spec capture §4).
> La détection automatique choisit une langue par fenêtre ; sur un passage alterné, elle bascule et
> rend du charabia translittéré — et le papier d'Omnilingual note lui-même que *« des langues
> proches dans le jeu d'entraînement peuvent confondre le modèle »*, ce que le conditionnement
> explicite existe pour corriger.
>
> **C'est l'église qui déclare ses langues, pas la machine qui les devine** — la règle du dépôt
> entier, *le calcul propose, la personne dispose*, appliquée à la porte d'entrée du son.

> ✅ **D10 — la confiance par segment est une colonne, pas un réglage.** `urim_transcript_segment`
> la porte déjà (`confidence real NOT NULL`), et le contrôle de couverture existe :
> **plus de 30 % des segments sous le seuil ⇒ aucune synthèse**, le transcript brut reste. S-6
> hérite de cette règle telle quelle pour la **digestion S-1** : couverture insuffisante ⇒ **aucun
> digest, aucune capsule**, et le pasteur est prévenu que la transcription n'était pas assez bonne.

> ✅ **D11 — un segment sous le seuil s'affiche comme non reconnu, jamais lissé, jamais effacé.**
> *« un travail abandonné laisse le transcript en `partiel` — jamais un silence »*. Un trou visible
> se corrige ; une phrase inventée se croit.

### 5.3 Les langues locales — **le « facteur limitant probable » ne l'est plus** (13/08/2026)

La spec de capture écrivait, en août 2025, que le dioula, le baoulé et le nouchi étaient
*« le facteur limitant probable »* et que la question n'était *« pas instruite »*. Elle l'est
maintenant, et la réponse a changé.

**`Omnilingual ASR` couvre 1 237 langues, Apache 2.0, et les nôtres sont dedans** — vérifié dans
`lang_ids.py` du dépôt Meta, pas déduit d'une annonce :

| Langue | Code | Heures d'entraînement | **CER** (7B, variante LLM) |
| :-- | :-- | --: | --: |
| Français | `fra_Latn` | 4 615 h | **2,2 %** |
| Bambara | `bam_Latn` | 15 h | 1,0 % |
| Mooré | `mos_Latn` | 120 h | 1,9 % |
| Agni / Anyin | `any_Latn` | 42 h | 2,7 % |
| **Dioula** | `dyu_Latn` | 93 h | **6,5 %** |
| **Baoulé** | `bci_Latn` | **8 h** | **10,7 %** |
| Sénoufo (cebaara) | `sef_Latn` | — | ⛔ **absent** |

⚠️ **Et voici pourquoi ces chiffres ne sont pas une promesse.** Quatre réserves, dans l'ordre où
elles mordent :

1. **C'est du CER, pas du WER.** Un taux d'erreur **par caractère** de 6,5 % correspond, selon la
   langue, à un taux **par mot** de deux à quatre fois supérieur. Les deux mesures ne se comparent
   pas, et c'est la seconde qui décide si un transcript est lisible ;
2. **les conditions d'évaluation ne sont pas un culte.** Le corpus MMS-Lab est fait
   d'*« enregistrements de haute qualité »* avec *« une poignée de locuteurs par langue »*. Un culte,
   c'est une salle réverbérante, un prédicateur qui force la voix, une assemblée qui répond, de la
   musique. **Le papier le dit lui-même** : ces taux *« ne sont pas directement comparables »* à
   ceux de la parole spontanée ;
3. **regardez la colonne des heures avant celle du CER.** Le baoulé est entraîné sur **huit heures**.
   Le bambara affiche 1,0 % sur quinze heures — un chiffre trop beau, qui parle surtout de la
   petitesse de son jeu d'évaluation. **La colonne « heures » est le meilleur prédicteur de ce qui
   tiendra sur le terrain**, et elle dit : français oui, dioula peut-être, baoulé non ;
4. **le code-switching reste non instruit.** Ces modèles se conditionnent sur **une** langue (D9).
   Un prédicateur qui glisse trois phrases de dioula au milieu de son français n'est traité par
   aucun des chiffres ci-dessus, et le papier ne dit rien de ce cas.

> ✅ **D18 — le nombre à promettre, c'est celui qu'on aura mesuré nous-mêmes ; celui-ci ne sert
> qu'à décider d'essayer.** Ce que le relevé tranche n'est pas *« ça marche »*, c'est
> *« ça vaut d'être mesuré »* — ce qui, pour le baoulé, n'était pas vrai il y a un an. La ligne 2
> du §9 (trois cultes réels) devient le seul chiffre opposable, et elle se mesure **par langue**.

> ✅ **D19 — l'offre est graduée, et elle se dit par langue, jamais en bloc.** *« Dorea transcrit
> le français ; le dioula est en évaluation ; le baoulé ne l'est pas encore »* est une phrase
> tenable. *« Dorea transcrit vos langues »* ne l'est pas, et *« Dorea transcrit le français »*
> — ce que cette note affirmait avant ce relevé — est devenu **inutilement faux**.

> **Ce que ça ne change pas.** Le port (**D5**) reste ce qui rend le pari réversible ; la confiance
> par segment (**D10**) et l'affichage du non-reconnu (**D11**) restent la protection réelle, quelle
> que soit la langue. Une couverture élargie déplace la frontière du reconnaissable — **elle ne
> supprime pas la frontière.** → **Q6**.

---

## 6. La relecture par le pasteur

**Question posée : la transcription est-elle *toujours* affichée avant usage ? — Oui, toujours.
Mais « affichée » et « bloquante » ne sont pas la même chose, et le dépôt a déjà tranché les deux.**

| | Ce qui est affiché | Ce qui **bloque** |
| :-- | :-- | :-- |
| **Dictée** | le texte **atterrit dans le champ de saisie**, éditable ; le pasteur déclenche lui-même la recherche | rien, **sauf** signal non univoque → **confirmation S36** : *« J'ai entendu : "…". C'est bien ce que vous vouliez ? »* |
| **Culte** | le transcript est consultable **à côté du digest**, avec ses trous marqués | l'**approbation du digest** — qui existe depuis S-0 (`brouillon → approuvé → publié`) |

> ✅ **D12 — pour la dictée, le champ de saisie EST la relecture.** Ajouter un écran de
> confirmation systématique fatiguerait le pasteur qui a visé juste — c'est la règle de D-E,
> appliquée en amont. La confirmation bloquante reste réservée au cas que S36 a nommé : une dictée
> qui ne produit pas de signal univoque. ⚠️ **Et elle n'est possible que parce que la provenance
> voyage** : sans `EntryOrigin.DICTATED`, le moteur devrait *deviner* qu'un micro est resté ouvert.

> ✅ **D13 — pour le culte, on ne demande à personne de relire neuf mille mots.** Le garde-fou
> n'est pas la relecture du transcript, ce serait un vœu pieux. Ce sont **trois murs déjà en
> place** : le transcript **n'est jamais publié au membre** (aucun des plans en présence ne le
> prévoit — ni l'ancien tableau des quatre objets, ni le chantier 11) ; tout ce qui atteint le
> membre passe par une **capsule approuvée** (pilier 2 : *« l'IA ne publie jamais seule ;
> l'approbation est l'onction »*, repris tel quel en **11d** : *« rien de non approuvé n'atteint le
> membre »*) ; et le digest **ne se génère pas** si la couverture est insuffisante (**D10**).
>
> Ce que S-6 ajoute est modeste et décisif : **le transcript est affiché à côté du digest**, pour
> que le pasteur puisse distinguer *« l'IA a mal compris »* de *« je me suis mal exprimé »*. Sans
> lui, il approuve une capsule sans savoir d'où elle vient.

> **La porte humaine allège le verrou de qualité — elle ne l'annule pas.** Le verrou de la capture
> — *étape 1 seule jusqu'à mesure du taux d'erreur dans trois églises réelles* — existe parce que
> le **Retour n'a pas de porte humaine** : il présente au pasteur un constat sur son propre
> ministère, qu'il croira dans un an. Une chaîne qui **finit par une approbation** (S-0 aujourd'hui,
> 11d demain) hérite donc du verrou de **qualité** (D10 : pas de digest sur un mauvais transcript)
> sans hériter du verrou de **séquencement**. ⚠️ Ce n'est pas une permission de construire : voir §8.

---

## 7. Le mur qui tient partout : **aucun texte biblique ne sort du modèle**

Règle de M9-1, reprise mot pour mot dans `urim/adapters/mistral.py` : *« l'IA retrouve la
référence, la Bible donne le texte »*. Un transcript ne l'affaiblit pas — il ouvre une **troisième
voie d'entrée** pour une citation approximative, après le texte tapé et la recherche par personnage.

> ✅ **D14 — une référence entendue est un CANDIDAT, jamais un fait.** Elle passe par
> `check_reference` (`urim/infrastructure/corpus/readers.py`) et le texte affiché vient
> **exclusivement du corpus**. C'est déjà la règle de `urim_cited_verse` (§10.4 de la spec
> capture) : *« les références qui apparaissent dans la synthèse proviennent exclusivement de
> `cited_verse`, jamais du texte généré »*.

⚠️ **Et la limite de ce garde-fou, dite franchement, parce que quelqu'un la découvrira autrement.**

`check_reference` attrape **l'impossible**, pas **le faux** :

```
« Romains vingt-huit »   → écarté  : « Romains compte 16 chapitres »        ✅ attrapé
« Jean trois six »  (dit « Jean 3:16 »)  → Jean 3:6 existe                  ⛔ non attrapé
```

Une erreur de reconnaissance sur un chiffre produit une référence **valide et fausse**, et aucun
contrôle de corpus ne peut la distinguer. La seule protection réelle est humaine :
**la référence s'affiche avec l'horodatage de son segment**, à côté de ce qui a été entendu. Le
pasteur sait ce qu'il a prêché ; on lui montre où regarder. C'est aussi ce qui explique pourquoi
`urim_cited_verse` porte `detected_by` et un `confidence` — et pourquoi *« sous le seuil, on
n'écrit rien »* : **mieux vaut manquer une citation que d'en inventer une.**

---

## 8. Où ça se construit — **la collision a déjà été tranchée, contre S-6**

C'est le seul endroit où cette note contredit la façon dont le chantier lui a été demandé, et il
vaut mieux le dire ici que le découvrir en écrivant le premier fichier.

**S-6 et `urim/capture` transcrivent le même dimanche.** Rien n'oblige une église à avoir les deux,
mais si elle les a, le même culte serait transcrit deux fois — et la transcription est **la seule
ligne du budget qui compte** (§2.3). La duplication a été vue, et elle a été résolue, il y a une
semaine :

> `docs/Plan_Urim_Producteur.md` (05/08/2026) : *« **S-6 et `urim/capture` étaient le même travail.**
> Le lot audio / speech-to-text de `sermon` n'a jamais été écrit ; la transcription du culte est la
> raison d'être de `urim/capture`. Le retrait **supprime une duplication qui existait déjà** au lieu
> d'en créer une. »*

Ce plan **révoque D-B et S32**, retire le contexte `sermon` (R0→R4), fait d'Urim le seul producteur
de ce que le fidèle lit, et **renomme le lot** : *chantier 10 — Capture (nouveau nom du lot S-6)*.

### L'état réel, au 13/08/2026

| | Ce que dit le plan | Ce que dit le dépôt |
| :-- | :-- | :-- |
| Retrait de `sermon` | décidé le 05/08, R0→R4 *« faisables tout de suite »* | ⏳ **rien n'a commencé** — `app/contexts/sermon/` est intact, S-0→S-5 tournent |
| Chantier 10 (capture) | ⛔ bloqué par **S31** | ✅ **S31 est levé** — `Dorea_Urim_Capture_et_Retour.md` a été écrit le 06/08, les quatre tables sont définies |
| Chantier 10 (capture) | ⛔ bloqué par **Architecture v2 §11** | ⛔ **toujours** — il manque *un dimanche réel dans une église réelle* |
| Chantier 11 (publication) | dépend du chantier 6 (moteur assemblé) | ⛔ `PIPELINE` dépend du corpus, **chantier 1 non fait** |

### Ce que ça impose

> ✅ **D15 — ne pas construire le transcripteur dans `sermon`.** Deux raisons, et la seconde suffit
> à elle seule :
>
> 1. ce serait **le lot le plus lourd du module**, écrit dans le contexte dont le retrait est
>    décidé — 31 fichiers, 3 tables, 10 routes à démolir en R4. Le plan pose la règle inverse en
>    toutes lettres : *« on relocalise avant de démolir »* ;
> 2. **le poste de dépense doit avoir un seul propriétaire.** Deux transcripteurs, ce sont deux
>    fournisseurs, deux plafonds, deux rétentions à tenir — et un jour, deux factures pour un culte.
>
> **Un culte, un transcript. Jamais deux.**

> ✅ **D16 — les décisions de cette note sont portables ; le branchement ne l'est pas.** D1→D14
> décrivent un port, des tarifs, des formats, des seuils, des rétentions et une relecture : rien
> n'y dépend du contexte hôte. Elles s'appliquent **à `urim`, chantier 10**, sans réécriture. Ce qui
> était propre à `sermon` — brancher `kind=audio` derrière `SermonTextExtractor` — est ce qui
> disparaît, et c'est tant mieux : c'était le maillon le plus mince.

> ⚠️ **Et le quatrième mur ne bouge d'aucun côté.** `FORBIDDEN_IN_MODEL_PROMPT` est déjà écrit dans
> `urim/capture/__init__.py`, **avant le module qu'il garde**. Que le digest vienne de S-1 ou du
> chantier 11c, il voit un texte de ce qui a été **dit**, jamais un plan de ce qui devait l'être —
> sans quoi le modèle **fabrique la conformité**, et les capsules décrivent le sermon prévu plutôt
> que celui qui a été prêché.

### La conséquence qu'il faut regarder en face

**Suivre D15, c'est accepter qu'aucune transcription du culte ne sorte avant longtemps** : le
chantier 10 attend un dimanche réel (Architecture v2 §11) *et* la mesure du taux d'erreur dans trois
églises, et le chantier 11 attend le corpus. C'est un coût réel, et il se paie en fonctionnalité.

Ce qui **n'est pas** bloqué par là, et qui vaut d'être séparé :

- **la dictée de préparation** (§2.4). Elle ne dépend ni de `sermon`, ni du chantier 10, ni d'un
  octet d'audio serveur : `EntryOrigin.DICTATED` est **déjà** consommé par l'étage 0 livré. Il
  manque un client qui pose le champ. **C'est le seul morceau de ce chantier qui soit livrable
  aujourd'hui, et il coûte zéro** ;
- **la mesure du taux d'erreur** (§9, ligne 7). Elle ne demande aucun contexte : trois cultes
  enregistrés, un script, un chiffre. C'est même le **prérequis** du verrou qu'on attend — on ne
  peut pas lever *« mesuré dans trois églises »* sans avoir mesuré.

> Autrement dit : **la dictée s'ouvre, la mesure commence, le dimanche attend.** → **Q7**.

---

## 9. Ce que ça demanderait de construire — **et pourquoi ça s'arrête ici**

Cette note appelle du code. Elle le nomme, et elle s'arrête.

| # | À construire | Où | Dépend de |
| :-- | :-- | :-- | :-- |
| **1** | **Le client pose `entry_origin=dictated`** — dictée sur l'appareil, zéro octet serveur (**D1**) | mobile / PWA | **rien.** Le contrat serveur existe et est testé |
| **2** | Un **banc de mesure du taux d'erreur, PAR LANGUE**, sur trois cultes réels — à la discipline de `scripts/urim_mesure_cout.py` (paramètres en dur et datés, entrées réelles). Compare au minimum `omniASR-CTC` auto-hébergé et une API, sur le **même** audio | `scripts/` | de l'audio réel · **Q3, Q6** |
| **2bis** | Un **essai d'auto-hébergement** : un GPU, `omniASR-CTC-7B`, mesurer le RTF réel sur la machine retenue plutôt que sur l'A100 de la fiche | hors dépôt | **Q1** |
| 3 | Port `Transcriber` + `TranscriptResult` (segments, confiance, `provider`, `model_ref`) — c'est le `TranscriptionPort` de la spec de capture §4 | `urim/capture/` | le dégel du chantier 10 |
| 4 | `NullTranscriber` + adaptateur réel + `build_transcriber(settings)` | `urim/capture/` | 3 · **Q1** (quel fournisseur) |
| 5 | Lecture de durée `m4a`/ISO-BMFF + bornes audio propres (**D8**) | réutilise `media/application/video.py` | — |
| 6 | Contrôle de couverture (30 %) avant toute digestion (**D10**) | côté producteur (chantier 11) | 3 |
| 7 | Écriture de `urim_usage_window` — **la table est lue et n'a jamais été écrite** | `urim/` | **D2, D3, D4** |
| 8 | Transcripteur serveur pour la dictée, si l'appareil ne suffit pas | `urim/` | 3, 4 · mesure de la ligne 1 |

> ⚠️ **Les deux premières lignes sont les seules qui puissent commencer, et elles sont dans cet
> ordre pour une raison.** La ligne 2 vient avant tout le reste du tableau : D9-D11 posent des
> **seuils** (confiance par segment, 30 % de couverture) qui sont aujourd'hui des paris, et
> *« un pari à calibrer sur du réel, comme tous les autres »*. Le dépôt a déjà payé pour apprendre
> qu'on ne raisonne pas sur un coût sans l'avoir mesuré — et il a même appris qu'il l'avait
> **surestimé d'un facteur dix**. On ne raisonnera pas davantage sur un taux d'erreur qu'on n'a
> pas vu.
>
> **Les lignes 3 à 8 sont derrière le verrou du §8.** Elles sont décrites pour que le jour où il
> tombe, il n'y ait plus qu'à écrire.

---

## 10. Questions ouvertes — à trancher par un humain

| # | Question | Pourquoi elle ne se tranche pas dans cette note |
| :-- | :-- | :-- |
| **Q1** | **Souveraineté — et elle ne coûte plus rien à partir d'une certaine taille.** Accepte-t-on qu'un culte ivoirien complet, voix de l'assemblée comprises, transite par un serveur américain ou européen ? Et la dictée par les serveurs de Google (**D1**) ? | Ce n'était pas un arbitrage de prix, et ça l'est encore moins depuis §2.2bis : les poids ouverts sont en **Apache 2.0**, et au-delà de ~300 églises **le GPU souverain est le moins cher des deux**. La question qui reste est celle de l'**exploitation** — qui tient la machine, la nuit du dimanche |
| **Q2** | **Qui paie, et combien de cultes.** Quelle offre de `Tenant_Subscription` ouvre l'audio du dimanche, et à quel `ceiling` mensuel (**D2, D4**) ? | L'abonnement d'église est une **note de design non implémentée**. Tant qu'elle l'est, **D3** (ouverture par configuration) tient lieu de réponse |
| **Q3** | **Le modèle, et sa qualité réelle en français ivoirien.** *(point ouvert n° 1 de la spec de capture)* | Se mesure, ne se choisit pas — ligne **2** du §9. Le port (**D5**) existe pour que le choix reste réversible, et **D17** dit seulement par quelle famille de décodeur commencer |
| **Q4** | **L'information de l'assemblée.** Faut-il prévenir les fidèles qu'un culte est enregistré, et est-ce une obligation légale dans les 7 pays ? *(point ouvert n° 5 de la spec de capture)* | Question de droit, à instruire pays par pays. ⚠️ La rétention J+7 et la purge datée sont une **atténuation**, pas une réponse |
| **Q5** | **La rétention J+7 est-elle négociable ?** Un pasteur peut-il demander à garder son audio plus longtemps, et en porter la responsabilité ? | Arbitrage entre son usage (retranscrire un jour mieux) et les voix de la salle, qui n'ont rien demandé |
| **Q6** | **Les langues locales — jusqu'où va la promesse, langue par langue ?** (**§5.3, D19**) La question a changé de nature le 13/08 : ce n'est plus *« accepte-t-on de dire non ? »* mais *« à partir de quel taux d'erreur mesuré dit-on oui, et pour laquelle ? »* | Le dioula (93 h d'entraînement) et le baoulé (**8 h**) ne se décident pas ensemble. ⚠️ Et une décision de plus, qui n'est pas technique : **est-il acceptable de proposer une transcription médiocre dans la langue de quelqu'un**, ou vaut-il mieux ne rien proposer que mal ? |
| **Q7** | ⚠️ **La plus urgente. Accepte-t-on qu'aucune transcription du culte ne sorte tant que le chantier 10 est gelé** (**D15**, §8) — ou faut-il rouvrir le retrait de `sermon`, décidé le 05/08 et non commencé, pour livrer plus tôt un producteur qu'on a jugé moins bien gardé ? | C'est un arbitrage **délai contre rigueur**, déjà posé par le plan de retrait : *« un producteur médiocre disponible aujourd'hui contre un producteur rigoureux disponible plus tard — un bon échange, à condition de le faire les yeux ouverts »*. Cette note **ne le rouvre pas**, elle en chiffre le prix |
| **Q8** | **Qui décide qu'une église a la capture**, et donc qu'on ne retranscrit pas son culte une seconde fois ? | Dépend du dégel du chantier 10 et de la façon dont les deux produits se vendent (ADR-007 les destine à se séparer) |
| **Q9** | **Le seuil de confiance et les 30 % de couverture** : quelles valeurs ? | Des paris, aujourd'hui. Se calibrent sur les trois cultes réels de la ligne **2** du §9 — pas avant |

---

*Note de conception — fait foi sur les décisions **D1 à D19**. `Dorea_Urim_Architecture_Transcription.md`
et `Dorea_Urim_Capture_et_Retour.md` font foi sur la capture ; `Plan_Urim_Producteur.md` sur le
retrait de `sermon` et sur l'ordre des chantiers ; `Sermon_Companion.md` sur l'état d'avant ce
retrait. **Aucun code n'a été écrit.***
