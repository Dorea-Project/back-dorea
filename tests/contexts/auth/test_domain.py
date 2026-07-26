"""Tests du domaine Auth."""

import pytest

from app.contexts.auth.domain.errors import InvalidSecretCodeFormatError
from app.contexts.auth.domain.secret_code import SecretCode


class TestSecretCode:
    def test_accepts_4_to_6_digits(self):
        assert SecretCode("1234").value == "1234"
        assert SecretCode(" 123456 ").value == "123456"

    @pytest.mark.parametrize("bad", ["123", "1234567", "abcd", "12a4", ""])
    def test_rejects_invalid(self, bad):
        with pytest.raises(InvalidSecretCodeFormatError):
            SecretCode(bad)

    def test_str_is_masked(self):
        assert str(SecretCode("1234")) == "******"
