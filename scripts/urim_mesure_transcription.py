"""Le banc de mesure de la transcription — **le mode de panne avant le taux d'erreur**.

S6 §9 ligne 2 demande un banc du taux d'erreur par langue sur trois cultes réels. Il n'existe
pas encore, et il ne peut pas exister aujourd'hui : les trois cultes ne sont pas enregistrés.
Ce script mesure donc **l'autre chose**, celle qui se mesure tout de suite et qui décide
davantage — *comment un candidat échoue quand il n'a rien à entendre*.

C'est la question de D17. Un décodeur autorégressif privé de signal continue la phrase : il
rend du français fluide et faux. Un décodeur CTC rend une bouillie. Les deux échouent, un seul
échoue **visiblement** — et pour un culte, la bouillie se marque non reconnue (D11) là où la
phrase inventée se croit.

**Ce que le banc peut prouver, et ce qu'il ne peut pas.** Il peut montrer qu'un candidat rend
trois phrases nettes sur trente secondes de silence — c'est une preuve, et elle suffit à
classer le candidat. Il ne peut pas prouver l'inverse : un candidat muet sur ce banc-ci peut
inventer ailleurs. **Le ratio non-lettres est un signal, pas un verdict** (T-Rec v1.2 §1).

**Quatre candidats, jamais trois.** « Google » n'est pas une ligne de ce banc : Chirp et Gemini
Flash sont deux architectures aux modes de panne opposés, et les confondre referait avec Google
l'erreur déjà faite avec Voxtral — juger un modèle sur son fournisseur plutôt que sur son
décodeur (I34). Chaque relevé porte donc son architecture (I35) et la juridiction où l'audio a
transité (I36), à côté du score et pas en note de bas de page.

**L'audio réel ne part pas par défaut.** Les captures de `capture_audio/` sont des voix de
pasteurs. Les envoyer chez un tiers est une décision, pas un détail d'exécution : sans
`--audio-reel`, le banc ne fait tourner que les échantillons fabriqués. Q1 n'est pas tranchée
(S6 §10.1) et ce script ne la tranche pas.

**Ce banc ne fait entrer personne en production** (I37). Le seul chemin reste S6 §8 : trois
églises réelles, tous candidats confondus.

    python scripts/urim_mesure_transcription.py                 # échantillons fabriqués
    python scripts/urim_mesure_transcription.py --audio-reel    # + les captures du dépôt
    python scripts/urim_mesure_transcription.py --candidats chirp,gemini
"""

from __future__ import annotations

import argparse
import array
import io
import math
import os
import pathlib
import random
import sys
import time
import unicodedata
import wave
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RACINE = pathlib.Path(__file__).resolve().parent.parent


def _charger_env() -> None:
    """Les clés se rangent dans `.env`, comme celles de Mistral et d'Infobip.

    Le banc ne passe pas par `get_settings()` : ces clés-ci ne servent qu'à mesurer, elles
    n'ont rien à faire dans la configuration de l'application (I37 — rien de ce banc n'entre
    en production par inadvertance). Une variable d'environnement déjà posée gagne, pour
    qu'on puisse essayer une autre clé sans toucher au fichier.
    """
    fichier = RACINE / ".env"
    if not fichier.is_file():
        return
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, _, valeur = ligne.partition("=")
        os.environ.setdefault(cle.strip(), valeur.strip().strip("\"'"))


_charger_env()

#: La capture telle que D53 l'écrit : PCM 16 bits, 16 kHz, mono. Ni rééchantillonnage ni
#: décodage entre le disque et le banc — c'est ce que le téléphone a réellement produit.
TAUX = 16_000
LARGEUR = 2
CANAUX = 1

#: Speech-to-Text v2 accepte l'audio en ligne jusqu'à ~60 s. Le fragment de D53 fait trente
#: secondes : l'unité d'écriture du téléphone est aussi l'unité du banc, sans redécoupage.
SECONDES_MAX = 30

#: Identifiants relevés le 01/09/2026, **non vérifiés contre la documentation Google**.
#: Même discipline que les tarifs de `urim_mesure_cout.py` : en dur, datés, à revérifier avant
#: de fonder une décision dessus. T-Rec v1.2 §6 les liste explicitement comme non confirmés.
MODELE_CHIRP = "chirp_2"
#: Corrigé le 02/09/2026 **par l'API elle-même** : `gemini-2.5-flash` répond 404 avec le
#: message « no longer available to new users … use models/gemini-3.6-flash ». La preuve, en
#: passant, que ces constantes datées ne sont pas une précaution rhétorique.
MODELE_GEMINI = "gemini-3.6-flash"

