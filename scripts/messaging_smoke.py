"""Envoi reel d'un code, par le chemin de production.

Ne rejoue pas l'exemple du fournisseur : passe par `build_otp_sender`, donc par
le meme code que la connexion mobile — aiguillage, modele, repli SMS compris.
C'est le seul moyen de verifier que ce qui est branche fonctionne, et pas
seulement que l'API repond.

    python scripts/messaging_smoke.py --to +2250747769069
    python scripts/messaging_smoke.py --to +2250747769069 --code 424242

Le code s'affiche ici parce que c'est un essai mene a la main. Le code de
l'application, lui, ne le journalise jamais.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.contexts.auth.domain.otp import OtpChannel, OtpPurpose
from app.contexts.auth.infrastructure.otp_delivery import build_otp_sender
from app.contexts.messaging.domain.errors import MessagingError
from app.core.config import get_settings


async def main() -> int:
    parser = argparse.ArgumentParser(description="Envoi reel d'un code de test.")
    parser.add_argument("--to", required=True, help="Numero, format +225...")
    parser.add_argument("--code", default="123456", help="Code a envoyer")
    args = parser.parse_args()

    settings = get_settings()

    print(f"hote      : {settings.infobip_base_url}")
    print(f"emetteur  : {settings.whatsapp_sender}")
    print(f"modele    : {settings.whatsapp_otp_template} ({settings.whatsapp_otp_language})")
    print(f"messagerie: {'branchee' if settings.messaging_enabled else 'JOURNAL (rien ne partira)'}")
    print(f"vers      : {args.to}")
    print(f"code      : {args.code}")
    print()

    sender = build_otp_sender(settings)

    try:
        await sender.send(
            channel=OtpChannel.SMS,
            target=args.to,
            code=args.code,
            purpose=OtpPurpose.NEW_DEVICE,
        )
    except MessagingError as e:
        # Les deux erreurs ne se traitent pas pareil : l'une se rejoue, l'autre
        # demande de corriger le message ou le destinataire.
        print(f"ECHEC [{e.code}] {e.message}")
        if e.details:
            print(f"       details : {e.details}")
        return 1

    print("ACCEPTE par le fournisseur.")
    print("Le sort reel (remis / lu / echoue) arrive par accuse de reception —")
    print("les webhooks sont l'etape 2 : pour l'instant, regarde le telephone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
