# DOREA URIM — Architecture de la transcription

**2 août 2026** — complète `Dorea_Urim_Capture_et_Retour.md`
**Module :** `urim/capture/`
**Statut :** spécification. Construction non autorisée (séquencement inchangé).

---

## 1. Vue d'ensemble

```
APPAREIL                          │  SERVEUR
                                  │
 Micro prédicateur                │
   ↓                              │
 VAD + encodage Opus              │
   ↓                              │
 Fragments 45 s  ──── outbox ────→│  Ingestion (clé d'idempotence)
   (écrits au fil)   réseau       │    ↓
                     revenu       │  File Postgres (job)
                                  │    ↓
                                  │  TranscriptionPort  ← fournisseur remplaçable
                                  │    ↓
                                  │  transcript_segment
                                  │    ↓
                                  │  Extraction des versets
                                  │   ├─ références énoncées   (précision haute)
                                  │   └─ citations reconnues   (rappel)
                                  │    ↓
                                  │  Alignement au squelette
                                  │    ↓
                                  │  reflection (constats)
                                  │    ↓
                                  │  Purge audio  (J+7)
```

**Aucune infrastructure nouvelle.** File de travaux en table PostgreSQL, consommée par les workers planifiés existants. Ni Redis, ni RabbitMQ — conforme à la V1.

---

## 2. Côté appareil

### 2.1 Écriture au fil, jamais en un bloc

**Fragments de 45 secondes, écrits sur le disque au fur et à mesure.** Une prédication est un fichier de 60 fragments, pas un fichier de 45 minutes.

Motif : batterie vide, application tuée par Android, tablette qui redémarre. Un enregistrement monolithique perd tout ; un fragment perdu coûte 45 secondes. **Ce qui n'est pas capté dimanche est perdu pour toujours** — c'est la contrainte qui prime sur toutes les autres.

### 2.2 Encodage

| Paramètre | Valeur | Motif |
|---|---|---|
| Codec | Opus | Conçu pour la parole, décodable partout |
| Échantillonnage | 16 kHz mono | Suffisant pour l'ASR, inutile d'aller au-delà |
| Débit | 20 kbit/s VBR | 45 min ≈ **6,5 Mo** — transportable sur un réseau ivoirien |
| VAD | Actif | Les silences ne sont pas encodés |

Vérification obligatoire sur **IDINO NOTEBOOK-10** (Android 8.1, MT6737M). Si l'encodage temps réel n'y tient pas, repli sur AAC-LC matériel et débit supérieur — la capture prime sur la taille.

### 2.3 Outbox

```
capture_chunk_local
    capture_id · ordinal · sha256 · path · bytes
    state: local | envoye | acquitte
```

Envoi quand le réseau revient, dans l'ordre, reprise là où ça s'est arrêté. **Suppression locale seulement après acquittement serveur.** Clé d'idempotence : `capture_id + ordinal + sha256` — un fragment renvoyé n'est jamais transcrit deux fois.

### 2.4 Ce qui n'est pas fait sur l'appareil

**Pas de transcription locale sur la tablette de référence.** Un MT6737M ne fait pas tourner un modèle ASR utile. L'appareil capte, encode, transmet. Rien d'autre.

Si le prédicateur capture depuis un téléphone récent, la transcription embarquée redeviendra une option — **derrière le même port** (§4), donc sans changer l'architecture.

---

## 3. File de travaux

```sql
CREATE TABLE urim.capture_job (
    id              uuid PRIMARY KEY,
    capture_id      uuid NOT NULL REFERENCES urim.capture,
    kind            text CHECK (kind IN
        ('transcrire','extraire_versets','aligner','purger_audio')),
    state           text CHECK (state IN
        ('en_attente','en_cours','fait','echoue','abandonne')),
    attempts        smallint NOT NULL DEFAULT 0,
    not_before      timestamptz NOT NULL DEFAULT now(),
    locked_until    timestamptz,
    last_error      text,
    idempotency_key text NOT NULL UNIQUE
);
CREATE INDEX job_a_prendre ON urim.capture_job (state, not_before)
    WHERE state = 'en_attente';
```

Prise de travail :

```sql
UPDATE urim.capture_job SET state='en_cours', locked_until = now() + interval '10 min'
WHERE id IN (
    SELECT id FROM urim.capture_job
    WHERE state='en_attente' AND not_before <= now()
    ORDER BY not_before LIMIT 5
    FOR UPDATE SKIP LOCKED
) RETURNING *;
```

**Reprise exponentielle**, abandon après 5 tentatives avec `last_error` conservé. Un travail abandonné laisse le transcript en `partiel` — **jamais un silence**. Le pasteur voit ce qui a échoué.

---

## 4. Le port de transcription