#: La région décide de la juridiction, donc de la réponse à Q1 (I36). Elle n'est pas un réglage
#: de performance : la changer change ce que le rapport a le droit de conclure.
REGION_CHIRP = os.getenv("GOOGLE_STT_LOCATION", "europe-west4")

#: Ce qu'on demande à un modèle génératif pour qu'il transcrive au lieu de commenter. Un
#: modèle autorégressif obéit à l'invite ; l'invite fait donc partie du candidat mesuré, et
#: elle est en dur pour que deux exécutions se comparent.
INVITE_GEMINI = (
    "Transcris mot pour mot ce qui est prononcé dans cet audio. "
    "N'ajoute rien, ne corrige rien, ne traduis rien. "
    "Si tu n'entends aucune parole, réponds exactement : (aucune parole)."
)


# --------------------------------------------------------------------------------------
# Les candidats — l'architecture est une donnée du relevé, pas un commentaire (I35)
# --------------------------------------------------------------------------------------

AUTOREGRESSIF = "autorégressif"
CTC = "CTC"
NON_VERIFIEE = "non vérifiée"


@dataclass(frozen=True)
class Candidat:
    cle: str
    nom: str
    fournisseur: str
    architecture: str
    juridiction: str
    #: Ce que D17 prédit. Le banc l'écrit avant de mesurer, pour qu'un résultat puisse
    #: contredire une attente au lieu de la confirmer après coup.
    attendu_sur_le_vide: str


CANDIDATS = {
    "chirp": Candidat(
        "chirp",
        f"Chirp ({MODELE_CHIRP})",
        "Google Cloud Speech-to-Text v2",
        # La source qui donne Chirp comme CTC décrit Google USM (2023), pas nécessairement la
        # version commerciale servie aujourd'hui. C'est précisément ce que le banc va voir.
        NON_VERIFIEE,
        f"Google · {REGION_CHIRP}",
        "bouillie visible, si l'architecture CTC tient encore",
    ),
    "gemini": Candidat(
        "gemini",
        f"Gemini Flash ({MODELE_GEMINI})",
        "Google AI Studio",
        AUTOREGRESSIF,
        "Google · région non garantie par l'API AI Studio",
        "phrase fluide et fausse — le mode de panne de Whisper",
    ),
    "voxtral": Candidat(
        "voxtral",
        "voxtral-mini-latest",
        "Mistral",
        AUTOREGRESSIF,
        "Mistral · UE",
        "phrase fluide et fausse",
    ),
    "omniasr-ctc": Candidat(
        "omniasr-ctc",
        "omniASR-CTC-7B",
        "poids ouverts, auto-hébergé",
        CTC,
        "aucune — l'audio ne sort pas",
        "bouillie visible (D17, choix retenu D21)",
    ),
    "omniasr-llm": Candidat(
        "omniasr-llm",
        "omniASR-LLM-7B",
        "poids ouverts, auto-hébergé",
        AUTOREGRESSIF,
        "aucune — l'audio ne sort pas",
        "phrase fluide et fausse",
    ),
}


# --------------------------------------------------------------------------------------
# Les échantillons — le vide fabriqué d'abord, la voix réelle seulement sur demande
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Echantillon:
    cle: str
    quoi: str
    #: Ce qu'un transcripteur honnête devrait rendre. Sur du vide fabriqué, on le connaît :
    #: rien. C'est ce qui rend ce banc concluant là où un banc de taux d'erreur ne l'est pas
    #: sans transcription de référence faite à la main.
    verite: str
    pcm: bytes = field(repr=False)

    @property
    def secondes(self) -> float:
        return len(self.pcm) / (TAUX * LARGEUR)

    @property
    def reel(self) -> bool:
        return self.cle.startswith("culte-")


def _pcm(echantillons: list[int]) -> bytes:
    borne = [max(-32768, min(32767, int(e))) for e in echantillons]
    return array.array("h", borne).tobytes()


