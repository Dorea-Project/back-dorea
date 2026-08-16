"""Ce que Swagger raconte — la carte du produit, pas la liste des routes.

FastAPI documente déjà chaque route par son `summary` et sa docstring. Ce qui manquait est
l'**étage au-dessus** : trente-deux tags s'affichaient bruts, sans qu'aucun ne dise à quelle
surface il appartient, qui la garde, ni ce que le contexte fait dans le produit. Un intégrateur
qui ouvre `/docs` devait deviner que `platform:watch` est un cron et `mission:public` une page
sans authentification.

**L'ordre de `TAGS` est l'ordre d'affichage.** Il n'est pas alphabétique : il suit le parcours
réel — on entre par l'authentification, on appartient, on se réunit, on prend soin ; puis le
backoffice ; puis les crons ; puis ce qui est public. Une table des matières qui raconte
l'histoire du produit vaut mieux qu'un index.

**Une règle pour la suite** : tout contexte qui ouvre une route ajoute son tag ici, avec une
phrase qui dit *ce qu'il fait*, jamais *ce qu'il est techniquement*. Un tag sans description est
une route que personne d'extérieur ne saura appeler.
"""

from __future__ import annotations

#: Une ligne de tableau markdown ne se coupe pas — d'où la concaténation, qui garde les lignes
#: de code courtes sans casser le rendu.
_SURFACES = "\n".join(
    (
        "| Surface | Préfixe | Client | Ce qui autorise |",
        "| :-- | :-- | :-- | :-- |",
        "| **Mobile** | `/api/mobile` | application Flutter — le fidèle, le responsable"
        " | jetons + appareil de confiance |",
        "| **Backoffice** | `/api/backoffice` | PWA Next.js — propriétaire, pasteur, admin"
        " | cookie de session |",
        "| **Publique** | `/api` | aucun client authentifié"
        " | **le code est l'autorisation** — invitation, carte d'événement, onboarding |",
    )
)


DESCRIPTION = f"""
Backend monolithe de Dorea. Il possède le schéma et le fait évoluer.

### Trois surfaces, trois gardes

{_SURFACES}

Les routes sous `/api/backoffice/platform` ne sont pas destinées à un humain : ce sont les
**cadences** appelées par un ordonnanceur externe, gardées par un jeton de service.

### Deux conventions qui traversent tout le produit

**Ce qui est refusé l'est avec un motif.** Les erreurs de domaine portent un code stable
(`WATCH_…`, `URIM_…`) et une phrase lisible par un humain — jamais un statut nu.

**Le silence n'est jamais une donnée.** Aucune route n'expose « qui n'est pas venu », « qui n'a
pas répondu », « qui n'a pas réagi ». Ce que le produit sait, il le sait d'un acte que quelqu'un
a posé.
"""

