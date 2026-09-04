# DOREA URIM — Capture et Retour : le schéma

*Écrit le 2026-08-06 pour lever **S31**. `Dorea_Urim_Architecture_Transcription.md` référençait
quatre tables sans les définir — `capture`, `transcript_segment`, `cited_verse`, `reflection` — et
`capture_job` portait une `REFERENCES` vers une table qui n'existait nulle part. Rien n'est inventé
ici : chaque colonne se dérive d'une phrase de la spec de transcription, citée en commentaire.*

**Préfixes, pas de schéma Postgres** (D-A) : `urim_capture`, `urim_capture_job`, … Et **aucune clé
étrangère ne franchit une frontière de contexte** (§3.9) — `church_id` et `author_id` sont des
`uuid` nus.

---

## 1. La boucle, et où elle s'arrête aujourd'hui

🔴 **Redessiné le 04/09/2026 — D24 (S6 §1bis).** Le dessin précédent faisait passer toute la
branche « prêcher » par le transcript, et le verrou de séquencement bloquait donc tout. Ce
n'est plus le tronc : **le tronc est l'audio retravaillé.**

```
préparer  ─────────►  prêcher  ─────────►  édition  ─────────►  LA PIÈCE
(8 étages livrés)     (capture)         (découper,                  │
                                        retravailler)               │
                                                                    ├──►  publication (Dorea app)
                                                                    │
                                                                    ├──►  transcription  ──►  synthèse ──► epub
                                                                    │           ▲                  ▲
                                                                    │      étape 2-3          étape 4
                                                                    │                    ⛔ VERROUILLÉ
                                                                    │
                                                                    └──►  l'équipe écoute ──►  interprétation
```

**Le verrou n'a pas bougé de sévérité, il a bougé de portée.** Il ne garde plus que la flèche
`transcription → synthèse` : extraction des versets (étape 2), alignement (3), synthèse (4)
restent fermés jusqu'à mesure du taux d'erreur dans **trois églises réelles**.

> *« Une synthèse bâtie sur une transcription non mesurée est une invention présentée comme un
> souvenir. »*

✅ **Ce qui sort du verrou, et qui n'aurait jamais dû y être :** l'édition, la publication de
l'audio, et l'interprétation. Aucune des trois ne traverse un modèle. L'interprète de l'équipe
Dorea **écoute la pièce** — il n'a besoin ni de Whisper, ni de `decider()`, ni d'une synthèse.

Les tables des étapes 2 à 4 sont définies ici quand même : les définir maintenant coûte zéro
— aucune ligne n'existe — et les définir plus tard coûterait une reprise.

⚠️ **Ce que ce schéma ne porte pas encore.** *La pièce* n'a pas de table. Elle en aura besoin
d'une — ses bornes dans la capture, son titre, son état, sa date de publication — et
`urim_reflection.capture_id`, unique et non nul (§6), interdit aujourd'hui qu'un même dimanche
en produise deux. C'est le premier travail de schéma que D24 appelle.

---

## 2. `urim_capture` — l'enregistrement d'un culte

```sql
CREATE TABLE urim_capture (
    id               uuid PRIMARY KEY,
    church_id        uuid NOT NULL,          -- uuid nu, jamais de FK (§3.9)
    author_id        uuid NOT NULL,          -- le prédicateur ; l'archive le suit
    -- « On peut prêcher sans avoir préparé » : le lien est facultatif, comme
    -- `preached.preparation_id`. Une capture sans préparation reste un transcript utile.
    preparation_id   uuid,
    preached_on      date NOT NULL,
    service_timezone text NOT NULL,          -- un dimanche est local, pas UTC

    -- §4 : « `provider` et `model_ref` sont stockés PAR TRANSCRIPT. Sans eux, impossible de
    -- savoir plus tard pourquoi certains dimanches sont mauvais. » Le fournisseur est
    -- remplaçable, et la question des langues locales n'est pas instruite.
    provider         text,
    model_ref        text,

    -- §8 : la purge est un travail planifié, pas une option d'administration.
    audio_purge_at   timestamptz NOT NULL,
    audio_purged_at  timestamptz,

    -- §3 : « un travail abandonné laisse le transcript en `partiel` — jamais un silence.
    -- Le pasteur voit ce qui a échoué. »
    state            text NOT NULL CHECK (state IN
                       ('captée','transcrite','partielle','échouée')),

    -- §9 : « la capture n'est JAMAIS refusée. » Plafond atteint, l'enregistrement a lieu et
    -- l'audio est conservé ; la transcription est différée. Ce qui n'est pas capté dimanche est
    -- perdu pour toujours ; un transcript peut attendre lundi.
    transcription_deferred boolean NOT NULL DEFAULT false,

    created_at       timestamptz NOT NULL
);
CREATE INDEX capture_auteur ON urim_capture (author_id, preached_on DESC);
CREATE INDEX capture_a_purger ON urim_capture (audio_purge_at)
    WHERE audio_purged_at IS NULL;
```