def _fabriquer() -> list[Echantillon]:
    """Le vide, sous les trois formes qu'un culte en produit vraiment.

    Un culte n'est pas fait de silence numérique : il est fait de blancs habités — une salle
    qui respire, un micro ouvert sur rien, une assemblée qui bouge. Un banc qui n'essaierait
    que le zéro parfait raterait le cas qui arrive quatre-vingts fois par dimanche.
    """
    alea = random.Random(20260901)  # graine datée : deux exécutions se comparent
    n = TAUX * SECONDES_MAX

    silence = [0] * n

    # Souffle de micro : le plancher de bruit d'une salle vide, très en dessous de la parole
    # (RMS relevé sur les captures réelles : 1000 à 2800).
    souffle = [alea.gauss(0, 60) for _ in range(n)]

    # Rumeur d'assemblée : un grondement basse fréquence plus un bruit de fond, sans parole.
    rumeur = []
    for i in range(n):
        t = i / TAUX
        grondement = 900 * math.sin(2 * math.pi * 82 * t) * (0.5 + 0.5 * math.sin(2 * math.pi * 0.4 * t))
        rumeur.append(grondement + alea.gauss(0, 220))

    return [
        Echantillon("vide-silence", "trente secondes de silence numérique", "", _pcm(silence)),
        Echantillon("vide-souffle", "souffle de micro, salle vide", "", _pcm(souffle)),
        Echantillon("vide-rumeur", "rumeur d'assemblée, aucune parole", "", _pcm(rumeur)),
    ]


def _captures_reelles() -> list[Echantillon]:
    """Les captures du dépôt, un fragment par échantillon.

    On prend le **premier fragment** de chaque capture, pas la capture entière : c'est l'unité
    que le téléphone écrit (D53) et elle passe en ligne dans les deux API sans découpage
    supplémentaire. La vérité de terrain est inconnue — ces échantillons ne mesurent pas un
    taux d'erreur, ils montrent ce que chaque candidat rend sur la même voix.
    """
    dossier = RACINE / "capture_audio"
    if not dossier.is_dir():
        return []
    sortie = []
    for capture in sorted(dossier.iterdir()):
        if not capture.is_dir():
            continue
        frags = sorted(capture.glob("*.pcm"))
        if not frags:
            continue
        brut = frags[0].read_bytes()[: TAUX * LARGEUR * SECONDES_MAX]
        if len(brut) < TAUX * LARGEUR * 5:  # moins de cinq secondes : rien à en tirer
            continue
        sortie.append(
            Echantillon(
                f"culte-{capture.name[:8]}",
                f"voix réelle, {frags[0].name} de la capture {capture.name[:8]}",
                "inconnue — pas de transcription de référence",
                brut,
            )
        )
    return sortie


def _wav(pcm: bytes) -> bytes:
    tampon = io.BytesIO()
    with wave.open(tampon, "wb") as f:
        f.setnchannels(CANAUX)
        f.setsampwidth(LARGEUR)
        f.setframerate(TAUX)
        f.writeframes(pcm)
    return tampon.getvalue()


# --------------------------------------------------------------------------------------
# Le relevé
# --------------------------------------------------------------------------------------


@dataclass
class Releve:
    candidat: Candidat
    echantillon: Echantillon
    texte: str
    secondes_calcul: float
    erreur: str = ""
    passe: int = 1

    @property
    def ratio_non_lettres(self) -> float:
        """La part de caractères qui ne sont ni lettre ni espace — le signal « bouillie ».

        Un CTC privé de signal rend des caractères décousus, ponctuation et fragments ; un
        décodeur autorégressif rend des phrases propres. Le ratio monte donc chez l'un et
        reste bas chez l'autre. ⚠️ Il est aveugle au cas le plus dangereux : une phrase
        française **fluide et fausse** a exactement le même ratio qu'une phrase juste. Ce
        chiffre trie les architectures, il ne juge pas une transcription.
        """
        utiles = [c for c in self.texte if not c.isspace()]
        if not utiles:
            return 0.0
        return sum(1 for c in utiles if not unicodedata.category(c).startswith("L")) / len(utiles)

    @property
    def mots(self) -> int:
        return len(self.texte.split())

    @property
    def a_parle_sur_du_vide(self) -> bool:
        """Le verdict qui compte sur un échantillon vide : le candidat a-t-il inventé ?

        La vérité de terrain est « rien ». Tout mot rendu est un mot qui n'a pas été prononcé.
        Deux ou trois caractères parasites sont du bruit de décodage ; une phrase est une
        invention. On coupe à trois mots pour ne pas confondre les deux.
        """
        return self.echantillon.verite == "" and self.mots >= 3


