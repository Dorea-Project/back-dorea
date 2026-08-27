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


class ElementInconnuError(UrimError):
    """Une section de plan dont le code n'est pas de la liste.

    ⚠️ **Le motif nomme les sections acceptées.** Un refus qui dit seulement « code invalide »
    laisse un pasteur devant un formulaire qu'il ne peut pas remplir — et la liste est courte
    assez pour tenir dans la phrase.

    On n'arrive ici qu'après canonisation : `Divisions`, `POINT`, `Intro`, `sous point` sont
    déjà retombés sur leur code. Ce qui est refusé est ce qu'on ne sait vraiment pas ranger, et
    ranger au hasard serait pire — la section disparaîtrait sous une autre."""

    code = "URI_ELEMENT_UNKNOWN"
    http_status = 422


class LivrableSansPlanError(UrimError):
    """**Le refus qui porte la règle centrale du livrable.**

    Le document met en page ce que le pasteur a écrit ; il ne l'écrit pas à sa place. Sans une
    division de son plan, il n'y a littéralement rien à imprimer — la page est vide par
    arithmétique, pas par politique.

    Le motif **oriente** : un refus qui n'oriente pas est une porte fermée (S2)."""

    code = "URI_DELIVERABLE_NO_PLAN"
    http_status = 422


class LivrableNonValideError(UrimError):
    """On demande le fichier d'un livrable qui porte une citation altérée.

    **Le seul endroit où le verrou du produit devient un refus HTTP.** Le dossier de
    validation, lui, revient en 201 avec ses verdicts — c'est ce que le produit veut
    montrer. Demander les octets de ce qui a été rejeté est autre chose : c'est réclamer
    précisément ce que le contrôle existe pour ne pas produire."""

    code = "URI_DELIVERABLE_NOT_VALIDATED"
    http_status = 409


class ArchiveIllisibleError(UrimError):
    """Ce qu'on demande d'archiver n'est pas lisible — et le motif vient **du corpus**.

    *« Hébreux 2 compte 18 versets »*, jamais *« saisie invalide »* : on dit ce qui manque au
    corpus, jamais ce qui manque au pasteur (S19). 422 — la forme est bonne, c'est le contenu
    qui ne désigne rien."""

    code = "URI_ARCHIVE_UNREADABLE"
    http_status = 422


class CorpusNonSemeError(UrimError):
    """Le corpus est vide — Urim n'a rien à lire.

    Un message qui dit **quoi faire**, pas seulement que ça casse : sans corpus, aucun
    étage ne peut travailler, et l'installation n'est pas terminée."""

    code = "URI_CORPUS_EMPTY"
    http_status = 503

class TitreIllisibleError(UrimError):
    """Un titre écrit à la main plus long qu'un titre.

    ⚠️ **Le motif porte la limite.** « Titre invalide » laisse le pasteur raccourcir au
    hasard jusqu'à ce que ça passe ; le nombre lui dit combien couper. Au-delà de cette
    longueur, ce n'est plus un titre mais la première phrase — et elle a déjà sa place."""

    code = "URI_TITLE_TOO_LONG"
    http_status = 422

    def __init__(self, *, limite: int) -> None:
        super().__init__(f"Un titre tient en {limite} caractères.")
        self.limite = limite


class RangementImpossibleError(UrimError):
    """Ranger, ou ressortir, une préparation abandonnée.

    « Abandonnée » est posé par « reformuler » : la saisie a rouvert sans rien conserver.
    La ranger écraserait la trace du renoncement ; la ressortir la ressusciterait sans son
    contenu. On refuse plutôt que d'inventer un état qui n'a jamais existé."""

    code = "URI_SHELVING_REFUSED"
    http_status = 409

    def __init__(self) -> None:
        super().__init__("Une préparation abandonnée ne se range pas.")