```python
class TranscriptionPort(Protocol):
    def transcribe(
        self,
        chunks: Sequence[AudioChunk],
        language_hints: Sequence[str],   # ['fra'] + langues déclarées par l'église
    ) -> TranscriptResult: ...

@dataclass(frozen=True, slots=True)
class TranscriptResult:
    segments:   tuple[Segment, ...]      # texte, ms début/fin, confiance
    provider:   str
    model_ref:  str                      # tracé : la qualité varie d'un modèle à l'autre
```

**Le fournisseur est remplaçable sans toucher au reste.** C'est délibéré : la question des langues locales (dioula, baoulé, nouchi) n'est pas instruite, et c'est le facteur limitant probable. L'architecture ne doit pas parier sur un fournisseur avant que le terrain ait tranché.

`provider` et `model_ref` sont **stockés par transcript**. Sans eux, impossible de savoir plus tard pourquoi certains dimanches sont mauvais.

---

## 5. Extraction des versets — deux détecteurs

C'est la brique à construire en premier, avant tout résumé. Elle survit à un transcript imparfait.

### 5.1 Références énoncées — précision haute

**Un prédicateur annonce sa référence à voix haute bien plus souvent qu'il ne cite mot pour mot.** C'est le signal le plus rentable, et il demande un analyseur distinct de celui du texte écrit.

> « Romains chapitre huit, verset quinze »
> « ouvrons dans Luc quinze »
> « au verset dix-sept »   ← référence relative, résolue par le contexte proche

Il faut donc un **analyseur de nombres en toutes lettres**, par langue — pas la table d'abréviations écrites (`Rom`/`Rm`/`Ro`), qui ne sert à rien ici. Plus la gestion des références relatives, qui héritent du dernier livre et chapitre mentionnés.

### 5.2 Citations reconnues — rappel

Fenêtre glissante sur les segments, ancres rares IDF, similarité trigramme — **le moteur de résolution de l'étage 1, appliqué à un autre flux d'entrée.**

