"""La conversion PDF — **le premier processus externe du backend**, et il est borné.

Le PDF est gardé parce que c'est le format qui circule réellement : il s'ouvre sur n'importe
quel téléphone, ne se déforme pas d'un appareil à l'autre, et se projette depuis un écran quand
il n'y a pas d'ordinateur.

> **Ce n'est pas un troisième document, c'est un troisième encodage.** On convertit le fichier
> **déjà validé** ; on ne remet pas en page.

## Pourquoi une conversion et pas un rendu natif

Écrire un troisième moteur de mise en page (`reportlab`, `fpdf2`, `weasyprint`) ferait dériver
deux rendus du même document — **et ils dériveraient en silence**. Le jour où le PDF oublie une
mise en garde que le `.docx` porte encore, personne ne le voit, et c'est la note du pasteur qui
devient fausse.

En convertissant, la propriété qui compte est acquise par construction : **le PDF ne peut pas
dire autre chose que le fichier dont il sort.**

## Ce que ce module apporte, et que le dépôt n'avait jamais eu

Aucun `subprocess` n'existait dans `app/`. Trois gardes viennent donc avec :

- **un délai maximum** — une conversion qui pend ne doit pas retenir une requête ;
- **un répertoire temporaire isolé**, effacé quoi qu'il arrive : le document d'un pasteur ne
  traîne pas sur le disque d'un serveur ;
- **une seule conversion à la fois** — `soffice` est gourmand, et une file non bornée est une
  panne mémoire un dimanche matin.

⚠️ **Un échec ne bloque rien.** Le service rend alors le format natif, avec son motif : *aucun
mur un vendredi soir*, la règle du moteur s'applique ici telle quelle.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from app.core.logging import get_logger

_logger = get_logger("urim.pdf")

#: Au-delà, on rend le format natif. Une note de préparation se convertit en quelques secondes ;
#: trente est large pour un serveur chargé, et court pour quelqu'un qui attend.
DELAI = 30

#: `soffice` tient mal la concurrence — deux instances sur le même profil se marchent dessus.
#: Un sémaphore plutôt qu'une file : ce qui attend trop longtemps rend le format natif.
_UNE_A_LA_FOIS = asyncio.Semaphore(1)

#: Le nom du binaire. Nommé ici pour qu'un déploiement puisse le remplacer sans toucher au code.
BINAIRE = "soffice"


class ConversionIndisponibleError(RuntimeError):
    """LibreOffice n'est pas là, ou n'a pas abouti.

    Une erreur nommée plutôt qu'un `OSError` nu : l'appelant doit pouvoir décider de **servir
    autre chose**, et il ne le fera que s'il reconnaît le cas."""


async def convertir_en_pdf(octets: bytes, *, extension: str) -> bytes:
    """`.docx`/`.pptx` → `.pdf`, par LibreOffice sans interface.

    ⚠️ **Le fichier passe par le disque, et le disque est nettoyé.** `soffice` ne lit pas
    l'entrée standard ; le répertoire temporaire est donc obligatoire, et son effacement l'est
    tout autant — un document de préparation est privé."""
    async with _UNE_A_LA_FOIS:
        with tempfile.TemporaryDirectory(prefix="urim-") as dossier:
            racine = Path(dossier)
            source = racine / f"livrable.{extension}"
            source.write_bytes(octets)

            try:
                processus = await asyncio.create_subprocess_exec(
                    BINAIRE,
                    "--headless",
                    # Un profil jetable par conversion : sans lui, deux appels se disputent le
                    # profil par défaut de l'utilisateur du conteneur et l'un des deux échoue.
                    f"-env:UserInstallation=file://{racine / 'profil'}",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(racine),
                    str(source),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
            except (FileNotFoundError, OSError) as exc:
                raise ConversionIndisponibleError(
                    "LibreOffice n'est pas installé : le PDF n'est pas disponible."
                ) from exc

            try:
                _, erreur = await asyncio.wait_for(processus.communicate(), DELAI)
            except TimeoutError as exc:
                processus.kill()
                raise ConversionIndisponibleError(
                    f"La conversion a dépassé {DELAI} secondes."
                ) from exc

            rendu = source.with_suffix(".pdf")
            if processus.returncode != 0 or not rendu.exists():
                _logger.warning(
                    "urim_pdf_echec",
                    code=processus.returncode,
                    erreur=(erreur or b"").decode(errors="replace")[:200],
                )
                raise ConversionIndisponibleError("La conversion PDF n'a pas abouti.")
            return rendu.read_bytes()
