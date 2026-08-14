"""Le banc de l'arbre — **le chiffre qui compte est le mur, pas la couverture**.

    python scripts/urim_banc_arbre.py
    python scripts/urim_banc_arbre.py --tout      # chaque prise en entier, pour relire

Le produit tient une règle partout : *aucun mur un vendredi soir*. `Outcome.DEGRADE` ne coupe
jamais le pipeline, les adaptateurs `Null*` sont des états de production, une panne de modèle
n'est jamais une panne d'Urim. **Un chemin conversationnel sans issue viole cette règle**, et
il ne se voit pas en lisant le code — il se voit en marchant.

## Ce que ce banc mesure, et rien d'autre

Une seule propriété, posée à chaque tour :

> **Après ce tour, le pasteur a-t-il quelque chose à faire ?**

Des options à toucher, une action ouverte, ou une barre de saisie **dont la passerelle est
nommée**. Un tour qui n'offre rien des trois est un mur, et le banc le nomme.

    murs sur les chemins reels           DOIT etre 0
    murs sur les chemins confessionnels  DOIT etre 0 — catholique, protestant, orthodoxe
    murs sur les chemins absurdes        DOIT etre 0 — micro ouvert, livre inconnu, saisie vide
    cellules de l'arbre visitees         informatif : ce que la marche a effectivement touche

**Les trois premiers chiffres sont des échecs.** Le quatrième ne l'est pas : une cellule non
visitée n'est pas une cellule cassée — `docs/Urim_Arbre_Conversationnel.md` dit lesquelles sont
inatteignables par construction, et pourquoi.

## Pourquoi tout se relit

🔴 La leçon la plus chère de la journée : un instrument qu'on ne peut pas relire fait arbitrer
sur sa parole — neuf « formes interdites » signalées, huit étaient les meilleures lignes du
corpus. `--tout` redéballe donc chaque prise entière : `say`, `why`, `ask`, `expects` et les
blocs. Le verdict du banc ne vaut que ce que vaut la prise qu'on peut relire derrière lui.

## Ce qu'il n'y a pas ici

**Aucune doublure de corpus.** Le banc tourne contre les 31 170 versets réels et les 4 561
unités curées : un arbre marché sur deux versets de test dirait surtout que la doublure est
petite. Il exige donc la base, et le dit s'il ne l'a pas.

**Le modèle est facultatif.** Sans clé, les suggestions disparaissent — et c'est le cas le
plus **sévère**, celui où le moteur n'a que le corpus. Les murs se cherchent là.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ⚠️ La sortie porte le vocabulaire du produit — « ⚠ ce texte le complique » est un libellé
# d'option, pas une décoration. Une console en cp1252 le fait tomber en UnicodeEncodeError, et
# le banc s'arrête au milieu d'une prise. On force l'encodage plutôt que d'appauvrir ce qu'on
# affiche : un banc qui n'imprime pas ce que le pasteur lit ne prouve rien.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.contexts.urim.adapters.mistral import MistralAssistant
from app.contexts.urim.application.ports import UsageSnapshot
from app.contexts.urim.application.study_service import UrimStudyService
from app.contexts.urim.domain.errors import OptionInconnueError
from app.contexts.urim.engine.stages.bound_pericope import TEL_QUEL
from app.contexts.urim.engine.stages.route_entry import REFORMULER
from app.contexts.urim.engine.state import EntryOrigin
from app.contexts.urim.infrastructure.corpus.index import load_corpus_index
from app.contexts.urim.interface.schemas import StudyView
from app.core.config import get_settings
from app.core.database import async_session_factory

AUTEUR = UUID("22222222-2222-2222-2222-222222222222")
#: Horloge figée : le banc doit rendre deux fois le même verdict sur le même corpus.
FIGE = datetime(2026, 8, 13, 9, 0, tzinfo=UTC)

REELLE, CONFESSION, ABSURDE = "reelle", "confession", "absurde"

# --------------------------------------------------------------------- les gestes du pasteur

#: ⚠️ **Fermé**, comme le vocabulaire d'intentions et les loci. Un geste de banc qui se
#: paramètre finement finit par décrire un pasteur qui n'existe pas.
SUIVRE = "suivre"  # prendre la première option offerte, tour après tour, jusqu'au bout
ECARTER_TOUT = "ecarter_tout"  # repousser tout ce qui est proposé — le cas de la liste épuisée
ABANDONNER = "abandonner"  # « ce n'est pas ça » — le micro resté ouvert, refermé en un tap
MES_BORNES = "mes_bornes"  # garder sa demande telle quelle au bornage (S22), puis continuer

#: ⚠️ **`MES_BORNES` n'est pas un cas tordu : c'est un bouton de l'écran de bornage.**
#:
#: Il fait retomber `pericope_id` à `None`, donc plus rien de curé n'est lisible en aval — la
#: pesée dégrade, aucun axe n'est retenu, et le pipeline s'arrête là. C'est le **seul chemin
#: vivant** vers la cellule où vivait le mur n°2 depuis que la curation couvre les 66 livres.
#: Sans ce geste, le banc serait vrai par vacuité sur la moitié de ce qu'il prétend garder.


@dataclass(frozen=True)
class Cas:
    saisie: str
    famille: str
    geste: str = SUIVRE
    note: str = ""
    #: S36 — le système **sait** d'où vient la chaîne, il ne le déduit pas des mots. C'est le
    #: seul chemin vers la main rendue par l'étage 0.
    dictee: bool = False


_BANC: tuple[Cas, ...] = (
    # ------------------------------------------------- les vraies saisies du Pasteur X
    Cas("Romains 8:1-11", REELLE, note="une reference nette — le chemin le plus court"),
    Cas("Dieu est l'auteur et le consommateur de notre foi, sur l'autel Divin", REELLE,
        note="bancale, et c'est une vraie predication"),
    Cas("l'amour fraternel n'existe plus dans l'eglise", REELLE,
        note="une PLAINTE, pas une intention"),
    Cas("l'amour fraternel n'existe plus dans l'eglise", REELLE, ECARTER_TOUT,
        note="LE MUR N.1 — les dix loci ecartes l'un apres l'autre"),
    Cas("je veux faire un culte sur l'adultère dans", REELLE,
        note="TRONQUEE — documentee dans _SYSTEME_AXES"),
    Cas("le fils prodigue rentre chez son pere", REELLE, note="une scene racontee de memoire"),
    Cas("on prie pour les malades et rien ne change", REELLE),
    Cas("1 Roi ou 2 Roi, il s'agit de Jezabel", REELLE, note="S24 — l'hesitation sur le livre"),
    Cas("Romains 8:1", REELLE, MES_BORNES,
        note="LE MUR N.2 — un verset garde tel quel, et plus rien de cure n'est lisible"),

    # ------------------------------------------------- les trois confessions
    #
    # ⚠️ Ce que ces cas mesurent n'est PAS si Urim a raison sur la doctrine — il n'a pas
    # d'avis, et c'est la règle. Ils mesurent qu'un pasteur dont le sujet n'entre dans aucun
    # des dix loci reçoive quand même un chemin. Les dix loci sont la dogmatique de CE corpus.
    Cas("l'Immaculée Conception", CONFESSION, note="catholique — aucun des dix loci ne la porte"),
    Cas("l'Immaculée Conception", CONFESSION, ECARTER_TOUT,
        note="catholique — le sujet sans locus, et la liste epuisee"),
    Cas("la montée de Marie au ciel", CONFESSION, note="catholique — l'Assomption"),
    Cas("Luc 1:28", CONFESSION,
        note="catholique — LE proof-text : un verset seul, que le bornage rouvre en entier"),
    Cas("Luc 1:28", CONFESSION, MES_BORNES,
        note="catholique — il GARDE son verset seul : S22, on ne punit pas une liberte accordee"),
    Cas("Apocalypse 12", CONFESSION, note="catholique — la femme couronnee d'etoiles"),
    Cas("le salut par la foi seule, sans les oeuvres", CONFESSION, note="protestant — sola fide"),
    Cas("Romains 3:28", CONFESSION, note="protestant — le texte de la sola fide"),
    Cas("la theosis, l'homme appele a devenir dieu par grace", CONFESSION,
        note="orthodoxe — aucun des dix loci ne la nomme"),
    Cas("2 Pierre 1:4", CONFESSION, note="orthodoxe — participants de la nature divine"),
    Cas("la Dormition de la Mere de Dieu", CONFESSION, ECARTER_TOUT, note="orthodoxe"),

    # ------------------------------------------------- les chemins que personne ne prevoit
    Cas("Ma voiture 406, a besoin de reparation , jefgf Paradis", ABSURDE,
        note="le micro reste ouvert — documente dans engine/state.py"),
    Cas("Ma voiture 406, a besoin de reparation , jefgf Paradis", ABSURDE, ABANDONNER,
        dictee=True, note="le meme, DICTE et referme en un tap — S36"),
    Cas("Ma voiture 406, a besoin de reparation , jefgf Paradis", ABSURDE, SUIVRE,
        dictee=True, note="dicte, et le pasteur confirme quand meme ce qu'il a dit"),
    Cas("je crois que Dieu veut guerir mon eglise", ABSURDE, SUIVRE, dictee=True,
        note="une vraie intention DICTEE — elle se fait confirmer, une tapee non"),
    Cas("Zorobabel 3:5", ABSURDE, note="la forme d'une reference, le livre inconnu"),
    Cas("   ", ABSURDE, note="la saisie vide — aucun token"),
    Cas("jefgf", ABSURDE, note="un mot qui n'est rien"),
    Cas("oui", ABSURDE, note="un acquiescement seul, sans question posee"),
    Cas("prie pour moi", ABSURDE, note="hors_champ a la porte — il parle, on ne sait pas repondre"),
    Cas("Hébreux 2:29", ABSURDE, note="Hb 2 compte 18 versets — la note du Pasteur X"),
)


# --------------------------------------------------------------------- ce qu'une prise garde


@dataclass
class Prise:
    """Un tour, tel que le pasteur l'a reçu — **et de quoi le relire en entier**."""

    cas: Cas
    rang: int
    etage: str
    outcome: str
    say: str
    why: str
    ask: str
    expects: str
    blocs: tuple[tuple[str, int], ...]
    touchables: int
    actions: int
    mur: str | None = None


