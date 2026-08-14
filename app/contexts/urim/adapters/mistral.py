"""L'IA d'Urim — **elle retrouve la référence, la Bible donne le texte**.

C'est la règle de M9-1, et elle vaut ici mot pour mot : le modèle n'écrit jamais un verset.
Il rend `{found, book, chapter, verse}` et rien d'autre ; le texte vient du corpus, toujours.
Un modèle qui cite de mémoire cite faux, et personne ne s'en aperçoit.

## Deux ports, une même propriété de sûreté

`AssistedResolver` cherche un passage quand le résolveur déterministe n'en trouve aucun.
`MistralConviction` lève des drapeaux de risque sur une intention. Ni l'un ni l'autre ne peut
**retirer** quoi que ce soit : le premier ajoute un candidat, le second ajoute des textes qui
résistent. C'est la seule raison pour laquelle on les autorise à parler — leur erreur est
inoffensive, leur absence l'est aussi.

## Pourquoi ce fichier duplique la trentaine de lignes de `mission`

`MistralVerseResolver` existe dans `mission` et fait exactement cela. L'importer d'ici serait
permis (on est dans `adapters/`) mais coupleraient deux produits qu'ADR-007 destine à se
séparer : Urim s'installe seul, `mission` vit dans le Church OS. Ce qui vaut d'être partagé
est **l'invite système**, et elle l'est — recopiée à l'identique.
"""

from __future__ import annotations

import asyncio
import json
import re

from app.contexts.urim.application.ports import NullVerseResolver, PlanSuggestion
from app.contexts.urim.engine.state import AxisGloss, PassageSuggestion, Reference
from app.core.config import Settings
from app.core.logging import get_logger

_logger = get_logger("urim.mistral")

#: 🐛 **Un appel sans délai maximum a figé une préparation 35 minutes.** Mesuré le 2026-08-14 :
#: résolveur construit à 15:35:44, réponse du modèle à 16:10:35, un seul appel entre les deux.
#:
#: Le pire n'est pas l'attente, c'est qu'elle est **invisible** : tout ce fichier est bâti sur
#: « une panne du modèle n'est jamais une panne d'Urim », et le repli déterministe ne se
#: déclenche que sur une erreur. Un appel qui **pend** n'échoue pas — il attend, et le pasteur
#: attend avec lui. La garde manquait exactement là où le reste était prévu.
#:
#: La valeur est large : les appels mesurés tiennent en 2 à 8 secondes, et le premier d'un
#: processus coûte le chargement de l'index, pas le réseau. Quarante-cinq secondes laissent
#: passer une lenteur réelle et coupent une connexion morte.
#:
#: ⚠️ Le délai est posé **ici** et non dans le SDK : `Mistral.__init__` expose `(*args,
#: **kwargs)`, on ne peut pas vérifier ce qu'il accepte, et le cap doit couvrir ses éventuelles
#: reprises internes autant que l'appel lui-même.
DELAI_MODELE = 45