#: Description par tag. L'ordre **est** l'ordre d'affichage dans Swagger.
TAGS: list[dict[str, str]] = [
    # --- Mobile : le parcours d'un membre ---------------------------------------------------
    {
        "name": "Système",
        "description": "Santé du service — la seule route qui ne demande rien à personne.",
    },
    {
        "name": "Membres · auth",
        "description": (
            "Entrer. Deux profils, deux identifiants : le membre par téléphone + code secret, "
            "le propriétaire par e-mail + mot de passe. **L'OTP vérifie l'appareil, jamais "
            "l'identité** — un appareil de confiance ne se redemande pas."
        ),
    },
    {
        "name": "Membres · account",
        "description": "Changer son numéro ou son code secret — chaque fois confirmé par un OTP.",
    },
    {
        "name": "Membres · iam",
        "description": (
            "Appartenir. Rejoindre une église par code, lire ses appartenances et ses rôles, "
            "poser sa date de naissance et **choisir qui la voit**."
        ),
    },
    {
        "name": "Membres · groups",
        "description": (
            "Rejoindre un groupe par lien d'invitation, ou le quitter. L'arbre des groupes et "
            "les nominations se gèrent au backoffice."
        ),
    },
    {
        "name": "Vie d'église · attendance",
        "description": (
            "La présence, à **deux voix** : le responsable pointe, ou le membre saisit le code "
            "de séance affiché. On n'enregistre que des présences — l'absence est *déduite*, "
            "jamais écrite. Et la dignité de prévenir : déclarer une période d'absence avec un "
            "tag, sans avoir à s'expliquer."
        ),
    },
    {
        "name": "Communication · announcements",
        "description": (
            "Le fil de l'église. Le **type** de l'annonce pilote sa couleur, ses emojis et son "
            "intention ; on réagit, on s'engage, et le sujet d'une annonce qui le nomme doit y "
            "consentir."
        ),
    },
    {
        "name": "Vie d'église · appointments",
        "description": (
            "L'agenda du pasteur, gardé par la secrétaire. Le membre demande avec un sujet "
            "**confidentiel** ; on confirme, ou l'on décline toujours avec un mot."
        ),
    },
    {
        "name": "Vie d'église · events",
        "description": (
            "Le happening publié — date, lieu, géo. Tout membre publie pour son église ; les "
            "portées élargies s'ouvrent avec le compte Business. Le tableau de rayonnement dit "
            "la portée et les présents confirmés."
        ),
    },
    {
        "name": "Vie d'église · mission",
        "description": (
            "La main tendue vers l'extérieur : un lien d'invitation qui s'ouvre sur une carte, "
            "un chercheur qu'on accompagne, puis qu'on intègre. **L'IA retrouve la référence du "
            "verset ; c'est la Bible qui en donne le texte.**"
        ),
    },
    {
        "name": "Vie d'église · sermons",
        "description": (
            "La Parole après dimanche : le pasteur dépose, l'IA résume en capsules publiées au "
            "fil, et un compagnon privé accompagne le membre. ⚠️ **Contexte en cours de retrait** "
            "— Urim en reprend la production (voir `docs/Plan_Urim_Producteur.md`)."
        ),
    },
    {
        "name": "Urim · préparation",
        "description": (
            "L'atelier du pasteur **avant** le dimanche. **Un seul champ, rien à cocher** : "
            "référence, citation ou intention ne sont pas des cases à remplir — le moteur les "
            "reconnaît en croisant la saisie avec les 31 170 versets, sur l'ordre des mots et "
            "non sur le vocabulaire. Puis huit étages l'accompagnent "
            "jusqu'au texte — unité littéraire motivée, contexte sourcé, axes doctrinaux portés "
            "ou **résistants**, mises en garde, couple plan x matière dont les refus sont "
            "expliqués. Le moteur ne choisit jamais à sa place : quand il hésite, il rend la "
            "main avec ses options et ses motifs. ⚠️ Une ambiguïté revient en **200** avec son "
            "`outcome`, jamais en 4xx — c'est le raisonnement qui est le produit, pas la réponse."
        ),
    },
    {
        "name": "Veille · watch",
        "description": (
            "La veille fraternelle, côté membre **et** côté responsable. Le membre signale une "
            "inquiétude, déclare un geste posé pour quelqu'un, indique par qui on peut le "
            "rejoindre, ou demande qu'on cesse de le contacter. Le responsable reçoit ses cas, "
            "relit avant d'appeler, et les ferme sur une issue **choisie**."
        ),
    },
    {
        "name": "Communication · notifications",
        "description": "Enregistrer et oublier ses appareils — le socle des notifications push.",
    },
    {
        "name": "Membres · billing",
        "description": (
            "Le compte Business d'une **personne**, activé par carte prépayée Visa et non "
            "facturé. Il ouvre les portées élargies d'un événement."
        ),
    },
    {
        "name": "Communication · media",
        "description": "Téléverser une image — corps brut, sans multipart.",
    },
    # --- Backoffice : ce que l'église administre --------------------------------------------
    {
        "name": "Membres · auth (backoffice)",
        "description": "Session backoffice par cookie, appareil vérifié.",
    },
    {
        "name": "Vie d'église · tenant (backoffice)",
        "description": (
            "L'église elle-même : profil, annexes, famille, et la succession du siège de "
            "propriétaire. Le provisionnement est un acte de la Plateforme."
        ),
    },
    {
        "name": "Membres · iam (backoffice)",
        "description": (
            "Enrôler, attribuer et révoquer des rôles, faire évoluer un statut — et le "
            "**transfert de membre** entre églises, que la destination initie et que la source "
            "accepte."
        ),
    },
    {
        "name": "Membres · groups (backoffice)",
        "description": (
            "L'arbre des groupes : créer, nommer des responsables, **multiplier** une cellule "
            "en déplaçant des membres, et jusqu'à émanciper un groupe en église autonome."
        ),
    },
    {
        "name": "Vie d'église · attendance (backoffice)",
        "description": (
            "Les lectures pastorales : tableau de bord, liste « à interpeller », tendance d'un "
            "groupe, trajectoire d'un membre, arbre de multiplication."
        ),
    },
    {
        "name": "Veille · watch (backoffice)",
        "description": (
            "Le **rodage** : voir ce que Dorea aurait signalé pendant que l'église observe, puis "
            "décider de la laisser parler. Et arbitrer ce que la mesure suggère de changer."
        ),
    },
    {
        "name": "Communication · announcements (backoffice)",
        "description": "L'archive du fil, et la publication depuis le poste de l'église.",
    },
    {
        "name": "Vie d'église · appointments (backoffice)",
        "description": (
            "La file des demandes, l'agenda des créneaux confirmés, les disponibilités "
            "récurrentes d'un pasteur."
        ),
    },
    {
        "name": "Vie d'église · onboarding (backoffice)",
        "description": "Valider ou rejeter une demande d'église.",
    },
    {
        "name": "Communication · media (backoffice)",
        "description": "Téléverser une image depuis le backoffice.",
    },
    # --- Plateforme : les cadences, pas des humains ------------------------------------------
    {
        "name": "Urim · curation (plateforme)",
        "description": (
            "**Curation du corpus.** L'unique surface où un humain signe ce qu'Urim dira aux "
            "pasteurs : bornes d'une unité littéraire et leur motif, pesées sur les dix loci, "
            "mises en garde, contexte sourcé, faisabilité homilétique. Gardée par le jeton "
            "Plateforme parce que le corpus est **global** — aucune table ne porte de "
            "`church_id`, et curer change ce que toutes les églises lisent. `/coverage` donne "
            "la seule mesure honnête de l'état d'Urim : la part de l'Écriture sur laquelle il "
            "a du relu à dire."
        ),
    },
    {
        "name": "Veille · watch (cron)",
        "description": (
            "**Cron.** La passe de veille (échéances dues, escalades, garde-fous), la boucle "
            "froide qui mesure les seuils, et le résumé aux églises en rodage."
        ),
    },
    {
        "name": "Communication · notifications (cron)",
        "description": "**Cron.** Dispatcher les notifications planifiées arrivées à échéance.",
    },
    {
        "name": "Communication · announcements (Dorea)",
        "description": "Publier une annonce Dorea vers toutes les églises.",
    },
    {
        "name": "Vie d'église · events (modération)",
        "description": "Modération : la file des événements signalés, et leur retrait.",
    },
    # --- Publique : le code est l'autorisation ------------------------------------------------
    {
        "name": "Vie d'église · onboarding (public)",
        "description": (
            "Sans authentification. Un aspirant propriétaire dépose sa demande, vérifie son "
            "e-mail, et suit l'état de sa candidature."
        ),
    },
    {
        "name": "Vie d'église · mission (public)",
        "description": (
            "Sans authentification — **le code de la carte est l'entrée**. Voir l'invitation, "
            "y répondre en laissant un contact, ou simplement réagir."
        ),
    },
    {
        "name": "Vie d'église · events (public)",
        "description": (
            "La carte d'un événement, partageable hors de Dorea. Ce qui est rationné est la "
            "notification, jamais la diffusion."
        ),
    },
    {
        "name": "Messagerie · webhooks (public)",
        "description": (
            "Ce que le fournisseur nous renvoie : accusés de réception et messages entrants. "
            "Appelées par un tiers, donc sans session — gardées par un secret partagé, faute "
            "de signature côté fournisseur. **Aucune décision de sécurité n'en dépend** : "
            "elles renseignent un journal d'acheminement et enregistrent les refus, elles "
            "n'ouvrent aucun accès et ne valident aucun code."
        ),
    },
]


