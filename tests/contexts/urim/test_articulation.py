"""L'articulation proposée — **la seule prose d'Urim, et le mur qui l'enferme**.

Le pasteur demande au modèle de développer un point de son plan. C'est le contraire de tout ce
que ce contexte a refusé jusqu'ici, et ça ne tient qu'à une condition : **ce texte n'atteint
aucun document.**

Le livrable n'imprime que `preparation_element.body` — ce que le pasteur a écrit ou repris. La
proposition vit dans **sa propre table**, et le fichier ne peut pas y accéder : `Note` n'a aucun
champ pour la porter, exactement comme `Deck` n'en a aucun pour une mise en garde.

Cinq propriétés, et la première est celle qui décide :

1. **La proposition n'entre jamais dans un document** — structurel, pas déclaratif.
2. **Elle ne s'écrit pas dans le plan du pasteur** : deux tables, jamais un champ partagé.
3. **Sans modèle, rien ne casse** — l'atelier fonctionne, c'est un état de production.
4. **Elle est demandée, et elle coûte** : c'est un appel de modèle, il est compté.
5. **Un point réécrit repose la question** ; le même point ne la repose pas.
"""

from __future__ import annotations

from dataclasses import fields

import pytest

from app.contexts.urim.application.ports import ElementRecord, PlanSuggestion
from app.contexts.urim.application.study_service import UrimStudyService
from app.contexts.urim.deliverable.domain.documents import Note

from .test_study_service import (
    AUTEUR,
    EGLISE,
    MAINTENANT,
    _Acces,
    _index,
    _Reservations,
    _Studies,
)

pytestmark = pytest.mark.asyncio

_POINT = ElementRecord("divisions", 1, "1- La fin de l'œuvre de Christ sur terre.")
_SUIVANT = ElementRecord("divisions", 2, "2- Un événement annoncé.")


class _Modele:
    """Un modèle **qui note ce qu'on lui donne** — l'invite est ce qu'on vérifie."""

    #: ⚠️ `None` doit vouloir dire **« le modèle n'a rien rendu »**, pas « prends le défaut ».
    #: Avec un `or`, la doublure ne pouvait pas jouer l'absence de modèle — et c'est justement
    #: l'état de production qu'on veut éprouver.
    _DEFAUT = PlanSuggestion(
        body="Christ monte au ciel comme il en était descendu.",
        transition="Voyons maintenant ce que les prophètes en disaient.",
        model="mistral-essai",
    )

    def __init__(self, *, propose: PlanSuggestion | None = _DEFAUT) -> None:
        self.propose = propose
        self.demandes: list[dict] = []

    async def resolve(self, text): return None

    async def axes(self, text): return ()

    async def passages(self, text): return ()

    async def lever(self, text): return ()

    async def vestibule(self, text, *, sujet_en_cours=None):
        """Le double ne conduit pas de conversation : **il s'efface**, comme un modèle
        injoignable, et la préparation descend sans consentement — le régime d'avant le
        vestibule, qui est ce que ces tests éprouvent."""
        return None

    async def aiguiller(self, text): return None

    async def articuler(self, *, point, reference, texte, suivant, appuis=""):
        self.demandes.append({
            "point": point, "reference": reference, "texte": texte,
            "suivant": suivant, "appuis": appuis,
        })
        return self.propose


class _StudiesAvecPlan(_Studies):
    """Le dépôt, plus le mémo des articulations — la vraie signature du port."""

    def __init__(self, *elements: ElementRecord) -> None:
        super().__init__()
        self._elements = list(elements)
        self.articulations: dict[tuple, tuple[str, PlanSuggestion]] = {}
        #: Ce que le service a **effectivement** écrit — la fermeture des codes s'y lit.
        self.elements_ecrits: list[ElementRecord] = []

    #: --- Le fil (2026-08-23) ---------------------------------------------------------------
    #: Le double garde ce qu'on lui donne, en mémoire : ces tests éprouvent le service, pas la
    #: persistance. Ce qui compte ici est qu'**écrire dans le fil n'échoue pas** — le tour ne
    #: doit jamais tomber parce qu'une parole n'a pas pu être gardée.

    async def append_thread(self, parole, *, study_id):
        self.fil.append(parole)

    async def list_thread(self, study_id):
        return tuple(self.fil)

    async def promote_thread(self, entry_id, *, at):
        return None

    async def list_elements(self, study_id):
        return self._elements

    async def set_elements(self, study_id, elements):
        self.elements_ecrits = list(elements)
        self._elements = list(elements)

    async def save_plan_suggestion(
        self, study_id, element_code, ordinal, input_hash, suggestion, at
    ):
        self.articulations[(study_id, element_code, ordinal)] = (input_hash, suggestion)

    async def get_plan_suggestion(self, study_id, element_code, ordinal, input_hash):
        garde = self.articulations.get((study_id, element_code, ordinal))
        if garde is None or garde[0] != input_hash:
            return None
        return garde[1]


