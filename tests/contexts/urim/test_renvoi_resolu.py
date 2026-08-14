"""Une note de contexte est **sourcée, ou absente** (S40) — et ici la source est résolue.

Les autres lots vérifient la *forme* d'une ligne générée : pas de manuscrit, pas d'autorité.
Celui des notes de contexte vérifie son **appui**, parce que sa dimension le lui impose. Un
modèle ne source pas, il récite ; ce qu'il récite d'une coutume ou d'une chronologie n'a aucun
contradicteur dans le dépôt.

La ligne qui a décidé du lot est celle d'Aggée — *« 520 av. J.-C., seize ans après le retour »*.
Elle est juste, et si elle avait été fausse **rien ne l'aurait vue** : D3 n'y trouve ni
manuscrit ni autorité, D5 compare des mots cités au passage et une date n'est pas une citation.
Les cas ci-dessous sont les quatre façons dont une érudition inventée essaie de passer.
"""

from __future__ import annotations

import pytest
from scripts.urim_curate_context import (
    IndexDesLivres,
    Renvoi,
    Unite,
    lire_renvoi,
    verifier_note,
)

#: Un corpus minuscule et suffisant : Jean 3 (le passage), Nombres 21 (le renvoi juste),
#: Genèse 3 (le piège du livre inconnu qui retomberait sur un verset existant).
JEAN, NOMBRES, GENESE = 43, 4, 1

VERSETS = {
    (JEAN, 3, 14): ("Et comme Moise eleva le serpent dans le desert…",
                    "et comme moise eleva le serpent dans le desert"),
    (JEAN, 3, 15): ("afin que quiconque croit en lui ait la vie eternelle.",
                    "afin que quiconque croit en lui ait la vie eternelle"),
    (NOMBRES, 21, 8): ("Fais-toi un serpent brulant, et place-le sur une perche.",
                       "fais toi un serpent brulant et place le sur une perche"),
    (NOMBRES, 21, 9): ("Moise fit un serpent d'airain, et le placa sur une perche.",
                       "moise fit un serpent d airain et le placa sur une perche"),
    (GENESE, 3, 2): ("La femme repondit au serpent…", "la femme repondit au serpent"),
}

#: Le passage curé, normalisé — c'est contre lui que l'ancrage d'un renvoi se mesure.
TEXTE = " ".join(norme for (livre, _, _), (_, norme) in VERSETS.items() if livre == JEAN)

LIVRES = IndexDesLivres()

#: L'unité curée : Jean 3, versets 14-15.
UNITE = Unite(JEAN, frozenset({3}))

#: 🔴 **La rareté, mesurée — et non la longueur d'un mot.**
#:
#: Le premier réglage comptait comme ancre tout mot d'au moins cinq lettres. Le passage sur le
#: corpus entier l'a démenti sur sa prise la plus nette : une note de Jérémie 50:44 renvoyant
#: l'image du lion à Amos 3:4, juste et correctement citée, **jetée parce que `lion` fait quatre
#: lettres** — alors que c'est le seul mot que les deux versets partagent. Descendre le seuil à
#: quatre aurait fait de `Dieu` un laissez-passer. `urim_corpus_idf` tranche les deux : lion
#: 6,02, serpent 6,74, dieu 2,15.
#: ⚠️ Les mots outils y figurent **explicitement**. Un token absent de la table est tenu pour
#: rare — c'est le bon défaut en production, où la table couvre tout le vocabulaire du corpus et
#: où une lacune ne peut donc porter que sur un mot inhabituel. Mais un jeu d'essai incomplet
#: ferait de « le » et « la » des ancres, et n'importe quels deux versets se répondraient.
IDF = {
    "serpent": 6.74, "perche": 7.9, "airain": 7.5, "desert": 5.6, "eternelle": 6.1,
    "moise": 5.2, "femme": 4.1, "repondit": 4.4, "posterite": 6.2, "adam": 6.6,
    "dieu": 2.15, "dans": 1.69, "pour": 1.81, "comme": 1.9, "vie": 3.1, "livre": 4.3,
    "le": 0.4, "la": 0.4, "les": 0.4, "de": 0.4, "du": 0.5, "des": 0.5, "et": 0.4,
    "en": 0.6, "un": 0.7, "une": 0.7, "que": 0.6, "qui": 0.7, "lui": 1.1, "sur": 0.9,
    "il": 0.5, "d": 0.6, "au": 0.8, "est": 0.7, "ou": 0.8, "ne": 0.9, "se": 1.0,
    "afin": 2.4, "ait": 2.6, "croit": 3.8, "eleva": 4.9, "fais": 3.4, "fit": 2.9,
    "toi": 2.2, "place": 4.2, "placa": 4.6, "brulant": 4.8, "voici": 2.7, "verset": 4.0,
    "quiconque": 4.7, "chapitre": 4.1, "precedent": 4.4, "evoque": 4.5, "rappele": 4.6,
}


