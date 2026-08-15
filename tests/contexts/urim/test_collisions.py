"""Le détecteur de collisions — **et surtout ce qu'il refuse de dire**.

Ce fichier garde deux choses de nature différente.

**Les prises qui ont coûté cher.** Chaque cas nommé ici correspond à une famille de faux
signaux découverte en lisant les prises, jamais en relisant le code : le nom propre au plafond
de l'IDF, l'article élidé qui déplaçait la majuscule, le témoin qui reformule et qu'on comptait
pour un accord. Les remettre en test, c'est empêcher qu'un futur assouplissement les ramène sans
qu'on s'en aperçoive — ils ne se voient qu'à la relecture, et personne ne relit deux fois.

**La frontière que ce module ne doit jamais franchir.** Une collision n'est pas une variante
textuelle. C'est la seule chose qui rendrait cette fonctionnalité nuisible : un pasteur qui
affirme en chaire, sur la foi de cet écran, qu'un manuscrit porte autre chose. La distinction ne
peut pas rester dans une docstring — `test_aucune_phrase_ne_parle_de_manuscrits` la rend
exécutable, sur le patron des tests de vocabulaire du dépôt.
"""

from difflib import SequenceMatcher

from scripts.urim_collisions import (
    FORMES,
    PROXIMITE_GRAPHIQUE,
    _apparie,
    _ecart,
    _empreinte,
    _forme,
    _mots,
    _nom_propre,
    detecter,
)

from app.contexts.urim.application.ports import CollisionSeen, WitnessRead
from app.contexts.urim.interface.schemas import (
    _CE_QUE_LA_FORME_DIT,
    CollisionView,
)

#: Un lexique minuscule : chaque mot y pèse, la valeur exacte n'a d'importance que pour l'ordre.
POIDS = {
    "dieu": 1.0, "appela": 4.0, "le": 0.5, "sec": 6.0, "terre": 3.0, "lamas": 9.0,
    "des": 0.5, "eaux": 5.0, "mers": 7.0, "vit": 4.0, "que": 0.5, "cela": 2.0,
    "etait": 1.0, "bon": 3.0, "rassemblement": 8.0, "nomma": 4.5, "et": 0.2,
    "il": 0.3, "ciel": 5.0, "jour": 2.0,
}


def _verset(texte: str) -> tuple[str, str]:
    """`(corps, norme)` — la normalisation est ici triviale, les textes sont écrits normalisés."""
    return texte, texte.lower()


# --------------------------------------------------------------- la répartition, jamais la cause


def test_un_seul_temoin_qui_parle_ne_rend_jamais_la_segond_seule():
    """🔴 Le piège de la lecture à quatre, et il est en français avant d'être en code.

    Si Darby diverge et que les deux autres se taisent, il est **littéralement** vrai que tous
    ceux qui se sont prononcés divergent. Mais « la Segond est seule à lire ce mot » se lit
    comme *trois traducteurs contre elle* — sur la foi d'un seul. La liste des muets voyage
    avec la ligne, et la forme reste `temoin_isole`."""
    assert _forme(("DARBY",), ("DARBY",)) == "temoin_isole"
    assert _forme(("DARBY", "OST", "MARTIN"), ("DARBY", "OST", "MARTIN")) == "segond_seule"
    assert _forme(("DARBY",), ("DARBY", "OST", "MARTIN")) == "temoin_isole"
    assert _forme(("OST", "MARTIN"), ("DARBY", "OST", "MARTIN")) == "partage"


def test_les_formes_ne_nomment_qu_une_repartition():
    """Aucune des trois ne désigne une cause — ni édition, ni style, ni époque.

    Il a existé ici une quatrième forme, `ligne_des_editions`, tombée sur la mesure : « Darby
    seul » dans le Nouveau Testament rend surtout *« aisé »* contre *« facile »*, et la vraie
    ligne des familles sépare {Segond, Darby} de {Ostervald, Martin}. Une forme qui explique
    est une forme qui peut se tromper ; celles-ci décrivent."""
    assert set(FORMES) == {"temoin_isole", "partage", "segond_seule"}


# ------------------------------------------------------------------ le deuxième artefact, la fin


