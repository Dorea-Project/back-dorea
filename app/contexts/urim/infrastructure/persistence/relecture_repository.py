"""Lecture de la file et écriture des verdicts. **Rien ici ne juge.**

Deux choses méritent d'être lues.

**L'empreinte se recalcule, elle ne se lit pas.** Elle pourrait être stockée sur la péricope et
mise à jour à chaque écriture ; ce serait plus rapide et faux le premier jour où un script écrit
du corpus sans passer par le service — ce qui est exactement comment les 45 557 lignes actuelles
sont entrées. Une valeur dérivée qui a un chemin d'écriture parallèle n'est pas une valeur
dérivée, c'est un cache qui ment.

**Le poids d'une unité est une somme SQL, pas un classement.** `sum(severity)` reproduit ce que
le détecteur écrit dans sa file texte. La base ne connaît aucun autre ordre, et n'a pas à en
connaître : *les détecteurs signalent, ils ne jugent pas.*
"""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.urim.application.curation import (
    COUCHE_MISE_EN_GARDE,
    COUCHE_PESEE,
    PORTEE_ENSEMBLE,
    SIGNATAIRE_IA,
    empreinte_de_curation,
    verdict_couvre,
)
from app.contexts.urim.application.relecture import (
    Compteur,
    LigneCuration,
    Signalement,
    UniteSignalee,
    VerdictPose,
    Verset,
)
from app.contexts.urim.infrastructure.persistence.corpus_models import (
    CorpusBookNameModel,
    CorpusDoctrinalBearingModel,
    CorpusDoctrinalCaveatModel,
    CorpusPericopeModel,
    CorpusReviewerModel,
    CorpusReviewModel,
    CorpusSignalModel,
    CorpusVerseModel,
    CorpusVersionModel,
)

#: La version **contre laquelle la curation a été écrite**. Servir le passage dans une autre
#: ferait relire une pesée de la Segond sur le français de 1744 — c'est déjà ce qui avait produit
#: treize fausses accusations d'invention dans le détecteur d'écarts.
VERSION_DE_CURATION = "LSG"