> **`audio_purged_at` plutôt qu'un booléen `audio_purged`.** La spec dit « marque `audio_purged` » ;
> une date dit la même chose *et* quand. Sur une donnée qu'on détruit pour tenir une promesse de
> confidentialité, savoir *quand* elle a disparu est ce qu'on voudra prouver.

---

## 3. `urim_capture_job` — la file de travaux

Reprise telle quelle de la spec §3, préfixée et sans FK inter-contexte.

```sql
CREATE TABLE urim_capture_job (
    id              uuid PRIMARY KEY,
    capture_id      uuid NOT NULL,           -- même contexte : la FK serait licite, mais on
                                             -- garde l'intégrité applicative partout (§3.9)
    kind            text NOT NULL CHECK (kind IN
                      ('transcrire','extraire_versets','aligner','purger_audio')),
    state           text NOT NULL CHECK (state IN
                      ('en_attente','en_cours','fait','echoue','abandonne')),
    attempts        smallint NOT NULL DEFAULT 0,
    not_before      timestamptz NOT NULL DEFAULT now(),
    locked_until    timestamptz,
    last_error      text,
    idempotency_key text NOT NULL UNIQUE
);
CREATE INDEX job_a_prendre ON urim_capture_job (state, not_before)
    WHERE state = 'en_attente';
```

**Aucune infrastructure nouvelle** : la file vit en table Postgres. La prise de travail utilise
`FOR UPDATE SKIP LOCKED`, la reprise est exponentielle, et l'abandon survient après **5 tentatives**
avec `last_error` conservé.

---

## 4. `urim_transcript_segment` — ce qui a été dit

```sql
CREATE TABLE urim_transcript_segment (
    capture_id  uuid NOT NULL,
    ordinal     integer NOT NULL,            -- l'ordre du flux ; les `segment_refs` de la
                                             -- synthèse pointent dessus (§10.2)
    body        text NOT NULL,
    started_ms  integer NOT NULL,            -- §4 : texte, ms début/fin, confiance
    ended_ms    integer NOT NULL,
    confidence  real NOT NULL,
    PRIMARY KEY (capture_id, ordinal),
    CONSTRAINT segment_borne CHECK (ended_ms >= started_ms)
);
```

> `confidence` porte le contrôle de **couverture** de §10.5 : *« plus de 30 % des segments sources
> sous le seuil ⇒ aucune synthèse »*. Sans cette colonne, ce garde-fou est inécrivable — et c'est
> le seul des quatre contrôles qui protège contre un transcript globalement mauvais plutôt que
> contre une phrase isolée.

---

## 5. `urim_cited_verse` — les versets réellement convoqués

```sql
CREATE TABLE urim_cited_verse (
    id           uuid PRIMARY KEY,
    capture_id   uuid NOT NULL,
    book_id      smallint NOT NULL,          -- vers le corpus : uuid/entier nu, jamais de FK
    chapter      smallint NOT NULL,
    verse_start  smallint,
    verse_end    smallint,

    -- §5 : deux détecteurs aux propriétés opposées — la référence énoncée est PRÉCISE,
    -- la citation reconnue apporte le RAPPEL. Une même citation vue par les deux est
    -- consolidée (§5.3), et l'origine reste tracée : elle dira laquelle des deux voies
    -- se dégrade quand les mesures arriveront.
    detected_by  text NOT NULL CHECK (detected_by IN ('enoncee','reconnue','fusionnee')),
    confidence   real NOT NULL,
    segment_ordinal integer NOT NULL,        -- où, dans le flux — sert l'alignement (§6)

    -- §5.3 : « c'est LE SIGNAL INTÉRESSANT — les textes convoqués sans avoir été prévus. »
    -- Calculé par différence déterministe avec la préparation, JAMAIS par le modèle (§10.1).
    -- NULL quand il n'y avait pas de préparation : on ne compare pas à rien.
    was_prepared boolean
);
CREATE INDEX cited_verse_capture ON urim_cited_verse (capture_id, segment_ordinal);
CREATE INDEX cited_verse_passage ON urim_cited_verse (book_id, chapter);
```

