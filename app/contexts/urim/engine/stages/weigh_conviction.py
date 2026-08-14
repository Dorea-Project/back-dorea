"""Étage 1-bis — **le chemin inversé** : d'une intention vers un texte (Architecture §7).

Les autres étages partent d'un passage et cherchent ce qu'il porte. Celui-ci part de ce que
le pasteur veut dire et cherche quel texte le porte — d'où *inversé*. Il n'existait pas, et
`bound_pericope` le disait lui-même : *« tant que ce chemin n'existe pas, une conviction
n'atteint simplement pas cet étage »*.

Deux temps, deux `AWAIT`, et la même règle aux deux : **le moteur nomme, le pasteur choisit.**

## 1. Quel axe ?

Les **dix loci**, toujours les dix. C'est l'écran de base, pas un écran de secours (S12) :
le pasteur peut désigner son axe lui-même, et c'est ce qui rend Urim livrable **sans aucun
modèle branché** — terrain tablette, connexion irrégulière (Architecture v2 §10).

Quand un modèle est branché, il **annote et n'écarte jamais**. La conséquence n'est pas
cosmétique : c'est elle qui maintient la propriété de sûreté de S37. Un port qui pourrait
retirer une option pourrait nuire en se trompant ; un port qui ne peut qu'ajouter une phrase
ne le peut pas.

Une conviction est souvent une **plainte, pas un thème** (S10) : « trop de malades malgré
les prières » touche la guérison *et* la prière sans réponse. Les dix restent donc au même
rang — ordonner serait interpréter le for intérieur de celui qui écrit.

## 2. Quel texte ?

Les unités qui **disent quelque chose** de l'axe retenu — portantes **et résistantes, au
même rang** (§7, S20). C'est ici que vit toute la protection du mode conviction, et elle a
une propriété rare : *elle ne dépend pas de la justesse de l'axe choisi*. Un pasteur qui
retient « guérison » verra quand même les textes qui compliquent la guérison ; un pasteur
qui accuse son assemblée verra quand même ceux qui se retournent vers le prédicateur.

## Le risque, et pourquoi il ne se lève qu'ici

`risk_flags` ne **choisit aucun texte** — il élargit les résistants et relève le
`proof_text_risk` que l'étage 6 affichera. Et il ne se lève que sur ce chemin : une saisie
qui nomme sa référence n'a pas de charge à peser, le pasteur a déjà dit sur quoi il prêche.

⚠️ **Le motif nomme l'effet, jamais l'état de celui qui écrit.** « Formulation à forte
charge — davantage de textes qui résistent sont affichés » se vérifie et se conteste ;
« vous êtes dans la plainte » est un diagnostic, et S10 l'interdit.
"""

from __future__ import annotations

from app.contexts.urim.engine.deps import BearingSite, EngineDeps
from app.contexts.urim.engine.outcomes import Option, Outcome, StageResult
from app.contexts.urim.engine.state import EntryMode, StudyState

#: Ce que chaque force dit du texte, en une clause lisible à l'écran. `absent` n'y figure
#: pas : une unité qui ne dit rien d'un axe n'est pas un candidat, et le port l'a déjà
#: écartée.
_CE_QUE_LE_TEXTE_FAIT = {
    "dominant": "ce texte en fait son sujet",
    "porte": "ce texte le soutient",
    "resiste": "⚠ ce texte le complique ou le contredit",
}

#: Le mot de `reviewed_by`, et pas un synonyme : le client connaît déjà « ia-mistral » par le
#: bandeau de l'unité littéraire. Deux vocabulaires pour la même question — *qui a écrit ça ?* —
#: lui feraient traiter deux fois le même cas.
SIGNATURE_GLOSE = "ia-mistral"

#: ⚠️ **Combien de textes par groupe — et le même nombre pour les trois.**
#:
#: 🔴 L'étage servait **toutes** les unités de l'axe : 4 302 sur l'anthropologie, 3 971 sur la
#: théologie propre. Ce n'était pas un écran trop long, c'était un garde-fou enterré : les
#: sites arrivent triés par force, si bien que le **premier texte qui résiste** tombait en
#: 4 298ᵉ position sur l'anthropologie, en 1 730ᵉ sur la sotériologie. Le contrat dit *« elles
#: sont affichées au même rang, exprès »* ; l'ordre disait le contraire, et personne ne
#: scrollait jusque-là.
#:
#: Le quota **identique** pour les trois groupes est ce qui rend « au même rang » mécanique
#: plutôt que déclaratif : six textes qui portent, six qui résistent, et le pasteur les voit
#: dans le même écran. Un quota proportionnel aurait reproduit l'enterrement en plus discret.
#:
#: Six est un pari, comme tous les seuils du produit — à revoir sur des saisies réelles, pas à
#: graver. La maquette en montre quatre ; `_resistent_ailleurs` s'en tient à trois, mais il
#: *avertit* là où cet écran demande de **choisir**.
PAR_GROUPE = 6


