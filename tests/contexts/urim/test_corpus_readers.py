"""Ce que le corpus répond — et surtout **comment il distingue citer d'employer les mots**.

`scripture_affinity` est le seul chiffre qui décide du chemin d'entrée : au-dessus du seuil
la saisie part en citation, en dessous en conviction. Deux mesures plausibles y ont échoué
avant celle-ci, et les deux échecs sont gardés ici — parce qu'un jour quelqu'un trouvera
que le rappel serait « plus simple ».
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from uuid import uuid4

from app.contexts.urim.engine.normalizer import normalize, tokens
from app.contexts.urim.engine.state import Reference
from app.contexts.urim.infrastructure.corpus.index import CorpusIndex, VerseRow
from app.contexts.urim.infrastructure.corpus.readers import (
    IndexedCorpusReader,
    _plus_longue_suite,
)

#: Un corpus minuscule mais **réaliste sur le point qui compte** : les convictions y
#: trouvent tout leur vocabulaire, exactement comme dans la Bible entière. C'est cette
#: propriété-là qui a cassé la mesure précédente, pas la taille.
TEXTES: dict[tuple[str, int, int], str] = {
    ("Jean", 3, 16): (
        "Car Dieu a tant aimé le monde qu'il a donné son Fils unique, afin que quiconque "
        "croit en lui ne périsse point, mais qu'il ait la vie éternelle."
    ),
    ("Jean", 11, 35): "Jésus pleura.",
    ("Romains", 12, 10): (
        "Par amour fraternel, soyez pleins d'affection les uns pour les autres."
    ),
    ("Actes", 12, 5): (
        "Pierre donc était gardé dans la prison; et l'Église ne cessait d'adresser pour lui "
        "des prières à Dieu."
    ),
    ("Philippiens", 4, 13): "Je puis tout par celui qui me fortifie.",
    ("Luc", 19, 41): (
        "Comme il approchait de la ville, Jésus, en la voyant, pleura sur elle."
    ),
    # Un livre à **chapitre unique** — sans lui, la lecture des nombres n'est pas éprouvée.
    ("Jude", 1, 24): "Or, à celui qui peut vous préserver de toute chute...",
    ("Jude", 1, 25): (
        "à Dieu seul, notre Sauveur, par Jésus-Christ notre Seigneur, soient gloire, "
        "majesté, force et puissance, dès avant tous les temps, et maintenant, et dans "
        "tous les siècles ! Amen!"
    ),
}


def _index() -> CorpusIndex:
    """Construit un index gelé à partir de `TEXTES`, idf et postings compris."""
    livres = {
        "Jean": 43, "Romains": 45, "Actes": 44, "Philippiens": 50, "Luc": 42, "Jude": 65,
    }

    suites = {cle: tuple(normalize(corps).split()) for cle, corps in TEXTES.items()}
    df = Counter()
    for suite in suites.values():
        df.update(set(suite))
    n = len(suites)
    idf = {mot: math.log((n + 1) / freq) for mot, freq in df.items()}

    versets = tuple(
        VerseRow(
            book_id=livres[livre], chapter=ch, verse=v, body=TEXTES[(livre, ch, v)],
            tokens=frozenset(suite), sequence=suite,
            weight=sum(idf[m] for m in set(suite)),
        )
        for (livre, ch, v), suite in suites.items()
    )

    postings: dict[str, list[int]] = defaultdict(list)
    for rang, verset in enumerate(versets):
        for mot in verset.tokens:
            postings[mot].append(rang)

    tenus: dict[int, set[int]] = defaultdict(set)
    dernier: dict[tuple[int, int], int] = {}
    for verset in versets:
        tenus[verset.book_id].add(verset.chapter)
        cle = (verset.book_id, verset.chapter)
        dernier[cle] = max(dernier.get(cle, 0), verset.verse)

    return CorpusIndex(
        snapshot="essai", fallback_version_id=uuid4(), metered_versions=frozenset(),
        books_by_form={(normalize(nom),): (livre,) for nom, livre in livres.items()},
        forms_by_length=tuple((normalize(nom),) for nom in livres),
        label_by_book={livre: nom for nom, livre in livres.items()},
        book_by_label=livres,
        osis_by_book={},
        chapters_held={k: frozenset(v) for k, v in tenus.items()},
        max_verse_held=dernier,
        idf=idf, verses=versets,
        postings={m: tuple(r) for m, r in postings.items()},
        pericopes=(), bearings={}, caveats={}, notes={}, couples={}, dominant={},
    )


def _affinite(saisie: str) -> float:
    return IndexedCorpusReader(_index()).scripture_affinity(tokens(saisie))


# ================================================================ la suite contiguë, seule


def test_la_suite_contigue_rend_les_mots_pas_leur_nombre():
    """Elle rend la **suite**, parce que deux mots qui se suivent ne se valent pas.

    `jésus pleura` désigne un verset ; `le cantique` n'en désigne aucun. Compter les mots
    faisait franchir le seuil au second — il faut pouvoir les peser."""
    assert _plus_longue_suite(("a", "b", "c"), ("x", "a", "b", "c", "y")) == ("a", "b", "c")
    assert _plus_longue_suite(("a", "b", "c"), ("a", "x", "b", "x", "c")) == ("a",)
    assert _plus_longue_suite(("a", "b"), ("c", "d")) == ()


# ============================================================= le discriminant, sur du réel


def test_une_citation_exacte_atteint_un():
    assert _affinite("je puis tout par celui qui me fortifie") == 1.0


def test_une_suite_faite_d_articles_ne_fait_pas_une_citation():
    """🔴 **Le cas « Miriam chantait le cantique ».**

    Deux mots qui se suivent — `le cantique`, dans *Cantique des cantiques 1:1* — sur quatre
    faisaient 0,50 et franchissaient le seuil. Or un article ne désigne rien. Pesée par l'idf,
    la même suite tombe sous le seuil, tandis qu'une vraie citation **monte**."""
    assert _affinite("le cantique de Salomon que Miriam chantait") < 0.45


