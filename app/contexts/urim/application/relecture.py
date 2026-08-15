"""La relecture — **descendre la file, et signer ce qu'on a jugé**.

`curation.py` écrit le corpus ; ce module juge ce qui y est écrit. La séparation n'est pas de
symétrie : ce sont deux gestes qui ne s'exercent pas au même moment ni sur le même objet. On
cure une unité qui n'existe pas encore ; on relit une unité que quelqu'un — le plus souvent le
modèle — a déjà remplie.

## Le chiffre qui commande ce module

**0 pesée relue par un humain, sur 45 557.** `curation.py` promet que les pesées et les mises en
garde « restent à quelqu'un qui répond de ce qu'il affirme » ; elles sont toutes signées
`ia-mistral`. Ce n'est pas une fonctionnalité manquante, c'est une dette — et la seule chose qui
la fasse décroître est qu'un théologien puisse **descendre une file**. Une commande shell avec
`--ref "Apocalypse 5:5-14" --portee D4` ne sera jamais utilisée par la personne dont on a besoin.

## Trois choses que ce module refuse de faire

**Trier à la place du relecteur.** L'ordre de la file est la gravité que les détecteurs ont
posée, rien d'autre. Aucun score, aucun pré-verdict, aucun modèle. `accepte` existe pour dire
*« l'écart est réel et la curation est juste quand même »* — Apocalypse 5 porte réellement huit
loci — et c'est un jugement, pas un défaut à corriger.

**Masquer ce que l'IA a écrit.** Chaque ligne du dossier porte sa signature, et `generee` la
rend lisible d'un coup d'œil : *rien de généré ne doit se confondre avec une relecture*.

**Prendre l'empreinte avant le verdict.** Elle se calcule au moment où l'on signe, sur ce que la
base contient alors — jamais sur ce que le balayage avait vu. C'est ce qui rend l'ordre
`corriger d'abord, signer ensuite` mécanique plutôt que recommandé : signer `corrige` avant de
réparer figerait le verdict sur la curation fautive, et la réparation le périmerait aussitôt.
L'unité reviendrait en file toute seule. **Le mécanisme se garde lui-même** ; c'est pour ça
qu'il n'y a pas de contrôle supplémentaire ici.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.contexts.urim.application.curation import (
    PORTEE_ENSEMBLE,
    SIGNATAIRE_IA,
    empreinte_de_curation,
    verdict_couvre,
    verifier_verdict,
)
from app.contexts.urim.domain.errors import (
    CurationInvalideError,
    RelecteurInconnuError,
    UniteIntrouvableError,
)

#: Combien d'unités une page de file rend. Assez pour choisir, trop peu pour décourager :
#: la file fait ~140 unités, pas 4 561, et c'est tout l'intérêt des détecteurs.
PAGE_DE_FILE = 20


# -- qui signe -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Relecteur:
    """Un signataire **prouvé**, pas déclaré.

    Le `nom` est ce qui atterrit dans `reviewed_by` et que le pasteur lira ; l'`identifiant` ne
    sort jamais de l'authentification. Cet objet est le seul chemin par lequel un nom entre dans
    le corpus depuis une requête HTTP — et c'est toute la réforme : le nom n'est plus un champ
    de formulaire."""

    identifiant: str
    nom: str


def empreinte_de_secret(secret: str) -> str:
    """SHA-256 nu, **parce que le secret est tiré au sort et non choisi**.

    Une dérivation lente (argon2, comme le PIN d'un membre) protège d'une attaque par
    dictionnaire sur un secret qu'un humain a inventé. Ici `scripts/urim_relecteur.py` tire 32
    octets d'aléa : il n'existe pas de dictionnaire des tirages. Le jour où un relecteur
    choisirait son secret, cette fonction devient fausse — et cette phrase est là pour qu'on
    s'en aperçoive à ce moment-là plutôt qu'après."""
    return hashlib.sha256(secret.encode()).hexdigest()


class RegistreRepository(Protocol):
    async def secret_et_nom(self, identifiant: str) -> tuple[str, str] | None:
        """`(empreinte du secret, nom affiché)` d'un relecteur **actif**, ou rien."""
        ...


@dataclass(slots=True)
class RegistreDesRelecteurs:
    """Rend un nom contre la preuve d'un secret. **Le point où le nom cesse d'être une entrée.**

    Le jour où la console d'administration Dorea existe (`docs/Dorea_Platform_Admin.md`), c'est
    cette classe qu'on remplace par la session d'un compte staff : les routes ne bougent pas,
    parce qu'elles ne connaissent que `Relecteur`."""

    registre: RegistreRepository

    async def identifier(self, porteur: str | None) -> Relecteur:
        """`identifiant:secret` → un signataire. Tout le reste est un refus."""
        if not porteur or ":" not in porteur:
            raise RelecteurInconnuError(
                "Un acte de curation se signe : présentez « identifiant:secret » dans "
                "l'en-tête X-Urim-Relecteur. Le jeton de service dit « la Plateforme », "
                "il ne dit pas qui."
            )
        identifiant, _, secret = porteur.partition(":")
        trouve = await self.registre.secret_et_nom(identifiant.strip())
        if trouve is None:
            # Le hachage est fait quand même : sans lui, un identifiant inconnu répondrait plus
            # vite qu'un mauvais secret, et la différence se mesure.
            empreinte_de_secret(secret)
            raise RelecteurInconnuError("Relecteur inconnu, ou révoqué.")
        attendu, nom = trouve
        if not secrets.compare_digest(empreinte_de_secret(secret), attendu):
            raise RelecteurInconnuError("Relecteur inconnu, ou révoqué.")
        return Relecteur(identifiant=identifiant.strip(), nom=nom)


# -- ce qu'on relit ------------------------------------------------------------


@dataclass(slots=True)
class Signalement:
    """Ce qu'un détecteur a trouvé. **Il ne dit pas ce qui est vrai, il dit ce qui est suspect.**"""

    detecteur: str
    libelle: str
    gravite: int
    detail: str
    #: La ligne de curation entière, quand le détecteur en cite une. Un fragment d'expression
    #: régulière ne se juge pas : c'est ce qui a failli faire refuser huit bonnes mises en garde.
    corps: str
    #: L'empreinte de la curation **au moment du balayage**. Différente de l'empreinte courante,
    #: elle dit que le signalement parle d'une ligne réécrite depuis.
    empreinte_balayage: str


@dataclass(slots=True)
class VerdictPose:
    portee: str
    verdict: str
    note: str | None
    relu_par: str
    relu_le: datetime
    empreinte_jugee: str


@dataclass(slots=True)
class LigneCuration:
    """Une ligne du corpus, **avec sa signature**. Elle s'affiche toujours."""

    couche: str
    axe: str
    force: str | None
    corps: str
    source: str
    signee_par: str

    @property
    def generee(self) -> bool:
        return self.signee_par == SIGNATAIRE_IA


@dataclass(slots=True)
class Verset:
    chapitre: int
    verset: int
    texte: str


@dataclass(slots=True)
class UniteSignalee:
    """Une entrée de file : l'unité, ce qu'on lui reproche, et ce qui a déjà été jugé."""

    id: UUID
    reference: str
    libelle: str | None
    #: Qui a signé le **découpage** — `ia-mistral` dans l'immense majorité des cas.
    signature: str
    empreinte_courante: str
    signalements: list[Signalement] = field(default_factory=list)
    verdicts: list[VerdictPose] = field(default_factory=list)

    @property
    def _juges(self) -> dict[str, str]:
        return {v.portee: v.empreinte_jugee for v in self.verdicts}

    @property
    def restants(self) -> list[Signalement]:
        """Les signalements qu'aucun verdict encore valide ne couvre.

        Une liste vide et une unité absente de la file disent la même chose ; une liste vide sur
        une unité qui porte des verdicts dit quelque chose de plus : *quelqu'un est passé*."""
        juges = self._juges
        return [
            s for s in self.signalements
            if not verdict_couvre(juges, self.empreinte_courante, s.detecteur)
        ]

    @property
    def poids(self) -> int:
        """La gravité restante — l'ordre de la file, et rien d'autre qu'elle."""
        return sum(s.gravite for s in self.restants)

    @property
    def relue_en_entier(self) -> bool:
        return self._juges.get(PORTEE_ENSEMBLE) == self.empreinte_courante


@dataclass(slots=True)
class Dossier:
    """Ce qu'un relecteur doit avoir sous les yeux pour trancher — **et rien de moins**.

    Le texte du passage vient en premier : juger une pesée sans lire le passage qu'elle pèse
    n'est pas une relecture, c'est une signature."""

    unite: UniteSignalee
    versets: list[Verset]
    lignes: list[LigneCuration]

    @property
    def lignes_generees(self) -> int:
        return sum(1 for ligne in self.lignes if ligne.generee)


@dataclass(slots=True)
class Compteur:
    """**De combien la promesse est en retard sur le fait.**

    Le rapport du détecteur affiche déjà « 0 unités relues en entier par un humain » en première
    ligne. C'est la seule mesure qui dise cela, et la surface doit l'**alimenter** — pas en
    fabriquer une plus flatteuse. D'où `lignes_humaines` compté sur les signatures réelles des
    pesées et des mises en garde, et non sur le nombre de verdicts posés : un verdict `accepte`
    laisse la ligne signée `ia-mistral`, et il serait malhonnête de l'appeler autrement."""

    unites: int
    unites_signalees: int
    unites_relues: int
    signalements: int
    signalements_tranches: int
    lignes: int
    lignes_humaines: int
    #: Quand la file a été calculée. ⚠️ **Une file dont on ne sait pas l'âge ment** : les
    #: détecteurs tournent hors ligne, et une curation régénérée depuis n'y figure pas.
    derniere_analyse: datetime | None

    @property
    def part_relue(self) -> float:
        return self.lignes_humaines / self.lignes if self.lignes else 0.0


class RelectureRepository(Protocol):
    async def file(self, *, limite: int, decalage: int) -> list[UniteSignalee]: ...

    async def unite(self, pericope_id: UUID) -> UniteSignalee | None: ...

    async def lignes(self, pericope_id: UUID) -> list[LigneCuration]: ...

    async def texte(self, pericope_id: UUID) -> list[Verset]: ...

    async def enregistrer_verdict(
        self, pericope_id: UUID, verdict: VerdictPose
    ) -> None: ...

    async def retirer_verdict(self, pericope_id: UUID, portee: str) -> str | None: ...

    async def compteur(self) -> Compteur: ...


@dataclass(slots=True)
class Relecture:
    repo: RelectureRepository
    clock: object

    async def file(
        self, *, limite: int = PAGE_DE_FILE, decalage: int = 0
    ) -> list[UniteSignalee]:
        """La file, du plus douteux au moins — **moins ce qui est déjà tranché**.

        Le filtrage se fait ici et non en SQL parce qu'il dépend de l'empreinte courante, donc
        du contenu de la curation, pas d'un état stocké. Une unité jugée dont les pesées ont été
        régénérées **revient** : c'est la propriété qu'on ne veut surtout pas perdre en
        optimisant."""
        return [u for u in await self.repo.file(limite=limite, decalage=decalage) if u.restants]

    async def dossier(self, pericope_id: UUID) -> Dossier:
        unite = await self.repo.unite(pericope_id)
        if unite is None:
            raise UniteIntrouvableError("Cette unité littéraire n'existe pas.")
        return Dossier(
            unite=unite,
            versets=await self.repo.texte(pericope_id),
            lignes=await self.repo.lignes(pericope_id),
        )

    async def poser(
        self,
        pericope_id: UUID,
        *,
        portee: str,
        verdict: str,
        note: str | None,
        relecteur: Relecteur,
    ) -> VerdictPose:
        """Signer. **L'empreinte est prise ici, sur ce que la base contient maintenant.**"""
        verifier_verdict(verdict, portee, relecteur.nom)
        unite = await self.repo.unite(pericope_id)
        if unite is None:
            raise UniteIntrouvableError("Cette unité littéraire n'existe pas.")

        connus = {s.detecteur for s in unite.signalements}
        if portee != PORTEE_ENSEMBLE and portee not in connus:
            # Un verdict sur un détecteur muet ne couvrirait jamais rien : il aurait l'air d'un
            # travail fait et ne ferait pas décroître la file d'une unité.
            raise CurationInvalideError(
                f"Aucun signalement « {portee} » sur cette unité — les portées jugeables sont "
                f"{sorted(connus) or '-'}, ou « {PORTEE_ENSEMBLE} » pour l'unité entière."
            )

        lignes = await self.repo.lignes(pericope_id)
        pose = VerdictPose(
            portee=portee,
            verdict=verdict,
            note=note,
            relu_par=relecteur.nom,
            relu_le=self.clock(),
            empreinte_jugee=empreinte_de_curation(
                (ligne.couche, ligne.axe, ligne.corps) for ligne in lignes
            ),
        )
        await self.repo.enregistrer_verdict(pericope_id, pose)
        return pose

    async def retirer(self, pericope_id: UUID, portee: str) -> str:
        """Rendre la table à ce qu'elle doit dire : **personne n'a relu cette unité**.

        ⚠️ Ce n'est pas un détail d'outillage. Un verdict posé à tort — par erreur, par un essai,
        au nom de quelqu'un qui n'a rien jugé — ne se répare pas en le *remplaçant* : cela
        laisserait une signature à la place d'une autre. Le registre des relecteurs rend le cas
        beaucoup plus rare qu'avant ; il ne le rend pas impossible, et un verdict qu'on ne peut
        pas défaire serait pire que pas de verdict du tout."""
        retire = await self.repo.retirer_verdict(pericope_id, portee)
        if retire is None:
            raise UniteIntrouvableError(
                f"Aucun verdict à retirer sur cette unité pour la portée « {portee} »."
            )
        return retire

    async def compteur(self) -> Compteur:
        return await self.repo.compteur()
