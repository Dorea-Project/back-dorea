"""Surface **Plateforme** d'Urim — curer le corpus, et relire ce qui y a été écrit.

Gardée par le jeton de service Plateforme, et c'est structurel, pas prudentiel : aucune table
`urim_corpus_*` ne porte de `church_id`. Curer change ce que **toutes** les églises lisent ;
le geste n'a pas la portée d'un tenant. Un pasteur ne peut donc pas curer — pas par défiance,
mais parce que le geste n'a pas la bonne portée.

## Deux gardes, et ils ne disent pas la même chose

**`X-Service-Token` dit que l'acte vient de la Plateforme.** Il suffit pour *lire*.

**`X-Urim-Relecteur` dit *qui* le pose.** Il est exigé de **toute écriture**, sans exception —
et le nom qu'il rend est le seul qui entre dans `reviewed_by`. Aucun corps de requête ne porte
plus ce champ.

🔴 **Pourquoi ce second garde existe.** `verifier_verdict()` faisait déjà tout ce qu'un
validateur peut faire sur une chaîne : refuser le vide, les noms de semis, `ia-mistral`. Il n'a
jamais pu refuser le nom **de quelqu'un d'autre** — et un verdict d'essai a été posé au nom du
propriétaire du dépôt, qu'il a fallu retirer. Le défaut n'était pas dans le garde mais en amont :
*tant que le nom est une donnée d'entrée, aucune vérification ne le sauve.*

Ce que la surface garantit désormais : **on ne signe que d'un nom dont on détient le secret, et
ce nom se révoque.** Pas « c'est bien Untel » — il n'y a pas d'identité authentifiée dans ce
produit avant la console d'administration Dorea (`docs/Dorea_Platform_Admin.md`). C'est un cran,
et le jour où la console existe c'est `exiger_relecteur` qui change de source, pas ces routes.

Effet de bord voulu : **plus rien de généré ne peut entrer par HTTP.** `ia-mistral` reste une
signature légitime sur le découpage littéraire, mais elle n'est écrivable que par le lot hors
ligne, qui passe par SQLAlchemy en direct. La frontière humaine et la frontière machine ne sont
plus la même porte.

## La boucle du relecteur

    GET  /urim/relecture/file                        ce qui reste, du plus douteux au moins
    GET  /urim/relecture/unites/{id}                 le passage, la curation, les signalements
    …                                                corriger, s'il y a lieu (routes ci-dessus)
    POST /urim/relecture/unites/{id}/verdict         signer
    GET  /urim/relecture/compteur                    de combien la promesse est en retard

⚠️ **On corrige d'abord, on signe ensuite**, et ce n'est pas une convention : l'empreinte est
prise au moment du verdict. Signer `corrige` avant de réparer figerait la décision sur la
curation fautive — que la réparation périmerait aussitôt, renvoyant l'unité en file. Le
mécanisme se garde lui-même ; il n'y a donc aucun contrôle de plus.

**Chaque écriture purge l'index** (gelé par processus) : sans cela une curation tout juste
signée resterait invisible jusqu'au redémarrage. Elle change aussi l'empreinte du corpus, donc
les préparations ouvertes signalent `corpus_drifted` — leur trace n'est plus celle du jour.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from app.contexts.tenant.interface.dependencies import require_platform_token
from app.contexts.urim.application.curation import (
    BearingDraft,
    CaveatDraft,
    ContextDraft,
    FeasibilityDraft,
    PericopeDraft,
)
from app.contexts.urim.application.relecture import PAGE_DE_FILE
from app.contexts.urim.interface.curation_schemas import (
    BearingsBody,
    CaveatBody,
    ContextBody,
    CoverageView,
    FeasibilityBody,
    PericopeBody,
    PericopeCreatedView,
    PericopeView,
    ResignBody,
)
from app.contexts.urim.interface.dependencies import (
    CurationDep,
    PieceServiceDep,
    RelecteurDep,
    RelectureDep,
)
from app.contexts.urim.interface.relecture_schemas import (
    CompteurView,
    DossierView,
    UniteDeFileView,
    VerdictBody,
    VerdictRetireView,
    VerdictView,
)
from app.contexts.urim.interface.schemas import InterpretationView, RefusBody

router = APIRouter(dependencies=[Depends(require_platform_token)])


# -- l'interprétation : la boucle de l'équipe Dorea ----------------------------
#
# D62 — le pasteur prêche en français, une part de son assemblée entend le dioula, le baoulé
# ou le malinké. Ce travail est **tenu par des gens**, un interprète maîtrisé par langue :
# aucune synthèse vocale ne dit ces langues, et faire semblant serait pire que se taire.
#
#     POST /urim/interpretations/{id}/prise      un interprète s'en charge
#     POST /urim/interpretations/{id}/rendu      voici l'audio
#     POST /urim/interpretations/{id}/refus      on ne peut pas, et voici pourquoi
#
# 🔴 **Ces routes vivent ici, pas sur la surface mobile, et c'est structurel.** L'interprète
# n'est pas membre de l'église qu'il sert ; un contrôle d'appartenance refuserait exactement
# la personne qui doit agir. Le geste vient de la Plateforme, comme la curation du corpus.
#
# ⛔ **Aucune de ces routes n'enregistre *qui* a agi, et c'est délibéré.** Le dépôt porte déjà
# la leçon, quelques lignes plus haut dans ce fichier : un verdict de curation a été posé au
# nom du propriétaire du dépôt parce que le nom était une donnée d'entrée — et *tant que le
# nom est une donnée d'entrée, aucune vérification ne le sauve*. Ajouter un en-tête
# `X-Urim-Interprete` referait la même faute en la croyant réparée.
#
# La colonne `interpreted_by` et son garde arriveront **ensemble**, avec la console
# d'administration Dorea. D'ici là, la Plateforme agit et le dépôt ne prétend pas savoir qui.
#
# ⚠️ **L'écran n'existe pas encore.** Ces routes sont posées avant lui pour que la boucle soit
# complète côté serveur : le pasteur demande, l'équipe répond, l'état est vrai à chaque
# instant. Sans elles, une demande partait dans une file que rien ne pouvait vider.


@router.post(
    "/interpretations/{demande_id}/prise",
    response_model=InterpretationView,
    summary="Un interprète prend ce travail",
)
async def prendre_interpretation(
    demande_id: UUID, service: PieceServiceDep
) -> InterpretationView:
    """La demande sort de la file d'attente.

    ⚠️ **Seule une demande en attente se prend.** Reprendre un travail rendu effacerait sa
    date de livraison, et le pasteur verrait sa version en langue redevenir « en cours » sans
    que rien ne se soit passé."""
    return InterpretationView.from_domain(
        await service.prendre_interpretation(demande_id=demande_id)
    )


@router.post(
    "/interpretations/{demande_id}/rendu",
    response_model=InterpretationView,
    summary="Rendre l'interprétation — avec son audio",
)
async def rendre_interpretation(
    demande_id: UUID, request: Request, service: PieceServiceDep
) -> InterpretationView:
    """Le corps porte l'audio, comme pour une pièce : du WAV, en brut.

    🔴 **Une interprétation sans audio n'est pas rendue.** L'agrégat le refuse, et l'audio se
    range avant la transition : une demande marquée « rendue » dont le fichier manque
    sortirait de la file de l'équipe **en laissant le pasteur sans version** — le pire des
    deux mondes, et personne ne verrait la contradiction."""
    return InterpretationView.from_domain(
        await service.rendre_interpretation(
            demande_id=demande_id, octets=await request.body()
        )
    )


@router.post(
    "/interpretations/{demande_id}/refus",
    response_model=InterpretationView,
    summary="Refuser — et dire pourquoi",
)
async def refuser_interpretation(
    demande_id: UUID, payload: RefusBody, service: PieceServiceDep
) -> InterpretationView:
    """🔴 *Un travail abandonné laisse une trace, jamais un silence.*

    Une demande qui disparaît est indiscernable d'une demande jamais partie : le pasteur
    attendrait un samedi soir devant un écran muet. Le motif est donc exigé — une langue non
    couverte, un audio inaudible — et il remonte jusqu'à lui."""
    return InterpretationView.from_domain(
        await service.refuser_interpretation(
            demande_id=demande_id, motif=payload.motif
        )
    )