# --------------------------------------------------------------------------------------
# Les mesures — une fonction par candidat, jamais une pour « Google » (I34)
# --------------------------------------------------------------------------------------


def _mesurer_chirp(ech: Echantillon) -> tuple[str, str]:
    """Speech-to-Text v2, reconnaissance en ligne, modèle Chirp.

    Le mode « temps réel » existe et n'est pas mesuré ici : la transcription du culte est batch
    par construction (D6, D20), et comparer en flux ferait varier le modèle **et** le mode de
    traitement à la fois — l'écart observé ne voudrait plus rien dire (T-Rec v1.2 §2).
    """
    try:
        from google.api_core.client_options import ClientOptions
        from google.cloud import speech_v2
        from google.cloud.speech_v2.types import cloud_speech
    except ImportError:
        return "", "google-cloud-speech absent (pip install google-cloud-speech)"

    projet = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not projet:
        return "", "GOOGLE_CLOUD_PROJECT absente"

    client = speech_v2.SpeechClient(
        client_options=ClientOptions(api_endpoint=f"{REGION_CHIRP}-speech.googleapis.com")
    )
    config = cloud_speech.RecognitionConfig(
        explicit_decoding_config=cloud_speech.ExplicitDecodingConfig(
            encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=TAUX,
            audio_channel_count=CANAUX,
        ),
        # D9 — la langue est déclarée, jamais devinée. La détection automatique choisit une
        # langue par fenêtre et bascule sur un passage alterné, ce qu'un culte ivoirien fait
        # constamment.
        language_codes=["fr-FR"],
        model=MODELE_CHIRP,
    )
    reponse = client.recognize(
        request=cloud_speech.RecognizeRequest(
            recognizer=f"projects/{projet}/locations/{REGION_CHIRP}/recognizers/_",
            config=config,
            content=ech.pcm,
        )
    )
    morceaux = [
        r.alternatives[0].transcript for r in reponse.results if r.alternatives
    ]
    return " ".join(morceaux).strip(), ""


