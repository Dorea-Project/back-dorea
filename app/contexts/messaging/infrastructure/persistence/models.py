"""Modèles ORM de la messagerie — l'acheminement et le refus.

Deux tables, et ce qu'elles ne contiennent pas compte autant que ce qu'elles
contiennent.

**`messaging_deliveries`** — le sort d'un message. Ni le numéro, ni le contenu :
`message_id` est notre identifiant, et il suffit à répondre à la seule question
qu'on pose ici — « le code est-il arrivé ? ». Un journal d'acheminement qui
garderait les numéros deviendrait un annuaire des membres avec l'heure de leurs
codes.

**`messaging_opt_outs`** — qui a dit stop. Le numéro y est, lui, et ne peut pas
en sortir : c'est la clé de vérification avant tout envoi, et la preuve du refus
le jour où quelqu'un demandera pourquoi il ne reçoit plus rien.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DeliveryModel(Base):
    __tablename__ = "messaging_deliveries"

    __table_args__ = (
        # Le seul accès non trivial : retrouver un accusé par l'identifiant du
        # fournisseur, quand c'est lui qui parle en premier.
        Index("ix_messaging_deliveries_provider", "provider_message_id"),
    )

    #: Notre identifiant, transmis au fournisseur à l'envoi. Clé primaire :
    #: deux accusés pour le même message se remplacent, ils ne s'empilent pas.
    message_id: Mapped[str] = mapped_column(String, primary_key=True)

    channel: Mapped[str] = mapped_column(String)

    #: Pourquoi le message est parti (`new_device`, `mobile_registration`…).
    #: Suffit au diagnostic sans rien dire du destinataire.
    purpose: Mapped[str] = mapped_column(String)

    provider_message_id: Mapped[str | None] = mapped_column(String, nullable=True)

    #: Dernier état connu : `accepted`, `delivered`, `read`, `failed`.
    status: Mapped[str] = mapped_column(String)

    #: Code d'erreur du fournisseur, quand il y en a un.
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OptOutModel(Base):
    __tablename__ = "messaging_opt_outs"

    #: Numéro international sans `+`, tel qu'il arrive du fournisseur.
    phone_number: Mapped[str] = mapped_column(String, primary_key=True)

    #: Le canal sur lequel le refus a été exprimé. Un STOP par WhatsApp ne dit
    #: rien du SMS — mais avec un numéro unique pour toute la plateforme, il
    #: vaut pour toutes les églises.
    channel: Mapped[str] = mapped_column(String)

    #: Le mot reçu, conservé tel quel : c'est la preuve du refus.
    keyword: Mapped[str] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