def test_le_nom_propre_au_milieu_d_une_phrase_est_ecarte():
    """*Hakkots*, *Achrach*, *Olympe* : les mots rares de la Bible sont massivement des noms.

    Ils occupent exactement le plafond de l'IDF, c'est-à-dire la zone que le seuil retient —
    environ deux prises sur dix en étaient. La majuscule les distingue sans qu'on ait à tenir
    une liste, qui serait fausse au premier toponyme ajouté par un traducteur."""
    assert _nom_propre("hakkots", "le septième, à Hakkots ; le huitième, à Abija ;")
    assert _nom_propre("olympe", "Saluez Philologue et Julie, Nérée, Olympe et les saints.")


def test_l_article_elide_ne_cache_pas_la_majuscule():
    """`d'Ijjé-Abarim` se normalise en `dijje` : la majuscule n'est plus en tête.

    Sans le retrait de l'élision, le mot paraissait commencer par une minuscule et le nom propre
    passait le filtre. C'est le normaliseur partagé qui colle l'article au mot (S21) — un choix
    juste, dont il fallait tenir compte ici plutôt que le contourner."""
    assert _nom_propre("dijje", "Ils partirent d\u2019Ijjé-Abarim, et campèrent à Dibon-Gad.")
    assert _nom_propre("dacharchel", "et les familles d\u2019Acharchel, fils d\u2019Harum.")


def test_un_mot_en_tete_de_phrase_ne_conclut_rien():
    """« Nommons un chef » est une vraie collision, « Nocha le quatrième » un nom propre.

    La position ne les sépare pas, et rien d'autre ne le fait. Le doute profite donc à la prise :
    on préfère un nom propre de trop, qui se voit en relisant, à une collision perdue, qui ne se
    voit jamais."""
    assert not _nom_propre(
        "nommons",
        "Et ils se dirent l\u2019un à l\u2019autre : Nommons un chef, et retournons en Égypte.",
    )
    assert not _nom_propre(
        "lamas", "Dieu appela le sec terre, et il appela l\u2019amas des eaux mers."
    )


def test_les_noms_divins_ne_sont_pas_atteints_par_ce_filtre():
    """« Dieu », « l'Éternel », « l'Esprit » sont capitalisés — et hors de portée du seuil.

    Le filtre les qualifierait de noms propres, ce qui est d'ailleurs vrai ; il ne les rencontre
    jamais, parce que leur poids est très en dessous de la zone retenue. La propriété tient par
    la fréquence, pas par une exception — une exception aurait été une liste à tenir."""
    assert _nom_propre("leternel", "Et Josué vainquit Amalek, au tranchant de l\u2019Éternel.")
    assert POIDS["dieu"] < POIDS["lamas"]  # le poids, pas une liste d'exceptions


def test_la_borne_de_longueur_ne_change_aucun_resultat():
    """L'accélération de `_apparie` est une **borne**, pas une approximation.

    Le ratio de `SequenceMatcher` vaut `2·M / T`, où `M` — le nombre de caractères appariés —
    ne peut pas dépasser la longueur du plus court des deux mots. Un couple qui échoue à cette
    borne ne pouvait pas atteindre le seuil. La distinction compte : une heuristique se
    justifierait par des mesures et pourrait mordre un jour sur une vraie graphie, une borne
    ne le peut pas — et c'est ce que ce test vérifie plutôt que de le supposer."""
    complet = [
        ("leschem", {"leshem"}), ("kirjath", {"kiriath"}), ("core", {"kore"}),
        ("lamas", {"rassemblement"}), ("fade", {"insipide"}), ("aise", {"facile"}),
        ("consacrerent", {"sanctifierent"}), ("obeirons", {"ecouterons", "servirons"}),
        ("a", {"abcdefghij"}), ("dieu", {"dieux", "adieu", "lieu"}),
    ]
    for mot, autres in complet:
        attendu = any(
            SequenceMatcher(None, mot, autre).ratio() >= PROXIMITE_GRAPHIQUE
            for autre in autres
        )
        assert _apparie(mot, autres) is attendu, mot


# --------------------------------------------------------- le silence est une valeur, pas un vide


