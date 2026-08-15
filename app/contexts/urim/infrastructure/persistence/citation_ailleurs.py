"""Chercher la citation **dans les autres versions détenues** — la seconde passe.

🐛 **L'index ne charge le texte que de la version de repli** (`load_corpus_index` filtre sur
`version_id == repli.id`). Le détecteur d'entrée compare donc toute saisie à une seule Bible.

Le cas qui l'a montré, et il est sans appel :

    saisie du pasteur     « l'amour ne perir jamais »
    Darby                 « L'amour ne périt jamais. »        ← mot pour mot
    Segond 1910           « La charité ne périt jamais. »     ← ce que l'index contient

Segond rend ἀγάπη par **charité** en 1 Corinthiens 13. Le mot le plus lourd de la saisie —
`lamour`, idf 6,3 — **n'est pas dans le verset** que l'index détient. Aucun seuil, aucune
tolérance orthographique ne pouvait rattraper cela : `lamour` et `charite` ne sont pas une
faute de frappe l'un de l'autre, ce sont deux mots.

## Pourquoi une seconde passe, et non un index plus gros

Charger les quatre versions ferait passer l'index de 31 000 à 125 000 versets — avec les
postings et les séquences — pour un gain qui ne sert **que** la détection d'entrée. Ici on ne
paie que sur les saisies dont la première passe n'a rien tiré, c'est-à-dire rarement. C'est le
patron déjà retenu pour Q9 côté livrable, et pour la même raison.

⚠️ **Et elle passe AVANT le modèle.** Une citation retrouvée dans le corpus n'a pas à être
devinée : le chemin le moins cher est aussi le plus sûr, et il ne consomme aucun quota.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.urim.application.ports import CitationTrouvee
from app.contexts.urim.engine.state import Reference
from app.contexts.urim.infrastructure.corpus.index import CorpusIndex
from app.contexts.urim.infrastructure.corpus.readers import _suites_communes

#: Combien de mots-ancres portent la recherche. Trois suffisent : au-delà, on décrit la saisie
#: plutôt qu'on ne la retrouve, et la requête se ferme sur les fautes de frappe.
_ANCRES = 3

#: Le plafond de lignes rapportées. `lamour` paraît des centaines de fois chez Darby ; les
#: peser toutes coûte moins qu'un appel de modèle, mais il faut une borne.
_CANDIDATS = 400


class SqlCitationAilleurs:
    """La même mesure de contiguïté, appliquée aux versions que l'index ne porte pas."""

    def __init__(self, session: AsyncSession, index: CorpusIndex) -> None:
        self._s = session
        self._index = index

    async def retrouver(self, mots: Sequence[str]) -> CitationTrouvee | None:
        saisie = tuple(mots)
        if len(saisie) < 2:
            return None

        # Les mots que **le corpus connaît**, du plus rare au plus fréquent. Un mot inconnu
        # (`perir` là où le texte dit `périt`) ne peut pas porter la recherche : on cherche
        # par ce qui est sûr, on pèse ensuite par tout.
        ancres = sorted(
            ((self._index.idf.get(mot, 0.0), mot) for mot in set(saisie)),
            reverse=True,
        )
        retenues = [mot for poids, mot in ancres if poids > 0.0][:_ANCRES]
        if not retenues:
            return None

        # ⚠️ **OU, jamais ET.** Exiger toutes les ancres ferait échouer exactement le cas qui
        # motive ce module : `perir` est rare, et absent du verset cherché. Une seule ancre
        # suffit à ramener le candidat ; c'est la contiguïté qui tranche ensuite.
        conditions = " OR ".join(
            f"v.body_norm LIKE :mot{rang}" for rang in range(len(retenues))
        )
        # 🐛 **`LIMIT` sans `ORDER BY` rendait des lignes ARBITRAIRES.** La condition `OR`
        # ramène des milliers de versets ; Postgres en coupait 400 au hasard, si bien que la
        # même saisie trouvait Darby 1 Co 13:8 une fois sur deux et Psaumes 9:19 l'autre fois.
        #
        # Dans un moteur dont l'invariant fondateur est le déterminisme — `test_determinisme`
        # rejoue cent fois la même saisie — c'est plus grave qu'un mauvais score : c'est une
        # préparation qui ne s'ouvre pas deux fois pareil.
        #
        # On ordonne donc par **le nombre d'ancres présentes**, puis par l'ordre du canon. Le
        # verset qui porte deux des mots rares de la saisie passe avant celui qui n'en porte
        # qu'un, et à égalité c'est la Genèse qui vient d'abord — jamais le hasard du disque.
        compte = " + ".join(
            f"(CASE WHEN v.body_norm LIKE :mot{rang} THEN 1 ELSE 0 END)"
            for rang in range(len(retenues))
        )
        parametres = {f"mot{rang}": f"%{mot}%" for rang, mot in enumerate(retenues)}
        parametres["repli"] = str(self._index.fallback_version_id)

        lignes = (await self._s.execute(
            text(
                f"SELECT b.id, n.label, v.chapter, v.verse, v.body_norm, ver.label,"
                f" ver.id, ({compte}) AS ancres"
                " FROM urim_corpus_verse v"
                " JOIN urim_corpus_version ver ON ver.id = v.version_id"
                " JOIN urim_corpus_book b ON b.id = v.book_id"
                " JOIN urim_corpus_book_name n ON n.book_id = b.id AND n.language = 'fr'"
                f" WHERE v.version_id <> :repli AND ({conditions})"
                " ORDER BY ancres DESC, b.id, v.chapter, v.verse, ver.label"
                f" LIMIT {_CANDIDATS}"
            ),
            parametres,
        )).all()

        total = sum(
            self._index.idf.get(mot, self._index.idf_median) for mot in saisie
        )
        if total <= 0:
            return None

        meilleur: CitationTrouvee | None = None
        for _livre, livre_label, chapitre, verset, corps, version, vid, _n in lignes:
            suite = _suites_communes(saisie, tuple(corps.split()))
            if len(suite) < 2:
                continue
            score = sum(self._index.idf.get(mot, 0.0) for mot in suite) / total
            # ⚠️ **Strictement supérieur** : à égalité, le premier rencontré gagne, et
            # l'ordre est celui du canon. Deux versions qui rendent la même phrase ne
            # doivent pas se départager par le hasard de la requête.
            if meilleur is None or score > meilleur.score:
                meilleur = CitationTrouvee(
                    reference=Reference(livre_label, chapitre, verset, verset),
                    version=version,
                    version_id=vid,
                    score=score,
                )
        return meilleur