#: Reprise de M9-1 — la contrainte « jamais le texte » est dans l'invite.
#:
#: ⚠️ **Le modèle RETROUVE un passage désigné ; il n'en CHOISIT jamais un pour un sujet.**
#:
#: Ce sont deux questions différentes, et l'invite de `mission` ne distinguait qu'implicitement.
#: « parler de l'espérance aux familles en deuil » recevait 1 Thessaloniciens 4:13 — une réponse
#: serviable, et exactement le proof-texting contre lequel Urim est bâti : le pasteur repartait
#: avec un verset qu'il n'avait pas demandé, et les dix loci ne s'ouvraient jamais.
#:
#: La règle du produit tient en une ligne : *on croise d'abord si c'est un verset ; ce n'est
#: qu'ensuite, quand ça n'en est pas un, que l'intention s'analyse pour orienter le pasteur.*
#: Un thème qui reçoit un verset court-circuite ce « ensuite ». D'où `found=false` obligatoire.
_SYSTEME_REFERENCE = (
    "Tu es un assistant biblique. On te donne une saisie approximative, mal orthographiée ou "
    "décrite de mémoire. Ta SEULE tâche est de retrouver le passage que la saisie DÉSIGNE : "
    "une citation rapportée de mémoire, une scène racontée, un personnage nommé, un épisode. "
    "Identifie UNIQUEMENT la référence (livre, chapitre, verset) dans la Bible Louis Segond. "
    "Donne le nom du livre en français (ex. Jean, Psaumes, Ésaïe, 1 Corinthiens). Ne fournis "
    "JAMAIS le texte du verset : seulement la référence. "
    "INTERDICTION ABSOLUE : si la saisie exprime un THÈME, un SUJET, une INTENTION de "
    "prédication ou une opinion — 'parler de l'espérance aux familles en deuil', 'l'amour "
    "fraternel a disparu', 'je veux prêcher sur le pardon' — tu renvoies found=false, MÊME SI "
    "tu connais un passage qui conviendrait. Choisir un texte pour un sujet n'est pas ta tâche. "
    "Réponds par un objet JSON avec exactement les clés : found (booléen), book (chaîne), "
    "chapter (entier), verse (entier). Dans le doute, renvoie found=false."
)

#: ⚠️ L'invite dit **l'effet**, jamais l'état de celui qui écrit (S10, S37). « Formulation à
#: forte charge » se conteste ; « vous êtes dans la plainte » est un diagnostic, et le produit
#: l'interdit. Le modèle ne nomme donc que des marques de forme, jamais des sentiments.
_SYSTEME_RISQUE = (
    "Tu analyses la formulation d'un pasteur qui prépare une prédication. Tu ne diagnostiques "
    "JAMAIS son état intérieur et tu ne nommes aucun sentiment. Tu relèves uniquement des "
    "marques de FORME qui appellent des garde-fous : 'charge_forte' (formulation très "
    "affirmative ou émotionnelle), 'accusation' (la phrase met en cause l'assemblée ou "
    "quelqu'un), 'intention_persuasive' (le pasteur annonce vouloir obtenir un comportement). "
    "Réponds par un objet JSON : {\"flags\": [...]} avec zéro, une ou plusieurs de ces trois "
    "valeurs exactement. Aucune autre valeur, aucun commentaire."
)


#: Les dix loci, tels qu'ils sont en base. Le modèle **annote**, il n'écarte pas : l'invite ne
#: lui demande donc pas de classer ni de choisir, seulement de dire lesquels la formulation
#: touche. Ce qu'il oublie reste offert au pasteur, ce qu'il ajoute à tort reste une phrase.
_SYSTEME_AXES = (
    "Tu analyses l'intention de prédication d'un pasteur. Dis quels loci de la dogmatique "
    "classique cette formulation TOUCHE, parmi exactement : theologie_propre, christologie, "
    "pneumatologie, anthropologie, hamartiologie, soteriologie, ecclesiologie, angelologie, "
    "demonologie, eschatologie. "
    "Une intention en touche souvent plusieurs — « trop de malades malgré les prières » touche "
    "la théologie propre et l'anthropologie. "
    "Dès qu'un SUJET est identifiable, rattache-le, même si la phrase est inachevée ou "
    "maladroite : « je veux faire un culte sur l'adultère dans » touche l'hamartiologie et "
    "l'anthropologie, et une phrase coupée reste une intention claire. Ne renvoie une liste "
    "vide QUE dans deux cas. Le premier : aucun sujet n'est discernable — une salutation, un "
    "mot isolé ambigu, une suite de touches. Le second : la saisie n'a AUCUN rapport avec "
    "l'Écriture, la prédication ou la vie d'une assemblée — un exercice scolaire, une recette, "
    "du code, une question médicale ou technique. Ces deux cas se distinguent des saisies "
    "maladroites : une phrase bancale, tronquée ou mal orthographiée qui parle de Dieu, de la "
    "foi, de l'Église ou d'un texte biblique doit TOUJOURS être rattachée. Dans le doute, "
    "rattache. "
    "Pour CHAQUE locus retenu, donne aussi : un TITRE de 2 à 5 mots, dans la langue du "
    "pasteur et non celle de l'école — pour 'on prie pour les malades et rien ne change', "
    "theologie_propre se dit « La prière sans réponse » et anthropologie « La souffrance du "
    "croyant » ; et une GLOSE d'une demi-phrase qui dit ce que cet angle ouvrirait, par "
    "exemple « Ce que devient la foi quand rien ne vient ». "
    "Le titre nomme un ANGLE DE PRÉDICATION, jamais l'état de celui qui écrit : « La prière "
    "sans réponse » se prêche, « Votre découragement » est un diagnostic et c'est interdit. "
    'Réponds par un objet JSON : {"loci": [{"code": "...", "titre": "...", "glose": "..."}]} '
    "avec zéro, un ou plusieurs de ces codes exactement. Aucun autre code."
)