def _touchables(tour) -> int:
    """Ce que le pasteur peut toucher — pastilles, unités groupées, bornes."""
    return sum(
        len(getattr(bloc, "items", ()))
        + sum(len(g.items) for g in getattr(bloc, "groups", ()))
        for bloc in tour.blocks
        if bloc.kind != "actions"
    )


def _actions_ouvertes(tour) -> int:
    return sum(
        1
        for bloc in tour.blocks
        if bloc.kind == "actions"
        for item in bloc.items
        if item.enabled
    )


def mur(tour) -> str | None:
    """**La seule question du banc** : après ce tour, que peut faire le pasteur ?

    Trois issues suffisent, et elles sont testées de la plus concrète à la plus mince. Un tour
    qui n'en offre aucune est un mur — quelle que soit la beauté de sa phrase.

    ⚠️ La barre de saisie ne compte que si la **passerelle est nommée**. `expects: text` sans
    `ask` laisse le pasteur devant un champ vide sans savoir ce qu'on attend de lui : c'est un
    cul-de-sac poli, et c'est exactement la forme sous laquelle un mur survit à une relecture.
    """
    if _touchables(tour):
        return None
    if _actions_ouvertes(tour):
        return None
    if tour.expects == "choice":
        # Le moteur attend un choix et l'écran n'en propose aucun : le client ouvre un
        # sélecteur vide. C'est le mur n°1, et il tenait à un filtre.
        return "un choix demande, et aucune option a toucher"
    if tour.expects == "nothing":
        return "ni option, ni action, ni saisie"
    if not tour.ask.strip():
        return "barre ouverte, mais aucune passerelle nommee"
    return None


