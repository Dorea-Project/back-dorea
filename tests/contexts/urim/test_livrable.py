"""Le livrable — **le cœur pur** : ce qui décide, avant qu'aucun fichier n'existe.

Deux propriétés, et ce sont celles dont tout le reste du module dépend.

**1. La troncature n'est pas l'altération.** C'est la correction S4, et elle est vitale : un
booléen rejetterait au même titre le pasteur qui coupe la fin d'un verset pour l'écran — donc
tout le monde — et le garde-fou mourrait de son excès de zèle, contourné par ceux qu'il protège.

**2. La frontière écran/note tient dans le TYPE.** `Deck` n'a nulle part où mettre une mise en
garde. Un filtre s'oublie à la première refonte ; un champ qui n'existe pas ne s'oublie pas.

Chaque cas présente le **couple** : ce qui passe, et sa jumelle qui ne passe pas. Une garde qui
refuse tout ne prouve rien.
"""

from __future__ import annotations

from dataclasses import fields

from app.contexts.urim.deliverable.domain.citation import (
    ALTERE,
    EXACT,
    EXTRAIT,
    juger,
    juger_parmi,
    mots,
)
from app.contexts.urim.deliverable.domain.documents import (
    ELEMENTS,
    ELEMENTS_OBSERVES,
    POINT_CENTRAL,
    Deck,
    Diapositive,
    Note,
    point_central_renseigne,
)

#: Romains 8:1 en LSG — le verset le plus piégeux du Nouveau Testament, et celui sur lequel une
#: altération d'une clause change la doctrine (S17).
ROM_8_1 = (
    "Il n'y a donc maintenant aucune condamnation pour ceux qui sont en Jésus-Christ."
)


# ============================================================ 1. troncature ≠ altération


def test_le_verset_mot_pour_mot_est_exact():
    assert juger(ROM_8_1, ROM_8_1).verdict == EXACT


def test_couper_la_fin_pour_l_ecran_est_un_extrait_legitime():
    """Le geste le plus universel de la projection. Le rejeter ferait contourner la validation
    — et une validation contournée ne protège personne."""
    verdict = juger("Il n'y a donc maintenant aucune condamnation", ROM_8_1)
    assert verdict.verdict == EXTRAIT
    assert verdict.projetable


def test_un_seul_mot_change_est_une_alteration():
    """Le couple du test précédent, et **la raison d'être du contrôle**.

    « aucune condamnation » devenu « aucune accusation » se prêche sans que personne dans
    l'assemblée n'ouvre sa Bible pour vérifier."""
    verdict = juger(
        "Il n'y a donc maintenant aucune accusation pour ceux qui sont en Jésus-Christ.",
        ROM_8_1,
    )
    assert verdict.verdict == ALTERE
    assert not verdict.projetable
    # …et le motif porte le texte servi : on dit ce que le corpus a, pas seulement « non ».
    assert "aucune condamnation" in verdict.rationale


def test_la_clause_du_texte_recu_ajoutee_est_une_alteration():
    """Le cas d'école de S17 : le Texte Reçu ajoute « qui ne marchent point selon la chair ».

    Sans la clause, « aucune condamnation » est inconditionnel ; avec elle, c'est une condition
    morale — **deux sermons opposés sur la même référence**. Une addition doit donc être vue
    comme telle, jamais absorbée comme une variante de style."""
    verdict = juger(
        ROM_8_1[:-1] + ", qui ne marchent point selon la chair.",
        ROM_8_1,
    )
    assert verdict.verdict == ALTERE


def test_l_ellipse_autorise_plusieurs_fragments_dans_l_ordre():
    verdict = juger("Il n'y a donc maintenant aucune condamnation … en Jésus-Christ.", ROM_8_1)
    assert verdict.verdict == EXTRAIT


def test_l_ellipse_n_autorise_pas_de_remonter_le_texte():
    """Le couple du précédent — et il garde une propriété qu'on perdrait sans y penser.

    Fragments dans l'**ordre** et **sans chevauchement** : sinon « … » deviendrait un jeu de
    construction permettant de composer, avec les mots du corpus, une phrase que le texte ne
    dit pas."""
    verdict = juger("en Jésus-Christ … aucune condamnation", ROM_8_1)
    assert verdict.verdict == ALTERE


def test_l_accent_oublie_sur_une_tablette_n_est_pas_une_falsification():
    """« Jesus-Christ » sans accent, tapé un vendredi soir. La comparaison porte sur des suites
    de mots repliées — exiger la typographie serait refuser le terrain."""
    saisi = ROM_8_1.replace("é", "e").replace("'", chr(0x2019))
    assert juger(saisi, ROM_8_1).verdict == EXACT