#: ⚠️ **Plusieurs passages, jamais un seul** — c'est la différence avec `_SYSTEME_REFERENCE`.
#:
#: Là-bas, le modèle a interdiction de proposer un texte pour un sujet : il rendrait UNE
#: référence que le moteur poserait comme résolue, et la question serait close avant d'être
#: ouverte. Ici il en rend quatre à six, elles deviennent des options, et le pasteur tranche.
#: Le pipeline reprend ensuite entier — pesées, mises en garde, textes qui résistent.
#:
#: La diversité demandée n'est pas cosmétique : quatre passages du même auteur sur le même
#: ton confirmeraient une seule lecture, ce qui reviendrait à n'en proposer qu'une.
_SYSTEME_PASSAGES = (
    "Tu es bibliste. On te donne le sujet ou la formulation d'un pasteur qui prépare une "
    "prédication. Propose 4 à 6 passages de la Bible Louis Segond qui TRAITENT ce sujet — pas "
    "des versets isolés qui contiennent le mot, mais des unités qui en parlent vraiment. "
    "EXIGENCE DE DIVERSITÉ : varie les livres, et l'Ancien et le Nouveau Testament quand le "
    "sujet s'y prête. Si un passage COMPLIQUE le sujet au lieu de le confirmer, propose-le "
    "aussi — c'est précieux. "
    "Donne le nom du livre en français (Jean, Psaumes, Ésaïe, 1 Corinthiens) et des bornes "
    "réelles. Ne fournis JAMAIS le texte : seulement la référence et une phrase disant ce que "
    "ce passage apporte au sujet. "
    "RENVOIE UNE LISTE VIDE si la saisie n'a AUCUN rapport avec l'Écriture, la prédication ou "
    "la vie d'une assemblée — un exercice scolaire, une recette, du code, une question "
    "médicale ou technique. Tu n'as pas à trouver un verset pour tout sujet. En revanche une "
    "saisie bancale, tronquée ou mal orthographiée qui parle de Dieu, de la foi, de l'Église "
    "ou d'un fait biblique — une coutume, un personnage, un objet du texte — appelle des "
    "passages comme les autres. Dans le doute, propose. "
    'Réponds par un objet JSON : {"passages": [{"livre": "...", "chapitre": 13, "debut": 1, '
    '"fin": 13, "motif": "..."}]}'
)

