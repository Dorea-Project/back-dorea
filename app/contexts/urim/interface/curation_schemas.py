"""Schémas de la curation.

Les contraintes de forme sont ici ; les règles de fond (les dix loci ensemble, la signature
qui désigne quelqu'un, les bornes qui existent dans le texte) sont dans le service — elles
ont besoin du corpus, et un schéma ne le lit pas.

Une seule chose vaut d'être notée : `reviewed_by` est **requis partout**, y compris là où la
base ne le demanderait qu'une fois. Signer chaque acte plutôt que la session est ce qui rend
la trace lisible six mois plus tard.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.contexts.urim.application.curation import CoverageReport, PericopeSummary

Force = Literal["dominant", "porte", "resiste", "absent"]
GenreCaveat = Literal["exegetique", "confessionnel"]
GenreContexte = Literal["historique", "litteraire"]
Risque = Literal["faible", "moyen", "eleve"]


class PericopeBody(BaseModel):
    book: str = Field(min_length=2, max_length=40, description="Libellé français du livre")
    start_ch: int = Field(ge=1, le=150)
    start_v: int = Field(ge=1, le=200)
    end_ch: int = Field(ge=1, le=150)
    end_v: int = Field(ge=1, le=200)
    label: str | None = Field(default=None, max_length=200)
    #: La phrase que le pasteur lit pour comprendre *pourquoi ces bornes-là* — et pour vous
    #: contredire s'il n'est pas d'accord. Une longueur minimale est imposée par le service.
    rationale: str = Field(min_length=20, max_length=2000)
    source_ref: str = Field(min_length=2, max_length=300)
    reviewed_by: str = Field(min_length=3, max_length=120)


class PericopeCreatedView(BaseModel):
    id: UUID


class BearingItem(BaseModel):
    axis_code: str = Field(min_length=3, max_length=40)
    strength: Force
    #: Exigé même sur `absent` : dire *pourquoi* un texte ne porte pas un axe est aussi utile
    #: que de dire qu'il le porte, et c'est ce qui distingue « j'ai regardé » de « j'ai laissé ».
    rationale: str = Field(min_length=10, max_length=2000)
    source_ref: str = Field(min_length=2, max_length=300)


class BearingsBody(BaseModel):
    #: Exactement dix — le service vérifie que ce sont **les** dix loci, pas dix quelconques.
    bearings: list[BearingItem] = Field(min_length=10, max_length=10)
    reviewed_by: str = Field(min_length=3, max_length=120)


class CaveatBody(BaseModel):
    axis_code: str = Field(min_length=3, max_length=40)
    caveat_kind: GenreCaveat
    body: str = Field(min_length=10, max_length=2000)
    #: Requis pour un caveat confessionnel. Il sert à **nommer** les traditions qui divergent,
    #: jamais à filtrer l'affichage : un caveat confessionnel s'affiche toujours (D-F).
    tradition_scope: list[str] | None = Field(default=None, max_length=12)
    source_ref: str = Field(min_length=2, max_length=300)
    reviewed_by: str = Field(min_length=3, max_length=120)


class ContextBody(BaseModel):
    context_kind: GenreContexte
    body: str = Field(min_length=10, max_length=2000)
    ordinal: int = Field(ge=1, le=99)
    source_ref: str = Field(min_length=2, max_length=300)
    reviewed_by: str = Field(min_length=3, max_length=120)


class FeasibilityItem(BaseModel):
    plan_source: str = Field(min_length=3, max_length=40)
    subject_matter: str = Field(min_length=3, max_length=40)
    feasible: bool
    proof_text_risk: Risque
    refusal_reason: str | None = Field(default=None, max_length=2000)


class FeasibilityBody(BaseModel):
    couples: list[FeasibilityItem] = Field(min_length=1, max_length=40)
    reviewed_by: str = Field(min_length=3, max_length=120)


class PericopeView(BaseModel):
    id: UUID
    book: str
    bornes: str
    label: str | None
    reviewed_by: str
    n_bearings: int
    n_caveats: int
    n_context: int
    n_feasibility: int
    #: Les dix loci pesés. C'est le seul sens défendable de « relue » (S38) — en dessous,
    #: l'unité est ouverte, pas finie.
    complete: bool

    @classmethod
    def from_summary(cls, s: PericopeSummary) -> PericopeView:
        return cls(
            id=s.id, book=s.book,
            bornes=f"{s.start_ch}:{s.start_v}-{s.end_ch}:{s.end_v}",
            label=s.label, reviewed_by=s.reviewed_by,
            n_bearings=s.n_bearings, n_caveats=s.n_caveats,
            n_context=s.n_context, n_feasibility=s.n_feasibility,
            complete=s.complete,
        )


class CoverageView(BaseModel):
    verses_total: int
    verses_covered: int
    #: La part de l'Écriture sur laquelle Urim a du relu à dire. **Le chiffre qui compte** :
    #: partout ailleurs, le moteur dégrade — correctement, mais il dégrade.
    part_couverte: float
    pericopes: int
    pericopes_completes: int
    par_locus: dict[str, int]
    par_livre: dict[str, int]

    @classmethod
    def from_report(cls, r: CoverageReport) -> CoverageView:
        return cls(
            verses_total=r.verses_total, verses_covered=r.verses_covered,
            part_couverte=round(r.part_couverte, 5),
            pericopes=r.pericopes, pericopes_completes=r.pericopes_completes,
            par_locus=r.par_locus, par_livre=r.par_livre,
        )