def juger(corps: str, renvois: list[str]) -> str | None:
    return verifier_note(corps, renvois, UNITE, TEXTE, VERSETS, LIVRES, IDF)


def test_la_note_qui_renvoie_a_un_texte_reel_et_parent_passe() -> None:
    """L'étalon de Jean 3 : le renvoi existe, et « serpent » les relie tous les deux."""
    assert juger(
        "Le passage reprend Nombres 21:8-9. La comparaison n'est pas ornementale : elle "
        "fournit la structure de l'argument.",
        ["Nombres 21:8-9"],
    ) is None


def test_le_renvoi_au_meme_livre_se_dit_sans_le_nommer() -> None:
    assert juger(
        "Le v. 15 conclut la comparaison ouverte au v. 14 : 3:14 et 3:15 forment une seule "
        "proposition que la ponctuation seule separe.",
        ["3:14", "3:15"],
    ) is None


def test_une_note_sans_aucun_renvoi_est_une_affirmation() -> None:
    """C'est la forme qu'aurait pris tout le contexte historique — une assertion nue."""
    assert juger(
        "Le passage se situe au debut du ministere, dans un climat de tension a Jerusalem.",
        [],
    ) == "sans renvoi"


def test_un_livre_inconnu_ne_retombe_pas_sur_le_livre_de_l_unite() -> None:
    """🔴 Le piège qui justifie tout le vérificateur.

    Un repli silencieux sur le livre de l'unité ferait résoudre « Hénoch 3:2 » en Genèse 3:2,
    qui existe. L'invention passerait en se faisant vérifier."""
    assert juger(
        "Le passage suppose le recit d'Henoch 3:2, ou la meme scene est racontee autrement.",
        ["Henoch 3:2"],
    ) == "renvoi introuvable"


def test_un_verset_hors_du_texte_tombe() -> None:
    assert juger(
        "Le passage prolonge Nombres 21:44, ou la perche est plantee une seconde fois.",
        ["Nombres 21:44"],
    ) == "renvoi introuvable"


def test_la_chronologie_est_refusee_meme_accompagnee_d_un_renvoi_juste() -> None:
    """La forme la plus vraisemblable de l'erreur : l'érudition en passager clandestin.

    L'exigence de renvoi seule ne suffirait pas — la date voyage avec une source valable."""
    assert juger(
        "L'entretien renvoie a Nombres 21:8-9, episode que la tradition situe au XIIIe siecle "
        "avant J.-C., soit bien avant la redaction johannique.",
        ["Nombres 21:8-9"],
    ) == "chronologie"


def test_l_ancrage_est_calcule_mais_ne_refuse_plus() -> None:
    """🔴 Le contrôle que les prises du corpus ont rétrogradé de refus en signal.

    L'idée était juste — un renvoi peut exister et n'avoir aucun rapport — mais le recouvrement
    lexical est un mauvais témoin du lien entre deux textes. Trois des quatre prises lisibles
    sur les 54 refus étaient fausses, dont **2 Rois 23:25 renvoyant à Deutéronome 6:5** : « de
    tout son cœur, de toute son âme et de toute sa force », la citation la plus littérale de
    l'Ancien Testament, refusée parce que le mot partagé le plus rare (`force`, 4,76) tombait
    sous le seuil. Une citation quasi verbatim ne partage pas un mot rare : elle partage une
    phrase.

    Le cas ci-dessous — un renvoi vraiment sans rapport — **passe désormais**. C'est le prix
    assumé, et ce qui reste pour attraper un renvoi ornemental est `aucun renvoi visible`."""
    versets = dict(VERSETS)
    versets[(GENESE, 5, 1)] = ("Voici le livre de la posterite d'Adam.",
                               "voici le livre de la posterite d adam")
    assert verifier_note(
        "Le passage prolonge Genese 5:1, dont il reprend la ligne genealogique.",
        ["Genese 5:1"], UNITE, TEXTE, versets, LIVRES, IDF,
    ) is None


