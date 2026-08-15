"""Erreurs du module Urim — codes préfixés `URI_`.

⚠️ **Ne pas confondre avec `engine/errors.py`.** Là-bas vivent les *bugs* du moteur : un
étage sans motif, un ordre violé. Ici vivent les refus qu'un utilisateur peut provoquer et
comprendre.

Et surtout : **une ambiguïté n'est pas une erreur.** Une résolution qui hésite entre Jean
et 1 Jean, un bornage contesté, un couple homilétique impossible sont des `Outcome`
(`AWAIT`, `REFUSE`) qui reviennent en 200 avec leurs options et leur motif. Les transformer
en exceptions HTTP ferait disparaître exactement ce que le produit veut montrer.
"""

from app._shared.domain.errors import DomainError, NotFoundError, UnauthorizedError


class UrimError(DomainError):
    code = "URI_ERROR"


class PreparationIntrouvableError(NotFoundError):
    code = "URI_PREPARATION_NOT_FOUND"


class UniteIntrouvableError(NotFoundError):
    """L'unité littéraire qu'on veut relire n'existe pas — ou n'existe plus.

    Le second cas est le vrai : la file du relecteur est une **photographie** d'un balayage, et
    une unité retirée entre-temps y figure encore. 404 plutôt qu'une file filtrée à la lecture —
    la surface doit dire que l'entrée est périmée, pas la faire disparaître en silence."""

    code = "URI_UNIT_NOT_FOUND"


class RelecteurInconnuError(UnauthorizedError):
    """Le porteur n'est pas un relecteur enrôlé, ou ne l'est plus.

    ⚠️ **401 et non 403.** Le jeton de service Plateforme, lui, est bon — ce qui manque n'est pas
    un droit mais une **identité** : la surface ne sait pas qui signerait. C'est précisément la
    distinction que la console d'administration Dorea viendra formaliser."""

    code = "URI_REVIEWER_UNKNOWN"


class OptionInconnueError(UrimError):
    """Le pasteur répond une option que l'étage n'a pas proposée.

    Le cas normal est un client désynchronisé : les options d'un étage dépendent de l'état,
    et l'état a pu changer entre l'affichage et la réponse. 422 plutôt que 400 — la forme
    est bonne, c'est le contenu qui ne correspond plus."""

    code = "URI_UNKNOWN_OPTION"
    http_status = 422


class CurationInvalideError(UrimError):
    """Une curation refusée — et le motif dit **quoi faire**, pas seulement que c'est non.

    Ces refus protègent la seule chose qui distingue Urim d'un moteur de proof-texting : que
    ce qui s'affiche comme relu l'ait été. Un message vague transformerait un garde en
    obstacle, et un obstacle se contourne."""

    code = "URI_CURATION_INVALID"
    http_status = 422


class CorpusNonSemeError(UrimError):
    """Le corpus est vide — Urim n'a rien à lire.

    Un message qui dit **quoi faire**, pas seulement que ça casse : sans corpus, aucun
    étage ne peut travailler, et l'installation n'est pas terminée."""

    code = "URI_CORPUS_EMPTY"
    http_status = 503