class _ReservationsQuiComptent(_Reservations):
    def __init__(self, *, epuise: bool = False) -> None:
        super().__init__(epuise=epuise)
        self.comptes: list[str] = []

    async def mark_assisted(self, *, church_id, author_id, pericope_key, at):
        self.comptes.append(pericope_key)


def _service(studies, *, modele=None, reservations=None) -> UrimStudyService:
    return UrimStudyService(
        studies=studies,
        reservations=reservations or _ReservationsQuiComptent(),
        access=_Acces(),
        index=_index(),
        clock=lambda: MAINTENANT,
        resolver=modele or _Modele(),
    )


async def _preparation(service, studies):
    dto = await service.open(
        actor_account_id=AUTEUR, church_id=EGLISE, raw_input="Hébreux 13:1-2"
    )
    return dto.record.id


# ============================================================ 1. le mur


async def test_la_proposition_n_a_nulle_part_ou_entrer_dans_un_document():
    """**La propriété qui rend cette fonctionnalité acceptable**, et elle est structurelle.

    `Note` — le type que le `.docx` met en page — n'a aucun champ pour une articulation
    proposée. Une implémentation pressée *ne peut pas* en imprimer une : il faudrait d'abord
    ajouter un champ, c'est-à-dire décider de le faire.

    Même parade que `Deck`, qui n'a nulle part où mettre une mise en garde."""
    champs = {f.name for f in fields(Note)}
    for interdit in ("suggestion", "articulation", "propose", "ia", "modele"):
        assert interdit not in champs
    # …et ce que la note imprime vient bien du plan du pasteur.
    assert "plan" in champs


async def test_la_proposition_ne_touche_pas_le_plan_du_pasteur():
    """Deux tables, jamais un champ partagé. Dans la même colonne, une reprise silencieuse
    ferait imprimer la machine sous son nom."""
    studies = _StudiesAvecPlan(_POINT)
    service = _service(studies)
    study_id = await _preparation(service, studies)

    await service.articuler(
        actor_account_id=AUTEUR, study_id=study_id, element_code="divisions", ordinal=1
    )

    assert (await studies.list_elements(study_id))[0].body == _POINT.body
    assert studies.articulations  # la proposition existe, ailleurs


# ============================================================ 2. ce qu'on donne au modèle


async def test_le_modele_recoit_le_point_le_passage_et_son_texte_seulement():
    """Pas les pesées (curées, il les redirait mal), pas les mises en garde (elles s'adressent
    au prédicateur), pas l'archive. Une invite qui reçoit tout produit une synthèse de tout, et
    le pasteur ne sait plus ce qui vient de lui."""
    studies = _StudiesAvecPlan(_POINT, _SUIVANT)
    modele = _Modele()
    service = _service(studies, modele=modele)
    study_id = await _preparation(service, studies)

    await service.articuler(
        actor_account_id=AUTEUR, study_id=study_id, element_code="divisions", ordinal=1
    )

    (demande,) = modele.demandes
    assert demande["point"] == _POINT.body
    assert "Hébreux" in demande["reference"]
    assert "amour fraternel" in demande["texte"]  # le texte servi, pas la curation
    assert demande["suivant"] == _SUIVANT.body
    # Le point ne cite aucune référence : rien à servir, et c'est un cas normal.
    assert demande["appuis"] == ""


async def test_un_point_vide_ne_s_articule_pas():
    """On n'articule pas un point qui n'existe pas : **ce serait l'écrire**, et c'est la seule
    chose que ce produit refuse de faire."""
    studies = _StudiesAvecPlan(ElementRecord("divisions", 1, "   "))
    modele = _Modele()
    service = _service(studies, modele=modele)
    study_id = await _preparation(service, studies)

    assert await service.articuler(
        actor_account_id=AUTEUR, study_id=study_id, element_code="divisions", ordinal=1
    ) is None
    assert modele.demandes == []  # le modèle n'a même pas été dérangé


# ============================================================ 3. sans modèle, rien ne casse


async def test_sans_modele_l_atelier_continue():
    """`None` n'est pas une erreur : c'est l'état de production d'un dépôt sans clé (§10). Le
    pasteur écrit son point comme il l'a toujours fait."""
    studies = _StudiesAvecPlan(_POINT)
    service = _service(studies, modele=_Modele(propose=None))
    study_id = await _preparation(service, studies)

    assert await service.articuler(
        actor_account_id=AUTEUR, study_id=study_id, element_code="divisions", ordinal=1
    ) is None
    assert studies.articulations == {}  # rien de vide n'est gardé


async def test_au_plafond_on_ne_demande_pas():
    """L'assistance s'éteint, Urim continue. Et surtout : **on ne facture pas un appel qu'on
    ne fait pas**."""
    studies = _StudiesAvecPlan(_POINT)
    modele = _Modele()
    service = _service(
        studies, modele=modele, reservations=_ReservationsQuiComptent(epuise=True)
    )
    study_id = await _preparation(service, studies)

    assert await service.articuler(
        actor_account_id=AUTEUR, study_id=study_id, element_code="divisions", ordinal=1
    ) is None
    assert modele.demandes == []


