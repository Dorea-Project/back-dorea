"""DOREA-024 appliqué au dépôt de sermon — **ce que le fichier est, pas ce qu'il prétend être**.

Le `kind` arrive **déclaré en paramètre de requête** (`mobile_router.upload_sermon`) : le client
dit ce qu'il veut. Sans recoupement, des octets arbitraires déclarés `pdf` partent tels quels
dans `pypdf`, et déclarés `pptx` dans `zipfile`/`python-pptx` — une surface de parseur sur entrée
non fiable, alors que le contexte `media` s'impose déjà ce contrôle (`_looks_like`,
`media/application/media_store.py`).

Deux écarts avec `media`, et ils vont dans le même sens :

- la table est indexée par `SermonSourceKind`, pas par `Content-Type` : ici c'est le `kind` qui
  aiguille l'extracteur, donc c'est lui qu'il faut recouper ;
- **un format absent de la table est refusé**, là où `media` « n'a pas d'avis ». Le silence ne
  peut pas valoir laissez-passer : le jour où `kind=audio` appellera un service facturé à la
  minute (S-6, décision **D8bis**), le chemin le plus court pour vider un solde serait d'envoyer
  n'importe quoi en le déclarant sermon. Brancher un format oblige donc à écrire d'abord comment
  on le reconnaît — pour l'audio ce sera la durée lue dans l'en-tête (D8), pas une déclaration.

La garde ne dit pas que le fichier est **valide** : elle dit qu'il a la bonne tête pour entrer.
Ce que l'archive contient vraiment reste l'affaire de `python-pptx` et de la garde anti-bombe
(DOREA-011, `infrastructure/extractor.py`) — ces contrôles se complètent, ils ne se remplacent pas.
"""

from __future__ import annotations

from app.contexts.sermon.domain.enums import SermonSourceKind
from app.contexts.sermon.domain.errors import (
    SermonFileTypeMismatchError,
    UnsupportedSermonFormatError,
)

# Signatures réelles des formats acceptés au dépôt. Un tuple vide = format sans signature.
_SIGNATURES: dict[SermonSourceKind, tuple[bytes, ...]] = {
    # Du texte n'a pas de signature : n'importe quels octets se décodent (`errors="replace"`),
    # et il n'y a pas de parseur derrière — rien à protéger, donc rien à exiger.
    SermonSourceKind.TEXT: (),
    SermonSourceKind.PDF: (b"%PDF-",),
    # Un `.pptx` est une archive ZIP : en-tête de fichier local `PK\x03\x04`. Les deux autres
    # en-têtes ZIP (`PK\x05\x06` archive vide, `PK\x07\x08` fragmentée) ne sont pas des decks.
    SermonSourceKind.PPTX: (b"PK\x03\x04",),
}


def ensure_declared_kind(data: bytes, kind: SermonSourceKind) -> None:
    """Refuse le dépôt quand les octets ne sont pas ceux du format déclaré.

    Appelée **avant** l'extracteur : le parseur ne reçoit que des octets déjà reconnus."""
    if kind not in _SIGNATURES:
        # Fail-closed — un format qu'on ne sait pas reconnaître est un format qu'on n'accepte pas.
        raise UnsupportedSermonFormatError(
            "Ce format de sermon n'est pas encore pris en charge.",
            details={"kind": kind.value},
        )
    signatures = _SIGNATURES[kind]
    if signatures and not any(data.startswith(signature) for signature in signatures):
        raise SermonFileTypeMismatchError(
            "Le contenu du fichier ne correspond pas au format annoncé.",
            details={"kind": kind.value},
        )