#: Les **familles de produit**, dans leur ordre d'affichage.
#:
#: Swagger UI ne connaît pas les groupes de tags — `x-tagGroups` est une extension Redoc.
#: Le regroupement ne peut donc passer que par le **nom** et l'**ordre** : un tag préfixé
#: `Membres · `, `Vie d'église · `, `Communication · `, `Veille · ` ou `Urim · ` se lit comme
#: appartenant à sa gamme, et le tri
#: ci-dessous les rend contigus à l'écran.
#:
#: ⚠️ **`Finance` n'y figure pas, et c'est voulu.** Le contexte n'existe pas encore ; un tag
#: décrit sans route ferait échouer `test_aucune_description_ne_survit_a_ses_routes`. Le dépôt
#: s'interdit d'annoncer dans sa documentation une gamme qui ne sert rien — la ligne s'ajoutera
#: le jour où elle ouvrira sa première route, pas avant.
_FAMILLES = ("Système", "Membres", "Vie d'église", "Communication", "Veille", "Urim")


def _rang(tag: dict[str, str]) -> int:
    return next(
        (i for i, f in enumerate(_FAMILLES) if tag["name"].startswith(f)), len(_FAMILLES)
    )


# Tri **stable** : les familles se regroupent, et à l'intérieur de chacune l'ordre de
# déclaration est conservé — celui qui suit le parcours réel du produit plutôt que l'alphabet.
TAGS.sort(key=_rang)