def test_la_glose_entre_crochets_ne_falsifie_pas_le_texte():
    """**Le témoin du 06/06 cite une version amplifiée** : « Jésus, se tenant debout, s'écria
    [à haute voix] : Si quelqu'un a soif ».

    Sans règle, chaque insertion casse la contiguïté et le verdict tombe à `altere` — le pasteur
    s'entendrait accuser de falsifier l'Écriture alors qu'il fait l'inverse : le crochet **dit
    lui-même** où finit le texte et où commence l'explication. À l'écran il reste visible ;
    seule la comparaison l'ignore."""
    servi = "Si quelqu'un a soif, qu'il vienne à moi, et qu'il boive."
    projete = "Si quelqu'un a soif [un besoin spirituel], qu'il vienne à moi, et qu'il boive."
    assert juger(projete, servi).verdict == EXACT


def test_la_glose_ne_couvre_pas_une_alteration_du_texte():
    """Le couple — sinon les crochets deviendraient une porte : il suffirait d'en poser autour
    d'un mot changé. Ce qui est **hors** crochets reste jugé mot pour mot."""
    servi = "Si quelqu'un a soif, qu'il vienne à moi, et qu'il boive."
    projete = "Si quelqu'un a faim [un besoin spirituel], qu'il vienne à moi, et qu'il boive."
    assert juger(projete, servi).verdict == ALTERE


def test_sans_texte_servi_on_refuse_plutot_que_de_laisser_passer():
    """Une référence dont le corpus ne rend rien ne peut pas être validée par défaut :
    affirmer sans référence serait pire que se taire."""
    assert juger("un texte quelconque", "").verdict == ALTERE


def test_une_diapositive_vide_ne_passe_pas_pour_un_extrait():
    assert juger("   ", ROM_8_1).verdict == ALTERE


def test_la_normalisation_separe_les_mots_de_l_elision():
    """`l'amour` doit valoir deux mots : c'est la granularité qui permet de voir qu'un mot a
    changé. (Le normaliseur du moteur, lui, colle l'élision — il cherche une ressemblance, pas
    une identité.)"""
    assert mots("l'amour fraternel") == ("l", "amour", "fraternel")


# ============================================================ 1 bis. toutes les versions (Q9)

#: Ce que le Texte Reçu ajoute à Romains 8:1, **qu'Ostervald porte et que la LSG omet**. Le cas
#: d'école du dépôt (S17) : sans la clause, « aucune condamnation » est inconditionnel ; avec
#: elle, c'est une condition morale. Deux sermons opposés sur la même référence.
CLAUSE = ", qui ne marchent point selon la chair, mais selon l'esprit"
ROM_8_1_OSTERVALD = ROM_8_1[:-1] + CLAUSE + "."


def test_un_texte_fidele_a_une_autre_version_detenue_n_est_pas_une_falsification():
    """**La correction de Q9**, et elle change la nature du refus.

    Jugé contre la seule LSG, ce texte rend `altere` — une accusation portée contre un pasteur
    qui cite fidèlement l'Ostervald, la version que les assemblées lisent. Jugé contre les
    versions détenues, il est reconnu, **et la version est nommée**."""
    servis = [("LSG", ROM_8_1), ("Ostervald", ROM_8_1_OSTERVALD)]
    verdict = juger_parmi(ROM_8_1_OSTERVALD, servis)
    assert verdict.verdict == EXACT
    assert verdict.version == "Ostervald"


def test_la_version_reconnue_n_est_pas_une_information_cosmetique():
    """S17 : sur ce verset, **la version détectée change la doctrine du sermon**. Le verdict la
    porte donc, et c'est elle que `citation_check.version_id` attend depuis sa déclaration."""
    servis = [("LSG", ROM_8_1), ("Ostervald", ROM_8_1_OSTERVALD)]
    assert juger_parmi(ROM_8_1, servis).version == "LSG"


def test_un_texte_qu_aucune_version_ne_porte_reste_refuse_et_les_nomme():
    """Le couple — sinon « une autre version » deviendrait la porte de sortie de n'importe quoi.

    Et le motif dit ce qui manque **au corpus** (S19) : les versions consultées, et le texte
    servi. Jamais « vous avez falsifié »."""
    servis = [("LSG", ROM_8_1), ("Ostervald", ROM_8_1_OSTERVALD)]
    verdict = juger_parmi("Il n'y a donc aucune accusation pour les croyants.", servis)
    assert verdict.verdict == ALTERE
    assert "LSG, Ostervald" in verdict.rationale
    assert verdict.version == ""


def test_exact_l_emporte_sur_extrait_quel_que_soit_l_ordre():
    """L'ordre est une préférence (la version de la préparation d'abord), pas une priorité
    absolue : mieux vaut nommer la version qui porte le texte **entier** que celle où il ne
    serait qu'un extrait."""
    servis = [("Ostervald", ROM_8_1_OSTERVALD), ("LSG", ROM_8_1)]
    assert juger_parmi(ROM_8_1, servis).version == "LSG"


def test_sans_aucune_version_servie_on_refuse():
    assert juger_parmi(ROM_8_1, []).verdict == ALTERE


# ============================================================ 2. la frontière est un type


