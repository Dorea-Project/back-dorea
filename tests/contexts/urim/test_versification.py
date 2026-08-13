"""Où un second témoin range une référence — et **quand il faut répondre rien**.

Les traductions ne numérotent pas pareil, et l'écart ne se voit pas : « Exode 7:26 » est une
référence parfaitement formée dans les deux schémas. Servir le verset 7:26 d'Ostervald sous cette
référence rendrait un texte juste sous un numéro faux, ou pire — chez Martin, Ézéchiel 43:27
porte deux versets fondus, dont un qui n'a rien à faire là.

C'est la seule faute que ce corpus refuse : **du mauvais texte sous la bonne référence**. Ne rien
rendre se voit, se dit au pasteur, et n'enseigne rien de faux.

Les cas d'ici sont ceux qui existent réellement en base — semés, cartographiés et vérifiés — et
non des exemples inventés pour la démonstration.
"""

from __future__ import annotations

from uuid import uuid4

from app.contexts.urim.infrastructure.corpus.index import CorpusIndex, Temoin

#: Les rangs canoniques dont ces cas ont besoin.
EXODE, EZECHIEL, LUC = 2, 26, 42


def _index(**temoins: Temoin) -> CorpusIndex:
    return CorpusIndex(
        snapshot="essai", fallback_version_id=uuid4(), metered_versions=frozenset(),
        books_by_form={}, forms_by_length=(), label_by_book={}, book_by_label={},
        osis_by_book={}, chapters_held={}, max_verse_held={}, idf={}, verses=(),
        postings={}, pericopes=(), bearings={}, caveats={}, notes={}, couples={},
        dominant={}, temoins=temoins,
    )


def test_identite_quand_le_temoin_tient_le_verset():
    """Le cas ordinaire, et il reste le cas ordinaire : la table est forcément partielle."""
    index = _index(OST=Temoin("OST", {(EXODE, 7): frozenset({1, 2, 3})}, {}))

    assert index.reference_chez("OST", EXODE, 7, 2) == (7, 2)


def test_la_correspondance_l_emporte_sur_l_identite():
    """Exode 7:26 de la Segond est en 8:1 chez Ostervald — le décrochage hébreu/latin."""
    index = _index(OST=Temoin(
        "OST",
        {(EXODE, 7): frozenset(range(1, 26)), (EXODE, 8): frozenset(range(1, 33))},
        {(EXODE, 7, 26): (8, 1)},
    ))

    assert index.reference_chez("OST", EXODE, 7, 26) == (8, 1)


def test_rien_quand_le_temoin_ne_tient_pas_le_verset():
    """Luc 10:42 n'a pas de cible en Ostervald : le verset y est fondu dans le 41.

    Aucune correspondance ne pouvait être écrite — la fusion ne se cartographie pas — et
    l'identité rendrait un 10:42 qui n'existe pas. C'est **rien** qu'il faut répondre."""
    index = _index(OST=Temoin("OST", {(LUC, 10): frozenset(range(1, 42))}, {}))

    assert index.reference_chez("OST", LUC, 10, 42) is None


def test_une_correspondance_vers_un_verset_absent_ne_vaut_pas_mieux():
    """La table propose, le texte tenu tranche — pour la table comme pour l'identité.

    Une correspondance qui pointe à côté est une table fausse, pas une permission de servir."""
    index = _index(OST=Temoin(
        "OST", {(EXODE, 8): frozenset({1, 2})}, {(EXODE, 7, 26): (8, 99)},
    ))

    assert index.reference_chez("OST", EXODE, 7, 26) is None


def test_le_verset_fondu_de_martin_ne_rend_pas_le_texte_du_voisin():
    """🔴 Ézéchiel 43:27 EXISTE chez Martin, et y porte le 25 recollé devant le 27.

    C'est le cas le plus dangereux du corpus, parce que l'identité y « marche » : elle trouve un
    verset et rend du texte. Le 25 n'ayant pas de correspondance — la fusion est en désordre,
    aucun marqueur ne dit où couper — la seule réponse honnête à « Ézéchiel 43:25 en Martin »
    est le silence."""
    index = _index(MARTIN=Temoin(
        "MARTIN",
        {(EZECHIEL, 43): frozenset([*range(1, 25), 26, 27])},
        {},
    ))

    assert index.reference_chez("MARTIN", EZECHIEL, 43, 25) is None
    # Le 26 et le 27, eux, sont bien à leur place et doivent le rester.
    assert index.reference_chez("MARTIN", EZECHIEL, 43, 26) == (43, 26)


def test_un_temoin_inconnu_ne_se_devine_pas():
    """Demander une version qui n'est pas semée n'est pas une raison d'en servir une autre."""
    index = _index(OST=Temoin("OST", {(EXODE, 7): frozenset({1})}, {}))

    assert index.reference_chez("VULGATE", EXODE, 7, 1) is None
