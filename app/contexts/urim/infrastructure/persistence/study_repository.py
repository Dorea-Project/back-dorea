"""Persistance des préparations et des réservations.

Rien ici ne raisonne : on lit et on écrit ce que le service a décidé. La seule règle
tenue par ce module est celle de la réservation — et elle est tenue **par la base**, pas
par un `if` : deux ouvertures concurrentes sur le même texte se disputent une ligne, et
c'est l'index unique qui tranche.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.urim.application.ports import (
    ElementRecord,
    PlanSuggestion,
    PreparationRecord,
    SuggestionSnapshot,
    SupportRecord,
    UsageSnapshot,
)
from app.contexts.urim.engine.state import AxisGloss, PassageSuggestion, Reference
from app.contexts.urim.infrastructure.persistence.models import (
    UrimModelSuggestionModel,
    UrimPlanSuggestionModel,
    UrimPreachedModel,
    UrimPreparationDismissalModel,
    UrimPreparationElementModel,
    UrimPreparationModel,
    UrimPreparationSupportModel,
    UrimResolutionAttemptModel,
    UrimStudyReservationModel,
    UrimUsageWindowModel,
)

#: Une réservation qui n'aboutit pas se périme d'elle-même. Le pasteur qui ferme sa
#: tablette au milieu d'une préparation ne doit pas bloquer son église.
_DUREE_RESERVATION = timedelta(hours=24)

#: Plafond par défaut d'une église sans fenêtre configurée. Généreux **exprès** : le
#: repli sur le domaine public est une protection de licence, pas un levier commercial,
#: et il ne doit jamais se déclencher par accident.
_PLAFOND_DEFAUT = 500

#: Quota mensuel de **textes assistés** d'un compte sans église — en nombre de péricopes
#: distinctes préparées avec le modèle dans le mois calendaire.
#:
#: ⚠️ **Volontairement haut, et provisoirement.** La valeur visée est 3 ; elle ne peut pas être
#: posée tant qu'aucune sortie ne fonctionne. `business_accounts` enregistre une carte prépayée
#: sans aucun cycle de facturation, et l'abonnement d'église n'existe qu'en note de design :
#: un pasteur qui bute sur 3 aujourd'hui ne pourrait ni payer ni rattacher une église. Un
#: plafond sans sortie n'est pas un plafond, c'est un cul-de-sac.
#:
#: Le jour où `UnlimitedTierPort` a un adaptateur qui répond « oui » à quelqu'un, ce nombre
#: descend à 3 et rien d'autre ne bouge.
_QUOTA_PERSONNEL = 500


class SqlStudyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, record: PreparationRecord) -> None:
        self._s.add(UrimPreparationModel(
            id=record.id,
            church_id=record.church_id,
            author_id=record.author_id,
            entry_mode=record.entry_mode,
            raw_input=record.raw_input,
            entry_origin=record.entry_origin,
            corpus_snapshot=record.corpus_snapshot,
            pericope_id=record.pericope_id,
            version_id=record.version_id,
            axis_code=record.axis_code,
            plan_source=record.plan_source,
            subject_matter=record.subject_matter,
            theme=record.theme,
            service_date=record.service_date,
            service_timezone=record.service_timezone,
            status=record.status,
            opened_at=record.opened_at or datetime.now(),
        ))
        await self._s.flush()

    async def get(self, study_id: UUID) -> PreparationRecord | None:
        row = await self._s.get(UrimPreparationModel, study_id)
        if row is None:
            return None
        return PreparationRecord(
            id=row.id,
            church_id=row.church_id,
            author_id=row.author_id,
            raw_input=row.raw_input,
            entry_mode=row.entry_mode,
            entry_origin=row.entry_origin,
            corpus_snapshot=row.corpus_snapshot,
            resolved_ref=await self._dernier_choix(study_id),
            pericope_id=row.pericope_id,
            # Le bornage forcé se **déduit** : des bornes explicites sans unité curée, il
            # n'y a pas d'autre façon d'y arriver. Une colonne de plus dirait la même
            # chose et pourrait la contredire.
            bounds_overridden=row.pericope_id is None and row.override_start_ch is not None,
            version_id=row.version_id,
            axis_code=row.axis_code,
            plan_source=row.plan_source,
            subject_matter=row.subject_matter,
            theme=row.theme,
            service_date=row.service_date,
            service_timezone=row.service_timezone,
            status=row.status,
            opened_at=row.opened_at,
            closed_at=row.closed_at,
        )

    async def save(self, record: PreparationRecord) -> None:
        row = await self._s.get(UrimPreparationModel, record.id)
        if row is None:
            return
        row.entry_mode = record.entry_mode
        row.entry_origin = record.entry_origin
        row.pericope_id = record.pericope_id
        row.version_id = record.version_id
        row.axis_code = record.axis_code
        row.plan_source = record.plan_source
        row.subject_matter = record.subject_matter
        row.theme = record.theme
        row.service_date = record.service_date
        row.status = record.status
        row.closed_at = record.closed_at
        if record.bounds_overridden:
            ref = record.resolved_ref.split("|") if record.resolved_ref else []
            if len(ref) == 4:
                row.override_start_ch = int(ref[1]) if ref[1] else None
                row.override_start_v = int(ref[2]) if ref[2] else None
                row.override_end_ch = int(ref[1]) if ref[1] else None
                row.override_end_v = int(ref[3]) if ref[3] else (
                    int(ref[2]) if ref[2] else None
                )
        else:
            row.override_start_ch = row.override_start_v = None
            row.override_end_ch = row.override_end_v = None
        await self._s.flush()

    async def _dernier_choix(self, study_id: UUID) -> str | None:
        return await self._s.scalar(
            select(UrimResolutionAttemptModel.chosen_ref)
            .where(UrimResolutionAttemptModel.preparation_id == study_id)
            .where(UrimResolutionAttemptModel.chosen_ref.is_not(None))
            .order_by(UrimResolutionAttemptModel.attempted_at.desc())
            .limit(1)
        )

    async def record_attempt(
        self,
        *,
        study_id: UUID,
        input_hash: str,
        candidates: list[str],
        chosen_ref: str | None,
        chosen_by: str | None,
        at: datetime,
    ) -> None:
        self._s.add(UrimResolutionAttemptModel(
            id=uuid4(),
            preparation_id=study_id,
            input_hash=input_hash,
            candidates=candidates,
            chosen_ref=chosen_ref,
            chosen_by=chosen_by,
            attempted_at=at,
        ))
        await self._s.flush()

    async def set_elements(self, study_id: UUID, elements: list[ElementRecord]) -> None:
        existants = {
            (r.element_code): r
            for r in (await self._s.execute(
                select(UrimPreparationElementModel).where(
                    UrimPreparationElementModel.preparation_id == study_id
                )
            )).scalars()
        }
        for e in elements:
            row = existants.get(e.element_code)
            if row is None:
                self._s.add(UrimPreparationElementModel(
                    preparation_id=study_id, element_code=e.element_code,
                    ordinal=e.ordinal, body=e.body,
                ))
            else:
                row.ordinal, row.body = e.ordinal, e.body
        await self._s.flush()

    async def list_elements(self, study_id: UUID) -> list[ElementRecord]:
        rows = (await self._s.execute(
            select(UrimPreparationElementModel)
            .where(UrimPreparationElementModel.preparation_id == study_id)
            .order_by(UrimPreparationElementModel.ordinal)
        )).scalars()
        return [ElementRecord(r.element_code, r.ordinal, r.body) for r in rows]

    async def set_supports(self, study_id: UUID, supports: list[SupportRecord]) -> None:
        """Remplacement **entier** de la chaîne — pas une fusion.

        Les éléments du squelette se fusionnent par leur code : chacun a une identité (l'
        introduction reste l'introduction). Une chaîne de textes n'en a pas — elle a un
        **ordre**, et c'est l'ordre qui porte le sens du sermon. Fusionner par rang ferait
        d'une insertion au milieu un décalage silencieux de tout ce qui suit."""
        await self._s.execute(
            delete(UrimPreparationSupportModel).where(
                UrimPreparationSupportModel.preparation_id == study_id
            )
        )
        for rang, support in enumerate(supports, start=1):
            self._s.add(UrimPreparationSupportModel(
                preparation_id=study_id, ordinal=rang, raw=support.raw[:200],
                book_id=support.book_id, chapter=support.chapter,
                verse_start=support.verse_start, verse_end=support.verse_end,
            ))
        await self._s.flush()

    async def list_supports(self, study_id: UUID) -> list[SupportRecord]:
        rows = (await self._s.execute(
            select(UrimPreparationSupportModel)
            .where(UrimPreparationSupportModel.preparation_id == study_id)
            .order_by(UrimPreparationSupportModel.ordinal)
        )).scalars()
        return [
            SupportRecord(r.raw, r.book_id, r.chapter, r.verse_start, r.verse_end)
            for r in rows
        ]

    async def dismiss(
        self, *, study_id: UUID, stage_code: str, option_code: str, at: datetime
    ) -> None:
        # Idempotent par la clé primaire : on relit avant d'insérer plutôt que d'attendre
        # une violation. Écarter deux fois la même option est le même fait, pas une erreur.
        deja = await self._s.get(
            UrimPreparationDismissalModel, (study_id, stage_code, option_code)
        )
        if deja is not None:
            return
        self._s.add(UrimPreparationDismissalModel(
            preparation_id=study_id, stage_code=stage_code,
            option_code=option_code, dismissed_at=at,
        ))
        await self._s.flush()

    async def restore(self, *, study_id: UUID, stage_code: str, option_code: str) -> None:
        await self._s.execute(
            delete(UrimPreparationDismissalModel)
            .where(UrimPreparationDismissalModel.preparation_id == study_id)
            .where(UrimPreparationDismissalModel.stage_code == stage_code)
            .where(UrimPreparationDismissalModel.option_code == option_code)
        )
        await self._s.flush()

    async def list_dismissals(self, study_id: UUID) -> list[tuple[str, str]]:
        rows = (await self._s.execute(
            select(
                UrimPreparationDismissalModel.stage_code,
                UrimPreparationDismissalModel.option_code,
            ).where(UrimPreparationDismissalModel.preparation_id == study_id)
        )).all()
        return [(r.stage_code, r.option_code) for r in rows]

    async def save_suggestions(
        self, study_id: UUID, snapshot: SuggestionSnapshot, at: datetime
    ) -> None:
        row = await self._s.get(
            UrimModelSuggestionModel, (study_id, snapshot.input_hash)
        )
        valeurs = dict(
            model=snapshot.model,
            axes=[{"code": a.code, "titre": a.title, "glose": a.gloss}
                  for a in snapshot.axes],
            flags=list(snapshot.flags),
            passages=[
                {
                    "livre": p.reference.book,
                    "chapitre": p.reference.chapter,
                    "debut": p.reference.verse_start,
                    "fin": p.reference.verse_end,
                    "motif": p.rationale,
                }
                for p in snapshot.passages
            ],
            suggested_at=at,
        )
        if row is None:
            self._s.add(UrimModelSuggestionModel(
                preparation_id=study_id, input_hash=snapshot.input_hash, **valeurs
            ))
        else:
            # Même question, réponse rafraîchie — le modèle a pu changer entre-temps.
            for cle, valeur in valeurs.items():
                setattr(row, cle, valeur)
        await self._s.flush()

    async def get_suggestions(
        self, study_id: UUID, input_hash: str
    ) -> SuggestionSnapshot | None:
        row = await self._s.get(UrimModelSuggestionModel, (study_id, input_hash))
        if row is None:
            return None
        return SuggestionSnapshot(
            input_hash=row.input_hash,
            model=row.model,
            axes=tuple(
                AxisGloss(a["code"], a.get("titre") or "", a.get("glose") or "")
                for a in row.axes
            ),
            flags=tuple(row.flags),
            passages=tuple(
                PassageSuggestion(
                    Reference(p["livre"], p["chapitre"], p.get("debut"), p.get("fin")),
                    p.get("motif") or "",
                )
                for p in row.passages
            ),
        )

    async def save_plan_suggestion(
        self,
        study_id: UUID,
        element_code: str,
        ordinal: int,
        input_hash: str,
        suggestion: PlanSuggestion,
        at: datetime,
    ) -> None:
        """Garder la proposition — **dans sa table, jamais dans la colonne du pasteur**."""
        row = await self._s.get(
            UrimPlanSuggestionModel, (study_id, element_code, ordinal)
        )
        valeurs = dict(
            input_hash=input_hash,
            model=suggestion.model,
            body=suggestion.body,
            transition=suggestion.transition or None,
            suggested_at=at,
        )
        if row is None:
            self._s.add(UrimPlanSuggestionModel(
                preparation_id=study_id, element_code=element_code,
                ordinal=ordinal, **valeurs,
            ))
        else:
            for cle, valeur in valeurs.items():
                setattr(row, cle, valeur)
        await self._s.flush()

    async def get_plan_suggestion(
        self, study_id: UUID, element_code: str, ordinal: int, input_hash: str
    ) -> PlanSuggestion | None:
        """Celle qui répond **à ce point-ci**. Un point réécrit n'a plus de réponse gardée —
        et c'est voulu : ce serait la réponse à une question qui n'est plus posée."""
        row = await self._s.get(
            UrimPlanSuggestionModel, (study_id, element_code, ordinal)
        )
        if row is None or row.input_hash != input_hash:
            return None
        return PlanSuggestion(
            body=row.body, transition=row.transition or "", model=row.model
        )

    async def recently_preached_axes(self, author_id: UUID, since: date) -> list[str]:
        # **Son** archive, clée sur l'auteur. Aucune lecture d'un autre contexte : cette
        # donnée est celle d'Urim, et c'est ce qui permet à l'étage du thème d'éviter la
        # répétition sans jamais consulter le calendrier ecclésial (E1).
        rows = await self._s.execute(
            select(UrimPreachedModel.axis_code)
            .where(UrimPreachedModel.author_id == author_id)
            .where(UrimPreachedModel.preached_on >= since)
            .where(UrimPreachedModel.axis_code.is_not(None))
        )
        return [a for a in rows.scalars() if a]


class SqlReservationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def reserve(
        self, *, church_id: UUID | None, author_id: UUID, pericope_key: str, at: datetime
    ) -> UUID:
        existante = await self._active(church_id, author_id, pericope_key, at)
        if existante is not None:
            return existante

        await self._liberer_les_perimees(church_id, author_id, pericope_key, at)

        reservation = UrimStudyReservationModel(
            id=uuid4(), church_id=church_id, author_id=author_id,
            pericope_key=pericope_key, window_id=None,
            reserved_at=at, expires_at=at + _DUREE_RESERVATION,
        )
        self._s.add(reservation)
        await self._s.flush()
        return reservation.id

    async def rekey_for(
        self,
        *,
        church_id: UUID | None,
        author_id: UUID,
        provisional_key: str,
        pericope_key: str,
        at: datetime,
    ) -> None:
        """S9 — la réservation se cale sur le texte résolu.

        Si une autre réservation tient déjà ce texte, la nôtre se **libère** : les deux
        entrées désignaient le même travail, et le facturer deux fois serait faire payer
        une hésitation de formulation."""
        courante = await self._active(church_id, author_id, provisional_key, at)
        if courante is None:
            return  # déjà re-clée, ou périmée — dans les deux cas rien à faire
        row = await self._s.get(UrimStudyReservationModel, courante)
        deja = await self._active(church_id, author_id, pericope_key, at, sauf=courante)
        if deja is not None:
            row.released_at = at
        else:
            # ⚠️ **Ici aussi.** On s'apprête à occuper `pericope_key` ; une ligne périmée et
            # jamais relâchée la tiendrait encore du point de vue de l'index. Le correctif
            # posé à la réservation ne suffisait pas — il manquait partout où l'on **prend**
            # une clé, et le re-clage en est un.
            await self._liberer_les_perimees(church_id, author_id, pericope_key, at)
            row.pericope_key = pericope_key
        await self._s.flush()

    async def _liberer_les_perimees(
        self, church_id: UUID | None, author_id: UUID, pericope_key: str, at: datetime
    ) -> None:
        """🐛 **Périmer, c'est relâcher.**

        L'index unique porte `WHERE released_at IS NULL` — il ignore l'échéance. Le code, lui,
        tenait une réservation pour inactive dès qu'elle était périmée. Une ligne périmée et
        jamais relâchée devenait donc **invisible au code et bloquante pour la base** :
        rouvrir le même passage le lendemain rendait un 409.

        Le commentaire de `_DUREE_RESERVATION` promettait qu'une réservation « se périme
        d'elle-même ». Elle ne périmait rien. Deux définitions d'« active » qui divergent, et
        c'est toujours la base qui gagne — d'où cet appel **partout où l'on prend une clé**.
        """
        await self._s.execute(
            update(UrimStudyReservationModel)
            .where(UrimStudyReservationModel.church_id == church_id)
            .where(UrimStudyReservationModel.author_id == author_id)
            .where(UrimStudyReservationModel.pericope_key == pericope_key)
            .where(UrimStudyReservationModel.released_at.is_(None))
            .where(UrimStudyReservationModel.expires_at <= at)
            .values(released_at=at)
        )

    async def _active(
        self,
        church_id: UUID | None,
        author_id: UUID,
        pericope_key: str,
        at: datetime,
        sauf: UUID | None = None,
    ) -> UUID | None:
        # ⚠️ **`author_id` compte**, parce que l'index unique le compte. Sans lui, deux
        # pasteurs de la même église préparant le même passage se seraient partagé une seule
        # réservation — celle du premier arrivé.
        requete = (
            select(UrimStudyReservationModel.id)
            .where(UrimStudyReservationModel.church_id == church_id)
            .where(UrimStudyReservationModel.author_id == author_id)
            .where(UrimStudyReservationModel.pericope_key == pericope_key)
            .where(UrimStudyReservationModel.released_at.is_(None))
            .where(UrimStudyReservationModel.expires_at > at)
        )
        if sauf is not None:
            requete = requete.where(UrimStudyReservationModel.id != sauf)
        return await self._s.scalar(requete.limit(1))

    async def mark_assisted(
        self, *, church_id: UUID | None, author_id: UUID, pericope_key: str, at: datetime
    ) -> None:
        """Poser `metered_at` — **une seule fois par texte**, et jamais rétroactivement.

        « Réserver n'est pas consommer » : à l'ouverture on ne sait pas encore si le modèle
        servira. Ce geste dit qu'il vient de servir. Il est idempotent parce que la ligne
        l'est : rouvrir, hésiter, revenir sur le même texte retombe sur la même réservation,
        et la date déjà posée n'est pas repoussée — sinon un pasteur qui reprend son travail
        le mois suivant se le verrait compter deux fois."""
        reservation = await self._active(church_id, author_id, pericope_key, at)
        if reservation is None:
            return
        row = await self._s.get(UrimStudyReservationModel, reservation)
        if row.metered_at is None:
            row.metered_at = at
            await self._s.flush()

    async def _quota_du_mois(self, author_id: UUID, at: datetime) -> int:
        """Combien de **textes distincts** cet auteur a préparés avec l'assistance ce mois-ci.

        On compte des réservations, pas des ouvertures : rouvrir six fois la même péricope est
        un seul travail. Compter les ouvertures ferait payer l'hésitation du samedi soir —
        or hésiter entre trois textes est le geste normal, pas un abus."""
        debut = at.date().replace(day=1)
        return await self._s.scalar(
            select(func.count())
            .select_from(UrimStudyReservationModel)
            .where(UrimStudyReservationModel.church_id.is_(None))
            .where(UrimStudyReservationModel.author_id == author_id)
            .where(UrimStudyReservationModel.metered_at.is_not(None))
            .where(UrimStudyReservationModel.metered_at >= debut)
        ) or 0

    async def usage(
        self, church_id: UUID | None, author_id: UUID, at: datetime
    ) -> UsageSnapshot:
        if church_id is None:
            consommes = await self._quota_du_mois(author_id, at)
            return UsageSnapshot(
                metered_units=consommes,
                ceiling=_QUOTA_PERSONNEL,
                # ⚠️ `ceiling_reached` reste **faux**. Il protège une licence, et l'antichambre
                # ne sert que du domaine public : il n'y a rien à replier.
                assistance_exhausted=consommes >= _QUOTA_PERSONNEL,
            )
        jour = at.date()
        row = await self._s.scalar(
            select(UrimUsageWindowModel)
            .where(UrimUsageWindowModel.church_id == church_id)
            .where(UrimUsageWindowModel.period_start <= jour)
            .where(UrimUsageWindowModel.period_end >= jour)
            .limit(1)
        )
        if row is None:
            # Pas de fenêtre : pas de plafond atteint. L'absence de configuration ne doit
            # jamais dégrader le service — le repli est une protection, pas une punition.
            return UsageSnapshot(ceiling=_PLAFOND_DEFAUT, ceiling_reached=False)
        return UsageSnapshot(
            window_id=row.id,
            metered_units=row.metered_units,
            ceiling=row.ceiling,
            ceiling_reached=row.ceiling > 0 and row.metered_units >= row.ceiling,
        )