> **Ce qui n'atteint pas le seuil n'entre pas.** §5.3 : *« sous le seuil, on n'écrit rien — un
> verset faussement attribué corrompt la couverture du canon, qui est l'usage final. Mieux vaut
> manquer une citation que d'en inventer une. »* Filtrer **avant** d'écrire, jamais stocker puis
> filtrer — le même patron que le `HAVING >= 5` des agrégats de veille.

---

## 6. `urim_reflection` — le Retour

```sql
CREATE TABLE urim_reflection (
    id              uuid PRIMARY KEY,
    capture_id      uuid NOT NULL UNIQUE,    -- un Retour par culte
    author_id       uuid NOT NULL,

    -- La comparaison préparé / prêché. §10.1 : « elle n'est JAMAIS faite par le modèle. Elle est
    -- calculée après coup, par différence déterministe, sur des données factuelles : versets
    -- cités, horodatages, ancres repérées. »
    prepared_verses integer NOT NULL DEFAULT 0,
    cited_verses    integer NOT NULL DEFAULT 0,
    unprepared      integer NOT NULL DEFAULT 0,   -- convoqués sans avoir été prévus
    unspoken        integer NOT NULL DEFAULT 0,   -- prévus et jamais cités

    -- §10.2 : sortie structurée, `segment_refs` non vide, vérifiée avant écriture. NULL tant que
    -- l'étape 4 n'a pas tourné — et elle ne tournera pas avant la mesure sur trois églises.
    synthesis       jsonb,

    -- §10.6 : « la synthèse est une PROPOSITION, pas un compte rendu. » Tant qu'elle n'est pas
    -- validée par son auteur, l'interface la distingue visuellement du transcript. Après
    -- validation elle devient sa parole — et il a pu la corriger.
    synthesis_state text CHECK (synthesis_state IN ('proposee','validee','rejetee')),
    validated_by    uuid,
    validated_at    timestamptz,

    computed_at     timestamptz NOT NULL,
    CONSTRAINT synthese_validee_signee CHECK (
        synthesis_state IS DISTINCT FROM 'validee'
        OR (validated_by IS NOT NULL AND validated_at IS NOT NULL)
    )
);
```

> **La contrainte `synthese_validee_signee` n'est pas dans la spec — je l'ajoute.** §10.6 dit
> « après validation, elle devient sa parole ». Une synthèse `validee` sans `validated_by` serait
> exactement le contraire : une parole attribuée à quelqu'un que personne n'a signée. C'est le même
> raisonnement que `reviewed_by NOT NULL` côté corpus, et que S39 sur la faisabilité.

---

## 7. Ce que ce schéma rend impossible

| Interdit | Comment il tient |
| :-- | :-- |
| Un verset inventé dans la synthèse | les références viennent **exclusivement** de `urim_cited_verse` (§10.4) — le modèle n'en produit aucune |
| Une synthèse sans provenance | `segment_refs` non vide, vérifié **avant** écriture, pas promis dans un prompt |
| Un audio qui survit à son échéance | `capture_a_purger` + un travail planifié qui **échoue bruyamment** |
| Une comparaison faite par le modèle | les quatre compteurs de `reflection` sont calculés par différence, et le modèle **ne voit jamais la préparation** — mur gardé par `FORBIDDEN_IN_MODEL_PROMPT` |
| Une capture refusée au plafond | `transcription_deferred` : l'enregistrement a toujours lieu |

---

## 8. Ce qui reste ouvert

- **Les langues locales** — dioula, baoulé, nouchi. §4 le dit : c'est *« le facteur limitant
  probable »*, et l'architecture ne parie sur aucun fournisseur avant que le terrain ait tranché ;
- **L'analyseur de nombres en toutes lettres** (S30) — « Romains chapitre huit, verset quinze » et
  les références relatives (« au verset dix-sept »). Machinerie neuve, distincte de la table
  d'abréviations écrites, et le normaliseur partagé en devient critique : trois flux en dépendent ;
- **Le seuil de consolidation** de §5.3 — un pari à calibrer sur du réel, comme tous les autres.
