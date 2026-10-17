"""Error types every integration raises. The job runner maps them to job states — never to a fake success."""


class IntegrationError(Exception):
    """Base class."""


class NotConfigured(IntegrationError):
    """Credentials / settings missing. Job → blocked ("Chưa cấu hình"), resumes once configured."""

    def __init__(self, service: str, missing: list[str]):
        self.service, self.missing = service, missing
        super().__init__(f"Chưa cấu hình {service}: thiếu {', '.join(missing)}")


class NotAvailable(IntegrationError):
    """The official API does not document / allow this operation. Job → blocked ("Chưa khả dụng")."""

    def __init__(self, service: str, reason: str):
        self.service, self.reason = service, reason
        super().__init__(f"Chưa khả dụng ({service}): {reason}")


class Transient(IntegrationError):
    """Network error, 429, 5xx… Retried with backoff."""

    def __init__(self, message: str, retry_after: float | None = None):
        self.retry_after = retry_after
        super().__init__(message)


class Permanent(IntegrationError):
    """The service refused the request in a way a retry will not fix (4xx, API error status). Job → failed."""


class Conflict(IntegrationError):
    """Target cell already filled by someone else — never overwritten."""


class Waiting(Transient):
    """Something outside is still in progress (DNS propagation, AutoSSL). Checked again later without using up a retry;
    the step that raises it keeps its own deadline in the job state and fails with Permanent when it is reached."""


def wait_or_fail(state: dict, key: str, hours: float, message: str, retry_after: float):
    """Raise Waiting until `hours` after the first wait recorded under state[key], then Permanent."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    since = datetime.fromisoformat(state.setdefault(key, now.isoformat()))
    waited = (now - since).total_seconds() / 3600
    if waited >= hours:
        raise Permanent(f"{message} — đã chờ {waited:.1f} giờ, quá hạn {hours:g} giờ")
    raise Waiting(f"{message} (đã chờ {int(waited * 60)} phút / tối đa {hours:g} giờ)", retry_after)