# -- la curation : écrire le corpus --------------------------------------------


@router.get(
    "/urim/coverage",
    response_model=CoverageView,
    summary="L'état réel de la curation — la seule mesure honnête d'Urim",
)
async def coverage(curation: CurationDep) -> CoverageView:
    return CoverageView.from_report(await curation.coverage())


@router.get(
    "/urim/pericopes",
    response_model=list[PericopeView],
    summary="Les unités curées, et ce qui leur manque",
)
async def list_pericopes(curation: CurationDep, book: str | None = None) -> list[PericopeView]:
    return [PericopeView.from_summary(s) for s in await curation.list_pericopes(book)]


@router.post(
    "/urim/pericopes",
    response_model=PericopeCreatedView,
    status_code=status.HTTP_201_CREATED,
    summary="Curer une unité littéraire — des bornes, et pourquoi celles-ci",
)
async def create_pericope(
    payload: PericopeBody, curation: CurationDep, relecteur: RelecteurDep
) -> PericopeCreatedView:
    nouvelle = await curation.create_pericope(
        PericopeDraft(
            book=payload.book,
            start_ch=payload.start_ch,
            start_v=payload.start_v,
            end_ch=payload.end_ch,
            end_v=payload.end_v,
            label=payload.label,
            rationale=payload.rationale,
            source_ref=payload.source_ref,
            reviewed_by=relecteur.nom,
        )
    )
    return PericopeCreatedView(id=nouvelle)


