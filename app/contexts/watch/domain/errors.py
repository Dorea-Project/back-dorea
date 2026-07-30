"""Erreurs du moteur de veille — codes préfixés `WATCH_`."""

from app._shared.domain.errors import DomainError


class WatchError(DomainError):
    code = "WATCH_ERROR"


class ForbiddenFactKindError(WatchError):
    """Un type de fait d'une famille que le produit s'interdit : inaction, argent, inférence.

    Levée à l'**enregistrement** d'une source, donc au démarrage — jamais en production."""

    code = "WATCH_FORBIDDEN_FACT_KIND"
    http_status = 500


class ActorRequiredError(WatchError):
    """Une source enregistrée pour un fait qui peut **retirer quelqu'un de la veille** sans
    déclarer l'acteur de ce geste.

    Levée à l'enregistrement, donc au démarrage. Sans elle, le repli « à défaut, le sujet » de la
    matérialisation faisait du **défunt** l'auteur déclaré de sa propre exclusion : une donnée
    d'audit fausse sur l'acte le plus grave du système."""

    code = "WATCH_ACTOR_REQUIRED"
    http_status = 500


class StateScopeError(WatchError):
    """Un interpreter a interrogé l'état sur **quelqu'un d'autre** que le sujet de son fait.

    L'état n'est plus chargé à l'échelle de l'église : il est lu pour le sujet du fait, et pour lui
    seul. Une question posée sur un tiers recevrait donc une réponse vide — et l'interpreter se
    tromperait en silence, ce qui est le pire des deux mondes. Un interpreter n'a jamais eu de
    raison légitime de regarder quelqu'un d'autre : la règle devient un type."""

    code = "WATCH_STATE_SCOPE"
    http_status = 500


class ReplayWouldEraseHumanActsError(WatchError):
    """Un rejeu du ledger effacerait des gestes que le journal ne contient pas.

    Le ledger porte des **faits** ; « j'ai ouvert ce cas », « j'ai appelé », « je ferme, voilà ce
    que j'ai trouvé », « cette consolation a été remise » sont des **actes** posés sur la
    projection. Les reconstruire est impossible : les rejouer reviendrait à les inventer.

    Tant que ces gestes ne sont pas eux-mêmes entrés au ledger, la reprojection est réservée aux
    églises où personne n'a encore rien fait — ou explicitement forcée, en sachant ce qu'on perd."""

    code = "WATCH_REPLAY_WOULD_ERASE"
    http_status = 409


class SourceNotRegisteredError(WatchError):
    """Un fait venu d'une source que l'engine ne connaît pas. Ajouter ≠ modifier."""

    code = "WATCH_SOURCE_NOT_REGISTERED"
    http_status = 422


class FactKindNotAllowedError(WatchError):
    """Cette source est enregistrée, mais pas pour dire cela."""

    code = "WATCH_KIND_NOT_ALLOWED"
    http_status = 422


class ConsentRequiredError(WatchError):
    """Ce type de fait ne peut pas entrer sans preuve de consentement."""

    code = "WATCH_CONSENT_REQUIRED"
    http_status = 422


class InvalidPayloadError(WatchError):
    """Le payload ne porte pas ce que ce type de fait exige."""

    code = "WATCH_INVALID_PAYLOAD"
    http_status = 422


class InvalidSignalTransitionError(WatchError):
    """Cette transition n'existe pas dans la machine à états. Refusée, pas invalidée."""

    code = "WATCH_INVALID_TRANSITION"
    http_status = 409


class AbsorbingOutcomeError(WatchError):
    """L'issue est absorbante : décès, ou demande explicite qu'on cesse. Rien n'en sort."""

    code = "WATCH_ABSORBING_OUTCOME"
    http_status = 409


class HumanClosureRequiredError(WatchError):
    """Fermer un cas est un acte humain — sauf quand le cas n'était pas réel."""

    code = "WATCH_HUMAN_CLOSURE_REQUIRED"
    http_status = 422


class SelfReferentError(WatchError):
    """Nul n'est son propre référent — sinon la couverture se remplirait de solitudes."""

    code = "WATCH_SELF_REFERENT"
    http_status = 422


class IneligibleReferentError(WatchError):
    """Compte inactif, appartenance close, ou personne retirée de la veille."""

    code = "WATCH_INELIGIBLE_REFERENT"
    http_status = 422


class CaseNotFoundError(WatchError):
    code = "WATCH_CASE_NOT_FOUND"
    http_status = 404


class NotYourCaseError(WatchError):
    """Un cas confié à quelqu'un d'autre. Deux responsables sur la même personne, c'est le
    double appel du même soir que tout le module existe pour éviter."""

    code = "WATCH_NOT_YOUR_CASE"
    http_status = 403


class SelfConcernError(WatchError):
    """On ne se signale pas soi-même par ce canal — c'est une déclaration, et elle passe devant.

    Router les deux vers le même type ferait entrer sa propre demande d'aide dans le plafond de
    débit, alors qu'elle en est justement exemptée."""

    code = "WATCH_SELF_CONCERN"
    http_status = 422


class ConcernRefusedError(WatchError):
    """La personne est retirée de la veille, ou a demandé qu'on cesse de la contacter.

    Cette parole est absorbante : aucune bonne intention ne la reprend."""

    code = "WATCH_CONCERN_REFUSED"
    http_status = 409


class NoInterpreterError(WatchError):
    """Aucun interpreter enregistré pour ce type de fait à cette date.

    Le fait reste au ledger — il sera interprété quand l'interpreter existera. On ne perd rien."""

    code = "WATCH_NO_INTERPRETER"
    http_status = 500