def test_une_reformulation_fait_abstenir_le_temoin():
    """Le quatrième artefact, déplacé : il n'écarte plus le verset, il fait taire le témoin.

    Quand un traducteur refait la phrase entière, l'absence d'un mot chez lui ne veut rien dire
    — ce n'est pas une lecture différente, c'est une autre phrase. `None` veut dire *« il ne se
    prononce pas »*, et c'est ce qui empêche « un seul diverge » de devenir « la Segond est
    seule »."""
    segond = "dieu appela le sec terre et il appela lamas des eaux mers"
    reformule = "et dieu nomma le sec terre et le rassemblement des eaux il appela mers jour"
    assert _ecart(_mots(segond, POIDS), _mots(reformule, POIDS)) is None


def test_deux_versets_sans_rapport_ne_se_comparent_pas():
    """Le premier artefact : la divergence maximale visait à l'envers.

    1 Chroniques 6:4 rendait « Éléazar engendra Phinées » d'un côté et « Les fils de Merari » de
    l'autre — deux textes sans rapport sous la même référence, et le désaccord le plus lourd du
    corpus. Un recouvrement minimum est la preuve, exigée **avant** de peser quoi que ce soit,
    qu'on tient bien le même verset."""
    assert _ecart(
        _mots("dieu appela le sec terre et il appela lamas des eaux mers", POIDS),
        _mots("jour ciel bon cela etait vit que terre", POIDS),
    ) is None


def test_une_substitution_propre_nomme_les_deux_cotes():
    """*« l'amas »* contre *« rassemblement »* : un mot pour un mot, et rien d'autre ne bouge."""
    perdus, gagnes = _ecart(
        _mots("dieu appela le sec terre et il appela lamas des eaux mers", POIDS),
        _mots("dieu appela le sec terre et il appela rassemblement des eaux mers", POIDS),
    )
    assert perdus == {"lamas"}
    assert gagnes == {"rassemblement"}


# ------------------------------------------------------------------------ le détecteur en entier


def _corpus(darby: str, ost: str, martin: str) -> dict:
    segond = "Dieu appela le sec terre, et il appela lamas des eaux mers"
    return {
        "LSG": {(1, 1, 10): _verset(segond)},
        "DARBY": {(1, 1, 10): _verset(darby)},
        "OST": {(1, 1, 10): _verset(ost)},
        "MARTIN": {(1, 1, 10): _verset(martin)},
    }


def test_un_temoin_muet_ne_compte_pas_pour_un_accord():
    """La propriété que la lecture à quatre existe pour tenir.

    Ostervald reformule, Martin ne tient pas le verset : ni l'un ni l'autre ne dit ce qu'il lit.
    Compter leur silence comme un accord donnerait *« un seul traducteur diverge »*, c'est-à-dire
    la conclusion inverse de ce qui a été observé."""
    textes = _corpus(
        darby="Dieu appela le sec terre, et il appela rassemblement des eaux mers",
        ost="et dieu nomma le sec terre le rassemblement des eaux il appela mers jour",
        martin="",
    )
    textes["MARTIN"] = {}
    renvoi = {code: {} for code in ("DARBY", "OST", "MARTIN")}

    [collision] = detecter(POIDS, renvoi, textes, ("DARBY", "MARTIN", "OST"))
    assert collision.mot == "lamas"
    assert collision.forme == "temoin_isole"
    assert collision.divergents == ("DARBY",)
    assert set(collision.muets) == {"OST", "MARTIN"}


def test_la_lecture_n_est_nommee_que_si_l_appariement_est_propre():
    """🔴 La prise qui a fait tomber le premier prototype.

    Il affirmait que Martin lisait *« donc »* là où la Segond porte *« Habazinia »* : l'écart
    comptait un mot de chaque côté, donc l'appariement paraissait certain — et le mot gagné
    n'avait aucun rapport. Ici, Ostervald perd **deux** mots d'un coup et n'en gagne aucun :
    rien ne dit ce qui a remplacé quoi, donc rien n'est nommé, et c'est le verset entier qui
    parle."""
    textes = _corpus(
        darby="Dieu appela le sec terre, et il appela rassemblement des eaux mers",
        ost="Dieu appela le sec terre, et il appela des eaux",
        martin="Dieu appela le sec terre, et il appela lamas des eaux mers",
    )
    renvoi = {code: {} for code in ("DARBY", "OST", "MARTIN")}

    [collision] = detecter(POIDS, renvoi, textes, ("DARBY", "MARTIN", "OST"))
    lectures = {le.code: le for le in collision.lectures}
    assert lectures["DARBY"].reading == "rassemblement"
    assert lectures["OST"].stance == "diverge"
    assert lectures["OST"].reading is None       # deux mots perdus : on ne devine pas
    assert lectures["MARTIN"].stance == "accorde"
    assert collision.forme == "partage"


