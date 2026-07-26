"""Sprint 4 — table de transition des statuts (domaine pur, §5.5)."""

import pytest

from app.contexts.iam.domain.enums import MembershipStatus as S
from app.contexts.iam.domain.enums import MembershipTransitionEvent as E
from app.contexts.iam.domain.errors import InvalidTransitionError, StatusSkipForbiddenError
from app.contexts.iam.domain.transitions import next_status


def test_forward_chain_one_step_at_a_time():
    assert next_status(S.INVITED, E.FIRST_ATTENDANCE_RECORDED) is S.VISITOR
    assert next_status(S.VISITOR, E.QUALIFY_SYMPATHIZER) is S.SYMPATHIZER
    assert next_status(S.SYMPATHIZER, E.QUALIFY_NEWCOMER) is S.NEWCOMER
    assert next_status(S.NEWCOMER, E.CONFIRM_MEMBER) is S.CONFIRMED_MEMBER


def test_fast_track_is_a_forbidden_skip():
    # invited → confirmed_member direct : interdit en V1.
    with pytest.raises(StatusSkipForbiddenError):
        next_status(S.INVITED, E.CONFIRM_MEMBER)
    # visitor → newcomer (saute sympathizer).
    with pytest.raises(StatusSkipForbiddenError):
        next_status(S.VISITOR, E.QUALIFY_NEWCOMER)


def test_regression_is_invalid():
    with pytest.raises(InvalidTransitionError):
        next_status(S.CONFIRMED_MEMBER, E.QUALIFY_SYMPATHIZER)


def test_out_of_chain_status_is_invalid():
    with pytest.raises(InvalidTransitionError):
        next_status(S.EXTERNAL_PARTICIPANT, E.QUALIFY_SYMPATHIZER)


def test_non_forward_event_is_invalid_here():
    # demote/close/… ne sont pas gérés par cette table (incrément cascade).
    with pytest.raises(InvalidTransitionError):
        next_status(S.NEWCOMER, E.DEMOTE)
