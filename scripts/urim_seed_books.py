"""Les 66 livres du canon protestant — codes OSIS, noms français, abréviations.

Cette table n'est **pas** de la curation : c'est de la donnée de référence, vraie
indépendamment de toute relecture théologique. Elle est donc séparée du semis de
démonstration, et elle a vocation à survivre à l'acquisition du vrai corpus.

Les abréviations sont lues par `find_reference_span` — **la table, jamais une regex**
(S33/S35). C'est pourquoi on y met les formes que les pasteurs écrivent réellement
(« 1 Co », « Ps », « Apo »), et pas seulement les sigles canoniques.
"""

from __future__ import annotations

# (canon_order, osis_code, testament, label français, abréviations)
BOOKS: tuple[tuple[int, str, str, str, tuple[str, ...]], ...] = (
    (1, "Gen", "AT", "Genèse", ('gen', 'gene', 'genese', 'gn')),
    (2, "Exod", "AT", "Exode", ('ex', 'exo', 'exod', 'exode')),
    (3, "Lev", "AT", "Lévitique", ('lev', 'levi', 'levit', 'levitique', 'lv')),
    (4, "Num", "AT", "Nombres", ('nb', 'nom', 'nomb', 'nombres')),
    (5, "Deut", "AT", "Deutéronome", ('deut', 'deuter', 'deuteronome', 'dt')),
    (6, "Josh", "AT", "Josué", ('jos', 'josue')),
    (7, "Judg", "AT", "Juges", ('jg', 'jug', 'juges')),
    (8, "Ruth", "AT", "Ruth", ('rt', 'rut', 'ruth')),
    (9, "1Sam", "AT", "1 Samuel", ('1 samuel', '1 sm', '1s', '1sa', '1sam', '1sm')),
    (10, "2Sam", "AT", "2 Samuel", ('2 samuel', '2 sm', '2s', '2sa', '2sam', '2sm')),
    (11, "1Kgs", "AT", "1 Rois", ('1 roi', '1 rois', '1 rs', '1r', '1ro', '1roi', '1rois', '1rs')),
    (12, "2Kgs", "AT", "2 Rois", ('2 roi', '2 rois', '2 rs', '2r', '2ro', '2roi', '2rois', '2rs')),
    (13, "1Chr", "AT", "1 Chroniques", ('1 ch', '1 chroniques', '1ch', '1chr', '1chron')),
    (14, "2Chr", "AT", "2 Chroniques", ('2 ch', '2 chroniques', '2ch', '2chr', '2chron')),
    (15, "Ezra", "AT", "Esdras", ('esd', 'esdr', 'esdras')),
    (16, "Neh", "AT", "Néhémie", ('ne', 'neh', 'nehemie')),
    (17, "Esth", "AT", "Esther", ('est', 'esth', 'esther')),
    (18, "Job", "AT", "Job", ('jb', 'job')),
    (19, "Ps", "AT", "Psaumes", ('ps', 'psa', 'psau', 'psaume', 'psaumes', 'pseaume')),
    (20, "Prov", "AT", "Proverbes", ('pr', 'pro', 'prov', 'proverbe', 'proverbes')),
    (21, "Eccl", "AT", "Ecclésiaste", ('ec', 'eccl', 'ecclesiaste', 'qo', 'qohelet')),
    (22, "Song", "AT", "Cantique des cantiques", ('cant', 'cantique', 'cantiques', 'ct')),
    (23, "Isa", "AT", "Ésaïe", ('es', 'esa', 'esaie', 'essaie', 'isaie', 'isaïe')),
    (24, "Jer", "AT", "Jérémie", ('jer', 'jere', 'jeremie', 'jeremy', 'jr')),
    (25, "Lam", "AT", "Lamentations", ('lam', 'lament', 'lamentations', 'lm')),
    (26, "Ezek", "AT", "Ézéchiel", ('ez', 'eze', 'ezec', 'ezech', 'ezechiel', 'ezekiel')),
    (27, "Dan", "AT", "Daniel", ('dan', 'danie', 'daniel', 'dn')),
    (28, "Hos", "AT", "Osée", ('os', 'ose', 'osee')),
    (29, "Joel", "AT", "Joël", ('jl', 'joe', 'joel')),
    (30, "Amos", "AT", "Amos", ('am', 'amo', 'amos')),
    (31, "Obad", "AT", "Abdias", ('ab', 'abd', 'abdias')),
    (32, "Jonah", "AT", "Jonas", ('jon', 'jona', 'jonas')),
    (33, "Mic", "AT", "Michée", ('mi', 'mic', 'mich', 'michee')),
    (34, "Nah", "AT", "Nahum", ('na', 'nah', 'nahum')),
    (35, "Hab", "AT", "Habacuc", ('ha', 'hab', 'habacuc')),
    (36, "Zeph", "AT", "Sophonie", ('so', 'sop', 'soph', 'sophonie')),
    (37, "Hag", "AT", "Aggée", ('ag', 'agg', 'aggee')),
    (38, "Zech", "AT", "Zacharie", ('za', 'zac', 'zach', 'zacharie')),
    (39, "Mal", "AT", "Malachie", ('mal', 'malachie', 'ml')),
    (40, "Matt", "NT", "Matthieu", (
        'mat', 'mathieu', 'mathieux', 'matt', 'matth', 'matthieu', 'mt'
    )),
    (41, "Mark", "NT", "Marc", ('mar', 'marc', 'mc', 'mr')),
    (42, "Luke", "NT", "Luc", ('lc', 'lu', 'luc')),
    (43, "John", "NT", "Jean", ('jan', 'jea', 'jean', 'jhn', 'jn', 'joh')),
    (44, "Acts", "NT", "Actes", ('ac', 'act', 'acte', 'actes', 'actes des apotres')),
    (45, "Rom", "NT", "Romains", ('rm', 'rmn', 'ro', 'rom', 'roma', 'romain', 'romains')),
    (46, "1Cor", "NT", "1 Corinthiens", (
        '1 c', '1 co', '1 cor', '1 corinthien', '1c', '1co', '1cor', '1corint', '1corinthiens'
    )),
    (47, "2Cor", "NT", "2 Corinthiens", (
        '2 c', '2 co', '2 cor', '2 corinthien', '2c', '2co', '2cor', '2corint', '2corinthiens'
    )),
    (48, "Gal", "NT", "Galates", ('ga', 'gal', 'gala', 'galate', 'galates')),
    (49, "Eph", "NT", "Éphésiens", ('ep', 'eph', 'ephes', 'ephesien', 'ephesiens')),
    (50, "Phil", "NT", "Philippiens", (
        'ph', 'phi', 'phil', 'philip', 'philippien', 'philippiens', 'php'
    )),
    (51, "Col", "NT", "Colossiens", ('col', 'colo', 'colos', 'coloss', 'colossien', 'colossiens')),
    (52, "1Thess", "NT", "1 Thessaloniciens", (
        '1 th', '1 thes', '1 thess', '1 thessalonicien', '1th', '1thes', '1thess'
    )),
    (53, "2Thess", "NT", "2 Thessaloniciens", (
        '2 th', '2 thes', '2 thess', '2 thessalonicien', '2th', '2thes', '2thess'
    )),
    (54, "1Tim", "NT", "1 Timothée", ('1 tim', '1 timothee', '1 tm', '1ti', '1tim', '1tm')),
    (55, "2Tim", "NT", "2 Timothée", ('2 tim', '2 timothee', '2 tm', '2ti', '2tim', '2tm')),
    (56, "Titus", "NT", "Tite", ('tit', 'tite', 'tt')),
    (57, "Phlm", "NT", "Philémon", ('phile', 'philem', 'philemon', 'phlm', 'phm')),
    (58, "Heb", "NT", "Hébreux", ('he', 'heb', 'hebr', 'hebreu', 'hebreux')),
    (59, "Jas", "NT", "Jacques", ('jac', 'jacq', 'jacque', 'jacques', 'jc', 'jq')),
    (60, "1Pet", "NT", "1 Pierre", ('1 pi', '1 pierre', '1p', '1pe', '1pi', '1pie', '1pierre')),
    (61, "2Pet", "NT", "2 Pierre", ('2 pi', '2 pierre', '2p', '2pe', '2pi', '2pie', '2pierre')),
    (62, "1John", "NT", "1 Jean", ('1 jean', '1 jn', '1j', '1je', '1jean', '1jn')),
    (63, "2John", "NT", "2 Jean", ('2 jean', '2 jn', '2j', '2je', '2jean', '2jn')),
    (64, "3John", "NT", "3 Jean", ('3 jean', '3 jn', '3j', '3je', '3jean', '3jn')),
    (65, "Jude", "NT", "Jude", ('jd', 'jud', 'jude')),
    (66, "Rev", "NT", "Apocalypse", ('ap', 'apo', 'apoc', 'apocalypse', 're', 'rev', 'revelation')),
)