def test_un_extrait_contigu_d_un_long_verset_reste_une_citation():
    """⚠️ **Le cas qui a tué la mesure par F1.**

    Sept mots de Jean 3:16 rendaient un F1 de 0,396 — sous le seuil — parce que le verset
    est long. Citer une partie d'un verset reste citer."""
    assert _affinite("car dieu a tant aime le monde") == 1.0


def test_une_conviction_faite_de_vocabulaire_biblique_n_est_pas_une_citation():
    """⚠️ **Le cas qui a tué la mesure par rappel.**

    Chacun de ces mots est dans le corpus — `lamour`, `fraternel`, `leglise` — et le rappel
    montait à 0,640. Aucun ne suit l'autre nulle part : ce n'est pas une citation."""
    assert _affinite("lamour fraternel nexiiste plus dans leglise") < 0.45


def test_une_faute_de_frappe_ne_fait_pas_perdre_la_citation():
    """La suite se rompt sur le mot fauté, pas avant. « Car Dieu a tant » suffit encore."""
    assert _affinite("car dieu a tant aimer le monde") >= 0.45


def test_un_mot_isole_ne_fait_pas_une_contiguite():
    """Sans ce plancher, toute saisie d'un mot biblique passerait pour une citation.

    En cas de doute, on route vers la conviction — jamais l'inverse (S33)."""
    assert _affinite("Dieu") == 0.0
    assert _affinite("pleura") == 0.0


def test_deux_mots_qui_se_suivent_suffisent():
    """« Jésus pleura » **est** Jean 11:35 — la citation la plus courte de la Bible."""
    assert _affinite("jesus pleura") == 1.0


# ================================================================= le classement, distinct


def test_le_classement_prefere_le_verset_qui_est_la_phrase_entiere():
    """Luc 19:41 contient « Jésus » et « pleura » au milieu d'une scène ; Jean 11:35 est la
    phrase entière. Le rappel seul mettait le premier devant."""
    lecteur = IndexedCorpusReader(_index())

    premier = lecteur.resolve_citation(tokens("et jesus pleura"))[0]

    assert (premier.reference.book, premier.reference.chapter) == ("Jean", 11)


# ============================================== les livres à chapitre unique (le bug de fond)


def _refs(saisie: str):
    return IndexedCorpusReader(_index()).parse_reference_candidates(tokens(saisie))


def test_sur_un_livre_a_chapitre_unique_un_nombre_seul_est_un_verset():
    """🔴 **Le bug que seule une épreuve à froid pouvait trouver.**

    Cinq livres n'ont qu'un chapitre — Abdias, Philémon, 2 Jean, 3 Jean, Jude. « Jude 25 »
    est une référence courante ; lue comme un chapitre, elle était refusée avec un motif
    juste sur la forme et faux sur le fond (*« Jude compte 1 chapitre »*) alors que personne
    n'avait demandé de chapitre.

    Jamais attrapé tant que le corpus semé ne contenait que des livres à plusieurs
    chapitres — un jeu de données taillé sur les tests ne peut pas produire ce diagnostic."""
    (jude,) = _refs("Jude 25")

    assert (jude.chapter, jude.verse_start) == (1, 25)


def test_le_chapitre_explicite_reste_compris_sur_ces_livres():
    """« Jude 1:25 » — le 1 est bien le chapitre, il ne devient pas un verset."""
    (jude,) = _refs("Jude 1:25")

    assert (jude.chapter, jude.verse_start, jude.verse_end) == (1, 25, None)


def test_un_intervalle_reste_un_intervalle_sur_ces_livres():
    (jude,) = _refs("Jude 3-5")

    assert (jude.chapter, jude.verse_start, jude.verse_end) == (1, 3, 5)


def test_un_livre_a_plusieurs_chapitres_lit_toujours_le_premier_nombre_en_chapitre():
    """Le contre-exemple, sans quoi le correctif pourrait s'appliquer partout."""
    jean = next(r for r in _refs("Jean 3:16") if r.book == "Jean")

    assert (jean.chapter, jean.verse_start) == (3, 16)


def test_le_refus_sur_un_livre_a_chapitre_unique_ne_nomme_pas_le_chapitre():
    """Renvoyer « Jude 1 compte 25 versets » serait exact et déroutant."""
    lecteur = IndexedCorpusReader(_index())

    ecarte = lecteur.check_reference(Reference("Jude", 1, 26))

    assert ecarte.exists is False
    assert ecarte.rationale.startswith("Jude compte 25 versets")


def test_l_existence_d_un_verset_se_lit_dans_le_texte():
    """Aucune table de comptes écrite à la main — le corpus est la source."""
    lecteur = IndexedCorpusReader(_index())

    assert lecteur.check_reference(Reference("Jean", 11, 35)).exists is True
    ecarte = lecteur.check_reference(Reference("Philippiens", 4, 99))
    assert ecarte.exists is False
    assert "13 versets" in ecarte.rationale