#: Au-delà, un écran cesse d'être un choix. 🔴 Ce compteur a trouvé le déversoir —
#: `weigh_conviction` servait **toutes** les unités de l'axe, 4 302 sur l'anthropologie — et
#: surtout ce qu'il enterrait : les textes qui résistent, en queue de tri, au 4 298ᵉ rang.
#:
#: Il est à zéro depuis le plafond par groupe. On le **garde** : c'est le genre de seuil qui
#: remonte tout seul le jour où un étage se remet à tout servir, et il ne coûte rien.
_DEVERSOIR = 60


def _deverse(prise: Prise) -> bool:
    """Le jumeau du mur : **rien à faire** d'un côté, **trop pour faire quoi que ce soit** de
    l'autre. Les deux se ressemblent depuis la chaise du pasteur."""
    return prise.touchables > _DEVERSOIR


def _promesse_creuse(prise: Prise) -> bool:
    """Le `say` annonce-t-il un contenu que l'écran n'a pas ?

    Ce n'est pas un mur au sens strict — le pasteur peut encore taper — mais c'est le mur tel
    qu'il se **présente** : « Voici ce que ce texte porte » au-dessus de zéro bloc."""
    return not prise.blocs and prise.say.lstrip().lower().startswith("voici")


# --------------------------------------------------------------------- la bordure, en memoire