@router.put(
    "/urim/pericopes/{pericope_id}/bearings",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Peser les DIX loci d'un coup — « absent » compris (S38)",
)
async def set_bearings(
    pericope_id: UUID, payload: BearingsBody, curation: CurationDep, relecteur: RelecteurDep
) -> None:
    """La route par laquelle un verdict `corrige` devient une correction."""
    await curation.set_bearings(
        pericope_id,
        [
            BearingDraft(b.axis_code, b.strength, b.rationale, b.source_ref)
            for b in payload.bearings
        ],
        relecteur.nom,
    )


@router.post(
    "/urim/pericopes/{pericope_id}/caveats",
    status_code=status.HTTP_201_CREATED,
    summary="Ce que le texte ne dit PAS — exégétique, ou confessionnel",
)
async def add_caveat(
    pericope_id: UUID, payload: CaveatBody, curation: CurationDep, relecteur: RelecteurDep
) -> dict[str, UUID]:
    nouveau = await curation.add_caveat(
        pericope_id,
        CaveatDraft(
            axis_code=payload.axis_code,
            caveat_kind=payload.caveat_kind,
            body=payload.body,
            source_ref=payload.source_ref,
            tradition_scope=payload.tradition_scope,
        ),
        relecteur.nom,
    )
    return {"id": nouveau}


@router.post(
    "/urim/pericopes/{pericope_id}/context",
    status_code=status.HTTP_201_CREATED,
    summary="Contexte historique ou littéraire — sourcé, ou rien",
)
async def add_context(
    pericope_id: UUID, payload: ContextBody, curation: CurationDep, relecteur: RelecteurDep
) -> dict[str, UUID]:
    nouveau = await curation.add_context(
        pericope_id,
        ContextDraft(
            context_kind=payload.context_kind,
            body=payload.body,
            ordinal=payload.ordinal,
            source_ref=payload.source_ref,
        ),
        relecteur.nom,
    )
    return {"id": nouveau}


@router.put(
    "/urim/pericopes/{pericope_id}/feasibility",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Les couples plan x matière — un refus voyage avec son motif",
)
async def set_feasibility(
    pericope_id: UUID, payload: FeasibilityBody, curation: CurationDep, relecteur: RelecteurDep
) -> None:
    await curation.set_feasibility(
        pericope_id,
        [
            FeasibilityDraft(
                plan_source=c.plan_source,
                subject_matter=c.subject_matter,
                feasible=c.feasible,
                proof_text_risk=c.proof_text_risk,
                refusal_reason=c.refusal_reason,
            )
            for c in payload.couples
        ],
        relecteur.nom,
    )


@router.patch(
    "/urim/pericopes/{pericope_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reprendre à son compte une unité découpée par le modèle",
)
async def resign_pericope(
    pericope_id: UUID, payload: ResignBody, curation: CurationDep, relecteur: RelecteurDep
) -> None:
    """La contrepartie de `ia-mistral` — sans elle, le découpage généré serait sans retour."""
    await curation.resign_pericope(
        pericope_id,
        reviewed_by=relecteur.nom,
        label=payload.label,
        rationale=payload.rationale,
    )


