"""Ports du moteur de veille vers le monde extérieur.

L'engine décide ; il ne connaît ni les rosters, ni M7, ni les tables de la Présence. Un
adaptateur écrit ce qu'il a décidé, et c'est le **seul** chemin d'écriture — condition pour
qu'une reprojection soit sûre.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.contexts.watch.domain.regime import TenantRegime


@dataclass(frozen=True)
class HumanTraces:
    """Ce qu'un rejeu du ledger **ne peut pas** reconstruire : les actes des humains.

    Le journal ne contient que des faits. « J'ai ouvert ce cas », « j'ai appelé », « je ferme,
    voilà ce que j'ai trouvé », « cette consolation a été remise » ne sont pas des faits admis à
    l'intake : ce sont des gestes posés sur la projection. Les compter avant d'effacer, c'est la
    différence entre une réparation et une perte.
    """

    seen: int = 0  # cas qu'un propriétaire a ouverts (`first_seen_at`)
    contacted: int = 0  # cas où un contact a commencé (`first_contact_at`)
    closed: int = 0  # cas clos par quelqu'un, avec son issue
    gestures: int = 0  # gestes réels posés et comptés
    delivered_memories: int = 0  # consolations déjà remises — jamais deux fois

    @property
    def total(self) -> int:
        return (
            self.seen + self.contacted + self.closed + self.gestures + self.delivered_memories
        )

    def as_details(self) -> dict[str, int]:
        return {
            "seen": self.seen,
            "contacted": self.contacted,
            "closed": self.closed,
            "gestures": self.gestures,
            "delivered_memories": self.delivered_memories,
        }


class NeutralizationStore(ABC):
    """Là où vit la neutralisation matérialisée.

    Implémenté au-dessus de l'absence planifiée M6 : c'est le seul objet que le roster et M7
    consultent déjà. Une table parallèle obligerait sept lectures pastorales à unir deux
    sources — et en oublier une seule ferait réapparaître un endeuillé comme absent silencieux.
    """

    @abstractmethod
    async def neutralize(
        self,
        *,
        subject_id: UUID,
        tenant_id: UUID,
        role: str | None,
        starts_at: datetime,
        expected_return_at: datetime,
        source_ref: UUID,
        declared_by_account_id: UUID,
        reason: str,
    ) -> None:
        """Pose ou **prolonge**. Jamais deux périodes, jamais un cumul de durées."""
        ...

    @abstractmethod
    async def extinguish(
        self, *, subject_id: UUID, tenant_id: UUID, cause: str, at: datetime
    ) -> None:
        """Ferme les neutralisations en cours sur cette personne, avec l'issue **stockée**."""
        ...

    @abstractmethod
    async def exclude_forever(
        self,
        *,
        subject_id: UUID,
        tenant_id: UUID,
        source_ref: UUID,
        declared_by_account_id: UUID,
        reason: str,
        at: datetime,
    ) -> None:
        """Retrait définitif de la veille. Absorbant — rien ne le lève."""
        ...

    @abstractmethod
    async def excluded_subject_ids(self, tenant_id: UUID) -> set[UUID]:
        """Toute l'église. Réservé aux écrans et à la calibration — **pas** au chemin d'un fait."""
        ...

    @abstractmethod
    async def open_neutralizations(
        self, tenant_id: UUID
    ) -> list[tuple[UUID, UUID, datetime, datetime]]:
        """`(id, subject_id, starts_at, expected_return_at)`, toute l'église. Même réserve."""
        ...

    @abstractmethod
    async def is_excluded(self, subject_id: UUID, tenant_id: UUID) -> bool:
        """La même question, **pour une personne**. C'est celle que pose le chemin d'un fait."""
        ...

    @abstractmethod
    async def neutralizations_of_subject(
        self, subject_id: UUID, tenant_id: UUID
    ) -> list[tuple[UUID, UUID, datetime, datetime]]:
        """Ce qui couvre le silence de cette personne-là. Une lecture indexée, pas un balayage."""
        ...

    @abstractmethod
    async def purge_projected_neutralizations(self, tenant_id: UUID) -> None:
        """Efface **uniquement** ce que le moteur a projeté, avant un rejeu du ledger.

        Ne touche jamais à ce qu'un membre a déclaré lui-même : sa parole n'est pas une
        projection, et une reconstruction ne doit pas pouvoir l'effacer. C'est la seule méthode
        autorisée à supprimer du projeté — tout le reste passe par elle."""
        ...


