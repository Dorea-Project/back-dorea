"""P1 — OtpService : émission + vérification (succès, mauvais code, expiré, verrou)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contexts.auth.application.otp_service import (
    _ISSUE_WINDOW,
    _MAX_ISSUES,
    OtpService,
)
from app.contexts.auth.application.ports import CodeGenerator, OtpSender, PasswordHasher
from app.contexts.auth.domain.errors import (
    OtpExpiredError,
    OtpInvalidError,
    OtpNotFoundError,
    OtpTooManyAttemptsError,
    OtpTooManyRequestsError,
)
from app.contexts.auth.domain.otp import MAX_ATTEMPTS, OtpChallenge, OtpChannel, OtpPurpose
from app.contexts.auth.domain.repositories import OtpChallengeRepository

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_TTL = 600


class _Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


class _FakeHasher(PasswordHasher):
    def hash(self, plain):
        return f"h:{plain}"

    def verify(self, hashed, plain):
        return hashed == f"h:{plain}"


class _FakeCodes(CodeGenerator):
    def __init__(self, code="123456"):
        self._code = code

    def generate(self):
        return self._code


class _FakeSender(OtpSender):
    def __init__(self):
        self.sent = []

    async def send(self, *, channel, target, code, purpose):
        self.sent.append({"channel": channel, "target": target, "code": code, "purpose": purpose})


class _FakeChallenges(OtpChallengeRepository):
    def __init__(self):
        self.items: list[OtpChallenge] = []

    async def add(self, challenge):
        self.items.append(challenge)

    async def count_issued_since(self, target, since):
        return sum(1 for c in self.items if c.target == target and c.created_at >= since)

    async def get_active(self, purpose, target, now):
        matches = [
            c
            for c in self.items
            if c.purpose is purpose and c.target == target and not c.is_consumed
        ]
        return matches[-1] if matches else None

    async def increment_attempts(self, challenge_id):
        for c in self.items:
            if c.id == challenge_id:
                c.attempts += 1

    async def mark_consumed(self, challenge_id, consumed_at):
        for c in self.items:
            if c.id == challenge_id:
                c.consumed_at = consumed_at


def _service(challenges, *, clock, sender=None):
    return OtpService(
        challenges,
        sender or _FakeSender(),
        _FakeHasher(),
        _FakeCodes(),
        clock=clock,
        ttl_seconds=_TTL,
    )


async def test_issue_stores_challenge_and_sends_code():
    challenges, sender = _FakeChallenges(), _FakeSender()
    svc = _service(challenges, clock=_Clock(_NOW), sender=sender)

    await svc.issue(purpose=OtpPurpose.NEW_DEVICE, channel=OtpChannel.EMAIL, target="a@b.c")

    assert len(challenges.items) == 1
    assert challenges.items[0].code_hash == "h:123456"  # hash, jamais le clair
    assert sender.sent[0]["code"] == "123456"  # envoyé en clair au destinataire
    assert sender.sent[0]["target"] == "a@b.c"


async def test_verify_consumes_on_success():
    challenges = _FakeChallenges()
    svc = _service(challenges, clock=_Clock(_NOW))
    await svc.issue(purpose=OtpPurpose.NEW_DEVICE, channel=OtpChannel.SMS, target="+225")

    result = await svc.verify(purpose=OtpPurpose.NEW_DEVICE, target="+225", code="123456")
    assert result.is_consumed  # usage unique

    # Un 2ᵉ usage du même code échoue (consommé → plus actif).
    with pytest.raises(OtpNotFoundError):
        await svc.verify(purpose=OtpPurpose.NEW_DEVICE, target="+225", code="123456")


async def test_verify_wrong_code_increments_attempts():
    challenges = _FakeChallenges()
    svc = _service(challenges, clock=_Clock(_NOW))
    await svc.issue(purpose=OtpPurpose.NEW_DEVICE, channel=OtpChannel.SMS, target="+225")

    with pytest.raises(OtpInvalidError):
        await svc.verify(purpose=OtpPurpose.NEW_DEVICE, target="+225", code="000000")
    assert challenges.items[0].attempts == 1


async def test_verify_expired_is_rejected():
    challenges = _FakeChallenges()
    clock = _Clock(_NOW)
    svc = _service(challenges, clock=clock)
    await svc.issue(purpose=OtpPurpose.NEW_DEVICE, channel=OtpChannel.SMS, target="+225")

    clock.t = _NOW + timedelta(seconds=_TTL + 1)  # au-delà du TTL
    with pytest.raises(OtpExpiredError):
        await svc.verify(purpose=OtpPurpose.NEW_DEVICE, target="+225", code="123456")


async def test_verify_locked_after_too_many_attempts():
    challenges = _FakeChallenges()
    challenges.items.append(
        OtpChallenge(
            id=uuid4(),
            purpose=OtpPurpose.NEW_DEVICE,
            channel=OtpChannel.SMS,
            target="+225",
            code_hash="h:123456",
            created_at=_NOW,
            expires_at=_NOW + timedelta(seconds=_TTL),
            attempts=MAX_ATTEMPTS,
        )
    )
    svc = _service(challenges, clock=_Clock(_NOW))
    with pytest.raises(OtpTooManyAttemptsError):
        await svc.verify(purpose=OtpPurpose.NEW_DEVICE, target="+225", code="123456")


async def test_unknown_target_raises_not_found():
    svc = _service(_FakeChallenges(), clock=_Clock(_NOW))
    with pytest.raises(OtpNotFoundError):
        await svc.verify(purpose=OtpPurpose.NEW_DEVICE, target="+225", code="123456")


# --------------------------------------------------------- DOREA-022 · plafond d'émission


async def _issue(svc, target="+2250700000001"):
    await svc.issue(purpose=OtpPurpose.NEW_DEVICE, channel=OtpChannel.SMS, target=target)


async def test_le_plafond_arrete_le_deluge_de_sms():
    """Sans plafond, réappuyer sur « renvoyer le code » fait pleuvoir des SMS sur un
    numéro : harcèlement pour la personne, facture pour l'église."""
    challenges, sender = _FakeChallenges(), _FakeSender()
    svc = _service(challenges, clock=_Clock(_NOW), sender=sender)

    for _ in range(_MAX_ISSUES):
        await _issue(svc)
    assert len(sender.sent) == _MAX_ISSUES

    with pytest.raises(OtpTooManyRequestsError):
        await _issue(svc)
    assert len(sender.sent) == _MAX_ISSUES  # rien de plus n'est parti


async def test_le_plafond_est_par_contact():
    """Le voisin n'est pas puni parce qu'un numéro a été martelé."""
    challenges = _FakeChallenges()
    svc = _service(challenges, clock=_Clock(_NOW))
    for _ in range(_MAX_ISSUES):
        await _issue(svc, "+2250700000001")

    await _issue(svc, "+2250700000002")  # ne lève pas


async def test_le_plafond_se_desserre_avec_le_temps():
    """C'est une fenêtre glissante, pas un bannissement."""
    challenges = _FakeChallenges()
    clock = _Clock(_NOW)
    svc = _service(challenges, clock=clock)
    for _ in range(_MAX_ISSUES):
        await _issue(svc)

    clock.t = _NOW + _ISSUE_WINDOW + timedelta(minutes=1)
    await _issue(svc)  # ne lève pas