def test_la_versification_est_appliquee():
    """Sans elle, le Psautier entier ressortirait — Martin ne numérote pas les suscriptions.

    Le premier signal aurait alors été du bruit pur sur le livre le plus prêché de la Bible."""
    textes = _corpus(
        darby="Dieu appela le sec terre, et il appela lamas des eaux mers",
        ost="Dieu appela le sec terre, et il appela lamas des eaux mers",
        martin="Dieu appela le sec terre, et il appela lamas des eaux mers",
    )
    # Martin range ce verset un cran plus loin, et n'a rien sous le numéro de la Segond.
    textes["MARTIN"] = {
        (1, 1, 11): _verset("Dieu appela le sec terre, et il appela rassemblement des eaux mers")
    }
    renvoi = {"DARBY": {}, "OST": {}, "MARTIN": {(1, 1, 10): (1, 11)}}

    [collision] = detecter(POIDS, renvoi, textes, ("DARBY", "MARTIN", "OST"))
    assert collision.divergents == ("MARTIN",)  # trouvé là où la carte l'envoie


def test_un_fragment_d_elision_n_est_pas_un_mot():
    """🔴 Le cinquième artefact, trouvé en relisant les 221 retenues.

    Deux d'entre elles portaient un mot d'une seule lettre — *« le pays d'Égypte **n'**
    échappera point »*, *« un agneau **d'** un an »*. La source laisse par endroits une espace
    après l'apostrophe ; le normaliseur, qui colle l'élision au mot suivant, n'a alors rien à
    quoi la coller et rend `n` ou `d`. Un fragment qui ne paraît nulle part ailleurs se
    retrouve au plafond de l'IDF, c'est-à-dire dans la zone que le seuil retient."""
    poids = {**POIDS, "n": 10.0, "echappera": 6.0, "pays": 3.0, "point": 2.0, "pas": 2.0}
    segond = "il etendra sa main le pays degypte n echappera point"
    textes = {
        "LSG": {(27, 11, 42): (segond, segond)},
        "DARBY": {(27, 11, 42): _verset("il etendra sa main le pays degypte nechappera pas")},
        "OST": {},
        "MARTIN": {},
    }
    renvoi = {code: {} for code in ("DARBY", "OST", "MARTIN")}

    assert detecter(poids, renvoi, textes, ("DARBY", "MARTIN", "OST")) == []


def test_aucune_collision_quand_tout_le_monde_lit_pareil():
    textes = _corpus(
        darby="Dieu appela le sec terre, et il appela lamas des eaux mers",
        ost="Dieu appela le sec terre, et il appela lamas des eaux mers",
        martin="Dieu appela le sec terre, et il appela lamas des eaux mers",
    )
    renvoi = {code: {} for code in ("DARBY", "OST", "MARTIN")}
    assert detecter(POIDS, renvoi, textes, ("DARBY", "MARTIN", "OST")) == []


# ------------------------------------------------------------------------------- la péremption


def test_l_empreinte_bouge_des_qu_un_temoin_entre():
    """Une collision dépend des versions semées : en ajouter une change **toutes** les formes.

    C'est le patron de `corpus_snapshot`, `input_hash` et `judged_fingerprint` — *une décision
    ne vaut que sur l'objet qu'elle a regardé.*"""
    trois = {"LSG": (31170, 3_000_000), "DARBY": (31167, 2_900_000)}
    quatre = {**trois, "OST": (31172, 2_950_000)}
    assert _empreinte(trois, 700) != _empreinte(quatre, 700)


