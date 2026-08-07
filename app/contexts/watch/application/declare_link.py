"""« Voici par qui vous pouvez me rejoindre. » — le lien qu'on déclare pour soi.

Le lien par geste arrive trop tard, et jamais pour celui qui en a le plus besoin : il n'apparaît
que quand quelqu'un s'est déjà approché. Pour la personne dont personne ne s'approche, le journal
reste vide exactement là où il fallait un nom. Cette porte attaque le problème par l'autre bout :
le jour de l'arrivée, la personne dit elle-même par où on peut la rejoindre.

**C'est le lien fort**, parce que c'est le seul qui porte un accord. En nommant Jean, Sondet ne
donne pas un renseignement : il dit *« vous pouvez passer par lui »*. `BE_WATCHED`, et le type de
consentement existait déjà.

---

**Trois noms au plus.** Pas parce qu'il y a trois propositions à l'écran — parce qu'au-delà on
fabrique une liste d'amis, et une liste d'amis est un objet social qui appelle un écran. Trois
chemins, c'est du routage.

**Le nommé n'est pas prévenu.** Jean n'apprend pas que Sondet l'a désigné. Sinon on fabrique une
déclaration d'affinité semi-publique — le sociogramme par la petite porte — et la blessure du
« je n'étais pas dans ses trois ». Le lien n'est pas un objet social, c'est un chemin de question.

**Retirable sans motif, et sans que personne l'apprenne.** C'est la clause qui compte le plus, et
elle existe pour un cas précis : le lien conjugal est celui qu'on a le plus de raisons de retirer.
Un foyer violent, une séparation en cours. Si le conjoint est la route par laquelle l'église prend
de vos nouvelles, la personne qui aurait besoin d'être rejointe *hors* du foyer n'a plus de sortie.
Le retrait n'écrit donc aucun motif et ne notifie personne.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.contexts.watch.application.intake import Intake
from app.contexts.watch.application.interpreters.self_declaration import DeclarationKind
from app.contexts.watch.application.ports import DeclaredLinkReader
from app.contexts.watch.application.referent_ports import PeopleDirectory
from app.contexts.watch.domain.errors import (
    IneligibleReferentError,
    SelfReferentError,
    TooManyLinksError,
)
from app.contexts.watch.domain.facts import (
    ConsentProof,
    ConsentScope,
    Fact,
    FactKind,
    SubjectKind,
)
from app.contexts.watch.domain.registry import COMPANION

# Au-delà, ce n'est plus du routage, c'est un carnet d'adresses affectif.
MAX_LINKS = 3


@dataclass(frozen=True)
class LinkAcknowledged:
    """« C'est noté. » — et **rien ne part vers la personne nommée**."""

    message: str = "C'est noté."
    remaining: int = 0


class DeclareLink:
    def __init__(
        self,
        intake: Intake,
        links: DeclaredLinkReader,
        people: PeopleDirectory,
        *,
        clock,
        id_factory=uuid4,
    ) -> None:
        self._intake = intake
        self._links = links
        self._people = people
        self._clock = clock
        self._new_id = id_factory

    async def execute(
        self, *, actor_account_id: UUID, linked_account_id: UUID, tenant_id: UUID
    ) -> LinkAcknowledged:
        if actor_account_id == linked_account_id:
            raise SelfReferentError(
                "On ne se désigne pas soi-même comme chemin vers soi.",
                details={"kind": DeclarationKind.LINK_DECLARED.value},
            )
        if not await self._people.is_eligible(linked_account_id, tenant_id):
            raise IneligibleReferentError(
                "Cette personne n'est pas un membre actif de cette église.",
                details={"account_id": str(linked_account_id)},
            )

        existing = await self._links.declared_links(
            subject_id=actor_account_id, tenant_id=tenant_id
        )
        already = {link.linked_account_id for link in existing}
        if linked_account_id not in already and len(existing) >= MAX_LINKS:
            raise TooManyLinksError(
                f"Vous pouvez indiquer {MAX_LINKS} personnes au plus. "
                "Retirez-en une pour en ajouter une autre.",
                details={"max": MAX_LINKS},
            )

        await self._emit(
            actor_account_id, linked_account_id, tenant_id, active=True
        )
        return LinkAcknowledged(remaining=max(0, MAX_LINKS - len(already | {linked_account_id})))

    async def remove(
        self, *, actor_account_id: UUID, linked_account_id: UUID, tenant_id: UUID
    ) -> LinkAcknowledged:
        """**Sans motif, et sans notification.** Le journal ne se corrige pas : on ajoute un fait
        qui dit autre chose, et le pli à la lecture n'en tient plus compte."""
        await self._emit(
            actor_account_id, linked_account_id, tenant_id, active=False
        )
        remaining = await self._links.declared_links(
            subject_id=actor_account_id, tenant_id=tenant_id
        )
        return LinkAcknowledged(remaining=max(0, MAX_LINKS - len(remaining)))

    async def _emit(
        self, actor: UUID, linked: UUID, tenant_id: UUID, *, active: bool
    ) -> None:
        now = self._clock()
        await self._intake.submit(
            Fact(
                fact_id=self._new_id(),
                tenant_id=tenant_id,
                occurred_at=now,
                recorded_at=now,
                source=COMPANION,
                kind=FactKind.SELF_DECLARATION,
                subject_kind=SubjectKind.PERSON,
                # Le sujet est **celui qui parle** : c'est sa parole sur lui-même, et c'est ce qui
                # la rend listable par lui. Le nommé, lui, n'est qu'une valeur du payload — aucun
                # fait n'est jamais posé *sur* lui.
                subject_id=actor,
                payload={
                    "kind": DeclarationKind.LINK_DECLARED.value,
                    "linked_account_id": str(linked),
                    "active": "true" if active else "false",
                },
                consent=ConsentProof(
                    given_by=actor, scope=ConsentScope.BE_WATCHED, given_at=now
                ),
            )
        )
