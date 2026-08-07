"""**L'étape 1 de la capture** — et rien d'autre, parce que rien d'autre n'est autorisé.

Deux règles portent tout ce fichier, et elles disent la même chose sous deux formes : *ce qui ne
peut pas se rattraper passe avant ce qui peut attendre.*

- **la capture n'est jamais refusée** — un dimanche ne se rejoue pas, un transcript peut attendre
  lundi ;
- **un travail abandonné laisse une trace visible** — un échec silencieux est indiscernable d'un
  dimanche où personne n'a prêché.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.urim.capture.domain import (
    BACKOFF_BASE,
    RETENTION_AUDIO,
    TENTATIVES_MAX,
    Capture,
    CaptureJob,
    CaptureState,
    JobKind,
    JobState,
)

_DIMANCHE = datetime(2026, 8, 9, 10, 0, tzinfo=UTC)


def _capture(**kw) -> Capture:
    base = {
        "id": uuid4(), "church_id": uuid4(), "author_id": uuid4(),
        "preached_on": _DIMANCHE, "at": _DIMANCHE,
    }
    return Capture.ouvrir(**{**base, **kw})


def _job(**kw) -> CaptureJob:
    base = {
        "id": uuid4(), "capture_id": uuid4(), "kind": JobKind.TRANSCRIRE,
        "idempotency_key": "cap-1:transcrire",
    }
    return CaptureJob(**{**base, **kw})


# --- La capture n'est jamais refusée -------------------------------------------------------------


def test_le_plafond_differe_la_transcription_il_n_empeche_pas_d_enregistrer():
    """**La seule ressource du produit dont le refus serait irréparable.**

    Ce qui n'est pas capté dimanche est perdu pour toujours ; un transcript peut attendre lundi."""
    capture = _capture(ceiling_reached=True)

    assert capture.state is CaptureState.CAPTEE
    assert capture.transcription_deferred is True


def test_hors_plafond_rien_n_est_differe():
    assert _capture().transcription_deferred is False


def test_on_peut_precher_sans_avoir_prepare():
    """Le lien à la préparation est facultatif — un transcript reste utile sans plan."""
    assert _capture().preparation_id is None


# --- L'audio ne survit pas à la semaine ----------------------------------------------------------


def test_l_echeance_de_purge_se_pose_a_la_capture():
    """Une échéance qu'on peut repousser n'est pas une promesse de confidentialité."""
    assert _capture().audio_purge_at == _DIMANCHE + RETENTION_AUDIO


def test_l_audio_est_a_purger_des_l_echeance_atteinte():
    capture = _capture()

    assert not capture.audio_a_purger(at=capture.audio_purge_at - timedelta(seconds=1))
    assert capture.audio_a_purger(at=capture.audio_purge_at)


def test_un_audio_deja_purge_ne_l_est_pas_deux_fois():
    capture = _capture()
    purgee = capture.purgee(at=capture.audio_purge_at)

    assert not purgee.audio_a_purger(at=capture.audio_purge_at + timedelta(days=30))


def test_la_purge_garde_sa_date_pas_un_booleen():
    """Sur une donnée qu'on détruit pour tenir une promesse, savoir **quand** elle a disparu est
    précisément ce qu'on voudra prouver."""
    capture = _capture().purgee(at=_DIMANCHE + timedelta(days=7))

    assert capture.audio_purged_at == _DIMANCHE + timedelta(days=7)


# --- Le fournisseur est tracé --------------------------------------------------------------------


def test_le_fournisseur_et_son_modele_sont_stockes_par_transcript():
    """Sans eux, impossible de savoir plus tard **pourquoi certains dimanches sont mauvais**.

    Et la question des langues locales n'étant pas instruite, le fournisseur changera."""
    capture = _capture(ceiling_reached=True).transcrite(
        provider="acme", model_ref="whisper-x-2026"
    )

    assert (capture.provider, capture.model_ref) == ("acme", "whisper-x-2026")
    assert capture.state is CaptureState.TRANSCRITE
    assert capture.transcription_deferred is False  # elle n'attend plus


# --- Un travail abandonné laisse une trace visible -----------------------------------------------


def test_un_echec_replanifie_avec_un_recul_exponentiel():
    """Un fournisseur qui tousse a besoin qu'on le laisse respirer, pas qu'on insiste."""
    apres_un = _job().echoue(motif="502", at=_DIMANCHE)
    apres_deux = apres_un.echoue(motif="502", at=_DIMANCHE)

    assert apres_un.state is JobState.EN_ATTENTE
    assert apres_un.not_before == _DIMANCHE + BACKOFF_BASE
    assert apres_deux.not_before == _DIMANCHE + BACKOFF_BASE * 2


def test_apres_cinq_tentatives_on_abandonne():
    job = _job()
    for _ in range(TENTATIVES_MAX):
        job = job.echoue(motif="502", at=_DIMANCHE)

    assert job.abandonne
    assert job.attempts == TENTATIVES_MAX


def test_un_travail_abandonne_conserve_son_motif():
    """**La règle qui compte.** Un échec silencieux est indiscernable d'un dimanche où personne
    n'a prêché — le pasteur doit voir ce qui n'a pas marché."""
    job = _job()
    for _ in range(TENTATIVES_MAX):
        job = job.echoue(motif="fournisseur indisponible", at=_DIMANCHE)

    assert job.last_error == "fournisseur indisponible"


def test_une_capture_dont_un_travail_est_abandonne_devient_partielle_jamais_muette():
    capture = _capture().partielle()

    assert capture.state is CaptureState.PARTIELLE


def test_une_reussite_efface_l_erreur_precedente():
    job = _job().echoue(motif="502", at=_DIMANCHE).reussi()

    assert job.state is JobState.FAIT
    assert job.last_error is None


# --- Le verrou de séquencement -------------------------------------------------------------------


@pytest.mark.parametrize(
    "verrouille", [JobKind.EXTRAIRE_VERSETS, JobKind.ALIGNER]
)
def test_les_travaux_des_etapes_2_et_3_existent_mais_ne_sont_pas_construits(verrouille):
    """Ils sont **nommés** dans la file, et c'est tout ce qu'ils doivent être aujourd'hui.

    Les définir maintenant coûte zéro — aucune ligne n'existe. Les construire avant la mesure du
    taux d'erreur dans trois églises produirait *« une invention présentée comme un souvenir »*."""
    assert verrouille in JobKind
