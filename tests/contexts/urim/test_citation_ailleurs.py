"""La citation trouvée **dans une autre version détenue** — et le motif qui ne bouge plus.

Le cas mesuré, en une ligne :

    saisie      « l'amour ne perir jamais »
    Darby       « L'amour ne périt jamais. »     ← mot pour mot
    Segond      « La charité ne périt jamais. »  ← la seule version que l'index porte

Deux choses se testent ici, et la seconde compte autant que la première :

1. l'étage lit la trouvaille et annonce une citation, en nommant la version ;
2. il annonce **la même chose au rejeu**, parce que la trace n'est pas persistée et que tout
   ce qui se recalcule sans la base finit par contredire ce qui est affiché à côté.

⚠️ La recherche elle-même n'est pas ici : elle est asynchrone, elle interroge la base, et
l'étage doit rester pur. Ce qu'on vérifie, c'est qu'il **relit** un fait stocké.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.contexts.urim.calendar.domain.ports import NullEcclesialContext
from app.contexts.urim.engine import (
    EngineDeps,
    EntryMode,
    EntryOrigin,
    Outcome,
    RouteEntry,
    StudyState,
)
from app.contexts.urim.engine.stages.route_entry import CITATION_AFFINITY

DARBY = "Darby (français)"
SAISIE = "l'amour ne perir jamais"


class _CorpusSourd:
    """L'index tel qu'il est vraiment : une seule Bible, qui ne reconnaît pas cette phrase."""

    def snapshot(self) -> str:
        return "corpus-2026-08"

    def find_reference_span(self, mots):
        return None

    def scripture_affinity(self, mots):
        return 0.10  # « charité » n'est pas « amour » : le recouvrement est faible

    def known_words(self, mots):
        return len(mots)


def _deps() -> EngineDeps:
    return EngineDeps(
        corpus=_CorpusSourd(),
        doctrine=None,
        homiletics=None,
        context=NullEcclesialContext(),
        versions=None,
        clock=lambda: datetime(2026, 8, 15, tzinfo=UTC),
    )


def _etat(*, version: str | None, saisi: EntryMode | None = None) -> StudyState:
    return StudyState(
        session_id=uuid4(),
        church_id=None,
        author_id=uuid4(),
        corpus_snapshot="corpus-2026-08",
        entry_mode=saisi,
        raw_input=SAISIE,
        entry_origin=EntryOrigin.TYPED,
        citation_version=version,
    )


def _executer(etat: StudyState):
    return RouteEntry().execute(etat, _deps())


def test_sans_la_trouvaille_la_saisie_reste_une_intention():
    """Le point de départ — et la raison d'être de la seconde passe.

    Sans elle, la phrase de Darby tombe en conviction : le pasteur reçoit les dix loci pour
    ce qui est une citation."""
    resultat = _executer(_etat(version=None))

    assert resultat.state.entry_mode is EntryMode.CONVICTION
    assert "intention" in resultat.rationale


def test_la_version_trouvee_fait_de_la_saisie_une_citation():
    resultat = _executer(_etat(version=DARBY))

    assert resultat.outcome is Outcome.CONTINUE
    assert resultat.state.entry_mode is EntryMode.CITATION


def test_le_motif_nomme_la_version_et_ne_dement_pas_le_resultat():
    """⚠️ **Le motif est lu par le pasteur.** Il ne peut pas dire « ni citation » à côté d'un
    verset résolu : c'était le défaut mesuré, et il n'était pas cosmétique — il rendait la
    résolution silencieuse sur son origine."""
    motif = _executer(_etat(version=DARBY)).rationale

    assert DARBY in motif
    assert "phrase des Écritures" in motif
    assert "ni référence ni citation" not in motif


def test_le_motif_est_le_meme_au_rejeu():
    """La trace n'est pas persistée : l'étage se ré-exécute à chaque lecture.

    Au rejeu, `entry_mode` revient de la base à `citation` — et sans le garde placé **avant**
    la branche du mode retenu, l'étage répondrait « lecture retenue par vous », en attribuant
    au pasteur un choix qu'il n'a pas fait."""
    premiere = _executer(_etat(version=DARBY)).rationale
    relecture = _executer(_etat(version=DARBY, saisi=EntryMode.CITATION)).rationale

    assert relecture == premiere
    assert "par vous" not in relecture


def test_le_seuil_de_citation_reste_celui_du_detecteur():
    """La seconde passe **emprunte** le seuil, elle n'en invente pas un plus bas.

    C'est ce qui garde l'accusation de S20 — « l'amour fraternel n'existe plus dans l'église »,
    mesurée à 0,42 chez Darby — du côté des intentions."""
    assert CITATION_AFFINITY == 0.45