class SignalStore(ABC):
    """Là où vivent les cas ouverts et la mémoire du lien.

    Contrairement à la neutralisation, le signal n'a pas d'équivalent ailleurs : il n'existe
    qu'ici, et il est **entièrement** une projection du ledger."""

    @abstractmethod
    async def open_case(
        self,
        *,
        subject_id: UUID,
        tenant_id: UUID,
        origin: str,
        reason: str,
        opened_at: datetime,
        expires_at: datetime | None,
        source_ref: UUID,
        held: bool,
        owner_account_id: UUID | None = None,
        held_reason: str | None = None,
    ) -> None:
        """Ouvre un cas, ou **enrichit** celui qui existe déjà. Jamais deux sur une personne.

        `owner_account_id` non nul assigne le cas dès l'ouverture. C'est ce qui permet à
        l'escalade et au garde-fou de ratio d'exister : un cas sans destinataire est un cas que
        personne ne traite, et dont personne ne répond."""
        ...

    @abstractmethod
    async def enrich_case(
        self,
        *,
        subject_id: UUID,
        tenant_id: UUID,
        source_ref: UUID,
        extend_to: datetime | None,
        annotation: str | None = None,
        priority: str | None = None,
        downgrade: bool = False,
    ) -> None:
        """Ajoute ce qu'on vient d'apprendre. L'annotation s'ajoute à la fiche, la raison
        d'origine ne bouge jamais, et la priorité ne monte que si c'est plus urgent."""
        ...

    @abstractmethod
    async def extinguish(
        self, *, subject_id: UUID, tenant_id: UUID, cause: str, at: datetime
    ) -> None:
        """Ferme les cas en cours **si la cause l'autorise sans humain**. Sinon ne fait rien."""
        ...

    @abstractmethod
    async def record_memory(
        self, *, subject_id: UUID, tenant_id: UUID, item: str, at: datetime, reason: str
    ) -> None:
        """La mémoire du lien — restituée plus tard, une seule fois, et jamais agrégée par
        membre. C'est ce qui permettra au Compagnon de **rendre avant de prendre**."""
        ...

    @abstractmethod
    async def live_cases(self, tenant_id: UUID) -> list[tuple[UUID, UUID, UUID | None, str, bool]]:
        """`(id, subject_id, owner_id, origin, is_held)`, **toute l'église**.

        Sert les écrans, la reprojection de référence et la calibration. Le chemin d'un fait, lui,
        ne la lit plus : il pose les deux questions bornées ci-dessous."""
        ...

    @abstractmethod
    async def case_of_subject(
        self, subject_id: UUID, tenant_id: UUID
    ) -> tuple[UUID, UUID, UUID | None, str, bool] | None:
        """Le cas en cours de cette personne, s'il y en a un. Une lecture indexée."""
        ...

    @abstractmethod
    async def open_cases_count(self, owner_id: UUID | None, tenant_id: UUID) -> int:
        """Combien de cas **pèsent** sur ce responsable — le plafond de débit, en un COUNT.

        Les retenus n'y sont pas : un cas `HELD` est détecté, pas encore sur ses épaules."""
        ...

    @abstractmethod
    async def do_not_contact_ids(self, tenant_id: UUID) -> set[UUID]:
        """Les personnes qui ont demandé qu'on cesse de les contacter.

        Une veille dont on ne peut pas sortir est un fichage. Ce retrait est absorbant et
        s'impose à **toutes** les surfaces, y compris à celles qui n'appartiennent pas au
        moteur — un rendez-vous en attente ne survit pas à cette parole."""
        ...

    @abstractmethod
    async def mark_contact_started(
        self, *, signal_id: UUID, tenant_id: UUID, at: datetime
    ) -> None:
        """L'effort est enregistré **au départ** — avant que l'application perde la main."""
        ...

    @abstractmethod
    async def origin_of(self, signal_id: UUID, tenant_id: UUID):
        """L'origine du cas — la péremption dure ne vaut que pour le régime d'échéance."""
        ...

    @abstractmethod
    async def extinguish_by_id(
        self, *, signal_id: UUID, tenant_id: UUID, cause: str, at: datetime
    ) -> None: ...

    # --- Ce que le signalement par un tiers a besoin de relire -----------------------------
    #
    # Trois lectures, et **aucune** ne prend le déclarant en argument ni ne le renvoie : elles
    # portent sur le cas, son propriétaire, son issue. « Qui a signalé qui » n'est reconstituable
    # par aucune d'elles, et c'est structurel — l'information n'est pas dans la table.

    @abstractmethod
    async def cases_of_owner(self, *, account_id: UUID, tenant_id: UUID) -> list:
        """La file d'un responsable : ses cas vivants, le plus urgent d'abord.

        Les cas `HELD` n'y figurent pas — ils sont détectés, pas encore sur ses épaules. Les
        montrer ferait mentir le plafond au moment même où il protège quelqu'un."""
        ...

    @abstractmethod
    async def get_case(self, *, signal_id: UUID, tenant_id: UUID):
        """Un cas, ou None. Le `tenant_id` est dans la signature, jamais déduit du cas."""
        ...

    @abstractmethod
    async def live_case_of(self, *, subject_id: UUID, tenant_id: UUID):
        """Le cas vivant d'une personne, ou None. **Il n'y en a jamais deux.**"""
        ...

    @abstractmethod
    async def cases_by_subjects(self, *, subject_ids, tenant_id: UUID) -> dict:
        """`{subject_id: cas vivant}` — une seule requête pour une liste de personnes.

        C'est ce qui permet à une surface d'afficher un état **dérivé du cas** sans maintenir sa
        propre liste : deux listes sur les mêmes personnes finissent par se contredire, et
        celui qui les lit ne sait plus laquelle croire."""
        ...

    @abstractmethod
    async def save_case(self, signal) -> None:
        """Persiste ce que l'agrégat a décidé. Le dépôt ne rejoue aucune règle."""
        ...

    @abstractmethod
    async def stale_concerns(
        self, *, tenant_id: UUID, opened_before: datetime
    ) -> list[tuple[UUID, UUID | None, datetime]]:
        """`(signal_id, owner_id, opened_at)` — inquiétudes vivantes sans **aucun** contact.

        Le critère est `first_contact_at IS NULL`, pas la clôture : un engagement tenu tard reste
        un engagement tenu, et ce qu'on cherche est celui que personne n'a commencé."""
        ...

    @abstractmethod
    async def concern_activity(
        self, *, tenant_id: UUID, since: datetime
    ) -> list[tuple[UUID | None, bool]]:
        """`(owner_id, contacté)` par inquiétude ouverte depuis. Le garde-fou lit un **ratio**."""
        ...

    @abstractmethod
    async def closed_cases_since(
        self, *, tenant_id: UUID, since: datetime
    ) -> list[tuple[str, str]]:
        """`(origine, issue)` des cas fermés **par un humain**. Deux chaînes, aucun identifiant.

        Le type de retour n'est pas une commodité : c'est l'interdit de la calibration rendu
        structurel. Ce port **ne peut pas** rendre une personne, donc rien de ce qui se calcule
        au-dessus ne pourra jamais descendre à quelqu'un.

        La clôture humaine est le filtre, et c'est le sens même de « vérité terrain » : une
        extinction système ferait noter la machine par la machine. Une inquiétude close parce que
        la personne est revenue d'elle-même n'a jamais été vérifiée par personne — la compter
        comme une intuition juste gonflerait la précision d'un tenant sans qu'un seul contact ait
        eu lieu. Les rétractées sont hors du compte pour la même raison qu'ailleurs : un cas
        devenu faux n'a rien résolu."""
        ...

    @abstractmethod
    async def ignored_by_owner(
        self, *, tenant_id: UUID, older_than: datetime
    ) -> list[tuple[UUID | None, int, int]]:
        """`(responsable, jamais ouverts, portés)` — la version **nominative** du taux d'ignorés.

        Elle vit dans la boucle chaude, et c'est délibéré : ce qui nomme quelqu'un doit produire
        une action sur lui — ici, quelqu'un qui vient l'aider. La boucle froide, elle, n'en lit
        que l'agrégat (`ignored_ratio`), parce qu'un seuil ne se calibre pas sur une personne."""
        ...

    @abstractmethod
    async def ignored_ratio(
        self, *, tenant_id: UUID, older_than: datetime
    ) -> tuple[int, int]:
        """`(jamais ouverts, portés)` — deux entiers, sur les cas plus vieux que cette date.

        Le seul indicateur qui **anticipe** : il monte avant l'abandon, quand le délai de contact
        a encore l'air normal parce que les cas traités le sont vite et que les autres ne sont
        simplement jamais ouverts."""
        ...

    @abstractmethod
    async def mark_contact_started_for_subject(
        self, *, subject_id: UUID, tenant_id: UUID, at: datetime
    ) -> None:
        """Un contact a commencé sur le cas vivant de cette personne — `first_contact_at`.

        Visé par la personne et non par un identifiant de cas, pour la même raison que partout
        ailleurs : un rejeu recrée les cas avec de nouveaux identifiants."""
        ...

    @abstractmethod
    async def mark_seen(self, *, subject_id: UUID, tenant_id: UUID, at: datetime) -> None:
        """Le cas vivant de cette personne a été **ouvert** par son destinataire.

        Visé par la personne et non par un identifiant : un rejeu recrée les cas avec de nouveaux
        identifiants, et il y a au plus un cas vivant par personne."""
        ...

    @abstractmethod
    async def resolve_case(
        self,
        *,
        subject_id: UUID,
        tenant_id: UUID,
        outcome: str,
        at: datetime,
        by_account_id: UUID,
    ) -> None:
        """Ferme le cas vivant de cette personne, avec l'issue **choisie** par un humain.

        L'agrégat refuse tout seul ce qui n'a pas lieu d'être : issue absorbante déjà posée,
        transition inexistante. Le dépôt ne rejoue aucune de ces règles."""
        ...

    @abstractmethod
    async def accompanied_since(self, *, subject_id: UUID, tenant_id: UUID):
        """La date de la **première** entrée de mémoire du lien, ou None.

        « Vous l'accompagnez depuis février » : une phrase que le responsable ne peut pas
        reconstruire de tête, et qui change complètement la façon d'ouvrir un appel."""
        ...

    @abstractmethod
    async def retract_held(self, *, subject_id: UUID, tenant_id: UUID, at: datetime) -> None:
        """Retire un cas **encore retenu**, dépassé par un signe de vie.

        Sans effet sur un cas émis : quelqu'un l'a peut-être déjà lu, et on n'efface pas ce qui a
        été vu."""
        ...

    @abstractmethod
    async def held_cases(self, *, tenant_id: UUID) -> list:
        """Les cas **détectés et retenus** par le plafond, en agrégats mutables.

        Ils sont réévalués chaque nuit : « retenu ≠ perdu » n'est vrai que si quelque chose les
        relâche."""
        ...

    @abstractmethod
    async def human_traces(self, tenant_id: UUID) -> HumanTraces:
        """Ce qu'un rejeu effacerait sans pouvoir le reconstruire — **à compter avant de purger**.

        Tant que les gestes du responsable ne sont pas au ledger, cette question est la seule
        protection contre une maintenance qui détruit l'histoire qu'elle croit reconstruire."""
        ...

    @abstractmethod
    async def purge_projected(self, tenant_id: UUID) -> None:
        """Efface cas et mémoire avant un rejeu.

        ⚠️ **Tout n'est pas reconstruit à partir des faits.** Les issues de clôture, le premier
        regard, le premier contact, les gestes comptés, la chaîne d'épisode et les consolations
        déjà remises sont des **actes**, absents du journal. Cette méthode les détruit. Le garde-fou
        est chez l'appelant (`RebuildProjections`), pas ici : un store ne discute pas d'un ordre."""
        ...