class _Studies:
    """Le dépôt en mémoire — **clé par étude**, et ce n'est pas un détail.

    🔴 Une première version partageait un seul ensemble d'écartées entre toutes les études :
    la deuxième saisie du banc s'ouvrait avec dix options déjà repoussées, et le banc annonçait
    un mur à l'ouverture. L'instrument mentait, pas le produit."""

    def __init__(self) -> None:
        self.records: dict[UUID, object] = {}
        self.ecartees: dict[UUID, set[tuple[str, str]]] = {}
        self.memos: dict[tuple, object] = {}

    async def add(self, record) -> None:
        self.records[record.id] = record

    async def get(self, study_id):
        return self.records.get(study_id)

    async def save(self, record) -> None:
        self.records[record.id] = record

    async def record_attempt(self, **_) -> None: ...

    async def set_elements(self, *_) -> None: ...

    async def list_elements(self, _) -> list:
        return []

    async def set_supports(self, *_) -> None: ...

    async def list_supports(self, _) -> list:
        return []

    async def dismiss(self, *, study_id, stage_code, option_code, at) -> None:
        self.ecartees.setdefault(study_id, set()).add((stage_code, option_code))

    async def restore(self, *, study_id, stage_code, option_code) -> None:
        self.ecartees.get(study_id, set()).discard((stage_code, option_code))

    async def list_dismissals(self, study_id) -> list:
        return sorted(self.ecartees.get(study_id, set()))

    async def save_suggestions(self, study_id, snapshot, at) -> None:
        self.memos[(study_id, snapshot.input_hash)] = snapshot

    async def get_suggestions(self, study_id, input_hash):
        return self.memos.get((study_id, input_hash))

    async def recently_preached_axes(self, *_) -> list:
        return []


class _Reservations:
    async def reserve(self, **_):
        return uuid4()

    async def rekey_for(self, **_) -> None: ...

    async def mark_assisted(self, **_) -> None: ...

    async def usage(self, *_):
        return UsageSnapshot()


class _Acces:
    async def ensure_may_prepare(self, **_) -> None: ...


# --------------------------------------------------------------------- la marche


#: Un fil de préparation ne fait pas onze tours ici : au-delà, ce n'est plus un chemin, c'est
#: une boucle qu'on n'a pas vue. Le plafond est une sonde, pas un réglage.
_TOURS_MAX = 8