# ============================================================ 4. ça coûte, et une seule fois


async def test_l_articulation_est_comptee():
    """C'est un appel de modèle comme les autres. Le livrable, lui, ne compte rien — la
    différence tient à qui demande : ici, le pasteur."""
    studies = _StudiesAvecPlan(_POINT)
    compteur = _ReservationsQuiComptent()
    service = _service(studies, reservations=compteur)
    study_id = await _preparation(service, studies)

    await service.articuler(
        actor_account_id=AUTEUR, study_id=study_id, element_code="divisions", ordinal=1
    )

    assert len(compteur.comptes) == 1


async def test_le_meme_point_ne_repose_pas_la_question():
    """Le mémo, pour la même raison que celui des suggestions : redemander ferait payer une
    question qui a déjà sa réponse — et le rejeu est constant dans ce moteur."""
    studies = _StudiesAvecPlan(_POINT)
    modele = _Modele()
    service = _service(studies, modele=modele)
    study_id = await _preparation(service, studies)

    for _ in range(3):
        await service.articuler(
            actor_account_id=AUTEUR, study_id=study_id,
            element_code="divisions", ordinal=1,
        )

    assert len(modele.demandes) == 1


async def test_un_point_reecrit_repose_la_question():
    """Le couple du précédent : la réponse gardée répondait à un point qui n'existe plus.
    La rendre serait répondre à une question que personne ne pose."""
    point = ElementRecord("divisions", 1, "1- La fin de l'œuvre de Christ.")
    studies = _StudiesAvecPlan(point)
    modele = _Modele()
    service = _service(studies, modele=modele)
    study_id = await _preparation(service, studies)

    await service.articuler(
        actor_account_id=AUTEUR, study_id=study_id, element_code="divisions", ordinal=1
    )
    studies._elements = [ElementRecord("divisions", 1, "1- Christ élevé à la droite du Père.")]
    await service.articuler(
        actor_account_id=AUTEUR, study_id=study_id, element_code="divisions", ordinal=1
    )

    assert len(modele.demandes) == 2


async def test_les_textes_cites_dans_le_point_sont_servis_au_modele():
    """🐛 **Trouvé au premier appel réel.** Sur un point qui citait Hébreux 9 alors qu'on
    servait Actes 1, le modèle a complété **de mémoire** : « dans le lieu très saint ». Exact,
    et hors du texte fourni — donc invérifiable par le pasteur, et c'est tout le problème.

    La cause n'était pas l'invite mais ce qu'on lui donnait : le point citait des textes qu'on
    ne servait pas. Il devait combler."""
    studies = _StudiesAvecPlan(
        ElementRecord("divisions", 1, "1- Il est entré une fois pour toutes Hb 13v1.")
    )
    modele = _Modele()
    service = _service(studies, modele=modele)
    study_id = await _preparation(service, studies)

    await service.articuler(
        actor_account_id=AUTEUR, study_id=study_id, element_code="divisions", ordinal=1
    )

    (demande,) = modele.demandes
    assert "Hébreux 13:1" in demande["appuis"]
    assert "amour fraternel" in demande["appuis"]  # le texte, pas seulement la référence


async def test_une_reference_fausse_du_point_n_est_pas_servie():
    """Ici on nourrit une invite : « Hébreux 2 compte 18 versets » n'a rien à y faire. C'est le
    **livrable** qui montre ce motif au pasteur, pas le modèle."""
    studies = _StudiesAvecPlan(
        ElementRecord("divisions", 1, "1- Couronné de gloire et d'honneur Hb 2v29.")
    )
    modele = _Modele()
    service = _service(studies, modele=modele)
    study_id = await _preparation(service, studies)

    await service.articuler(
        actor_account_id=AUTEUR, study_id=study_id, element_code="divisions", ordinal=1
    )

    assert modele.demandes[0]["appuis"] == ""


# ============================================================ 5. l'invite elle-même


async def test_l_invite_porte_ses_quatre_interdits():
    """L'invite est la seule garde de ce qui sort. Chaque interdit répare une faute qu'on
    aurait faite : un verset inventé, un fait culturel, un point ajouté, une illustration —
    et cette dernière est ce que le pasteur apporte, lui seul."""
    from app.contexts.urim.adapters.mistral import _SYSTEME_ARTICULATION

    for interdit in ("n'utilise AUCUN contenu biblique", "aucun fait historique",
                     "n'écris pas le sermon", "n'invente aucune illustration"):
        assert interdit in _SYSTEME_ARTICULATION
    # …et le style demandé, qui vient d'un retour de l'auteur sur la première esquisse.
    assert "français simple" in _SYSTEME_ARTICULATION