#: L'aiguilleur — **il classe, il ne répond jamais**.
#:
#: ⚠️ Trois choses qu'il ne voit pas, et c'est délibéré :
#:
#: **L'ouverture.** Au premier message le détecteur d'entrée fait mieux — il croise sur les
#: 31 170 versets, lit la notation du pasteur (`Hb 2v29`) et recale les noms de livres longs.
#: Un modèle qui trancherait « référence ou intention ? » serait moins fiable que ce qui est là.
#:
#: **Les réponses à une question posée.** « Ecclésiologie », « L'unité », « Expositif » sont des
#: *liaisons* vers une option déjà offerte, résolues par comparaison de chaînes avant tout appel.
#: L'aiguilleur ne les voit jamais — il se tromperait, « Ecclésiologie » ressemblant furieusement
#: à un sujet de prédication.
#:
#: **L'état.** Il ne reçoit que le texte. « Quel plan je peux tenir ? » posé avant qu'un texte
#: soit résolu part quand même en `interroger_travail`, et le répondeur dit la vérité — *il faut
#: d'abord un texte*. Aveugle, il reste une fonction pure : testable hors rejeu, et il ne reçoit
#: aucune confidence sur l'assemblée qu'il n'aurait pas besoin de connaître.
#:
#: ⚠️ **Le vocabulaire fermé est un clapet anti-retour.** Le modèle n'a aucun canal de sortie en
#: prose : rien de ce que le pasteur confie ne peut ressortir par lui. C'est structurel, pas une
#: politique.
_SYSTEME_AIGUILLAGE = (
    "Un pasteur prépare une prédication et vient d'écrire un message. Ta SEULE tâche est de "
    "dire ce qu'il veut, en choisissant EXACTEMENT un code parmi les sept suivants. Tu ne "
    "réponds jamais à sa question, tu ne commentes rien, tu ne produis aucune prose.\n"
    "- preciser : il corrige la façon dont on a lu sa saisie ('ce n'est pas ça', 'ce n'est pas "
    "une citation', 'c'est mon sujet', 'non je parlais du chapitre entier').\n"
    "- interroger_texte : il pose une question SUR LE TEXTE BIBLIQUE ou ce qui l'entoure — le "
    "sens d'un mot, l'original grec ou hébreu, pourquoi un passage commence ou finit là, un "
    "usage historique, une coutume, un personnage. MÊME si la réponse est incertaine ou si "
    "elle porte sur le monde antique plutôt que sur les mots.\n"
    "- interroger_travail : il pose une question SUR SA PROPRE PRÉPARATION — quel plan est "
    "tenable, ce qui résiste à son axe, ce qu'il a déjà choisi, où il en est.\n"
    "- demander_production : il demande qu'on lui FABRIQUE quelque chose — un thème, une mise "
    "en forme, un document, des diapositives.\n"
    "- changer_de_sujet : il abandonne le texte en cours pour un autre sujet de prédication.\n"
    "- hors_champ : il S'ADRESSE BIEN À TOI et on comprend sa demande, mais ce n'est pas ce que "
    "fait un atelier de préparation. Deux formes : un CONSEIL sur des personnes ou sur son "
    "assemblée (comment annoncer, que faire d'un membre, comment se sentir), et une demande "
    "qui te prend pour quelqu'un ('prie pour moi', 'tu penses quoi de moi').\n"
    "- indechiffrable : le message NE T'EST PAS ADRESSÉ, ou ne porte aucune demande. Trois "
    "formes : une parole captée par un micro resté ouvert et qui parle de tout autre chose "
    "qu'une prédication (la vie courante, un bout de conversation) ; des mots sans suite ou un "
    "fragment interrompu ; un acquiescement seul ('oui', 'ok').\n"
    "LE PARTAGE ENTRE LES DEUX N'EST PAS « ai-je compris ? » MAIS « me parle-t-il ? ». Une "
    "phrase parfaitement claire sur une voiture à réparer est indechiffrable : elle a atterri "
    "là par accident. 'Prie pour moi' est hors_champ : il te parle, et on ne sait pas répondre.\n"
    "DISTINCTION IMPORTANTE : une question sur ce que portaient les esclaves, sur une coutume "
    "ou sur un mot est 'interroger_texte' même si le corpus ne sait pas y répondre — c'est le "
    "répondeur qui dira ce qu'il a. 'hors_champ' est réservé aux conseils sur des PERSONNES.\n"
    'Réponds par un objet JSON : {"intention": "..."} avec exactement un de ces sept codes.'
)