class WeighConviction:
    """Le chemin inversé. Il ne trouve pas un texte : il en propose, et il en explique."""

    code = "weigh_conviction"

    def applies(self, state: StudyState) -> bool:
        """Seulement la conviction, et seulement tant qu'aucun texte n'est retenu.

        Dès que `resolved` est posé, l'étage s'efface et le pipeline reprend son cours
        ordinaire au bornage — sans qu'aucun étage aval n'ait à savoir par où c'est entré."""
        return state.entry_mode is EntryMode.CONVICTION and state.resolved is None

    def execute(self, state: StudyState, deps: EngineDeps) -> StageResult:
        if state.axis is None:
            return self._proposer_les_axes(state, deps)
        return self._proposer_les_textes(state, deps)

    # -- 1. l'axe ---------------------------------------------------------------

    def _proposer_les_axes(self, state: StudyState, deps: EngineDeps) -> StageResult:
        axes = deps.doctrine.axes()
        if not axes:
            return StageResult(
                outcome=Outcome.REFUSE,
                rationale=(
                    "Aucun axe doctrinal n'est curé dans ce corpus — il n'y a rien à quoi "
                    "rattacher une intention."
                ),
                state=state,
            )

        # Le modèle **annote**, il n'écarte pas : les dix sortent toujours.
        #
        # Deux sources, **réunies** : le port synchrone (hors ligne, sans réseau) et l'état
        # rejoué depuis la bordure (Mistral). Une union, jamais un choix — chacune ne peut
        # qu'ajouter une phrase à une option qui sortait de toute façon, et c'est ce qui rend
        # leur erreur inoffensive (S37).
        gloses = {g.code: g for g in state.suggested_axes}
        suggeres = frozenset(deps.conviction.candidate_axes(state.raw_input)) | set(gloses)

        # ⚠️ **Le titre habille le locus touché ; il ne le remplace jamais.** `code` reste
        # `axe:<locus>`, donc la décision, les pesées et le thème travaillent sur la même
        # chose qu'avant. Un pasteur ne pense pas « théologie propre », il pense « la prière
        # sans réponse » — et lui demander de traduire sa plainte en vocabulaire d'école avant
        # qu'Urim ne l'aide, c'est lui faire payer l'entrée.
        #
        # Les sept autres gardent leur libellé et leur place. Rien n'est retiré : c'est la
        # condition pour qu'une glose fausse reste sans conséquence.
        options = tuple(
            Option(
                code=f"axe:{axe.code}",
                # ⚠️ La signature suit **le libellé**, pas l'option : les dix loci viennent tous
                # du corpus, seuls certains sont habillés. Un client qui marquerait l'option
                # entière dirait que l'axe est généré, ce qui est faux.
                signature=SIGNATURE_GLOSE if gloses.get(axe.code) else None,
                label=(
                    gloses[axe.code].title if axe.code in gloses else ""
                ) or axe.label,
                rationale=(
                    (gloses[axe.code].gloss if axe.code in gloses else "")
                    or (
                        "Votre formulation touche cet axe."
                        if axe.code in suggeres
                        else "Disponible — c'est vous qui savez ce que vous prêchez."
                    )
                ),
                origin="locus",
            )
            for axe in axes
        )

        # **Les textes, à côté des angles.** Un pasteur qui a nommé son sujet et ne reçoit que
        # dix mots grecs n'a rien reçu. `origin` distingue les deux familles pour que le client
        # les présente séparément — *quel angle ?* d'un côté, *ou allez droit à un texte* de
        # l'autre. Aucun n'est retiré, et l'un ne remplace pas l'autre : passer par l'axe reste
        # le seul chemin qui donne des textes **pesés**.
        droit_au_texte = tuple(
            Option(
                code=_dire_reference(p.reference),
                label=_dire_reference(p.reference),
                rationale=p.rationale or "Traite ce sujet.",
                origin="sens",
            )
            for p in state.suggested_passages
        )
        return StageResult(
            outcome=Outcome.AWAIT,
            rationale=_motif_des_axes(state, suggeres, bool(droit_au_texte)),
            state=state,
            options=(*options, *droit_au_texte),
        )

    # -- 2. le texte ------------------------------------------------------------

    def _proposer_les_textes(self, state: StudyState, deps: EngineDeps) -> StageResult:
        sites = deps.doctrine.sites_for_axis(state.axis or "")
        if not sites:
            # ⚠️ **Le plafond de la curation ne doit pas ressembler au silence de l'Écriture.**
            #
            # Le motif le disait déjà — *ce n'est pas que l'Écriture n'en dise rien* — mais il
            # renvoyait quand même le pasteur les mains vides, en lui demandant d'entrer une
            # référence qu'il serait venu chercher ici s'il l'avait eue. Quand le sens a
            # proposé des passages, ils prennent la place du refus : rien n'est relu sur eux,
            # et c'est dit.
            if state.suggested_passages:
                return StageResult(
                    outcome=Outcome.AWAIT,
                    rationale=(
                        "Aucune unité relue ne porte cet axe dans ce corpus — ces passages le "
                        "traitent, mais rien n'y a encore été pesé. Lequel travaillez-vous ?"
                    ),
                    state=state,
                    options=tuple(
                        Option(
                            code=_dire_reference(p.reference),
                            label=_dire_reference(p.reference),
                            rationale=p.rationale or "Traite cet axe.",
                            origin="sens",
                        )
                        for p in state.suggested_passages
                    ),
                )

            # Le plafond dur du corpus curé, **dit franchement** (S2, S3). Ce n'est pas une
            # panne : c'est une limite, et la taire laisserait croire que le texte n'existe
            # pas alors que c'est la relecture qui manque.
            return StageResult(
                outcome=Outcome.REFUSE,
                rationale=(
                    "Aucune unité littéraire relue ne porte cet axe dans ce corpus. Ce n'est "
                    "pas que l'Écriture n'en dise rien — c'est que la curation ne couvre pas "
                    "encore ce terrain. Entrez une référence si vous savez déjà où aller."
                ),
                state=state,
            )

        retenus = _echantillon(sites)
        options = tuple(
            Option(
                code=f"texte:{site.pericope_id}",
                label=f"{site.label} — {_CE_QUE_LE_TEXTE_FAIT.get(site.strength, site.strength)}",
                rationale=site.rationale,
                # Ce que le texte fait de l'axe voyage **aussi** en clair : le libellé le dit
                # au pasteur, ce champ le dit au client, qui peut alors grouper sans lire.
                strength=site.strength,
            )
            for site in retenus
        )
        return StageResult(
            outcome=Outcome.AWAIT,
            rationale=_motif_des_textes(sites, retenus, state),
            state=state,
            options=options,
        )


