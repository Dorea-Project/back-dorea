"""Le normaliseur partagé — et la seule chose qu'il n'avait pas le droit de faire.

Ce fichier ne re-teste pas la casse ni les accents : quatre étages s'en servent déjà et le
diraient. Il garde la règle qui a manqué, parce qu'elle est **invisible à la relecture** —
`cœur` et `coeur` ne se distinguent pas d'un coup d'œil, et le résultat cassé (`c ur`) a
l'air d'un texte normal.
"""

from __future__ import annotations

from app.contexts.urim.engine.normalizer import normalize, tokens


def test_les_lettres_soudees_se_deplient_au_lieu_de_couper_le_mot():
    """🔴 Le bug qui a peuplé l'idf de fragments.

    `œ` et `æ` n'ont **aucune** décomposition Unicode : elles échappaient à NFKD et tombaient
    dans la classe « tout ce qui n'est pas `[0-9a-z]` », c'est-à-dire dans les frontières de
    mot. Le mot ne perdait pas un signe, il devenait deux mots — et ces deux-là entraient dans
    le lexique avec une fréquence moyenne, là où le vrai mot en sortait."""
    assert normalize("de tout son cœur") == "de tout son coeur"
    assert tokens("de tout son cœur") == ("de", "tout", "son", "coeur")
    assert normalize("les ŒUVRES et le CŒUR") == "les oeuvres et le coeur"
    assert normalize("Ægypte, ex æquo") == "aegypte ex aequo"


def test_ce_que_nfkd_deplie_deja_n_est_pas_redit():
    """La règle ajoutée est **courte parce qu'Unicode fait le reste** : les ligatures de
    compatibilité (`ﬁ`, `ﬂ`, `ĳ`) ont, elles, une décomposition. Les redéclarer à la main
    ferait croire à un catalogue à tenir à jour, alors qu'il n'y a que deux exceptions."""
    assert normalize("ﬁdèle et ﬂamme") == "fidele et flamme"


def test_la_ligature_ne_desactive_pas_l_elision_collee():
    """Les deux gestes travaillent sur la même chaîne, et l'ordre compte : dépliée d'abord,
    la ligature devient une lettre ordinaire que l'élision peut ensuite coller (S21)."""
    assert normalize("l'œuvre de l'Église") == "loeuvre de leglise"