#: ⚠️ **Une panne de débit ressemble exactement à un refus** — la leçon du banc de la porte.
#:
#: Une ouverture part en trois appels parallèles (axes, risque, passages). Enchaînées sans
#: pause, vingt-six ouvertures prennent un 429 dès la quinzième, les suggestions reviennent
#: vides, et le banc mesure le quota en croyant mesurer l'arbre. Ici le sens de l'erreur est
#: inverse de celui du banc de la porte — moins de suggestions, donc **plus** de murs
#: possibles — mais un chiffre faussé dans le sens sévère reste un chiffre faussé.
_PAUSE_ENTRE_CAS = 2.0

#: Le rang de la prise de relecture — elle n'est pas le tour n+1 d'un fil, c'est un autre geste.
_RELECTURE = -1


@dataclass
class Marche:
    prises: list[Prise] = field(default_factory=list)
    refus_au_clic: list[tuple[Cas, str, str]] = field(default_factory=list)


def _cible(cas: Cas, vivantes: list, etage: str):
    """L'option que ce pasteur-là toucherait — **et le motif de chaque préférence**.

    `reformuler` abandonne la préparation : le suivre par défaut couperait tous les chemins
    d'une dictée au premier tour, et le banc mesurerait un produit qu'on n'utilise pas."""
    if cas.geste == ABANDONNER:
        return next((o for o in vivantes if o.code == REFORMULER), vivantes[0])
    if cas.geste == MES_BORNES and etage == "bound_pericope":
        return next((o for o in vivantes if o.code == TEL_QUEL), vivantes[0])
    return next((o for o in vivantes if o.code != REFORMULER), vivantes[0])


async def _marcher(service, cas: Cas, marche: Marche) -> None:
    """Ouvrir, répéter le geste du pasteur, puis **rouvrir** la préparation.

    ⚠️ La relecture n'est pas un ornement : `GET /studies/{id}` rejoue les huit étages sur un
    état déjà décidé, si bien que les étages qui rendaient la main ne s'appliquent plus. Le
    tour qu'elle produit n'est celui d'aucun des chemins ci-dessus, et c'est pourtant l'écran
    qu'un pasteur voit chaque fois qu'il rouvre son travail du samedi."""
    dto = await service.open(
        actor_account_id=AUTEUR, raw_input=cas.saisie,
        entry_origin=EntryOrigin.DICTATED if cas.dictee else EntryOrigin.TYPED,
    )
    vue = StudyView.avec_tour(dto)
    _garder(marche, cas, 0, vue)

    for rang in range(1, _TOURS_MAX):
        vivantes = [o for o in vue.options if not o.dismissed]
        if not vivantes or vue.outcome != "await_decision":
            break

        etage = vue.turn.stage_code
        if cas.geste == ECARTER_TOUT:
            for option in vivantes:
                dto = await service.dismiss(
                    actor_account_id=AUTEUR, study_id=dto.record.id,
                    stage_code=etage, option_code=option.code,
                )
            _garder(marche, cas, rang, StudyView.avec_tour(dto))
            break

        cible = _cible(cas, vivantes, etage)
        try:
            dto = await service.decide(
                actor_account_id=AUTEUR, study_id=dto.record.id,
                stage_code=etage, option_code=cible.code,
            )
        except OptionInconnueError as refus:
            # 🔴 Une option offerte que le service refuse au clic. La réponse était juste ;
            # c'est le coup d'après qui tombe — et aucun test qui ne joue pas le coup d'après
            # ne peut l'attraper.
            marche.refus_au_clic.append((cas, cible.code, str(refus)))
            return
        vue = StudyView.avec_tour(dto)
        _garder(marche, cas, rang, vue)
        if cas.geste == ABANDONNER:
            break

    relu = await service.get(actor_account_id=AUTEUR, study_id=dto.record.id)
    _garder(marche, cas, _RELECTURE, StudyView.avec_tour(relu))


