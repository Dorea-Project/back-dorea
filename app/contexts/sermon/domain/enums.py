"""États et formats d'un sermon (contexte `sermon`)."""

from enum import StrEnum


class SermonStatus(StrEnum):
    """Cycle de vie — **l'IA rédige, le pasteur approuve, rien ne se publie sans onction.**

    Le digest IA (résumé, capsules, questions) sera relu à l'état `approved` (chantier S-1) ;
    ici, le socle porte déjà les trois états et leurs transitions."""

    DRAFT = "draft"  # déposé, en attente d'approbation du pasteur
    APPROVED = "approved"  # le pasteur a validé — prêt à publier
    PUBLISHED = "published"  # publié (capsules au fil, compagnon actif)


class SermonSourceKind(StrEnum):
    """D'où vient le texte. Un seul port d'extraction normalise tout en **texte** ; les formats
    lourds (PDF/PPTX/audio) ne sont que des adaptateurs ajoutés plus tard (S-5/S-6)."""

    TEXT = "text"  # texte / notes collées (S-0)
    PDF = "pdf"  # document PDF (S-5)
    PPTX = "pptx"  # présentation (S-5)
    AUDIO = "audio"  # enregistrement à transcrire (S-6)


class CompanionStatus(StrEnum):
    """L'état d'une session de compagnon (S-3) — la conversation privée d'un membre."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
