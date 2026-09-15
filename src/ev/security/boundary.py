from contextlib import contextmanager

from ev.config import Settings


class PersonalOnlyError(Exception):
    pass


def assert_personal_only(config: Settings) -> None:
    if not config.personal_only:
        raise PersonalOnlyError("EV is configured in personal-only mode; personal_only must be True")


@contextmanager
def personal_only_guard(config: Settings):
    assert_personal_only(config)
    yield


class Blocklist:
    def __init__(self, work_handles=None, work_domains=None):
        self.work_handles = set(work_handles or [])
        self.work_domains = set(work_domains or [])

    def is_blocked_repo(self, url_or_name: str) -> bool:
        lower = url_or_name.lower()
        for handle in self.work_handles:
            if handle.lower() in lower:
                return True
        return False

    def is_blocked_account(self, handle_or_email: str) -> bool:
        lower = handle_or_email.lower()
        for domain in self.work_domains:
            if domain.lower() in lower:
                return True
        for handle in self.work_handles:
            if handle.lower() in lower:
                return True
        return False