class SqlRegistreRepository:
    """Le registre des relecteurs. **Un inactif est introuvable**, pas « trouvé puis refusé ».

    La révocation n'efface pas la ligne — les verdicts déjà signés doivent continuer de désigner
    quelqu'un — mais elle doit se comporter comme une absence à l'authentification, sinon la
    différence entre « révoqué » et « inconnu » fuite dans les réponses."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def secret_et_nom(self, identifiant: str) -> tuple[str, str] | None:
        ligne = (await self._s.execute(
            select(CorpusReviewerModel.secret_hash, CorpusReviewerModel.display_name)
            .where(CorpusReviewerModel.identifiant == identifiant)
            .where(CorpusReviewerModel.active.is_(True))
        )).first()
        return (ligne[0], ligne[1]) if ligne else None


class SqlRelectureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # -- la file ---------------------------------------------------------------

    async def file(self, *, limite: int, decalage: int) -> list[UniteSignalee]:
        poids = (await self._s.execute(
            select(
                CorpusSignalModel.pericope_id,
                func.sum(CorpusSignalModel.severity).label("poids"),
            )
            .group_by(CorpusSignalModel.pericope_id)
            # 🔴 **Le départage n'est pas cosmétique.** Les 139 unités de la première file pèsent
            # 2 ou 3 : sans second critère, Postgres rend les ex æquo dans un ordre libre, et
            # deux appels ne donnent pas la même page. Avec `LIMIT/OFFSET`, une unité peut alors
            # passer de la page 2 à la page 1 entre deux requêtes — et **disparaître sans que le
            # relecteur puisse le savoir**. C'est précisément ce que la surface promet d'éviter.
            .order_by(
                func.sum(CorpusSignalModel.severity).desc(),
                CorpusSignalModel.pericope_id,
            )
            .limit(limite)
            .offset(decalage)
        )).all()
        return await self._unites([ligne[0] for ligne in poids])

    async def unite(self, pericope_id: UUID) -> UniteSignalee | None:
        trouvees = await self._unites([pericope_id])
        return trouvees[0] if trouvees else None

    async def _unites(self, ids: list[UUID]) -> list[UniteSignalee]:
        if not ids:
            return []
        rangs = {cle: rang for rang, cle in enumerate(ids)}
        libelles = await self._libelles_de_livres()

        pericopes = (await self._s.execute(
            select(CorpusPericopeModel).where(CorpusPericopeModel.id.in_(ids))
        )).scalars().all()

        signalements: dict[UUID, list[Signalement]] = defaultdict(list)
        for s in (await self._s.execute(
            select(CorpusSignalModel)
            .where(CorpusSignalModel.pericope_id.in_(ids))
            .order_by(CorpusSignalModel.severity.desc())
        )).scalars():
            signalements[s.pericope_id].append(Signalement(
                detecteur=s.detector, libelle=s.label, gravite=s.severity,
                detail=s.detail, corps=s.body, empreinte_balayage=s.scan_fingerprint,
            ))

        verdicts: dict[UUID, list[VerdictPose]] = defaultdict(list)
        for r in (await self._s.execute(
            select(CorpusReviewModel).where(CorpusReviewModel.pericope_id.in_(ids))
        )).scalars():
            verdicts[r.pericope_id].append(_en_verdict(r))

        empreintes = await self._empreintes(ids)

        unites = [
            UniteSignalee(
                id=p.id,
                reference=(
                    f"{libelles.get(p.book_id, p.book_id)} "
                    f"{p.start_ch}:{p.start_v}-{p.end_v}"
                ),
                libelle=p.label,
                signature=p.reviewed_by,
                empreinte_courante=empreintes.get(p.id, ""),
                signalements=signalements.get(p.id, []),
                verdicts=verdicts.get(p.id, []),
            )
            for p in pericopes
        ]
        # L'ordre des identifiants reçus **est** l'ordre de la file ; `IN (...)` ne le tient pas.
        unites.sort(key=lambda u: rangs.get(u.id, len(rangs)))
        return unites

    # -- le dossier ------------------------------------------------------------

    async def lignes(self, pericope_id: UUID) -> list[LigneCuration]:
        lues = [
            LigneCuration(
                couche=COUCHE_PESEE, axe=b.axis_code, force=b.strength,
                corps=b.rationale, source=b.source_ref, signee_par=b.reviewed_by,
            )
            for b in (await self._s.execute(
                select(CorpusDoctrinalBearingModel)
                .where(CorpusDoctrinalBearingModel.pericope_id == pericope_id)
                .order_by(CorpusDoctrinalBearingModel.axis_code)
            )).scalars()
        ]
        lues += [
            LigneCuration(
                couche=COUCHE_MISE_EN_GARDE, axe=c.axis_code, force=None,
                corps=c.body, source=c.source_ref, signee_par=c.reviewed_by,
            )
            for c in (await self._s.execute(
                select(CorpusDoctrinalCaveatModel)
                .where(CorpusDoctrinalCaveatModel.pericope_id == pericope_id)
                .order_by(CorpusDoctrinalCaveatModel.axis_code)
            )).scalars()
        ]
        return lues

    async def texte(self, pericope_id: UUID) -> list[Verset]:
        """Le passage, dans la version contre laquelle la curation a été écrite.

        Sans lui il n'y a pas de relecture possible : juger une pesée sans le passage qu'elle
        pèse revient à juger la vraisemblance d'une phrase, ce que le modèle fait déjà mieux."""
        bornes = await self._s.get(CorpusPericopeModel, pericope_id)
        if bornes is None:
            return []
        lignes = await self._s.execute(
            select(CorpusVerseModel.chapter, CorpusVerseModel.verse, CorpusVerseModel.body)
            .join(CorpusVersionModel, CorpusVersionModel.id == CorpusVerseModel.version_id)
            .where(CorpusVersionModel.code == VERSION_DE_CURATION)
            .where(CorpusVerseModel.book_id == bornes.book_id)
            .order_by(CorpusVerseModel.chapter, CorpusVerseModel.verse)
        )
        return [
            Verset(chapitre=ch, verset=v, texte=corps)
            for ch, v, corps in lignes
            if (bornes.start_ch, bornes.start_v) <= (ch, v) <= (bornes.end_ch, bornes.end_v)
        ]

    # -- le verdict ------------------------------------------------------------

    async def enregistrer_verdict(self, pericope_id: UUID, verdict: VerdictPose) -> None:
        existant = await self._s.get(CorpusReviewModel, (pericope_id, verdict.portee))
        if existant is None:
            self._s.add(CorpusReviewModel(
                pericope_id=pericope_id, scope=verdict.portee, verdict=verdict.verdict,
                judged_fingerprint=verdict.empreinte_jugee, note=verdict.note,
                reviewed_by=verdict.relu_par, reviewed_at=verdict.relu_le,
            ))
        else:
            # Un relecteur change d'avis : c'est son droit, et la trace suit son dernier mot.
            existant.verdict = verdict.verdict
            existant.judged_fingerprint = verdict.empreinte_jugee
            existant.note = verdict.note
            existant.reviewed_by = verdict.relu_par
            existant.reviewed_at = verdict.relu_le
        await self._s.flush()

    async def retirer_verdict(self, pericope_id: UUID, portee: str) -> str | None:
        existant = await self._s.get(CorpusReviewModel, (pericope_id, portee))
        if existant is None:
            return None
        signataire = existant.reviewed_by
        await self._s.delete(existant)
        await self._s.flush()
        return signataire

    # -- le compteur -----------------------------------------------------------

    async def compteur(self) -> Compteur:
        unites = await self._s.scalar(
            select(func.count()).select_from(CorpusPericopeModel)
        ) or 0
        signalements = await self._s.scalar(
            select(func.count()).select_from(CorpusSignalModel)
        ) or 0
        unites_signalees = await self._s.scalar(
            select(func.count(func.distinct(CorpusSignalModel.pericope_id)))
        ) or 0
        derniere = await self._s.scalar(select(func.max(CorpusSignalModel.scanned_at)))

        # ⚠️ **La mesure porte sur les signatures, pas sur les verdicts.** Un `accepte` laisse la
        # ligne signée `ia-mistral` — et c'est juste : le relecteur a validé une ligne générée,
        # il ne l'a pas écrite. Compter les verdicts ici gonflerait le chiffre exactement là où
        # il doit rester sévère.
        lignes, humaines = 0, 0
        for modele in (CorpusDoctrinalBearingModel, CorpusDoctrinalCaveatModel):
            lignes += await self._s.scalar(select(func.count()).select_from(modele)) or 0
            humaines += await self._s.scalar(
                select(func.count()).select_from(modele)
                .where(modele.reviewed_by != SIGNATAIRE_IA)
            ) or 0

        juges: dict[UUID, dict[str, str]] = defaultdict(dict)
        for r in (await self._s.execute(select(CorpusReviewModel))).scalars():
            juges[r.pericope_id][r.scope] = r.judged_fingerprint
        empreintes = await self._empreintes(list(juges))

        relues = sum(
            1 for cle, portees in juges.items()
            if portees.get(PORTEE_ENSEMBLE) == empreintes.get(cle, "")
        )
        tranches = 0
        if juges:
            for s in (await self._s.execute(
                select(CorpusSignalModel.pericope_id, CorpusSignalModel.detector)
                .where(CorpusSignalModel.pericope_id.in_(list(juges)))
            )).all():
                if verdict_couvre(juges[s[0]], empreintes.get(s[0], ""), s[1]):
                    tranches += 1

        return Compteur(
            unites=unites, unites_signalees=unites_signalees, unites_relues=relues,
            signalements=signalements, signalements_tranches=tranches,
            lignes=lignes, lignes_humaines=humaines, derniere_analyse=derniere,
        )

    # -- outils ----------------------------------------------------------------

    async def _empreintes(self, ids: list[UUID]) -> dict[UUID, str]:
        """L'empreinte courante de chaque unité — recalculée, jamais lue."""
        if not ids:
            return {}
        par_unite: dict[UUID, list[tuple[str, str, str]]] = defaultdict(list)
        for b in (await self._s.execute(
            select(
                CorpusDoctrinalBearingModel.pericope_id,
                CorpusDoctrinalBearingModel.axis_code,
                CorpusDoctrinalBearingModel.rationale,
            ).where(CorpusDoctrinalBearingModel.pericope_id.in_(ids))
        )).all():
            par_unite[b[0]].append((COUCHE_PESEE, b[1], b[2]))
        for c in (await self._s.execute(
            select(
                CorpusDoctrinalCaveatModel.pericope_id,
                CorpusDoctrinalCaveatModel.axis_code,
                CorpusDoctrinalCaveatModel.body,
            ).where(CorpusDoctrinalCaveatModel.pericope_id.in_(ids))
        )).all():
            par_unite[c[0]].append((COUCHE_MISE_EN_GARDE, c[1], c[2]))
        return {cle: empreinte_de_curation(par_unite.get(cle, [])) for cle in ids}

    async def _libelles_de_livres(self) -> dict[int, str]:
        return dict((await self._s.execute(
            select(CorpusBookNameModel.book_id, CorpusBookNameModel.label)
            .where(CorpusBookNameModel.language == "fr")
        )).all())


def _en_verdict(ligne: CorpusReviewModel) -> VerdictPose:
    return VerdictPose(
        portee=ligne.scope, verdict=ligne.verdict, note=ligne.note,
        relu_par=ligne.reviewed_by, relu_le=ligne.reviewed_at,
        empreinte_jugee=ligne.judged_fingerprint,
    )