class RegimeStore(ABC):
    """Le régime de rodage d'une église — et son défaut, qui n'est pas neutre."""

    @abstractmethod
    async def regime_of(self, tenant_id: UUID) -> TenantRegime:
        """`SHADOW` en l'absence de décision : aucune église ne se met à parler par oubli."""
        ...

    @abstractmethod
    async def set_regime(
        self, *, tenant_id: UUID, regime: TenantRegime, at: datetime, by_account_id: UUID
    ) -> None:
        """Sortir du rodage est une **décision**, datée et signée."""
        ...


class ScheduledCheckStore(ABC):
    """Les échéances du moteur — la seule porte par laquelle le temps entre dans la veille."""

    @abstractmethod
    async def schedule(
        self,
        *,
        subject_id: UUID,
        tenant_id: UUID,
        kind: str,
        reason: str,
        due_at: datetime,
        at: datetime,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        """Pose une échéance. Idempotent par `(sujet, kind, due_at)` — rejouer ne duplique pas.

        `payload` est ce que l'interpreter du tir lira dans trois semaines : écrit **maintenant**,
        au moment où on le sait, plutôt que relu plus tard dans un état qui aura bougé."""
        ...

    @abstractmethod
    async def cancel_for(
        self, *, subject_id: UUID, tenant_id: UUID, kind: str | None, at: datetime
    ) -> int:
        """Annule les échéances en attente. `kind=None` = toutes.

        **Vital.** Sans annulation, on programme des rappels sur des gens décédés ou qui ont
        demandé qu'on cesse — l'échec le plus coûteux que ce produit puisse produire."""
        ...

    @abstractmethod
    async def due(self, *, tenant_id: UUID, now: datetime, limit: int) -> list:
        """Ce qui est dû, **les plus anciennes d'abord**, borné par le garde anti-orage."""
        ...

    @abstractmethod
    async def mark_fired(self, *, check_id: UUID, at: datetime) -> None: ...

    @abstractmethod
    async def pending_count(self, *, tenant_id: UUID, now: datetime) -> int:
        """Combien restent dues après la passe — ce qu'on doit dire plutôt que taire."""
        ...

    @abstractmethod
    async def purge_projected(self, tenant_id: UUID) -> None:
        """Efface les échéances avant un rejeu : ce sont des **projections** du ledger.

        Une échéance déjà tirée porte son `CHECK_FIRED` au journal, donc le rejeu la reposera puis
        la retirera par le même chemin. Sans cette purge, une reprojection empilerait une seconde
        échéance en attente à côté de chaque ancienne : la personne serait relancée deux fois."""
        ...


class ContactAttemptStore(ABC):
    """Les tentatives de contact. Écrites au départ, résolues au retour — ou jamais.

    Depuis le lot 3bis, ce sont des **projections** : chaque tentative naît d'un fait au journal,
    et `purge_projected` permet à un rejeu de les reconstruire au lieu de les empiler."""

    @abstractmethod
    async def add(self, attempt) -> None: ...

    @abstractmethod
    async def purge_projected(self, tenant_id: UUID) -> None:
        """Efface les tentatives avant un rejeu — elles se reconstruisent depuis le journal."""
        ...

    @abstractmethod
    async def record(
        self,
        *,
        attempt_id: UUID,
        subject_id: UUID,
        tenant_id: UUID,
        by_account_id: UUID,
        channel: str,
        at: datetime,
    ) -> None:
        """Écrit la tentative depuis le fait.

        `attempt_id` vient du journal : rejouer ne l'empile pas une seconde fois."""
        ...

    @abstractmethod
    async def resolve(
        self, *, attempt_id: UUID, result: str, at: datetime, commitment: str | None = None
    ) -> None:
        """L'issue rapportée, et ce que le responsable s'engage à faire. Une seule fois."""
        ...

    @abstractmethod
    async def get(self, attempt_id: UUID): ...

    @abstractmethod
    async def save(self, attempt) -> None: ...

    @abstractmethod
    async def count_not_reached(self, signal_id: UUID) -> int:
        """Combien de fois on a essayé sans joindre — le compteur de la péremption dure."""
        ...

    @abstractmethod
    async def recent_for(self, *, signal_id: UUID, limit: int = 3) -> list:
        """Les dernières tentatives **résolues** de ce cas, la plus récente d'abord.

        Elles portent la date, le canal, l'issue — et l'engagement que le responsable avait écrit.
        C'est du déjà-écrit, cité tel quel : citer n'est pas résumer."""
        ...

    @abstractmethod
    async def pending_for(self, *, account_id: UUID, tenant_id: UUID, since: datetime) -> list:
        """Ce qu'on demandera à la réouverture, borné dans le temps."""
        ...