def _mesurer_gemini(ech: Echantillon) -> tuple[str, str]:
    """Gemini Flash, audio en ligne dans la requête.

    ⚠️ Ce candidat est mesuré parce qu'il est proposé, pas parce qu'il est plausible. Sa force
    annoncée — deviner le mot logique selon le contexte — est le mécanisme même que D17 range
    parmi les modes de panne dangereux. Un bon résultat ici ne dit rien du risque d'invention
    sur l'inconnu (C2).
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return "", "google-genai absent (pip install google-genai)"

    cle = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not cle:
        return "", "GEMINI_API_KEY absente"

    client = genai.Client(api_key=cle)
    reponse = client.models.generate_content(
        model=MODELE_GEMINI,
        contents=[
            types.Part.from_bytes(data=_wav(ech.pcm), mime_type="audio/wav"),
            INVITE_GEMINI,
        ],
        config=types.GenerateContentConfig(temperature=0),
    )
    return (reponse.text or "").strip(), ""


def _mesurer_voxtral(ech: Echantillon) -> tuple[str, str]:
    """Non câblé. Laissé en place pour que le banc porte les quatre candidats de S6 §9."""
    return "", "adaptateur non écrit"


def _mesurer_omniasr(ech: Echantillon) -> tuple[str, str]:
    """Non câblé — demande un GPU et les poids (S6 §9 ligne 2bis, dépend de Q1)."""
    return "", "adaptateur non écrit — demande un GPU (S6 §9 ligne 2bis)"


MESURES = {
    "chirp": _mesurer_chirp,
    "gemini": _mesurer_gemini,
    "voxtral": _mesurer_voxtral,
    "omniasr-ctc": _mesurer_omniasr,
    "omniasr-llm": _mesurer_omniasr,
}


def _mesurer(
    candidats: list[Candidat], echantillons: list[Echantillon], passes: int
) -> list[Releve]:
    """Plusieurs passes par échantillon — **la panne mesurée n'est pas déterministe.**

    Relevé le 02/09/2026 : sur trente secondes de zéros, `gemini-3.6-flash` à température 0 a
    rendu quatre textes sans rapport entre eux en quatre passes — un discours sur le numérique
    au Bénin, une consigne d'examen du DELF A2, deux phrases de dialogue. Une passe unique
    aurait pu tomber sur celle où il répond « (aucune parole) » et **innocenter un candidat qui
    invente une fois sur deux**. Une seule mesure d'une panne aléatoire n'est pas une mesure.
    """
    releves = []
    for candidat in candidats:
        print(f"\n{candidat.nom}  ·  {candidat.architecture}  ·  {candidat.juridiction}")
        for ech in echantillons:
            for passe in range(1, passes + 1):
                depart = time.monotonic()
                try:
                    texte, erreur = MESURES[candidat.cle](ech)
                except Exception as exc:  # une panne d'API est un relevé, pas un arrêt du banc
                    texte, erreur = "", f"{type(exc).__name__}: {exc}"
                releve = Releve(candidat, ech, texte, time.monotonic() - depart, erreur, passe)
                releves.append(releve)
                marque = f"{ech.cle} #{passe}"
                if erreur:
                    print(f"  {marque:<24} ⏭  {erreur}")
                    break  # un adaptateur absent le reste à la passe suivante
                rendu = texte.replace("\n", " ")[:56] or "(rien)"
                print(f"  {marque:<24} {releve.mots:>3} mots  « {rendu} »")
    return releves


# --------------------------------------------------------------------------------------
# Le rapport — l'architecture et la juridiction à côté du score, jamais en note (I35, I36)
# --------------------------------------------------------------------------------------


def _plier(texte: str, largeur: int) -> list[str]:
    """Le texte inventé s'imprime en entier : c'est la pièce à conviction, pas un aperçu."""
    lignes, courante = [], ""
    for mot in texte.split():
        if courante and len(courante) + 1 + len(mot) > largeur:
            lignes.append(courante)
            courante = mot
        else:
            courante = f"{courante} {mot}".strip()
    if courante:
        lignes.append(courante)
    return lignes or ["(rien)"]


def _rapport(releves: list[Releve]) -> None:
    mesures = [r for r in releves if not r.erreur]
    if not mesures:
        print("\nAucune mesure — aucun candidat n'a répondu. Rien à conclure.")
        _rappeler_ce_qui_manque(releves)
        return

    print("\n" + "=" * 92)
    print("  CE QUE CHAQUE CANDIDAT REND SUR DU VIDE  —  la question de D17")
    print("=" * 92)
    print("  La vérité de terrain est « rien ». Tout mot rendu est un mot jamais prononcé.\n")
    vides = [r for r in mesures if r.echantillon.verite == ""]
    print(
        f"  {'candidat':<24} {'architecture':<14} {'échantillon':<15} "
        f"{'a inventé':>10} {'mots max':>9} {'non-lettres':>12}"
    )
    print("  " + "-" * 88)
    lots: dict[tuple[str, str], list[Releve]] = {}
    for r in vides:
        lots.setdefault((r.candidat.cle, r.echantillon.cle), []).append(r)
    for lot in lots.values():
        r = lot[0]
        n = sum(1 for x in lot if x.a_parle_sur_du_vide)
        print(
            f"  {r.candidat.nom[:23]:<24} {r.candidat.architecture:<14} "
            f"{r.echantillon.cle:<15} {f'{n}/{len(lot)}':>10} "
            f"{max(x.mots for x in lot):>9} {max(x.ratio_non_lettres for x in lot) * 100:>11.1f}%"
        )

    inventions = [r for r in vides if r.a_parle_sur_du_vide]
    if inventions:
        print("\n" + "-" * 92)
        print("  CE QUI A ÉTÉ INVENTÉ, MOT POUR MOT")
        print("-" * 92)
        print("  Aucune de ces phrases n'a été prononcée. Il n'y avait rien à entendre, et l'invite")
        print("  donnait la sortie honnête : « réponds exactement : (aucune parole) ».\n")
        for r in inventions:
            print(f"  {r.candidat.nom} · {r.echantillon.cle} · passe {r.passe}")
            for ligne in _plier(r.texte, 86):
                print(f"    {ligne}")
            print()

    reels = [r for r in mesures if r.echantillon.reel]
    if reels:
        print("\n" + "=" * 92)
        print("  CE QUE CHAQUE CANDIDAT REND SUR LA VOIX RÉELLE")
        print("=" * 92)
        print("  ⚠️ Sans transcription de référence, ceci n'est PAS un taux d'erreur. On lit deux")
        print("     sorties côte à côte, on ne les note pas. Le banc de S6 §9 ligne 2 reste à faire.\n")
        for r in reels:
            print(f"  {r.candidat.nom[:30]:<32} {r.echantillon.cle}")
            print(f"    {r.texte[:200] or '(rien)'}")
            print()

    print("=" * 92)
    print("  OÙ L'AUDIO A TRANSITÉ  —  Q1 n'est pas tranchée, le banc ne la tranche pas (I36)")
    print("=" * 92)
    for candidat in {r.candidat.cle: r.candidat for r in mesures}.values():
        n = sum(1 for r in mesures if r.candidat.cle == candidat.cle)
        reel = sum(1 for r in mesures if r.candidat.cle == candidat.cle and r.echantillon.reel)
        marque = "  ← voix de pasteur" if reel else ""
        print(f"  {candidat.nom[:30]:<32} {candidat.juridiction:<42} {n:>2} envois, {reel} réels{marque}")

    print("\n" + "=" * 92)
    print("  CE QUE CE BANC NE DIT PAS")
    print("=" * 92)
    print("  · Un candidat muet ici peut inventer ailleurs. Le vide fabriqué est un cas, pas tous.")
    print("  · Un bon score ici ne dit rien du taux d'erreur sur un culte (C2).")
    print("  · Aucun résultat n'ouvre le §8 de S6 : la production se décide sur trois églises (I37).")
    _rappeler_ce_qui_manque(releves)


def _rappeler_ce_qui_manque(releves: list[Releve]) -> None:
    manques = {}
    for r in releves:
        if r.erreur:
            manques.setdefault(r.erreur, set()).add(r.candidat.nom)
    if not manques:
        return
    print("\n  Candidats non mesurés :")
    for erreur, noms in manques.items():
        print(f"    {', '.join(sorted(noms))[:50]:<52} {erreur}")


def main() -> None:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument(
        "--candidats",
        default="chirp,gemini",
        help="clés séparées par des virgules : " + ", ".join(CANDIDATS),
    )
    parseur.add_argument(
        "--passes",
        type=int,
        default=3,
        help="passes par échantillon — la panne mesurée n'est pas déterministe (défaut : 3)",
    )
    parseur.add_argument(
        "--audio-reel",
        action="store_true",
        help="envoyer aussi les captures du dépôt — des voix de pasteurs quittent la machine",
    )
    args = parseur.parse_args()

    demandes = [c for c in args.candidats.split(",") if c]
    # I34 avant tout le reste : « google » est une erreur qui mérite son propre message, pas
    # un « candidat inconnu » qui laisserait croire à une faute de frappe.
    if "google" in demandes:
        parseur.error(
            "« google » n'est pas un candidat — Chirp et Gemini Flash sont deux architectures "
            "aux modes de panne opposés, et le nom commercial masque la seule variable qui "
            "décide (I34). Choisir : chirp, gemini, ou les deux."
        )
    inconnus = [c for c in demandes if c not in CANDIDATS]
    if inconnus:
        parseur.error(f"candidat inconnu : {', '.join(inconnus)}")
    candidats = [CANDIDATS[c] for c in demandes]

    echantillons = _fabriquer()
    if args.audio_reel:
        reelles = _captures_reelles()
        if not reelles:
            print("Aucune capture dans capture_audio/ — le banc tourne sur le vide seul.")
        echantillons += reelles

    print("=" * 92)
    print("  BANC DE MESURE — TRANSCRIPTION  ·  le mode de panne, pas le taux d'erreur")
    print("=" * 92)
    print(f"  {len(candidats)} candidat(s), {len(echantillons)} échantillon(s), "
          f"{args.passes} passe(s), {sum(e.secondes for e in echantillons) * args.passes:.0f} s d'audio")
    if args.audio_reel:
        print("  ⚠️  --audio-reel : des voix réelles vont sortir de cette machine (I36, Q1).")

    _rapport(_mesurer(candidats, echantillons, args.passes))


if __name__ == "__main__":
    main()