#: ⚠️ **Fermé.** Un code hors liste est jeté à la source — même règle que `_LOCI_CONNUS`.
INTENTIONS_CONNUES = frozenset({
    "preciser", "interroger_texte", "interroger_travail",
    "demander_production", "changer_de_sujet", "hors_champ", "indechiffrable",
})

_LOCI_CONNUS = frozenset({
    "theologie_propre", "christologie", "pneumatologie", "anthropologie", "hamartiologie",
    "soteriologie", "ecclesiologie", "angelologie", "demonologie", "eschatologie",
})


def _reference_depuis(contenu: str) -> Reference | None:
    """Le JSON du modèle → une `Reference`, ou rien. **Aucune confiance accordée à la forme.**"""
    bloc = re.search(r"\{.*\}", contenu, re.S)
    if bloc is None:
        return None
    try:
        donnees = json.loads(bloc.group(0))
    except json.JSONDecodeError:
        return None
    if not donnees.get("found"):
        return None
    livre, chapitre, verset = (
        donnees.get("book"), donnees.get("chapter"), donnees.get("verse")
    )
    if not isinstance(livre, str) or not isinstance(chapitre, int):
        return None
    return Reference(livre.strip(), chapitre, verset if isinstance(verset, int) else None)


#: **La seule invite d'Urim qui produise de la prose** — et toutes ses contraintes sont là.
#:
#: Elle n'existe que parce que le pasteur la demande, point par point, dans son atelier. Ce
#: qu'elle rend n'atteint aucun document : le livrable n'imprime que ce que le pasteur a écrit
#: ou repris. C'est le patron du dépôt — *l'IA propose, l'homme dispose*.
#:
#: Quatre interdits, et chacun répare une faute qu'on aurait faite :
#:
#: 1. **aucun verset qui ne soit dans le texte fourni** — sinon l'invite devient un moteur de
#:    proof-texting, ce contre quoi Urim entier est bâti ;
#: 2. **aucune affirmation historique ou culturelle** — « chez les Hébreux les esclaves allaient
#:    pieds nus » se dit bien et ne se vérifie pas ; c'est la règle des realia ;
#: 3. **du français simple** — une note de préparation n'est pas un article de revue, et le
#:    pasteur ne doit pas traduire son propre travail pour s'en servir ;
#: 4. **court** — quelques phrases. Un paragraphe long se recopie ; trois phrases se retravaillent.
_SYSTEME_ARTICULATION = (
    "Tu aides un pasteur à développer UN point de son plan de prédication. On te donne : son "
    "point tel qu'il l'a écrit, la référence du passage qu'il prêche, le texte de ce "
    "passage, et le texte des autres passages qu'il cite dans son point. "
    "Ta tâche : proposer quelques phrases qui expliquent et articulent SON point à partir du "
    "texte fourni, puis une phrase de transition vers le point suivant s'il y en a un. "
    "INTERDICTIONS ABSOLUES : "
    "(1) n'utilise AUCUN contenu biblique qui ne soit pas dans les textes fournis — ni "
    "verset, ni référence, ni détail que tu croirais connaître : si le point mentionne un "
    "passage dont le texte n'est pas donné, tu n'en dis rien ; "
    "(2) n'affirme aucun fait historique, culturel ou linguistique — pas de 'chez les Hébreux', "
    "pas d'étymologie, pas de coutume ; "
    "(3) n'écris pas le sermon : tu développes SON point, tu n'en ajoutes pas d'autre, et tu ne "
    "conclus pas à sa place ; "
    "(4) n'invente aucune illustration, aucune anecdote, aucun exemple de la vie courante — "
    "c'est ce que le pasteur apporte, et lui seul. "
    "STYLE : français simple et direct, comme on parle. Pas de vocabulaire savant. "
    "Six phrases au maximum pour le développement, une seule pour la transition. "
    "Réponds par un objet JSON avec exactement les clés : body (chaîne), transition (chaîne, "
    "vide s'il n'y a pas de point suivant)."
)