def _echantillon(sites: tuple[BearingSite, ...]) -> tuple[BearingSite, ...]:
    """Un échantillon **par groupe**, à quota égal — et l'ordre du canon préservé.

    Les trois groupes sont traités séparément et reçoivent le même nombre de places : c'est ce
    qui empêche les 4 070 unités qui *portent* l'anthropologie d'écraser les 5 qui lui
    résistent. Le rendu reste dans l'ordre `dominant · porte · resiste`, celui du tri d'index
    et celui des groupes du tour."""
    par_force = {
        force: tuple(s for s in sites if s.strength == force)
        for force in _CE_QUE_LE_TEXTE_FAIT
    }
    inconnues = tuple(s for s in sites if s.strength not in _CE_QUE_LE_TEXTE_FAIT)
    return tuple(
        site
        for groupe in (*par_force.values(), inconnues)
        for site in _etaler(groupe, PAR_GROUPE)
    )


def _etaler(sites: tuple[BearingSite, ...], plafond: int) -> tuple[BearingSite, ...]:
    """`plafond` textes au plus, **étalés sur le canon** plutôt que pris au début.

    C'est la mécanique de `_resistent_ailleurs`, et pour la même raison : les sites arrivent
    dans l'ordre canonique, si bien que prendre les premiers rend six chapitres voisins de la
    Genèse. Un livre ne parle qu'une fois, puis on répartit — le pasteur reçoit un texte de la
    Loi, un des Prophètes, un des Épîtres.

    ⚠️ **Déterministe, donc rejouable.** C'est la condition du moteur, et elle exclut tout
    tirage : même corpus, même axe, mêmes six textes.

    Si les livres distincts ne suffisent pas à remplir l'écran, on complète avec le reste :
    montrer trois textes quand le corpus en a cent et qu'on s'autorisait six serait une autre
    façon de dissimuler."""
    if len(sites) <= plafond:
        return sites

    premiers, livres = [], set()
    for site in sites:
        livre = site.bounds.start.book
        if livre not in livres:
            livres.add(livre)
            premiers.append(site)

    if len(premiers) < plafond:
        # On complète dans l'ordre du canon, et on filtre `sites` pour le rendu : l'ordre
        # canonique se rétablit tout seul, sans comparer des sites entre eux — deux unités d'un
        # même chapitre peuvent être égales champ à champ sans être la même.
        gardes = {id(s) for s in premiers}
        for site in sites:
            if len(gardes) >= plafond:
                break
            gardes.add(id(site))
        return tuple(s for s in sites if id(s) in gardes)

    pas = (len(premiers) - 1) / (plafond - 1)
    return tuple(premiers[round(rang * pas)] for rang in range(plafond))


