"""La **curation** de démonstration — huit unités littéraires et ce qu'on en a dit.

⚠️ **Le texte biblique n'est plus ici.** Il vient de `lsg_dataset_path` (LSG 1910
entière, partagée avec `mission`). Ce fichier ne contient que ce qu'un humain doit
**écrire** : les bornes d'une péricope et leur motif, les pesées doctrinales, les mises
en garde, le contexte, la faisabilité homilétique.

C'est la bonne frontière : le texte s'acquiert, la curation se relit. Confondre les deux
— comme ce fichier le faisait — produit un corpus taillé sur les tests, qui a l'air de
marcher parce qu'on lui a donné les réponses.

Toute ligne porte `reviewed_by = 'semis-demo'` : la contrainte `reviewed_by NOT NULL`
existe pour que rien de non-relu ne s'affiche comme relu, et un semis n'est pas une
relecture. **La curation réelle — 40 péricopes et leurs pesées sur les 10 loci — reste
entière.**
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Les péricopes curées — clé interne, bornes, motif obligatoire
# ---------------------------------------------------------------------------
#
# Deux péricopes se **chevauchent volontairement** sur Jean 3 (14-21 et 16-21) : c'est
# la seule façon de faire tourner l'arbitrage de l'étage 2 et de vérifier S8 (AWAIT à
# N+1 options) sur des données réelles.

PERICOPES: tuple[dict, ...] = (
    {
        "key": "john3_14_21",
        "osis": "John", "start_ch": 3, "start_v": 14, "end_ch": 3, "end_v": 21,
        "label": "Le serpent élevé et le Fils élevé",
        "rationale": "L'unité tient par l'image de l'élévation (v. 14) que le v. 16 explicite et "
                     "que les v. 19-21 retournent en jugement. Couper avant le v. 14 ampute la "
                     "comparaison de son premier terme.",
        "source_ref": "Découpage BHS/NA28 usuel — semis de démonstration",
    },
    {
        "key": "john3_16_21",
        "osis": "John", "start_ch": 3, "start_v": 16, "end_ch": 3, "end_v": 21,
        "label": "L'amour de Dieu et la lumière venue dans le monde",
        "rationale": "Découpage alternatif qui ouvre sur l'affirmation du v. 16 plutôt que sur la "
                     "comparaison mosaïque. Défendable en prédication, plus faible en exégèse : "
                     "le « car » du v. 16 renvoie à ce qui précède.",
        "source_ref": "Découpage homilétique courant — semis de démonstration",
    },
    {
        "key": "2cor5_14_21",
        "osis": "2Cor", "start_ch": 5, "start_v": 14, "end_ch": 5, "end_v": 21,
        "label": "La réconciliation et la nouvelle création",
        "rationale": "L'unité est encadrée par l'amour de Christ qui presse (v. 14) et le "
                     "renversement du v. 21. Le v. 17, souvent cité seul, est la charnière et "
                     "non le sujet.",
        "source_ref": "Découpage NA28 — semis de démonstration",
    },
    {
        "key": "rom8_1_11",
        "osis": "Rom", "start_ch": 8, "start_v": 1, "end_ch": 8, "end_v": 11,
        "label": "Aucune condamnation — la loi de l'Esprit de vie",
        "rationale": "Le « donc » du v. 1 conclut le chapitre 7 ; l'unité court jusqu'au v. 11 où "
                     "l'Esprit qui habite reprend et clôt l'argument.",
        "source_ref": "Découpage NA28 — semis de démonstration",
    },
    {
        "key": "rom12_9_16",
        "osis": "Rom", "start_ch": 12, "start_v": 9, "end_ch": 12, "end_v": 16,
        "label": "La charité sans hypocrisie",
        "rationale": "Série d'impératifs participiaux formant un bloc parénétique distinct du "
                     "corps de l'argument doctrinal des ch. 1-11.",
        "source_ref": "Découpage NA28 — semis de démonstration",
    },
    {
        "key": "1kgs21_1_16",
        "osis": "1Kgs", "start_ch": 21, "start_v": 1, "end_ch": 21, "end_v": 16,
        "label": "La vigne de Naboth",
        "rationale": "Le récit est complet du refus de Naboth (v. 3) à la prise de possession "
                     "(v. 16). L'oracle d'Élie qui suit (v. 17-29) est une unité distincte.",
        "source_ref": "Découpage BHS — semis de démonstration",
    },
    {
        "key": "hag1_1_11",
        "osis": "Hag", "start_ch": 1, "start_v": 1, "end_ch": 1, "end_v": 11,
        "label": "« Considérez attentivement vos voies »",
        "rationale": "Le premier oracle daté, encadré par le refrain du v. 5 et du v. 7. La "
                     "réponse du peuple (v. 12-15) forme la seconde unité.",
        "source_ref": "Découpage BHS — semis de démonstration",
    },
    {
        "key": "2cor9_6_15",
        "osis": "2Cor", "start_ch": 9, "start_v": 6, "end_ch": 9, "end_v": 15,
        "label": "Celui qui sème abondamment",
        "rationale": "Conclusion de l'argumentaire sur la collecte (ch. 8-9), refermée par la "
                     "doxologie du v. 15.",
        "source_ref": "Découpage NA28 — semis de démonstration",
    },
)


# ---------------------------------------------------------------------------
# Les pesées doctrinales — (clé péricope, axe, force, motif)
# ---------------------------------------------------------------------------
#
# `resiste` apparaît trois fois. C'est la valeur qui distingue Urim d'un moteur de
# proof-texting : un texte qui **complique** un axe n'est pas un texte qui s'en tait.

BEARINGS: tuple[tuple[str, str, str, str], ...] = (
    ("john3_14_21", "soteriologie", "dominant",
     "Le salut par la foi est l'objet même du passage : « afin que quiconque croit »."),
    ("john3_14_21", "christologie", "porte",
     "Le Fils unique élevé — titre et geste christologiques, au service de l'argument sur le "
     "salut."),
    ("john3_14_21", "theologie_propre", "porte",
     "L'initiative est celle de Dieu qui aime et qui donne ; le passage la pose sans la "
     "développer."),
    ("john3_14_21", "hamartiologie", "resiste",
     "Le passage ne décrit pas le péché comme état mais comme préférence des ténèbres (v. 19). "
     "Une prédication sur la nature du péché y trouvera peu de prise et devra emprunter ailleurs."),
    ("john3_16_21", "soteriologie", "dominant",
     "Même axe dominant, avec un centre de gravité déplacé sur l'amour de Dieu."),
    ("john3_16_21", "theologie_propre", "porte",
     "L'amour de Dieu ouvre l'unité et en devient le premier mot."),
    ("2cor5_14_21", "soteriologie", "dominant",
     "La réconciliation est le mot répété — v. 18, 19, 20 — et l'échange du v. 21 en donne le "
     "mécanisme."),
    ("2cor5_14_21", "anthropologie", "porte",
     "« Nouvelle créature » dit quelque chose de l'homme, mais comme conséquence de l'oeuvre du "
     "v. 21, jamais comme thème autonome."),
    ("2cor5_14_21", "ecclesiologie", "porte",
     "Le ministère de la réconciliation confié (v. 18) fonde une fonction dans l'assemblée."),
    ("2cor5_14_21", "eschatologie", "absent",
     "L'unité ne dit rien des choses dernières."),
    ("rom8_1_11", "pneumatologie", "dominant",
     "L'Esprit est le sujet grammatical et théologique de bout en bout : loi de l'Esprit, "
     "affection de l'Esprit, Esprit qui habite."),
    ("rom8_1_11", "soteriologie", "porte",
     "L'absence de condamnation (v. 1) est le point de départ, pas le développement."),
    ("rom8_1_11", "anthropologie", "porte",
     "L'opposition chair/esprit décrit une condition humaine, au service de l'argument sur "
     "l'Esprit."),
    ("rom8_1_11", "hamartiologie", "porte",
     "Le péché est condamné dans la chair (v. 3) — mentionné comme vaincu, non analysé."),
    ("rom12_9_16", "ecclesiologie", "dominant",
     "Toutes les injonctions règlent le rapport des membres entre eux : « les uns pour les "
     "autres », « les uns envers les autres »."),
    ("rom12_9_16", "anthropologie", "porte",
     "L'exhortation suppose une capacité de l'homme régénéré à aimer sans hypocrisie."),
    ("rom12_9_16", "soteriologie", "resiste",
     "Le passage est parénétique et ne fonde rien : y chercher le salut par les oeuvres serait "
     "lire contre Romains 1-11. Une prédication sur le salut devra aller ailleurs."),
    ("1kgs21_1_16", "hamartiologie", "dominant",
     "Le récit est une anatomie du péché institué : convoitise, faux témoignage, meurtre légal."),
    ("1kgs21_1_16", "theologie_propre", "porte",
     "L'Éternel n'apparaît que dans la bouche de Naboth (v. 3) — présence discrète mais "
     "décisive, puisque c'est elle qui motive le refus."),
    ("1kgs21_1_16", "ecclesiologie", "absent",
     "Le récit est royal et judiciaire ; il ne dit rien de l'assemblée."),
    ("1kgs21_1_16", "soteriologie", "resiste",
     "Le récit s'arrête sur la prise de possession, sans rédemption ni retournement. Le prêcher "
     "comme texte de salut exige d'importer l'oracle des v. 17-29, qui n'est pas dans l'unité."),
    ("hag1_1_11", "theologie_propre", "dominant",
     "L'Éternel des armées parle quatre fois et c'est sa maison qui est en cause."),
    ("hag1_1_11", "ecclesiologie", "porte",
     "La maison de l'Éternel et les demeures lambrissées opposent le commun au privé."),
    ("hag1_1_11", "anthropologie", "porte",
     "Le diagnostic porte sur l'ordre des priorités humaines, pas sur la nature de l'homme."),
    ("2cor9_6_15", "ecclesiologie", "dominant",
     "La collecte lie deux assemblées ; le v. 12 en fait un acte de communion, non une "
     "transaction."),
    ("2cor9_6_15", "theologie_propre", "porte",
     "Dieu aime celui qui donne avec joie (v. 7), et c'est lui qui fournit (v. 10)."),
    ("2cor9_6_15", "soteriologie", "absent",
     "L'unité ne traite pas du salut."),
)


# ---------------------------------------------------------------------------
# Les mises en garde — ce que le texte ne dit PAS (D-F)
# ---------------------------------------------------------------------------
#
# Le caveat confessionnel s'affiche **toujours**, y compris quand la tradition de
# l'église est inconnue : d'où des formulations en « ici les traditions divergent »,
# jamais en « votre tradition dit X ».

CAVEATS: tuple[tuple[str, str, str, str, tuple[str, ...] | None, str], ...] = (
    ("john3_14_21", "soteriologie", "exegetique",
     "Le passage ne précise pas où s'arrête la parole de Jésus et où commence le commentaire de "
     "l'évangéliste ; les éditions divergent entre le v. 15 et le v. 21.",
     None, "NA28, apparat — semis de démonstration"),
    ("john3_14_21", "soteriologie", "confessionnel",
     "Sur l'étendue de « le monde » au v. 16, les traditions divergent. Le texte affirme le don, "
     "il ne tranche pas la question de son extension.",
     ("reformee", "arminienne", "catholique"), "Semis de démonstration"),
    ("2cor5_14_21", "soteriologie", "exegetique",
     "« Il l'a fait devenir péché » (v. 21) est une formule dense dont le mécanisme n'est pas "
     "expliqué par Paul ; le texte ne dit pas comment.",
     None, "Semis de démonstration"),
    ("2cor5_14_21", "anthropologie", "confessionnel",
     "Sur ce que « nouvelle créature » change dans la nature de l'homme, ici les traditions "
     "divergent. Le texte constate, il ne définit pas.",
     ("reformee", "lutherienne", "pentecotiste"), "Semis de démonstration"),
    ("rom8_1_11", "pneumatologie", "confessionnel",
     "Sur le moment où l'Esprit vient habiter le croyant, ici les traditions divergent. Le "
     "passage suppose l'habitation, il n'en date pas le commencement.",
     ("reformee", "pentecotiste", "wesleyenne"), "Semis de démonstration"),
    ("rom8_1_11", "pneumatologie", "exegetique",
     "Le v. 1 est concerné par une variante textuelle : les éditions qui suivent le Texte Reçu "
     "ajoutent « qui ne marchent pas selon la chair, mais selon l'esprit ». Le prêcher sans le "
     "signaler expose à une contradiction avec l'auditoire.",
     None, "NA28, apparat critique — semis de démonstration"),
    ("1kgs21_1_16", "hamartiologie", "exegetique",
     "Le récit ne porte aucun jugement explicite sur les actes qu'il rapporte ; le narrateur "
     "s'abstient et laisse le lecteur conclure. Prêter au texte une condamnation qu'il ne "
     "formule pas est le risque principal de ce passage.",
     None, "Semis de démonstration"),
    ("1kgs21_1_16", "hamartiologie", "confessionnel",
     "Sur la part respective d'Achab et de Jézabel dans la responsabilité, ici les lectures "
     "divergent — le texte distribue les rôles sans les peser.",
     ("reformee", "catholique"), "Semis de démonstration"),
    ("hag1_1_11", "theologie_propre", "exegetique",
     "Le lien entre la sécheresse et la négligence du temple est affirmé par le prophète pour "
     "cette situation précise ; le texte n'énonce pas une loi générale de rétribution.",
     None, "Semis de démonstration"),
    ("2cor9_6_15", "ecclesiologie", "exegetique",
     "« Sème abondamment, moissonnera abondamment » vise une collecte pour les saints de "
     "Jérusalem ; le texte ne promet aucun retour matériel au donateur.",
     None, "Semis de démonstration"),
    ("2cor9_6_15", "ecclesiologie", "confessionnel",
     "Sur le caractère obligatoire ou libre de la contribution, ici les traditions divergent. Le "
     "v. 7 exclut la contrainte, il ne règle pas la question de la règle.",
     ("reformee", "catholique", "pentecotiste"), "Semis de démonstration"),
)


# ---------------------------------------------------------------------------
# Le contexte — historique et littéraire, sourcé ou rien (S40)
# ---------------------------------------------------------------------------

CONTEXT_NOTES: tuple[tuple[str, str, int, str, str], ...] = (
    ("john3_14_21", "historique", 1,
     "L'entretien avec Nicodème se situe à Jérusalem, pendant la Pâque (2:23), au début du "
     "ministère.", "Semis de démonstration"),
    ("john3_14_21", "litteraire", 1,
     "Le passage reprend Nombres 21:8-9. La comparaison n'est pas ornementale : elle fournit la "
     "structure de l'argument.", "Semis de démonstration"),
    ("2cor5_14_21", "historique", 1,
     "Paul écrit après une crise avec l'assemblée de Corinthe ; la défense de son ministère "
     "traverse toute la lettre.", "Semis de démonstration"),
    ("2cor5_14_21", "litteraire", 1,
     "L'unité est bâtie en chiasme autour du ministère de la réconciliation (v. 18), encadré par "
     "l'amour qui presse et l'échange final.", "Semis de démonstration"),
    ("rom8_1_11", "litteraire", 1,
     "Le « donc » du v. 1 rattache l'unité au cri de 7:24-25 ; la lire sans le chapitre 7 en "
     "supprime la question à laquelle elle répond.", "Semis de démonstration"),
    ("1kgs21_1_16", "historique", 1,
     "Sous Achab, la vigne relève de l'héritage familial inaliénable (Lévitique 25:23) — ce que "
     "le refus de Naboth invoque et que le récit tient pour acquis.", "Semis de démonstration"),
    ("1kgs21_1_16", "litteraire", 1,
     "Le récit fonctionne par répétition ironique : les mots de Jézabel (v. 9-10) sont exécutés "
     "à la lettre (v. 12-13), ce qui souligne la mécanique du faux procès.",
     "Semis de démonstration"),
    ("hag1_1_11", "historique", 1,
     "Deuxième année de Darius (520 av. J.-C.), seize ans après le retour ; les fondations du "
     "temple sont posées et le chantier arrêté.", "Semis de démonstration"),
    ("2cor9_6_15", "historique", 1,
     "La collecte pour les saints de Jérusalem occupe Paul sur plusieurs années et plusieurs "
     "lettres (1 Co 16:1-4, Rm 15:25-28).", "Semis de démonstration"),
)


# ---------------------------------------------------------------------------
# La faisabilité homilétique — (péricope, plan, matière, faisable, motif, risque)
# ---------------------------------------------------------------------------
#
# Les refus voyagent avec les faisables : *une combinaison impossible est signalée,
# jamais fabriquée*. `refus_motive` interdit en base un `feasible = false` muet.

FEASIBILITY: tuple[tuple[str, str, str, bool, str | None, str], ...] = (
    ("john3_14_21", "expositif", "doctrinal", True, None, "faible"),
    ("john3_14_21", "textuel", "typologique", True, None, "moyen"),
    ("john3_14_21", "thematique", "doctrinal", True, None, "eleve"),
    ("john3_14_21", "expositif", "biographique", False,
     "L'unité ne met en scène aucun personnage : Nicodème a quitté le dialogue et Moïse n'est "
     "qu'un terme de comparaison. Un plan biographique devrait importer sa matière du dehors.",
     "eleve"),
    ("john3_16_21", "thematique", "doctrinal", True, None, "eleve"),
    ("john3_16_21", "expositif", "doctrinal", True, None, "moyen"),
    ("2cor5_14_21", "expositif", "doctrinal", True, None, "faible"),
    ("2cor5_14_21", "textuel", "doctrinal", True, None, "faible"),
    ("2cor5_14_21", "thematique", "ethique", False,
     "Le v. 17 isolé de son contexte devient un slogan de transformation personnelle, alors que "
     "Paul y fonde un ministère. C'est le proof-texting le plus fréquent sur ce passage.",
     "eleve"),
    ("rom8_1_11", "expositif", "doctrinal", True, None, "faible"),
    ("rom8_1_11", "textuel", "doctrinal", True, None, "faible"),
    ("rom8_1_11", "expositif", "biographique", False,
     "Aucun personnage dans l'unité ; le « je » du v. 2 est rhétorique et non narratif.",
     "eleve"),
    ("rom12_9_16", "expositif", "ethique", True, None, "faible"),
    ("rom12_9_16", "thematique", "ethique", True, None, "moyen"),
    ("rom12_9_16", "expositif", "doctrinal", False,
     "La série est parénétique et n'argumente rien : en tirer un exposé doctrinal reviendrait à "
     "fonder la doctrine sur l'exhortation qui en découle.",
     "eleve"),
    ("1kgs21_1_16", "expositif", "biographique", True, None, "moyen"),
    ("1kgs21_1_16", "textuel", "historique", True, None, "faible"),
    ("1kgs21_1_16", "expositif", "ethique", True, None, "moyen"),
    ("1kgs21_1_16", "thematique", "typologique", False,
     "Faire de Naboth une figure du juste souffrant demande une typologie que le texte n'appuie "
     "pas et que le Nouveau Testament ne reprend jamais.",
     "eleve"),
    ("hag1_1_11", "expositif", "prophetique", True, None, "faible"),
    ("hag1_1_11", "textuel", "historique", True, None, "faible"),
    ("hag1_1_11", "thematique", "ethique", True, None, "eleve"),
    ("2cor9_6_15", "expositif", "ethique", True, None, "moyen"),
    ("2cor9_6_15", "textuel", "doctrinal", True, None, "faible"),
    ("2cor9_6_15", "thematique", "ethique", False,
     "Détaché de la collecte pour Jérusalem, le passage sert couramment à promettre un retour "
     "matériel au donateur — ce que le texte ne dit nulle part.",
     "eleve"),
)


# ---------------------------------------------------------------------------
# Une variante textuelle — Romains 8:1 (S17)
# ---------------------------------------------------------------------------

TEXTUAL_VARIANTS: tuple[dict, ...] = (
    {
        "osis": "Rom", "chapter": 8, "verse": 1,
        "body": "Il n'y a donc maintenant aucune condamnation pour ceux qui sont en "
                "Jésus-Christ, qui ne marchent pas selon la chair, mais selon l'esprit.",
        "families_with": ("byzantin", "texte_recu"),
        "families_without": ("alexandrin", "NA28", "SBLGNT"),
        "doctrinal_weight": "notable",
        "note": "L'ajout reprend mot pour mot la fin du v. 4 et déplace le sens : la "
                "non-condamnation devient conditionnelle à la marche. Les éditions critiques le "
                "traitent comme une harmonisation tardive. La différence est visible pour tout "
                "auditeur qui suit sur une autre Bible.",
        "source_ref": "NA28, apparat critique — semis de démonstration",
    },
)


# ---------------------------------------------------------------------------
# Le lexique français — pour `known_words` (S34)
# ---------------------------------------------------------------------------
#
# ⚠️ **Le lexique de la LANGUE, pas celui du corpus biblique.** Une simulation l'a
# montré : le vocabulaire d'une conviction sur l'église d'aujourd'hui (*voiture*,
# *chômage*, *quartier*, *réseaux*) est précisément celui qui ne figure pas dans
# l'Écriture. Ces mots entrent donc dans `urim_corpus_idf` avec un idf **nul** — connus
# de la langue, sans aucun poids d'ancre scripturaire.

LEXIQUE_FR: tuple[str, ...] = (
    # outils grammaticaux
    "le", "la", "les", "un", "une", "des", "du", "de", "au", "aux", "et", "ou", "mais", "donc",
    "or", "ni", "car", "que", "qui", "quoi", "dont", "ou", "si", "ne", "pas", "plus", "jamais",
    "rien", "personne", "aucun", "aucune", "tout", "toute", "tous", "toutes", "meme", "aussi",
    "tres", "trop", "peu", "beaucoup", "assez", "bien", "mal", "encore", "deja", "toujours",
    "souvent", "parfois", "ici", "la", "ce", "cet", "cette", "ces", "celui", "celle", "ceux",
    "je", "tu", "il", "elle", "nous", "vous", "ils", "elles", "on", "me", "te", "se", "lui",
    "leur", "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses", "notre", "nos", "votre",
    "vos", "leurs", "dans", "sur", "sous", "avec", "sans", "pour", "par", "vers", "chez", "entre",
    "depuis", "pendant", "avant", "apres", "contre", "selon", "comme", "quand", "alors",
    "est", "sont", "etait", "etaient", "sera", "seront", "ete", "etre", "avoir", "ai", "as", "a",
    "avons", "avez", "ont", "avait", "avaient", "fait", "faire", "dit", "dire", "va", "aller",
    "peut", "pouvoir", "veut", "vouloir", "doit", "devoir", "sait", "savoir", "vient", "venir",
    # vie de l'assemblee
    "eglise", "assemblee", "communaute", "membre", "membres", "fidele", "fideles", "frere",
    "freres", "soeur", "soeurs", "pasteur", "ancien", "anciens", "diacre", "responsable",
    "culte", "priere", "louange", "chant", "offrande", "dime", "cotisation", "cotisations",
    "collecte", "temple", "batiment", "chantier", "construction", "projet", "reunion", "groupe",
    "cellule", "jeunesse", "jeunes", "enfants", "famille", "familles", "couple", "mariage",
    "bapteme", "temoignage", "mission", "evangelisation", "visite", "accueil", "service",
    # vie ordinaire — le vocabulaire absent de l'Ecriture
    "voiture", "travail", "emploi", "chomage", "argent", "salaire", "loyer", "quartier", "ville",
    "village", "ecole", "hopital", "medecin", "maladie", "telephone", "internet", "reseaux",
    "reseau", "message", "photo", "video", "ordinateur", "transport", "marche", "commerce",
    "entreprise", "patron", "collegue", "voisin", "voisins", "route", "moto", "taxi", "essence",
    "electricite", "eau", "nourriture", "repas", "logement", "maison", "loyers", "impot",
    # affects et jugements
    "amour", "amitie", "fraternel", "fraternelle", "fraternite", "haine", "colere", "peur",
    "joie", "tristesse", "souffrance", "douleur", "espoir", "esperance", "confiance", "doute",
    "fatigue", "decouragement", "motivation", "engagement", "indifference", "division",
    "conflit", "reconciliation", "pardon", "jalousie", "orgueil", "humilite", "patience",
    "existe", "existent", "manque", "manquent", "disparu", "disparait", "perdu", "trouve",
    "besoin", "besoins", "probleme", "problemes", "question", "reponse", "solution",
    # --- les formes elidees, collees comme le normaliseur les produit -----------
    #
    # Le normaliseur **supprime** l'apostrophe (S21) : « l'Eglise » devient `leglise`, et
    # c'est cette forme-la que le pasteur tape quand il va vite. Sans ces entrees,
    # `known_words` ne reconnaitrait rien dans « lamour fraternel nexiiste plus dans
    # leglise » — la phrase la plus francaise du monde serait declaree illisible.
    "leglise", "lamour", "lesprit", "lhomme", "lassemblee", "laccueil", "largent",
    "lecole", "lemploi", "lentreprise", "leau", "lelectricite", "lespoir", "lesperance",
    "lhumilite", "lindifference", "lorgueil", "lengagement", "leternel", "loffrande",
    "cest", "nest", "nexiste", "nexistent", "ny", "quil", "quelle", "quon", "qui",
    "jai", "jetais", "sil", "sest", "dun", "dune", "den", "lun", "lautre", "daccord",
    "aujourdhui", "quelquun", "jusqua", "parcequ", "sans", "davoir", "detre",
)
