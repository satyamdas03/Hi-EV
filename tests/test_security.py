import pytest

from ev.config import Settings
from ev.security.boundary import (
    Blocklist,
    PersonalOnlyError,
    assert_personal_only,
    personal_only_guard,
)


def test_assert_personal_only_raises_when_false():
    config = Settings(personal_only=False)
    with pytest.raises(PersonalOnlyError):
        assert_personal_only(config)


def test_blocklist_flags_work_repos():
    bl = Blocklist(work_handles=["financialsimplicity"], work_domains=["financialsimplicity.com"])
    assert bl.is_blocked_repo("https://github.com/financialsimplicity/secret-repo")
    assert bl.is_blocked_repo("https://github.com/acme-corp/secret-repo") is False
    assert bl.is_blocked_account("someone@financialsimplicity.com")


def test_personal_only_guard_accepts_true():
    config = Settings(personal_only=True)
    with personal_only_guard(config):
        pass  # should not raise