def _motif_des_axes(
    state: StudyState, suggeres: frozenset[str], des_textes: bool = False
) -> str:
    debut = (
        "Une intention peut porter plusieurs doctrines, et c'est souvent le cas. "
        "Laquelle prêchez-vous ?"
    )
    if suggeres:
        debut += (
            " Les axes que votre formulation touche sont signalés — les autres restent "
            "ouverts."
        )
    if des_textes:
        # Dire que le raccourci existe, et **ce qu'il coûte** — c'est la règle du `tel_quel`
        # au bornage : accorder une liberté sans nommer ce qu'elle ferme, c'est la faire
        # découvrir trop tard.
        debut += (
            " Des passages qui traitent ce sujet sont proposés plus bas ; y aller directement "
            "vous fait sauter la pesée doctrinale de l'axe."
        )
    return debut + _clause_de_risque(state)


def _motif_des_textes(
    sites: tuple[BearingSite, ...], retenus: tuple[BearingSite, ...], state: StudyState
) -> str:
    """⚠️ **On écourte, on ne dissimule pas.**

    Le compte réel voyage à côté de ce qui est montré — c'est la règle de la concordance, où
    `total` dit 126 pendant qu'on en affiche cinquante. Un extrait présenté comme un tout ferait
    conclure d'un échantillon, et ici la conclusion porterait sur ce que l'Écriture dit d'un
    axe."""
    resistants = sum(1 for s in sites if s.strength == "resiste")
    montres = sum(1 for s in retenus if s.strength == "resiste")
    motif = f"{len(sites)} unité(s) relue(s) disent quelque chose de cet axe."
    if len(retenus) < len(sites):
        motif += (
            f" En voici {len(retenus)}, réparties sur le canon — un livre ne parle qu'une "
            "fois, et le choix reste ouvert à toute référence que vous donnerez."
        )
    if resistants:
        # Annoncé, jamais glissé en bas de liste : c'est la partie qu'un pasteur pressé
        # sauterait, et c'est celle qui le protège.
        combien = f"{montres} sur {resistants}" if montres < resistants else str(montres)
        motif += (
            f" Dont {combien} qui le **compliquent ou le contredisent** — elles sont "
            "affichées au même rang, exprès."
        )
    return motif + _clause_de_risque(state)


def _clause_de_risque(state: StudyState) -> str:
    """Nomme **l'effet** du drapeau, jamais l'état de celui qui écrit (S10, S37)."""
    if not state.risk_flags:
        return ""
    return (
        " Formulation à forte charge : davantage de textes qui résistent sont affichés, "
        "et le risque de proof-texting sera relevé sur la mise en forme."
    )


def _dire_reference(reference) -> str:
    """La référence en clair — même forme que l'étage 1, pour que le code d'option soit
    relisible par `_reference_depuis_libelle` quel que soit l'étage qui l'a émis."""
    if reference.is_whole_book:
        return reference.book
    if reference.is_whole_chapter:
        return f"{reference.book} {reference.chapter}"
    if reference.verse_end and reference.verse_end != reference.verse_start:
        return f"{reference.book} {reference.chapter}:{reference.verse_start}-{reference.verse_end}"
    return f"{reference.book} {reference.chapter}:{reference.verse_start}"