def test_une_note_qui_ne_montre_aucune_reference_n_est_pas_controlable() -> None:
    """La note est lue par un pasteur, pas par le vérificateur qui l'a écrite.

    C'est le **seul** cas que ce contrôle refuse encore : rien dans la phrase ne dit au lecteur
    où aller voir. « v. 8 » ne compte pas ici — dans une note sur Jean 3, le numéro nu ne
    désigne pas Nombres 21:8."""
    assert juger(
        "Le passage reprend l'episode du serpent d'airain, raconte au v. 8 du recit du desert.",
        ["Nombres 21:8"],
    ) == "aucun renvoi visible"


def test_le_verset_de_l_unite_se_dit_a_la_maniere_des_neuf_notes_humaines() -> None:
    """🔴 Première prise contre l'instrument.

    Le premier réglage n'acceptait que « 3:15 ». Deux bonnes notes d'Aggée sont tombées pour
    avoir écrit « au v. 20 » — la convention même des neuf notes posées à la main : *« le
    chiasme autour du v. 18 »*, *« les mots de Jézabel (v. 9-10) »*. **L'étalon aurait échoué
    au contrôle**, ce qui est la définition d'un mauvais contrôle."""
    assert juger(
        "Le v. 15 conclut la comparaison ouverte au verset precedent : la proposition est une, "
        "et la ponctuation seule la coupe.",
        ["3:15"],
    ) is None


def test_une_plage_montre_les_versets_qu_elle_contient() -> None:
    """🔴 Deuxième prise, Aggée encore : la note écrivait « (1:12-15) » pour les renvois 1:13
    et 1:14. Refuser une note parce qu'elle cite un intervalle au lieu de ses membres, c'est
    contrôler la typographie et non la contrôlabilité."""
    versets = dict(VERSETS)
    for n in (12, 13, 14, 15):
        versets[(JEAN, 2, n)] = (f"Verset {n} du chapitre precedent, ou le serpent est evoque.",
                                 f"verset {n} du chapitre precedent ou le serpent est evoque")
    assert verifier_note(
        "Le passage repond a l'appel des versets qui precedent (2:12-15), dont il reprend le "
        "mouvement en le retournant.",
        ["2:13", "2:14"], UNITE, TEXTE, versets, LIVRES, IDF,
    ) is None


def test_un_seul_renvoi_visible_suffit_pour_la_note_entiere() -> None:
    """🔴 Troisième prise : « (v. 15.18) » montrait 15 mais pas 18, et la note tombait.

    Ce que le contrôle protège est que le lecteur ait de quoi vérifier — pas que chaque renvoi
    déclaré soit orthographié comme le script l'attend."""
    assert juger(
        "Les v. 14-15 forment une inclusion : la comparaison ouverte en 3:14 se referme sur la "
        "vie eternelle, et le mouvement se lit d'un trait.",
        ["3:14", "3:15"],
    ) is None


def test_la_forme_interdite_a_la_machine_vaut_ici_aussi() -> None:
    """`verifier_forme_machine` est partagé — le recopier ici l'aurait fait diverger."""
    assert juger(
        "Certains manuscrits ajoutent au v. 15 une clause absente de Nombres 21:8-9.",
        ["Nombres 21:8-9"],
    ) == "forme machine"


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        ("Nombres 21:8-9", Renvoi(NOMBRES, 21, 8, 9)),
        ("Nb 21:8", Renvoi(NOMBRES, 21, 8, 8)),
        ("3:14", Renvoi(JEAN, 3, 14, 14)),
        # Le modèle rend la même plage des deux façons ; une bonne note d'un témoin est tombée
        # sur la seconde.
        ("Nombres 21:8-21:9", Renvoi(NOMBRES, 21, 8, 9)),
        ("Nombres 21:8-22:1", None),  # une plage qui franchit un chapitre ne se verifie pas
        # 🔴 La forme dont la regle (3) a besoin : on demande au modele de declarer les versets
        # de sa propre unite, il les rend comme un humain les ecrit, et le verificateur les
        # jetait — en tuant la note que cette regle venait d'ajouter pour la sauver.
        ("v. 14", Renvoi(JEAN, 3, 14, 14)),
        ("vv. 14-15", Renvoi(JEAN, 3, 14, 15)),
        ("15", Renvoi(JEAN, 3, 15, 15)),
        ("Henoch 3:2", None),
        ("Nombres 21:9-8", None),  # une plage a l'envers n'est pas une reference
        ("au debut du livre", None),
        # 🔴 La section entière : 32 notes du corpus sont tombées sur cette forme, et les
        # deux prises visibles l'étaient toutes deux — « répondant à l'ordre donné en Exode
        # 25-31 ». Personne ne cite sept chapitres par un verset.
        ("Nombres 21", Renvoi(NOMBRES, 21, 1, 200, section=True)),
        ("Nombres 21-25", Renvoi(NOMBRES, 21, 1, 200, section=True)),
        # Sans nom de livre, « 21-25 » serait indiscernable d'une plage de versets.
        ("21-25", Renvoi(JEAN, 3, 21, 25)),
    ],
)
def test_lecture_d_un_renvoi(brut: str, attendu: tuple | None) -> None:
    assert lire_renvoi(brut, UNITE, LIVRES) == attendu


