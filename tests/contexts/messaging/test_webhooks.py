"""Webhooks Infobip : lecture des accuses, refus (STOP), et garde de la route."""

from datetime import UTC, datetime

import pytest

from app.contexts.messaging.application.inbound import InboundMessage
from app.contexts.messaging.domain.enums import Channel
from app.contexts.messaging.interface.schemas import (
    InfobipInboundBatch,
    InfobipReportBatch,
)


# --- Lecture des accuses ----------------------------------------------------


def test_a_successful_report_is_not_read_as_a_failure():
    """Infobip renvoie toujours un bloc `error` : NO_ERROR n'est pas une panne."""
    batch = InfobipReportBatch.model_validate(
        {
            "results": [
                {
                    "messageId": "notre-id",
                    "status": {"groupId": 3, "name": "DELIVERED_TO_HANDSET"},
                    "error": {"name": "NO_ERROR", "description": "No Error"},
                    "doneAt": "2026-08-16T00:10:00.000+0000",
                }
            ]
        }
    )

    report = batch.reports()[0]

    assert report.message_id == "notre-id"
    assert report.status == "delivered_to_handset"
    assert report.error_code is None
    assert report.is_failure is False


def test_a_real_failure_carries_its_reason():
    batch = InfobipReportBatch.model_validate(
        {
            "results": [
                {
                    "messageId": "notre-id",
                    "status": {"groupId": 5, "name": "REJECTED_NOT_ENOUGH_CREDITS"},
                    "error": {
                        "name": "EC_NOT_ENOUGH_CREDITS",
                        "description": "Not enough credits",
                    },
                }
            ]
        }
    )

    report = batch.reports()[0]

    assert report.is_failure is True
    assert report.error_code == "EC_NOT_ENOUGH_CREDITS"


def test_unknown_fields_do_not_break_the_reading():
    """Le fournisseur ajoute des champs sans prevenir : ca ne doit rien casser."""
    batch = InfobipReportBatch.model_validate(
        {
            "results": [
                {
                    "messageId": "notre-id",
                    "status": {"groupId": 3, "name": "DELIVERED"},
                    "champInconnu": {"encore": "un autre"},
                }
            ],
            "autreChamp": 42,
        }
    )

    assert batch.reports()[0].message_id == "notre-id"


def test_a_report_without_our_id_is_dropped():
    batch = InfobipReportBatch.model_validate(
        {"results": [{"status": {"groupId": 3, "name": "DELIVERED"}}]}
    )

    assert batch.reports() == []


# --- Messages entrants ------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["STOP", "stop", " Stop ", "STOP !", "arrêt", "Desabonner", "unsubscribe"],
)
def test_every_way_of_saying_stop_is_understood(text):
    message = InboundMessage(from_number="2250747769069", text=text)

    assert message.asks_to_stop is True


def test_a_normal_message_is_not_a_refusal():
    message = InboundMessage(from_number="2250747769069", text="Bonjour pasteur")

    assert message.asks_to_stop is False
    assert message.asks_to_resume is False


def test_start_lifts_the_refusal():
    assert InboundMessage(from_number="225", text="START").asks_to_resume is True


def test_a_photo_is_not_a_word():
    """Sans texte, aucune parole : on ne fabrique pas un message vide."""
    batch = InfobipInboundBatch.model_validate(
        {
            "results": [
                {
                    "from": "2250747769069",
                    "message": {"type": "IMAGE", "url": "https://…"},
                }
            ]
        }
    )

    assert batch.messages() == []


def test_an_inbound_text_is_read():
    batch = InfobipInboundBatch.model_validate(
        {
            "results": [
                {
                    "from": "2250747769069",
                    "receivedAt": "2026-08-16T00:10:00.000+0000",
                    "message": {"type": "TEXT", "text": "STOP"},
                }
            ]
        }
    )

    message = batch.messages()[0]

    assert message.from_number == "2250747769069"
    assert message.channel is Channel.WHATSAPP
    assert message.asks_to_stop is True
    assert message.received_at == datetime(2026, 8, 16, 0, 10, tzinfo=UTC)