def _champs(classe) -> set[str]:
    return {f.name for f in fields(classe)}


def test_le_deck_n_a_nulle_part_ou_mettre_une_mise_en_garde():
    """**La propriété structurelle du module.**

    Une mise en garde s'adresse au prédicateur, pas à l'assemblée. Ici ce n'est pas un filtre
    qu'on peut oublier : le type n'a aucun champ pour la porter, et une implémentation pressée
    *ne peut pas* en projeter une."""
    interdits = {
        "caveat", "caveats", "mises_en_garde", "rationale", "motif", "motifs",
        "pesees", "bearings", "proof_text_risk", "risque", "faisabilites",
        "signature", "corpus_snapshot", "ecartees",
    }
    assert _champs(Deck) & interdits == set()
    assert _champs(Diapositive) & interdits == set()


def test_la_note_distingue_le_choix_du_pasteur_du_dominant_du_corpus():
    """**Les deux ne coïncident pas toujours, et c'est l'information la plus utile.**

    Sur Actes 1:1-14, le corpus trouve la pneumatologie dominante ; le pasteur a prêché la
    christologie — et son plan entier lui donne raison. Les fondre dans une seule liste ferait
    disparaître le désaccord, or c'est là qu'il a quelque chose à décider.

    Le reste du dépôt tient déjà la distinction : l'archive range sous l'axe **retenu**, jamais
    sous le dominant calculé."""
    assert "axe_retenu" in _champs(Note)


def test_la_note_les_porte_toutes():
    """Le couple : ce que l'écran refuse, la note l'imprime — sinon la frontière ne
    protégerait rien, elle supprimerait."""
    attendus = {
        "mises_en_garde", "pesees", "faisabilites", "resistances", "ecartees",
        "signature", "corpus_snapshot", "original", "motif_unite",
    }
    assert attendus <= _champs(Note)


# ============================================================ 3. « quelque chose de lui »


def test_sans_point_central_il_n_y_a_pas_de_document():
    """Le critère n'est pas « a-t-il modifié ? » — le vérifier exigerait de lui écrire d'abord
    un brouillon, donc **le sermon à sa place**. C'est « y a-t-il quelque chose de lui ? »."""
    assert not point_central_renseigne({})
    assert not point_central_renseigne({POINT_CENTRAL: "   "})
    # Un titre ne suffit pas : c'est une étiquette, pas ce qu'il va dire.
    assert not point_central_renseigne({"titre": "L'ascension", "introduction": "…"})


def test_une_seule_division_suffit_et_on_ne_la_juge_pas():
    """Le couple. Aucune longueur minimale, aucun décompte : une machine qui jugerait la valeur
    du plan d'un prédicateur serait la machine à sermons sous un autre nom."""
    assert point_central_renseigne({POINT_CENTRAL: "1- La fin de l'œuvre de Christ sur terre."})
    assert point_central_renseigne({POINT_CENTRAL: "Les pleurs"})


def test_le_theme_ne_peut_pas_tenir_lieu_de_plan():
    """⚠️ **La raison pour laquelle le seuil n'est pas le thème** : `propose_theme` le remplit
    d'office, par gabarit fermé. Un verrou que le moteur satisfait lui-même n'en est pas un."""
    assert not point_central_renseigne({"theme": "soteriologie, en thematique doctrine"})


def test_le_seuil_accepte_les_trois_predications_reelles():
    """Les trois témoins de `docs/temoins/` — **et la première rédaction les refusait toutes**.

    Elle exigeait la `proposition` de Braga : aucune des trois n'en contient. Un verrou qui
    refuse son document aux trois pasteurs pour qui il est écrit ne protège personne — c'est le
    défaut de la chaîne de textes, qui n'avait « aucune surface où s'exercer »."""
    ascension = {"theme": "l'ascension", POINT_CENTRAL: "1- La fin de l'œuvre de Christ"}
    saint_esprit = {
        "objectif": "un retour aux fondamentaux",
        POINT_CENTRAL: "1- Si quelqu'un a soif…",
    }
    signes = {"definitions": "un signe dans la Bible", POINT_CENTRAL: "Les pleurs"}
    assert all(
        point_central_renseigne(temoin)
        for temoin in (ascension, saint_esprit, signes)
    )


def test_le_point_central_fait_partie_des_dix():
    """Garde-fou de cohérence : le verrou s'adosse à un code du squelette, pas à un onzième
    inventé ici."""
    assert POINT_CENTRAL in ELEMENTS
    assert len(ELEMENTS) == 10


def test_les_sections_observees_ne_ferment_rien():
    """Les témoins portent des sections que Braga ne nomme pas. Elles sont **proposées**, jamais
    imposées : fermer la liste refuserait à un pasteur la section qu'il tient depuis vingt ans."""
    assert set(ELEMENTS_OBSERVES).isdisjoint(ELEMENTS)
    assert "temoignage" in ELEMENTS_OBSERVES  # « Mon Témoignage », témoin du 09/08
