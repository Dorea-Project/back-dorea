"""Schémas de la surface du relecteur.

⚠️ **Aucun de ces corps ne porte de `reviewed_by`, et c'est le cœur du dispositif.** Le nom du
signataire ne se saisit plus : il est rendu par le registre contre la preuve d'un secret
(`X-Urim-Relecteur`). Un champ de formulaire ne peut pas se défendre d'être rempli du nom de
quelqu'un d'autre — c'est arrivé, et il a fallu retirer le verdict.

L'autre parti pris tient en une phrase : **la signature s'affiche partout**. `signature` sur
l'unité, `signee_par` et `generee` sur chaque ligne, `lignes_generees` sur le dossier. Rien de
généré ne doit pouvoir se confondre avec une relecture, pas même par inattention.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.contexts.urim.application.relecture import (
    Compteur,
    Dossier,
    LigneCuration,
    Signalement,
    UniteSignalee,
    VerdictPose,
    Verset,
)

Verdict = Literal["accepte", "corrige", "a_reprendre"]


class VerdictBody(BaseModel):
    """Ce qu'un relecteur envoie pour trancher. **Trois champs, aucun nom.**"""

    #: Le code d'un détecteur (`D1`…`D5`) ou `ensemble`. Le service refuse une portée qui n'a
    #: rien signalé sur cette unité : un verdict qui ne couvre rien aurait l'air d'un travail
    #: fait sans faire décroître la file d'une unité.
    portee: str = Field(min_length=2, max_length=20)
    #: ⚠️ `accepte` n'est pas « c'est bien » : c'est *« l'écart est réel et la curation est juste
    #: quand même »*. Apocalypse 5 porte réellement huit loci ; sans ce verdict elle reviendrait
    #: en tête de file éternellement.
    verdict: Verdict
    note: str | None = Field(default=None, max_length=2000)


class SignalementView(BaseModel):
    detecteur: str
    libelle: str
    gravite: int
    detail: str
    corps: str
    #: Vrai quand la curation a changé depuis le balayage : le signalement parle alors d'une
    #: ligne qui n'est plus celle qu'on lit. Affiché plutôt que filtré — c'est au relecteur de
    #: décider si ça vaut encore quelque chose.
    perime: bool

    @classmethod
    def depuis(cls, s: Signalement, empreinte_courante: str) -> SignalementView:
        return cls(
            detecteur=s.detecteur, libelle=s.libelle, gravite=s.gravite,
            detail=s.detail, corps=s.corps,
            perime=bool(s.empreinte_balayage) and s.empreinte_balayage != empreinte_courante,
        )


class VerdictView(BaseModel):
    portee: str
    verdict: str
    note: str | None
    relu_par: str
    relu_le: datetime
    empreinte_jugee: str
    #: Faux dès que la curation jugée a changé. Le verdict reste affiché — il dit ce que
    #: quelqu'un a pensé un jour — mais il ne couvre plus rien, et l'unité est revenue en file.
    encore_valable: bool

    @classmethod
    def depuis(cls, v: VerdictPose, empreinte_courante: str) -> VerdictView:
        return cls(
            portee=v.portee, verdict=v.verdict, note=v.note, relu_par=v.relu_par,
            relu_le=v.relu_le, empreinte_jugee=v.empreinte_jugee,
            encore_valable=v.empreinte_jugee == empreinte_courante,
        )


class UniteDeFileView(BaseModel):
    id: UUID
    reference: str
    libelle: str | None
    #: Qui a signé le découpage — `ia-mistral` dans l'immense majorité des cas, et il faut
    #: que ça se voie.
    signature: str
    poids: int
    relue_en_entier: bool
    empreinte_courante: str
    signalements: list[SignalementView]
    verdicts: list[VerdictView]

    @classmethod
    def depuis(cls, u: UniteSignalee) -> UniteDeFileView:
        return cls(
            id=u.id, reference=u.reference, libelle=u.libelle, signature=u.signature,
            poids=u.poids, relue_en_entier=u.relue_en_entier,
            empreinte_courante=u.empreinte_courante,
            signalements=[
                SignalementView.depuis(s, u.empreinte_courante) for s in u.signalements
            ],
            verdicts=[VerdictView.depuis(v, u.empreinte_courante) for v in u.verdicts],
        )


class VersetView(BaseModel):
    chapitre: int
    verset: int
    texte: str

    @classmethod
    def depuis(cls, v: Verset) -> VersetView:
        return cls(chapitre=v.chapitre, verset=v.verset, texte=v.texte)


class LigneView(BaseModel):
    couche: str
    axe: str
    force: str | None
    corps: str
    source: str
    signee_par: str
    generee: bool

    @classmethod
    def depuis(cls, ligne: LigneCuration) -> LigneView:
        return cls(
            couche=ligne.couche, axe=ligne.axe, force=ligne.force, corps=ligne.corps,
            source=ligne.source, signee_par=ligne.signee_par, generee=ligne.generee,
        )


class DossierView(BaseModel):
    """Le passage d'abord, la curation ensuite, les signalements en dernier.

    L'ordre du modèle est l'ordre de lecture attendu : **juger une pesée sans lire le passage
    qu'elle pèse n'est pas une relecture, c'est une signature.**"""

    unite: UniteDeFileView
    versets: list[VersetView]
    lignes: list[LigneView]
    lignes_generees: int

    @classmethod
    def depuis(cls, d: Dossier) -> DossierView:
        return cls(
            unite=UniteDeFileView.depuis(d.unite),
            versets=[VersetView.depuis(v) for v in d.versets],
            lignes=[LigneView.depuis(ligne) for ligne in d.lignes],
            lignes_generees=d.lignes_generees,
        )


class CompteurView(BaseModel):
    """**De combien la promesse est en retard sur le fait.** La première ligne du rapport."""

    unites: int
    unites_signalees: int
    unites_relues: int
    signalements: int
    signalements_tranches: int
    lignes: int
    lignes_humaines: int
    part_relue: float
    #: ⚠️ Quand la file a été calculée. Nulle tant qu'aucun balayage n'a été matérialisé — et
    #: une file dont on ne sait pas l'âge ment.
    derniere_analyse: datetime | None

    @classmethod
    def depuis(cls, c: Compteur) -> CompteurView:
        return cls(
            unites=c.unites, unites_signalees=c.unites_signalees,
            unites_relues=c.unites_relues, signalements=c.signalements,
            signalements_tranches=c.signalements_tranches,
            lignes=c.lignes, lignes_humaines=c.lignes_humaines,
            part_relue=round(c.part_relue, 6), derniere_analyse=c.derniere_analyse,
        )


class VerdictRetireView(BaseModel):
    portee: str
    #: Qui l'avait signé. La réponse le rend parce qu'un retrait silencieux effacerait la seule
    #: chose qu'on voudra savoir ensuite : au nom de qui le verdict avait été posé.
    etait_signe_par: str