def _garder(marche: Marche, cas: Cas, rang: int, vue) -> None:
    tour = vue.turn
    marche.prises.append(Prise(
        cas=cas, rang=rang, etage=tour.stage_code, outcome=vue.outcome,
        say=tour.say, why=tour.why, ask=tour.ask, expects=tour.expects,
        # Un `theme` ne porte ni items ni groupes : compté comme les autres, il s'affichait
        # « theme(0) » — c'est-à-dire exactement comme un bloc vide, celui qu'on traque.
        blocs=tuple(
            (b.kind, len(getattr(b, "items", ())) or sum(
                len(g.items) for g in getattr(b, "groups", ())
            ) or (1 if getattr(b, "body", "") else 0))
            for b in tour.blocks
        ),
        touchables=_touchables(tour), actions=_actions_ouvertes(tour),
        mur=mur(tour),
    ))


# --------------------------------------------------------------------- le rapport


_ETAGES = (
    "route_entry", "weigh_conviction", "resolve_passage", "bound_pericope",
    "serve_corpus", "load_context", "bear_axes", "shape_homiletic", "propose_theme",
)
_ISSUES = ("continue", "await_decision", "refuse", "degrade")


def _relire(prise: Prise) -> None:
    """Une prise, en entier. C'est ce qui permet de contredire le banc."""
    rang = "RELECTURE" if prise.rang == _RELECTURE else f"tour {prise.rang}"
    print(f"\n  --- [{prise.cas.famille}] « {prise.cas.saisie[:56]} »  {rang}")
    if prise.cas.note:
        print(f"      ({prise.cas.note})")
    print(f"      etage    {prise.etage}   issue {prise.outcome}   expects {prise.expects}")
    print(f"      SAY      {prise.say}")
    print(f"      WHY      {prise.why[:220]}")
    print(f"      ASK      {prise.ask or '(aucune)'}")
    blocs = " · ".join(f"{k}({n})" for k, n in prise.blocs) or "(aucun bloc)"
    print(f"      BLOCS    {blocs}")
    print(f"      a toucher {prise.touchables}   actions {prise.actions}")


