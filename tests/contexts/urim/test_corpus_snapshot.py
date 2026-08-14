"""L'empreinte du corpus — **ce qu'elle doit voir, et ce qu'elle ne doit pas inventer**.

`corpus_snapshot` est la clé du déterminisme : elle décide si `corpus_drifted` se lève. Deux
façons de la trahir, et il faut les deux tests, parce qu'elles se corrigent en sens contraire —
resserrer contre la première relâche la seconde :

    manquer une dérive    on croit relire, on recalcule
    en inventer une       le drapeau se leve sans raison, et on apprend a l'ignorer
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.contexts.urim.infrastructure.corpus.index import _condense, _empreinte

RELECTURE = datetime(2026, 8, 6, tzinfo=UTC)

#: Un corpus de référence, décrit par ce que le chargeur en tire. Les comptes sont **figés** :
#: c'est tout l'objet des tests qui suivent que de les laisser identiques.
SOCLE = {
    "versions": ("DARBY", "LSG"),
    "n_verses": 31170,
    "n_pericopes": 4561,
    "n_bearings": 45557,
    "derniere_relecture": RELECTURE,
}

TEXTE = _condense(["1:1:1 au commencement dieu crea", "19:37:31 la loi de son c ur"])
LEXIQUE = _condense(["c=3.608", "loi=4.2", "ur=3.57"])


def test_une_renormalisation_se_voit_alors_que_tous_les_comptes_tiennent():
    """🔴 La panne que cette empreinte n'attrapait pas.

    Rendre `cœur` au mot qu'une ligature coupait réécrit le texte sans toucher un seul compte :
    même nombre de versions, de versets, de péricopes, de pesées, même date de relecture. La
    dérive était donc invisible **exactement là où elle compte** — le texte contre lequel le
    moteur apparie."""
    avant = _empreinte(**SOCLE, texte=TEXTE, lexique=LEXIQUE)
    apres = _empreinte(
        **SOCLE,
        texte=_condense(["1:1:1 au commencement dieu crea", "19:37:31 la loi de son coeur"]),
        lexique=LEXIQUE,
    )
    assert avant != apres


def test_refaire_la_balance_seule_se_voit_aussi():
    """L'appariement lit le texte **et** le pèse. Un lissage changé, un lexique élargi, et le
    verset qui sort en tête change sans qu'un caractère du texte ne bouge."""
    assert _empreinte(**SOCLE, texte=TEXTE, lexique=LEXIQUE) != _empreinte(
        **SOCLE, texte=TEXTE, lexique=_condense(["c=9.9", "loi=4.2", "ur=3.57"])
    )


def test_le_meme_corpus_rend_la_meme_empreinte():
    """⚠️ Le test jumeau, et le plus important des deux.

    Un drapeau de dérive qui se lève sans raison apprend à ne plus le regarder. C'est pourquoi
    le chargeur ordonne sa requête de versets et trie l'idf : sans ça, l'empreinte suivrait le
    plan d'exécution de la base."""
    assert _empreinte(**SOCLE, texte=TEXTE, lexique=LEXIQUE) == _empreinte(
        **SOCLE, texte=TEXTE, lexique=LEXIQUE
    )


def test_la_frontiere_entre_deux_morceaux_compte():
    """Sans séparateur, deux découpages du même flux se confondraient — et deux versets dont
    l'un finit par ce que l'autre commence rendraient la même empreinte."""
    assert _condense(["ab", "c"]) != _condense(["a", "bc"])
    assert _condense(["ab", "c"]) != _condense(["abc"])