@router.delete(
    "/urim/pericopes/{pericope_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer une curation fautive — sans quoi une erreur de relecture serait définitive",
)
async def delete_pericope(
    pericope_id: UUID, curation: CurationDep, relecteur: RelecteurDep
) -> None:
    """⚠️ Le relecteur est **exigé sans être enregistré** : rien ne trace qui a effacé.

    C'est la limite assumée du registre, et elle appartient au journal d'audit que la console
    d'administration apportera (dette R6 de `Security_Audit.md`). En attendant, exiger un
    signataire enrôlé ferme au moins la porte à un effacement anonyme muni du seul jeton."""
    await curation.delete_pericope(pericope_id)


# -- la relecture : juger ce qui y est écrit -----------------------------------


@router.get(
    "/urim/relecture/compteur",
    response_model=CompteurView,
    summary="De combien la promesse est en retard sur le fait",
)
async def compteur(relecture: RelectureDep) -> CompteurView:
    """0 pesée relue sur 45 557 le jour où cette route est née. C'est la mesure, pas un défaut
    d'affichage — et elle ne bougera que du travail d'un humain."""
    return CompteurView.depuis(await relecture.compteur())


@router.get(
    "/urim/relecture/file",
    response_model=list[UniteDeFileView],
    summary="La file du relecteur — du plus douteux au moins, moins ce qui est tranché",
)
async def file(
    relecture: RelectureDep,
    limite: int = Query(default=PAGE_DE_FILE, ge=1, le=100),
    decalage: int = Query(default=0, ge=0),
) -> list[UniteDeFileView]:
    """⚠️ **Ce n'est pas une liste d'erreurs.** Les détecteurs savent qu'une ligne est
    incohérente, formulaire, aberrante ou qu'elle cite un texte absent du passage ; aucun ne sait
    si une pesée est théologiquement juste. L'ordre est leur gravité, rien d'autre.

    Le décalage porte sur la file **brute** : une unité tranchée laisse un trou dans la page
    plutôt que de décaler les suivantes. Descendre la file en sautant des entrées serait la
    seule façon de manquer quelque chose sans le savoir."""
    return [
        UniteDeFileView.depuis(u) for u in await relecture.file(limite=limite, decalage=decalage)
    ]


@router.get(
    "/urim/relecture/unites/{pericope_id}",
    response_model=DossierView,
    summary="Le dossier — le passage, la curation en cause, et qui l'a signée",
)
async def dossier(pericope_id: UUID, relecture: RelectureDep) -> DossierView:
    return DossierView.depuis(await relecture.dossier(pericope_id))


@router.post(
    "/urim/relecture/unites/{pericope_id}/verdict",
    response_model=VerdictView,
    status_code=status.HTTP_201_CREATED,
    summary="Trancher — l'empreinte de la curation est prise ici, pas avant",
)
async def poser_verdict(
    pericope_id: UUID,
    payload: VerdictBody,
    relecture: RelectureDep,
    relecteur: RelecteurDep,
) -> VerdictView:
    """Le geste qui fait décroître la file.

    L'empreinte se calcule sur ce que la base contient **maintenant** : *une décision ne vaut
    que sur l'objet qu'elle a regardé.* Corollaire pratique — corriger après avoir signé périme
    sa propre signature, et l'unité revient en file. C'est voulu."""
    pose = await relecture.poser(
        pericope_id,
        portee=payload.portee,
        verdict=payload.verdict,
        note=payload.note,
        relecteur=relecteur,
    )
    return VerdictView.depuis(pose, pose.empreinte_jugee)


@router.delete(
    "/urim/relecture/unites/{pericope_id}/verdict/{portee}",
    response_model=VerdictRetireView,
    summary="Retirer un verdict posé à tort — rendre la table à ce qu'elle doit dire",
)
async def retirer_verdict(
    pericope_id: UUID, portee: str, relecture: RelectureDep, relecteur: RelecteurDep
) -> VerdictRetireView:
    """Un verdict posé à tort ne se répare pas en le **remplaçant** : cela laisserait une
    signature à la place d'une autre. La seule réparation honnête est de rendre la table à ce
    qu'elle doit dire — personne n'a relu cette unité."""
    signataire = await relecture.retirer(pericope_id, portee)
    return VerdictRetireView(portee=portee, etait_signe_par=signataire)