def test_l_empreinte_bouge_quand_un_verset_est_recousu():
    """Une recouture ne change pas le nombre de versets — elle change leur longueur.

    C'est arrivé : une source avait mangé une séparation et servait deux versets sous un
    numéro. Les compter aurait suffi à croire le corpus inchangé."""
    avant = {"LSG": (31170, 3_000_000)}
    apres = {"LSG": (31170, 3_000_042)}
    assert _empreinte(avant, 700) != _empreinte(apres, 700)


def test_l_empreinte_bouge_quand_la_carte_de_numerotation_change():
    """La versification entre dans le calcul : elle décide de **quels versets** se comparent."""
    assert _empreinte({"LSG": (31170, 3_000_000)}, 700) != _empreinte(
        {"LSG": (31170, 3_000_000)}, 906
    )


# ------------------------------------------------- ⚠️ la frontière : jamais une variante textuelle


#: Le vocabulaire des manuscrits. Il appartient à `urim_corpus_textual_variant`, qui se remplit
#: depuis un apparat critique par un humain qui signe — et à rien d'autre.
_MOTS_DE_LA_VARIANTE = (
    "manuscrit", "variante", "texte reçu", "texte recu", "critique", "édition", "edition",
    "apparat", "original", "grec", "hébreu", "hebreu", "témoin", "temoin",
)


def test_aucune_phrase_ne_parle_de_manuscrits():
    """🔴 **Le test le plus important de ce fichier.**

    C'est la seule façon dont cette fonctionnalité pourrait nuire : un pasteur qui affirme en
    chaire, sur la foi de cet écran, qu'un manuscrit porte autre chose — devant une assemblée
    qui ne peut pas le vérifier.

    Et la tentation est réelle, parce qu'elle a l'air d'un progrès : la phrase serait plus
    frappante, l'écran paraîtrait plus savant. Elle serait fausse. Le détecteur rejette **par
    construction** ce dont une variante est faite — une proposition entière ajoutée ou retirée —
    et ne voit que des substitutions de mot, c'est-à-dire des choix de traducteur.

    Un commentaire ne tient pas cette règle : le prochain qui écrira ces phrases ne lira pas la
    docstring, il lira le dictionnaire juste au-dessus."""
    for forme, phrase in _CE_QUE_LA_FORME_DIT.items():
        assert phrase, forme
        for interdit in _MOTS_DE_LA_VARIANTE:
            assert interdit not in phrase.lower(), f"{forme} : « {interdit} »"


def test_chaque_forme_a_sa_phrase_et_chaque_ligne_porte_son_rappel():
    """La phrase vient du serveur — le client n'en écrit jamais une de sa propre autorité.

    C'est le contrat conversationnel du produit, et il vaut ici plus qu'ailleurs : une
    formulation écrite côté Flutter échapperait à la relecture, aux tests, et au test
    ci-dessus."""
    assert set(_CE_QUE_LA_FORME_DIT) == set(FORMES)

    vue = CollisionView.from_dto(CollisionSeen(
        reference="Genèse 1:10", word="lamas", form="temoin_isole",
        witnesses=(
            WitnessRead("LSG", "Segond 1910", "eclectique", "accorde", None, "…l\u2019amas…"),
            WitnessRead("DARBY", "Darby", "critique", "diverge", "rassemblement", "…le ras…"),
            WitnessRead("MARTIN", "Martin 1744", "texte_recu", "muet", None, ""),
        ),
    ))
    assert vue.says == _CE_QUE_LA_FORME_DIT["temoin_isole"]
    assert "pas une variante des manuscrits" in vue.caution
    assert [w.stance for w in vue.witnesses] == ["accorde", "diverge", "muet"]


def test_aucun_poids_ne_sort_vers_le_pasteur():
    """Un chiffre à côté d'un verset se lit comme une note, et rien ici n'est noté.

    Le poids a servi à choisir ce qui s'affiche ; il n'a rien à dire au pasteur, qui n'a aucun
    moyen de savoir ce que « 10,35 » vaudrait. Même raison que l'absence de compteur dans les
    motifs du plafond."""
    champs = set(CollisionView.model_fields)
    assert not champs & {"weight", "poids", "score", "centile", "rank"}
