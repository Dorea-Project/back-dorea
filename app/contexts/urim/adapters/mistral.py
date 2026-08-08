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

import json
import re

from app.contexts.urim.application.ports import NullVerseResolver
from app.contexts.urim.engine.state import Reference
from app.core.config import Settings
from app.core.logging import get_logger

_logger = get_logger("urim.mistral")

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
    "la théologie propre et l'anthropologie. N'en invente pas : si la formulation est trop "
    "courte ou trop vague pour rattacher quoi que ce soit, renvoie une liste vide. "
    "Tu ne diagnostiques JAMAIS l'état intérieur du pasteur et tu ne nommes aucun sentiment. "
    'Réponds par un objet JSON : {"loci": [...]} avec zéro, un ou plusieurs de ces codes '
    "exactement. Aucun autre code, aucun commentaire."
)

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

    async def demander(self, systeme: str, texte: str) -> str | None:
        """Un appel, une invite. Toute panne rend `None` — jamais une exception qui remonte.

        Publique parce que la curation s'en sert : découper un chapitre en unités littéraires
        est un troisième usage, hors ligne celui-là, et il n'a pas à recopier ce transport."""
        try:
            reponse = await self._client.chat.complete_async(
                model=self._model,
                messages=[
                    {"role": "system", "content": systeme},
                    {"role": "user", "content": texte},
                ],
                response_format={"type": "json_object"},  # sortie JSON garantie
                # ⚠️ **Zéro, parce qu'Urim est un moteur de rejeu.** « Le fils prodigue rentre
                # chez son père » rendait Luc 15:20 une fois sur deux et rien l'autre fois : la
                # même saisie n'ouvrait pas la même préparation. On ne stocke pas le
                # raisonnement, seulement les décisions — encore faut-il que la décision soit
                # reproductible, sinon la trace ment sur ce que le pasteur a vu.
                temperature=0,
            )
            return reponse.choices[0].message.content or ""
        except Exception as erreur:  # pragma: no cover - réseau
            # ⚠️ **Une panne du modèle n'est jamais une panne d'Urim.** Le résolveur
            # déterministe reprend, et le pasteur ne voit pas la différence.
            _logger.warning("mistral_echec", error=str(erreur))
            return None

    async def resolve(self, text: str) -> Reference | None:
        contenu = await self.demander(_SYSTEME_REFERENCE, text)
        return _reference_depuis(contenu) if contenu else None

    async def axes(self, text: str) -> tuple[str, ...]:
        """Les loci que l'intention touche — **annotation, jamais filtre**.

        L'étage réunit ce retour avec les dix loci qu'il affiche de toute façon. Un oubli du
        modèle laisse une option moins bien motivée ; un ajout erroné laisse une phrase de
        trop. Ni l'un ni l'autre ne retire au pasteur ce qu'il pouvait choisir."""
        return await self._codes(_SYSTEME_AXES, text, "loci", _LOCI_CONNUS)

    async def lever(self, text: str) -> tuple[str, ...]:
        """Les drapeaux de risque — **des marques de forme, jamais un sentiment**."""
        return await self._codes(
            _SYSTEME_RISQUE, text, "flags",
            frozenset({"charge_forte", "accusation", "intention_persuasive"}),
        )

    async def _codes(
        self, systeme: str, texte: str, cle: str, connus: frozenset[str]
    ) -> tuple[str, ...]:
        """Une liste de codes d'un vocabulaire **fermé** — le tronc commun d'`axes` et `lever`.

        Le filtre sur `connus` n'est pas une politesse : sans lui, un code inventé par le
        modèle traverserait jusqu'à une clé étrangère ou à un `if` qui ne le reconnaît pas, et
        échouerait loin d'ici. On coupe au plus près de la source."""
        contenu = await self.demander(systeme, texte)
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