class MistralAssistant:
    """Le moteur IA — **les deux lectures du port dans un seul objet**.

    Elles doivent voyager ensemble : la fabrique rend un adaptateur, et le service lui demande
    tantôt une référence, tantôt des drapeaux. Deux classes séparées auraient laissé la moitié
    du contrat manquante — et le trou ne serait apparu qu'au moment où quelqu'un pose la clé.

    Import **paresseux** du SDK : dépendance optionnelle, comme `minio` pour S3."""

    def __init__(self, api_key: str, model: str) -> None:
        # Import **paresseux et tolérant** : le SDK v2 range le client sous `mistralai.client`,
        # v1 l'expose à la racine. `mission` le savait déjà ; j'avais écrit le mien de mémoire
        # et il échouait en silence — `mistral_sdk_absent` à chaque appel, sans rien casser,
        # donc invisible jusqu'à ce qu'on regarde le journal.
        try:
            from mistralai import Mistral
        except ImportError:
            from mistralai.client import Mistral

        self._client = Mistral(api_key=api_key)
        self._model = model
        #: ⚠️ **Le compteur qui distingue « il n'a rien répondu » de « il n'a pas pu répondre ».**
        #:
        #: Toute panne rend `None`, et chaque lecture le transforme en liste vide : un 429 est
        #: donc *identique* à un refus du modèle. Tant que rien ne persistait, c'était sans
        #: conséquence — le rejeu redemandait. Depuis le mémo des suggestions, une coupure d'une
        #: seconde figerait une préparation vide **pour toujours**.
        #:
        #: Monotone, donc juste sous `asyncio.gather` : l'appelant prend une photo avant, une
        #: après, et n'écrit son mémo que si le nombre n'a pas bougé.
        self.echecs = 0

    async def demander(self, systeme: str, texte: str, *, etiquette: str = "?") -> str | None:
        """Un appel, une invite. Toute panne rend `None` — jamais une exception qui remonte.

        Publique parce que la curation s'en sert : découper un chapitre en unités littéraires
        est un troisième usage, hors ligne celui-là, et il n'a pas à recopier ce transport.

        `etiquette` ne sert qu'au journal. Elle existe parce qu'on a longtemps raisonné sur le
        coût d'une ouverture sans jamais l'avoir mesuré : sans elle, la consommation est un
        total mensuel sur une facture, et on ne sait pas **quelle** invite le fabrique."""
        try:
            reponse = await asyncio.wait_for(
                self._client.chat.complete_async(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": systeme},
                        {"role": "user", "content": texte},
                    ],
                    response_format={"type": "json_object"},  # sortie JSON garantie
                    # ⚠️ **Zéro, parce qu'Urim est un moteur de rejeu.** « Le fils prodigue
                    # rentre chez son père » rendait Luc 15:20 une fois sur deux et rien
                    # l'autre fois : la même saisie n'ouvrait pas la même préparation. On ne
                    # stocke pas le raisonnement, seulement les décisions — encore faut-il que
                    # la décision soit reproductible, sinon la trace ment sur ce que le
                    # pasteur a vu.
                    temperature=0,
                ),
                DELAI_MODELE,
            )
            usage = getattr(reponse, "usage", None)
            if usage is not None:
                _logger.info(
                    "urim_mistral_usage",
                    invite=etiquette,
                    model=self._model,
                    entree=getattr(usage, "prompt_tokens", None),
                    sortie=getattr(usage, "completion_tokens", None),
                )
            return reponse.choices[0].message.content or ""
        except TimeoutError:
            # ⚠️ **Nommée à part, jamais confondue avec une panne ordinaire.** Ce mode-là était
            # invisible : il ne produit ni erreur ni journal, seulement une requête qui ne
            # revient pas. Le distinguer est la seule façon de le voir revenir.
            self.echecs += 1
            _logger.warning(
                "mistral_delai_depasse", invite=etiquette, secondes=DELAI_MODELE
            )
            return None
        except Exception as erreur:  # pragma: no cover - réseau
            # ⚠️ **Une panne du modèle n'est jamais une panne d'Urim.** Le résolveur
            # déterministe reprend, et le pasteur ne voit pas la différence.
            self.echecs += 1
            _logger.warning("mistral_echec", error=str(erreur))
            return None

    async def articuler(
        self, *, point: str, reference: str, texte: str, suivant: str, appuis: str = ""
    ) -> PlanSuggestion | None:
        """Développer un point — **la seule sortie en prose du dépôt**, et elle est demandée.

        Rend `None` sur toute panne : l'atelier continue, le pasteur écrit son point comme il
        l'a toujours fait. Un modèle absent n'est pas un mode dégradé (§10)."""
        demande = "\n".join((
            f"Point du pasteur : {point}",
            f"Passage prêché : {reference}",
            f"Texte du passage : {texte}",
            f"Textes cités dans le point : {appuis or '(aucun)'}",
            f"Point suivant : {suivant or '(aucun)'}",
        ))
        contenu = await self.demander(
            _SYSTEME_ARTICULATION, demande, etiquette="articulation"
        )
        if not contenu:
            return None
        try:
            lu = json.loads(contenu)
        except json.JSONDecodeError:
            return None
        corps = (lu.get("body") or "").strip()
        if not corps:
            return None
        return PlanSuggestion(
            body=corps,
            transition=(lu.get("transition") or "").strip(),
            model=self._model,
        )

    async def resolve(self, text: str) -> Reference | None:
        contenu = await self.demander(_SYSTEME_REFERENCE, text, etiquette="reference")
        return _reference_depuis(contenu) if contenu else None

    async def axes(self, text: str) -> tuple[AxisGloss, ...]:
        """Les loci que l'intention touche, **dits dans la langue du pasteur**.

        L'étage réunit ce retour avec les dix loci qu'il affiche de toute façon. Un oubli du
        modèle laisse une option moins bien motivée ; un titre mal trouvé laisse une phrase
        contestable au-dessus du bon locus. Ni l'un ni l'autre ne retire au pasteur ce qu'il
        pouvait choisir — et c'est la seule raison pour laquelle on laisse un modèle nommer
        quoi que ce soit sur cet écran."""
        contenu = await self.demander(_SYSTEME_AXES, text, etiquette="axes")
        if not contenu:
            return ()
        bloc = re.search(r"\{.*\}", contenu, re.S)
        if bloc is None:
            return ()
        try:
            rendus = json.loads(bloc.group(0)).get("loci", [])
        except json.JSONDecodeError:
            return ()
        if not isinstance(rendus, list):
            return ()

        gloses: list[AxisGloss] = []
        vus: set[str] = set()
        for rendu in rendus:
            if not isinstance(rendu, dict):
                continue
            code = rendu.get("code")
            if code not in _LOCI_CONNUS or code in vus:
                continue
            titre = (rendu.get("titre") or "").strip()
            glose = (rendu.get("glose") or "").strip()
            # ⚠️ **Un titre manquant ne fait pas perdre le locus.** Je jetais l'entrée entière,
            # et « l'amour fraternel n'existe plus dans l'église » perdait son ecclésiologie —
            # une annotation juste, effacée par une habillage absent. L'étage retombe sur le
            # libellé du locus : moins joli, aussi vrai.
            vus.add(code)
            gloses.append(AxisGloss(code, titre[:80], glose[:200]))
        return tuple(gloses)

    async def passages(self, text: str) -> tuple[PassageSuggestion, ...]:
        """Les passages qui **traitent** le sujet — plusieurs, jamais un.

        Un seul serait une résolution déguisée. La pluralité n'est donc pas une commodité
        d'affichage : c'est ce qui maintient la décision du côté du pasteur."""
        contenu = await self.demander(_SYSTEME_PASSAGES, text, etiquette="passages")
        if not contenu:
            return ()
        bloc = re.search(r"\{.*\}", contenu, re.S)
        if bloc is None:
            return ()
        try:
            rendus = json.loads(bloc.group(0)).get("passages", [])
        except json.JSONDecodeError:
            return ()
        if not isinstance(rendus, list):
            return ()

        proposes: list[PassageSuggestion] = []
        for rendu in rendus:
            if not isinstance(rendu, dict):
                continue
            livre, chapitre = rendu.get("livre"), rendu.get("chapitre")
            if not isinstance(livre, str) or not isinstance(chapitre, int):
                continue
            debut, fin = rendu.get("debut"), rendu.get("fin")
            motif = (rendu.get("motif") or "").strip()
            proposes.append(PassageSuggestion(
                Reference(
                    livre.strip(),
                    chapitre,
                    debut if isinstance(debut, int) else None,
                    fin if isinstance(fin, int) and isinstance(debut, int) else None,
                ),
                motif[:300],
            ))

        # **Un seul passage rendu n'en est pas un** : il aurait l'autorité d'une résolution
        # sans en avoir passé les vérifications. On préfère ne rien proposer.
        return tuple(proposes) if len(proposes) > 1 else ()

    async def aiguiller(self, text: str) -> str | None:
        """Le tour du pasteur → **une intention**, ou rien.

        `None` n'est pas un échec silencieux : c'est un tour qu'on ne sait pas lire, et le
        répondeur le traitera comme `indechiffrable` — en le disant. Deviner serait pire, parce
        que les répondeurs sont déterministes : une intention mal aiguillée donne une réponse
        **hors sujet, jamais fausse**, et c'est ce qui rend l'aiguillage probabiliste acceptable
        devant eux."""
        contenu = await self.demander(_SYSTEME_AIGUILLAGE, text, etiquette="aiguillage")
        if not contenu:
            return None
        bloc = re.search(r"\{.*\}", contenu, re.S)
        if bloc is None:
            return None
        try:
            rendu = json.loads(bloc.group(0)).get("intention")
        except json.JSONDecodeError:
            return None
        return rendu if rendu in INTENTIONS_CONNUES else None

    async def lever(self, text: str) -> tuple[str, ...]:
        """Les drapeaux de risque — **des marques de forme, jamais un sentiment**."""
        return await self._codes(
            _SYSTEME_RISQUE, text, "flags",
            frozenset({"charge_forte", "accusation", "intention_persuasive"}),
            etiquette="risque",
        )

    async def _codes(
        self,
        systeme: str,
        texte: str,
        cle: str,
        connus: frozenset[str],
        *,
        etiquette: str = "?",
    ) -> tuple[str, ...]:
        """Une liste de codes d'un vocabulaire **fermé** — le tronc commun d'`axes` et `lever`.

        Le filtre sur `connus` n'est pas une politesse : sans lui, un code inventé par le
        modèle traverserait jusqu'à une clé étrangère ou à un `if` qui ne le reconnaît pas, et
        échouerait loin d'ici. On coupe au plus près de la source."""
        contenu = await self.demander(systeme, texte, etiquette=etiquette)
        if not contenu:
            return ()
        bloc = re.search(r"\{.*\}", contenu, re.S)
        if bloc is None:
            return ()
        try:
            rendus = json.loads(bloc.group(0)).get(cle, [])
        except json.JSONDecodeError:
            return ()
        if not isinstance(rendus, list):
            return ()
        return tuple(c for c in rendus if c in connus)


def build_verse_resolver(settings: Settings):
    """Mistral si la clé est posée, sinon le silence — patron OtpSender/S3 du dépôt.

    Bâti et câblé ; il s'active par configuration, sans toucher au code."""
    if settings.mistral_api_key:
        _logger.info("urim_resolveur_mistral", model=settings.mistral_model)
        return MistralAssistant(settings.mistral_api_key, settings.mistral_model)
    _logger.info("urim_resolveur_absent")
    return NullVerseResolver()
