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
        "name": "system",
        "description": "Santé du service — la seule route qui ne demande rien à personne.",
    },
    {
        "name": "auth",
        "description": (
            "Entrer. Deux profils, deux identifiants : le membre par téléphone + code secret, "
            "le propriétaire par e-mail + mot de passe. **L'OTP vérifie l'appareil, jamais "
            "l'identité** — un appareil de confiance ne se redemande pas."
        ),
    },
    {
        "name": "account",
        "description": "Changer son numéro ou son code secret — chaque fois confirmé par un OTP.",
    },
    {
        "name": "iam",
        "description": (
            "Appartenir. Rejoindre une église par code, lire ses appartenances et ses rôles, "
            "poser sa date de naissance et **choisir qui la voit**."
        ),
    },
    {
        "name": "groups",
        "description": (
            "Rejoindre un groupe par lien d'invitation, ou le quitter. L'arbre des groupes et "
            "les nominations se gèrent au backoffice."
        ),
    },
    {
        "name": "attendance",
        "description": (
            "La présence, à **deux voix** : le responsable pointe, ou le membre saisit le code "
            "de séance affiché. On n'enregistre que des présences — l'absence est *déduite*, "
            "jamais écrite. Et la dignité de prévenir : déclarer une période d'absence avec un "
            "tag, sans avoir à s'expliquer."
        ),
    },
    {
        "name": "announcements",
        "description": (
            "Le fil de l'église. Le **type** de l'annonce pilote sa couleur, ses emojis et son "
            "intention ; on réagit, on s'engage, et le sujet d'une annonce qui le nomme doit y "
            "consentir."
        ),
    },
    {
        "name": "appointments",
        "description": (
            "L'agenda du pasteur, gardé par la secrétaire. Le membre demande avec un sujet "
            "**confidentiel** ; on confirme, ou l'on décline toujours avec un mot."
        ),
    },
    {
        "name": "events",
        "description": (
            "Le happening publié — date, lieu, géo. Tout membre publie pour son église ; les "
            "portées élargies s'ouvrent avec le compte Business. Le tableau de rayonnement dit "
            "la portée et les présents confirmés."
        ),
    },
    {
        "name": "mission",
        "description": (
            "La main tendue vers l'extérieur : un lien d'invitation qui s'ouvre sur une carte, "
            "un chercheur qu'on accompagne, puis qu'on intègre. **L'IA retrouve la référence du "
            "verset ; c'est la Bible qui en donne le texte.**"
        ),
    },
    {
        "name": "sermons",
        "description": (
            "La Parole après dimanche : le pasteur dépose, l'IA résume en capsules publiées au "
            "fil, et un compagnon privé accompagne le membre. ⚠️ **Contexte en cours de retrait** "
            "— Urim en reprend la production (voir `docs/Plan_Urim_Producteur.md`)."
        ),
    },
    {
        "name": "urim",
        "description": (
            "L'atelier du pasteur **avant** le dimanche : il entre par une référence, une "
            "citation approximative ou une simple conviction, et huit étages l'accompagnent "
            "jusqu'au texte — unité littéraire motivée, contexte sourcé, axes doctrinaux portés "
            "ou **résistants**, mises en garde, couple plan x matière dont les refus sont "
            "expliqués. Le moteur ne choisit jamais à sa place : quand il hésite, il rend la "
            "main avec ses options et ses motifs. ⚠️ Une ambiguïté revient en **200** avec son "
            "`outcome`, jamais en 4xx — c'est le raisonnement qui est le produit, pas la réponse."
        ),
    },
    {
        "name": "watch",
        "description": (
            "La veille fraternelle, côté membre **et** côté responsable. Le membre signale une "
            "inquiétude, déclare un geste posé pour quelqu'un, indique par qui on peut le "
            "rejoindre, ou demande qu'on cesse de le contacter. Le responsable reçoit ses cas, "
            "relit avant d'appeler, et les ferme sur une issue **choisie**."
        ),
    },
    {
        "name": "notifications",
        "description": "Enregistrer et oublier ses appareils — le socle des notifications push.",
    },
    {
        "name": "billing",
        "description": (
            "Le compte Business d'une **personne**, activé par carte prépayée Visa et non "
            "facturé. Il ouvre les portées élargies d'un événement."
        ),
    },
    {"name": "media", "description": "Téléverser une image — corps brut, sans multipart."},
    # --- Backoffice : ce que l'église administre --------------------------------------------
    {"name": "backoffice:auth", "description": "Session backoffice par cookie, appareil vérifié."},
    {
        "name": "backoffice:tenant",
        "description": (
            "L'église elle-même : profil, annexes, famille, et la succession du siège de "
            "propriétaire. Le provisionnement est un acte de la Plateforme."
        ),
    },
    {
        "name": "backoffice:iam",
        "description": (
            "Enrôler, attribuer et révoquer des rôles, faire évoluer un statut — et le "
            "**transfert de membre** entre églises, que la destination initie et que la source "
            "accepte."
        ),
    },
    {
        "name": "backoffice:groups",
        "description": (
            "L'arbre des groupes : créer, nommer des responsables, **multiplier** une cellule "
            "en déplaçant des membres, et jusqu'à émanciper un groupe en église autonome."
        ),
    },
    {
        "name": "backoffice:attendance",
        "description": (
            "Les lectures pastorales : tableau de bord, liste « à interpeller », tendance d'un "
            "groupe, trajectoire d'un membre, arbre de multiplication."
        ),
    },
    {
        "name": "backoffice:watch",
        "description": (
            "Le **rodage** : voir ce que Dorea aurait signalé pendant que l'église observe, puis "
            "décider de la laisser parler. Et arbitrer ce que la mesure suggère de changer."
        ),
    },
    {
        "name": "backoffice:announcements",
        "description": "L'archive du fil, et la publication depuis le poste de l'église.",
    },
    {
        "name": "backoffice:appointments",
        "description": (
            "La file des demandes, l'agenda des créneaux confirmés, les disponibilités "
            "récurrentes d'un pasteur."
        ),
    },
    {"name": "backoffice:onboarding", "description": "Valider ou rejeter une demande d'église."},
    {"name": "backoffice:media", "description": "Téléverser une image depuis le backoffice."},
    # --- Plateforme : les cadences, pas des humains ------------------------------------------
    {
        "name": "platform:urim",
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
        "name": "platform:watch",
        "description": (
            "**Cron.** La passe de veille (échéances dues, escalades, garde-fous), la boucle "
            "froide qui mesure les seuils, et le résumé aux églises en rodage."
        ),
    },
    {
        "name": "platform:notifications",
        "description": "**Cron.** Dispatcher les notifications planifiées arrivées à échéance.",
    },
    {
        "name": "platform:announcements",
        "description": "Publier une annonce Dorea vers toutes les églises.",
    },
    {
        "name": "platform:events",
        "description": "Modération : la file des événements signalés, et leur retrait.",
    },
    # --- Publique : le code est l'autorisation ------------------------------------------------
    {
        "name": "onboarding",
        "description": (
            "Sans authentification. Un aspirant propriétaire dépose sa demande, vérifie son "
            "e-mail, et suit l'état de sa candidature."
        ),
    },
    {
        "name": "mission:public",
        "description": (
            "Sans authentification — **le code de la carte est l'entrée**. Voir l'invitation, "
            "y répondre en laissant un contact, ou simplement réagir."
        ),
    },
    {
        "name": "events:public",
        "description": (
            "La carte d'un événement, partageable hors de Dorea. Ce qui est rationné est la "
            "notification, jamais la diffusion."
        ),
    },
]