def test_la_forme_courte_est_refusee_a_cheval_sur_deux_chapitres() -> None:
    """« v. 14 » ne désigne rien sur une unité qui court de 3:30 à 4:5 : ce serait une devinette,
    et une devinette qui résout est pire qu'un refus."""
    assert lire_renvoi("v. 14", Unite(JEAN, frozenset({3, 4})), LIVRES) is None


def test_une_section_entiere_se_montre_par_son_chapitre() -> None:
    """🔴 Quatrième prise contre l'instrument, celle du corpus entier.

    Une note d'Exode 39 renvoyant l'achèvement du tabernacle à l'ordre d'« Exode 25-31 » est
    juste, et c'est la seule forme sous laquelle cette référence s'écrit. Le vérificateur
    exigeait un verset : la note tombait, avec 31 autres."""
    versets = dict(VERSETS)
    for n in (1, 2, 3):
        versets[(NOMBRES, 25, n)] = (f"Verset {n}, ou le serpent d'airain est rappele.",
                                     f"verset {n} ou le serpent d airain est rappele")
    assert verifier_note(
        "Le passage reprend l'episode raconte en Nombres 25, dont il fait la structure de son "
        "argument sur le serpent eleve.",
        ["Nombres 25"], UNITE, TEXTE, versets, LIVRES, IDF,
    ) is None


def test_une_citation_d_appui_non_ancree_ne_tue_pas_la_note() -> None:
    """🔴 Cinquième prise contre l'instrument, et la plus instructive du corpus.

    La note du lion de Jérémie 50:44 déclarait Amos 3:4 **et** Ésaïe 5:29. La première ancre sur
    « lion » ; la seconde non, parce que LSG y écrit « lionne » et « lionceaux ». Exiger
    l'ancrage de *chaque* renvoi faisait tomber une note dont la source principale était solide
    et dont toutes les références étaient réelles — la même erreur de structure que pour la
    visibilité, corrigée de la même façon : le contrôle porte sur la note, pas sur la ligne."""
    versets = dict(VERSETS)
    versets[(GENESE, 5, 1)] = ("Voici le livre de la posterite d'Adam.",
                               "voici le livre de la posterite d adam")
    assert verifier_note(
        "Le passage reprend le serpent de Nombres 21:8, image que prolonge encore Genese 5:1.",
        ["Nombres 21:8", "Genese 5:1"], UNITE, TEXTE, versets, LIVRES, IDF,
    ) is None


def test_le_renvoi_ornemental_reste_attrape_par_la_visibilite() -> None:
    """Ce qui garde le lot maintenant que l'ancrage ne refuse plus.

    Le passage sur les Proverbes avait montré la forme du mal : des références justes et
    résolues, accrochées à des notes qui ne s'en servaient pas — `['13:7', '13:8']` sur une note
    qui parlait des v. 11-12. Un renvoi que le modèle n'écrit pas dans sa propre phrase est un
    renvoi dont il ne s'est pas servi, et c'est une meilleure preuve qu'un compte de mots."""
    versets = dict(VERSETS)
    versets[(GENESE, 5, 1)] = ("Voici le livre de la posterite d'Adam.",
                               "voici le livre de la posterite d adam")
    assert verifier_note(
        "Le passage reprend l'episode du serpent d'airain et en fait la structure de son "
        "argument, sans jamais dire ou le lecteur pourrait le verifier.",
        ["Genese 5:1"], UNITE, TEXTE, versets, LIVRES, IDF,
    ) == "aucun renvoi visible"