Deux différences avec l'écrit : pas de ponctuation ni de casse en sortie d'ASR (la normalisation les supprimait déjà, donc c'est neutre), et un bruit de reconnaissance qui pénalise les mots courts. Les ancres rares y résistent mieux — c'est précisément pourquoi elles ont été choisies.

### 5.3 Fusion et seuil

Une même citation détectée par les deux voies est consolidée. **Sous le seuil, on n'écrit rien** — un verset faussement attribué corrompt la couverture du canon, qui est l'usage final. Mieux vaut manquer une citation que d'en inventer une.

`was_prepared` se calcule par différence avec la préparation : **c'est le signal intéressant**, les textes convoqués sans avoir été prévus.

---

## 6. Alignement au squelette

**Méthode simple, volontairement.** Les frontières de mouvement sont approchées par l'horodatage des versets d'ancrage de chaque mouvement du squelette Braga.

Pas d'alignement sémantique en V1. Il serait plus riche et beaucoup moins sûr, et l'erreur se paie cher : un temps mal attribué produit un constat faux présenté comme un fait.

**Un mouvement dont l'ancre n'est jamais citée est marqué « non repéré », pas « non traité ».** La nuance n'est pas rhétorique : Urim ne sait pas ce qui a été dit, il sait ce qu'il a reconnu.

---

## 7. Voix autres que le prédicateur

Le micro est celui du prédicateur, mais un micro capte la salle.

**Pas de diarisation, pas de colonne de locuteur** — c'est acquis (§2.1 du document Capture). Le filtrage repose sur des signaux non identifiants : niveau, proximité, VAD. Les segments qui n'y satisfont pas sont **écartés avant écriture**, jamais stockés puis filtrés.

**Risque résiduel assumé et déclaré :** un témoignage donné au micro du prédicateur peut passer. D'où la rétention audio courte, la propriété de l'auteur, et le point ouvert juridique sur l'information de l'assemblée.

---

## 8. Purge

`purger_audio` est un **travail planifié, pas une option d'administration**. Il supprime les objets audio à `audio_purge_at`, marque `audio_purged`, et échoue bruyamment s'il ne peut pas.

Un test vérifie qu'aucun objet audio ne survit à son échéance.

---

## 9. Plafond

La transcription est facturée à l'usage : elle entre dans le plafond mutualisé de l'église, unité = une capture.

> **La capture n'est jamais refusée.** Plafond atteint, l'enregistrement a lieu et l'audio est conservé ; la transcription est différée et le pasteur en est informé.

Ce qui n'est pas capté dimanche est perdu pour toujours. Un transcript, lui, peut attendre lundi.

---

## 10. La synthèse — IA sous contrainte

Le résumé est la seule étape de la chaîne où un modèle génère du texte. Le risque n'y est pas théorique : **le pasteur relira ce résumé dans un an et le croira.** Une synthèse fausse ne produit pas une gêne, elle produit un faux souvenir de son propre ministère.

### 10.1 Le modèle ne voit jamais la préparation — **règle centrale**

S'il reçoit le plan, il décrira le sermon comme ayant suivi le plan. C'est le mode d'hallucination le plus prévisible et le plus coûteux ici : il fabrique la conformité, et il détruit exactement ce que le Retour existe pour montrer.

> **La comparaison préparé / prêché n'est jamais faite par le modèle.**
> Elle est calculée après coup, par différence déterministe, sur des données factuelles : versets cités, horodatages, ancres repérées.

Le modèle voit le transcript. Rien d'autre.

### 10.2 Sortie structurée, jamais de prose libre

```python
class Synthese(BaseModel):
    mouvements:   list[Mouvement]     # titre, segments source
    illustrations: list[Element]      # récits, images employés
    applications: list[Element]       # ce qui a été demandé à l'assemblée

class Element(BaseModel):
    body:         str
    segment_refs: list[int]           # OBLIGATOIRE, non vide
```

`segment_refs` non vide est **un invariant vérifié**, pas une consigne de prompt. Une sortie sans provenance est rejetée avant d'atteindre la base — même discipline que `rationale` dans `StageResult`, et que `reviewed_by NOT NULL` dans le corpus.

### 10.3 Ce que la synthèse décrit, et ce qu'elle ne décrit pas

**Elle décrit la structure de ce qui a été dit.** Elle ne formule jamais la doctrine enseignée.

> ⛔ « Le pasteur a enseigné que le salut est reçu par la foi seule »
> ✅ « Deuxième mouvement — sur Romains 8.15, l'adoption (segments 34-51) »

Résumer la doctrine, c'est entrer dans l'herméneutique, dont Urim est sorti par décision. Et c'est se tromper d'une manière qui compte : un pasteur à qui l'on attribue une position qu'il n'a pas tenue a une raison définitive d'abandonner le produit.

### 10.4 Aucun verset ne sort du modèle

Les références qui apparaissent dans la synthèse proviennent **exclusivement de `cited_verse`**, jamais du texte généré. Un modèle qui « se souvient » d'une référence approximative en produit une plausible et fausse.

### 10.5 Vérification avant écriture

| Contrôle | Rejet si |
|---|---|
| Provenance | `segment_refs` vide ou hors bornes |
| Ancrage | Le contenu ne recoupe pas lexicalement ses segments source |
| Versets | Une référence apparaît sans exister dans `cited_verse` |
| Couverture | Plus de 30 % des segments sources sous le seuil de confiance |

**Échec du dernier contrôle ⇒ aucune synthèse.** Le transcript reste, brut et consultable. Rien plutôt qu'une reconstitution vraisemblable — c'est la même règle que le contexte historique sourcé-ou-absent.

### 10.6 La synthèse est une proposition, pas un compte rendu

```sql
ALTER TABLE urim.reflection ADD COLUMN synthesis_state text
    CHECK (synthesis_state IN ('proposee','validee','rejetee'));
ALTER TABLE urim.reflection ADD COLUMN validated_by  uuid;
ALTER TABLE urim.reflection ADD COLUMN validated_at  timestamptz;
```

Tant qu'elle n'est pas validée par son auteur, elle est **marquée comme proposition** dans l'interface, visuellement distincte du transcript. Après validation, elle devient sa parole — et il a pu la corriger.

Distinction tenue à l'écran : **ce qu'il a dit** (transcrit) et **ce que la machine en a compris** (proposé) ne se ressemblent jamais.

### 10.7 Séquencement

Cette étape reste la **quatrième et dernière**. Elle ne démarre pas avant que la capture ait tourné dans trois églises réelles avec un taux d'erreur mesuré. Une synthèse bâtie sur une transcription non mesurée est une invention présentée comme un souvenir.

---

## 11. Points ouverts

| # | Question | État |
|---|---|---|
| 1 | Fournisseur ASR et qualité réelle en français ivoirien | **Non instruit — mesurer avant de choisir** |
| 2 | Langues locales : dioula, baoulé, nouchi | **Non instruit. Facteur limitant probable** |
| 3 | Encodage Opus temps réel sur MT6737M | À tester sur l'IDINO |
| 4 | Stockage audio : quel objet, quelle région, quel coût | Non tranché |
| 5 | Information de l'assemblée — obligation légale ? | À instruire dans les 7 pays |

**Étape 1 uniquement** — capture, transport, transcript brut non exploité — jusqu'à mesure du taux d'erreur dans trois églises réelles. Le résumé ne se construit pas sur une qualité non mesurée.
