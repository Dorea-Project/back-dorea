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
    (1, "Gen", "AT", "Genèse", ("gn", "gen", "gene", "genese")),
    (2, "Exod", "AT", "Exode", ("ex", "exo", "exod", "exode")),
    (3, "Lev", "AT", "Lévitique", ("lv", "lev", "levit", "levitique")),
    (4, "Num", "AT", "Nombres", ("nb", "nom", "nomb", "nombres")),
    (5, "Deut", "AT", "Deutéronome", ("dt", "deut", "deuteronome")),
    (6, "Josh", "AT", "Josué", ("jos", "josue")),
    (7, "Judg", "AT", "Juges", ("jg", "jug", "juges")),
    (8, "Ruth", "AT", "Ruth", ("rt", "ruth")),
    (9, "1Sam", "AT", "1 Samuel", ("1s", "1sa", "1sam", "1 samuel")),
    (10, "2Sam", "AT", "2 Samuel", ("2s", "2sa", "2sam", "2 samuel")),
    (11, "1Kgs", "AT", "1 Rois", ("1r", "1ro", "1roi", "1rois", "1 roi", "1 rois")),
    (12, "2Kgs", "AT", "2 Rois", ("2r", "2ro", "2roi", "2rois", "2 roi", "2 rois")),
    (13, "1Chr", "AT", "1 Chroniques", ("1ch", "1chr", "1chron", "1 chroniques")),
    (14, "2Chr", "AT", "2 Chroniques", ("2ch", "2chr", "2chron", "2 chroniques")),
    (15, "Ezra", "AT", "Esdras", ("esd", "esdr", "esdras")),
    (16, "Neh", "AT", "Néhémie", ("ne", "neh", "nehemie")),
    (17, "Esth", "AT", "Esther", ("est", "esth", "esther")),
    (18, "Job", "AT", "Job", ("jb", "job")),
    (19, "Ps", "AT", "Psaumes", ("ps", "psa", "psau", "psaume", "psaumes")),
    (20, "Prov", "AT", "Proverbes", ("pr", "pro", "prov", "proverbes")),
    (21, "Eccl", "AT", "Ecclésiaste", ("ec", "eccl", "ecclesiaste")),
    (22, "Song", "AT", "Cantique des cantiques", ("ct", "cant", "cantique", "cantiques")),
    (23, "Isa", "AT", "Ésaïe", ("es", "esa", "esaie", "isaie")),
    (24, "Jer", "AT", "Jérémie", ("jr", "jer", "jere", "jeremie")),
    (25, "Lam", "AT", "Lamentations", ("lm", "lam", "lament", "lamentations")),
    (26, "Ezek", "AT", "Ézéchiel", ("ez", "eze", "ezech", "ezechiel")),
    (27, "Dan", "AT", "Daniel", ("dn", "dan", "danie", "daniel")),
    (28, "Hos", "AT", "Osée", ("os", "ose", "osee")),
    (29, "Joel", "AT", "Joël", ("jl", "joe", "joel")),
    (30, "Amos", "AT", "Amos", ("am", "amo", "amos")),
    (31, "Obad", "AT", "Abdias", ("ab", "abd", "abdias")),
    (32, "Jonah", "AT", "Jonas", ("jon", "jona", "jonas")),
    (33, "Mic", "AT", "Michée", ("mi", "mic", "michee")),
    (34, "Nah", "AT", "Nahum", ("na", "nah", "nahum")),
    (35, "Hab", "AT", "Habacuc", ("ha", "hab", "habacuc")),
    (36, "Zeph", "AT", "Sophonie", ("so", "sop", "soph", "sophonie")),
    (37, "Hag", "AT", "Aggée", ("ag", "agg", "aggee")),
    (38, "Zech", "AT", "Zacharie", ("za", "zac", "zach", "zacharie")),
    (39, "Mal", "AT", "Malachie", ("ml", "mal", "malachie")),
    (40, "Matt", "NT", "Matthieu", ("mt", "mat", "matt", "matth", "matthieu")),
    (41, "Mark", "NT", "Marc", ("mc", "mar", "marc")),
    (42, "Luke", "NT", "Luc", ("lc", "luc")),
    (43, "John", "NT", "Jean", ("jn", "jea", "jean")),
    (44, "Acts", "NT", "Actes", ("ac", "act", "acte", "actes")),
    (45, "Rom", "NT", "Romains", ("rm", "ro", "rom", "roma", "romain", "romains")),
    (46, "1Cor", "NT", "1 Corinthiens", ("1co", "1cor", "1corinthiens", "1 co", "1 cor")),
    (47, "2Cor", "NT", "2 Corinthiens", ("2co", "2cor", "2corinthiens", "2 co", "2 cor")),
    (48, "Gal", "NT", "Galates", ("ga", "gal", "gala", "galates")),
    (49, "Eph", "NT", "Éphésiens", ("ep", "eph", "ephes", "ephesiens")),
    (50, "Phil", "NT", "Philippiens", ("ph", "phi", "phil", "philippiens")),
    (51, "Col", "NT", "Colossiens", ("col", "colo", "coloss", "colossiens")),
    (52, "1Thess", "NT", "1 Thessaloniciens", ("1th", "1thess", "1 th", "1 thes")),
    (53, "2Thess", "NT", "2 Thessaloniciens", ("2th", "2thess", "2 th", "2 thes")),
    (54, "1Tim", "NT", "1 Timothée", ("1tm", "1ti", "1tim", "1 tim", "1 timothee")),
    (55, "2Tim", "NT", "2 Timothée", ("2tm", "2ti", "2tim", "2 tim", "2 timothee")),
    (56, "Titus", "NT", "Tite", ("tt", "tit", "tite")),
    (57, "Phlm", "NT", "Philémon", ("phm", "phile", "philemon")),
    (58, "Heb", "NT", "Hébreux", ("he", "heb", "hebr", "hebreux")),
    (59, "Jas", "NT", "Jacques", ("jc", "jac", "jacq", "jacques")),
    (60, "1Pet", "NT", "1 Pierre", ("1p", "1pi", "1pie", "1pierre", "1 pierre")),
    (61, "2Pet", "NT", "2 Pierre", ("2p", "2pi", "2pie", "2pierre", "2 pierre")),
    (62, "1John", "NT", "1 Jean", ("1jn", "1je", "1jean", "1 jean")),
    (63, "2John", "NT", "2 Jean", ("2jn", "2je", "2jean", "2 jean")),
    (64, "3John", "NT", "3 Jean", ("3jn", "3je", "3jean", "3 jean")),
    (65, "Jude", "NT", "Jude", ("jud", "jude")),
    (66, "Rev", "NT", "Apocalypse", ("ap", "apo", "apoc", "apocalypse")),
)