def _rapport(marche: Marche, tout: bool) -> None:
    prises = marche.prises

    print("\n" + "=" * 78)
    print("  LES CHIFFRES QUI SONT DES ECHECS")
    print("=" * 78)
    for famille in (REELLE, CONFESSION, ABSURDE):
        lot = [p for p in prises if p.cas.famille == famille]
        murs = [p for p in lot if p.mur]
        print(f"  murs sur les chemins {famille:<12} {len(murs)}/{len(lot)} tours")
    print("  -> un tour qui n'offre rien est un mur, quelle que soit la beaute de sa phrase")

    creuses = [p for p in prises if _promesse_creuse(p)]
    print(f"\n  promesses creuses (« Voici… » sur zero bloc)   {len(creuses)}/{len(prises)}")

    deverses = [p for p in prises if _deverse(p)]
    if deverses:
        print(f"\n  ECRANS DEVERSOIRS (plus de {_DEVERSOIR} choses a toucher)  "
              f"{len(deverses)}/{len(prises)}")
        print("  ce n'est pas un mur, c'en est le jumeau : trop pour choisir vaut rien a choisir")
        for prise in sorted(deverses, key=lambda p: -p.touchables)[:6]:
            print(f"    {prise.touchables:>6} a toucher   [{prise.etage}]  "
                  f"« {prise.cas.saisie[:44]} »")

    print("\n" + "=" * 78)
    print("  L'ARBRE — LES CELLULES TERMINALES, CELLES QUI RENDENT UN TOUR")
    print("=" * 78)
    print("  (un etage qui CONTINUE est traverse, pas terminal : le tour est celui du suivant)")
    print(f"  {'etage':<20}" + "".join(f"{i:>16}" for i in _ISSUES))
    visitees = 0
    for etage in _ETAGES:
        cellules = []
        for issue in _ISSUES:
            n = sum(1 for p in prises if p.etage == etage and p.outcome == issue)
            visitees += 1 if n else 0
            cellules.append(f"{n:>16}" if n else f"{'.':>16}")
        print(f"  {etage:<20}" + "".join(cellules))
    print(f"\n  {visitees} cellules sur {len(_ETAGES) * len(_ISSUES)} touchees en "
          f"{len(prises)} tours. Une cellule vide n'est pas une cellule cassee :")
    print("  docs/Urim_Arbre_Conversationnel.md dit lesquelles sont inatteignables, et pourquoi.")

    murs = [p for p in prises if p.mur]
    if murs:
        print("\n" + "=" * 78)
        print("  LES MURS  (le pasteur n'a rien a faire apres ce tour)")
        print("=" * 78)
        for prise in murs:
            print(f"\n  >>> {prise.mur}")
            _relire(prise)

    if creuses and not tout:
        print("\n" + "=" * 78)
        print("  LES PROMESSES CREUSES  (le say annonce, l'ecran ne montre rien)")
        print("=" * 78)
        for prise in creuses:
            _relire(prise)

    if marche.refus_au_clic:
        print("\n" + "=" * 78)
        print("  OFFERT PUIS REFUSE AU CLIC  (la reponse est juste, le coup d'apres tombe)")
        print("=" * 78)
        for cas, code, motif in marche.refus_au_clic:
            print(f"  « {cas.saisie[:40]} » -> {code}\n      {motif}")

    if tout:
        print("\n" + "=" * 78)
        print("  TOUTES LES PRISES, EN ENTIER")
        print("=" * 78)
        for prise in prises:
            _relire(prise)
    else:
        print("\n  (--tout pour relire les " + str(len(prises)) + " prises en entier)")


async def main() -> None:
    reglages = get_settings()
    try:
        async with async_session_factory() as session:
            index = await load_corpus_index(session)
    except Exception as panne:
        print(f"Corpus injoignable — rien a marcher.\n  {panne}")
        return

    modele = (
        MistralAssistant(reglages.mistral_api_key, reglages.mistral_model)
        if reglages.mistral_api_key
        else None
    )
    print(f"corpus {index.snapshot} — {len(index.verses)} versets, "
          f"{len(index.pericopes)} unites curees")
    print(f"modele : {reglages.mistral_model if modele else 'AUCUN (le cas le plus severe)'}")
    print(f"{len(_BANC)} cas\n")

    marche = Marche()
    for cas in _BANC:
        if modele is not None:
            await asyncio.sleep(_PAUSE_ENTRE_CAS)
        service = UrimStudyService(
            studies=_Studies(), reservations=_Reservations(), access=_Acces(),
            index=index, clock=lambda: FIGE,
            **({"resolver": modele} if modele else {}),
        )
        avant = len(marche.prises)
        await _marcher(service, cas, marche)
        tours = marche.prises[avant:]
        murs = sum(1 for p in tours if p.mur)
        marque = f"MUR x{murs}" if murs else "ok   "
        print(f"  {marque}  {cas.famille:<11} {len(tours)} tour(s)  "
              f"{cas.saisie[:44]}")

    _rapport(marche, tout="--tout" in sys.argv)

    # Le banc dit **dans quel état il a mesuré**. Un banc qui tait ses pannes de transport
    # rend le verdict le plus flatteur possible, et personne ne peut le contredire.
    echecs = getattr(modele, "echecs", 0)
    if echecs:
        print(f"\n  ATTENTION : {echecs} appels de modele ont echoue (429 ?). Les suggestions")
        print("  manquantes rendent l'arbre PLUS severe, pas moins — mais la mesure est faussee.")
        print("  Relancer avec une pause plus longue, ou sans cle du tout.")


if __name__ == "__main__":
    asyncio.run(main())
