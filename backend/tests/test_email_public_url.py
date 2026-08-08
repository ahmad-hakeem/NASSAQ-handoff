"""Email public-URL audit — recipient-facing links must never be localhost.

Contract under test (task: email link generation audit):

1. ``config.get_public_app_url()`` is the single source of truth for the
   public base URL used in every outbound email link. Resolution order:
   ``APP_URL`` → ``FRONTEND_URL`` → Replit-managed public domains
   (``REPLIT_DEPLOYMENT_URL`` → ``REPLIT_DOMAINS`` → ``REPLIT_DEV_DOMAIN``).
2. In non-development environments (production/staging) a missing or
   clearly non-public value (localhost, loopback, 0.0.0.0, .local) raises
   ``PublicUrlConfigError`` with an operator-facing message.
3. ``config.validate()`` performs the same check at startup so the app
   refuses to boot in production instead of silently sending broken links.
4. Runtime safety belt: email senders abort the send (return False, no
   provider call) when the resolved base — or a caller-supplied link —
   is non-public in a non-development environment.
5. Development keeps the localhost fallback (no real recipients).
"""

import pytest

import config as config_module
from config import NassaqConfig


ENV_VARS = (
    "APP_URL",
    "FRONTEND_URL",
    "REPLIT_DEPLOYMENT_URL",
    "REPLIT_DOMAINS",
    "REPLIT_DEV_DOMAIN",
)


@pytest.fixture
def clean_url_env(monkeypatch):
    """Remove every base-URL env var so each test builds its own matrix."""
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


# ---------------------------------------------------------------------------
# 1. Resolution order
# ---------------------------------------------------------------------------

def test_app_url_wins_and_trailing_slash_stripped(clean_url_env):
    clean_url_env.setenv("APP_URL", "https://nassaqapp.com/")
    clean_url_env.setenv("FRONTEND_URL", "https://other.example.com")
    assert config_module.get_public_app_url(environment="production") == "https://nassaqapp.com"


def test_frontend_url_is_read_when_app_url_missing(clean_url_env):
    clean_url_env.setenv("FRONTEND_URL", "https://nassaqapp.com")
    assert config_module.get_public_app_url(environment="production") == "https://nassaqapp.com"


def test_replit_domains_fallback_gets_https_scheme(clean_url_env):
    clean_url_env.setenv("REPLIT_DOMAINS", "myapp.replit.app,other.replit.app")
    assert config_module.get_public_app_url(environment="production") == "https://myapp.replit.app"


def test_replit_dev_domain_fallback(clean_url_env):
    clean_url_env.setenv("REPLIT_DEV_DOMAIN", "abc123.worf.replit.dev")
    assert config_module.get_public_app_url(environment="production") == "https://abc123.worf.replit.dev"


# ---------------------------------------------------------------------------
# 2. Fail-loud in non-development environments
# ---------------------------------------------------------------------------

def test_production_missing_config_raises_operator_message(clean_url_env):
    with pytest.raises(config_module.PublicUrlConfigError) as exc:
        config_module.get_public_app_url(environment="production")
    msg = str(exc.value)
    assert "APP_URL" in msg  # names the canonical variable for the operator


def test_staging_missing_config_raises(clean_url_env):
    with pytest.raises(config_module.PublicUrlConfigError):
        config_module.get_public_app_url(environment="staging")


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://localhost:5000",
        "https://localhost",
        "http://127.0.0.1:8000",
        "http://0.0.0.0:5000",
        "http://[::1]:5000",
        "https://myhost.local",
        "http://backend:8000",
        "http://10.0.0.5:5000",
        "http://192.168.1.10",
        "http://172.16.0.9:5000",
    ],
)
def test_production_rejects_non_public_values(clean_url_env, bad_url):
    clean_url_env.setenv("APP_URL", bad_url)
    with pytest.raises(config_module.PublicUrlConfigError):
        config_module.get_public_app_url(environment="production")


def test_production_rejects_non_http_scheme(clean_url_env):
    clean_url_env.setenv("APP_URL", "ftp://nassaqapp.com")
    with pytest.raises(config_module.PublicUrlConfigError):
        config_module.get_public_app_url(environment="production")


# ---------------------------------------------------------------------------
# 3. Development keeps a harmless fallback
# ---------------------------------------------------------------------------

def test_development_falls_back_to_localhost(clean_url_env):
    assert config_module.get_public_app_url(environment="development") == "http://localhost:5000"


def test_development_accepts_explicit_localhost(clean_url_env):
    clean_url_env.setenv("APP_URL", "http://localhost:3000")
    assert config_module.get_public_app_url(environment="development") == "http://localhost:3000"


# ---------------------------------------------------------------------------
# 4. Startup validation (config.validate) fails the boot in production
# ---------------------------------------------------------------------------

def test_config_validate_raises_in_production_when_url_missing(clean_url_env):
    clean_url_env.setattr(NassaqConfig, "ENVIRONMENT", "production")
    with pytest.raises(ValueError) as exc:
        NassaqConfig.validate()
    assert "APP_URL" in str(exc.value)


def test_config_validate_raises_in_production_on_localhost(clean_url_env):
    clean_url_env.setattr(NassaqConfig, "ENVIRONMENT", "production")
    clean_url_env.setenv("APP_URL", "http://localhost:5000")
    with pytest.raises(ValueError):
        NassaqConfig.validate()


def test_config_validate_passes_in_production_with_public_url(clean_url_env):
    clean_url_env.setattr(NassaqConfig, "ENVIRONMENT", "production")
    clean_url_env.setenv("APP_URL", "https://nassaqapp.com")
    issues = NassaqConfig.validate()
    assert isinstance(issues, list)


def test_config_validate_lenient_in_development(clean_url_env):
    clean_url_env.setattr(NassaqConfig, "ENVIRONMENT", "development")
    issues = NassaqConfig.validate()
    assert isinstance(issues, list)


# ---------------------------------------------------------------------------
# 5. Runtime safety belt in the email senders
# ---------------------------------------------------------------------------

@pytest.fixture
def resend_spy(monkeypatch):
    """Pretend Resend is configured and capture every send call."""
    import engines.email_service as email_service

    calls = []

    def _capture(payload):
        calls.append(payload)
        return {"id": "test-email-id"}

    monkeypatch.setattr(email_service, "RESEND_API_KEY", "test-key")
    monkeypatch.setattr(email_service.resend.Emails, "send", staticmethod(_capture))
    return calls


def test_password_reset_email_uses_public_base(clean_url_env, resend_spy):
    from engines.email_service import send_password_reset_email

    clean_url_env.setenv("ENVIRONMENT", "production")
    clean_url_env.setenv("APP_URL", "https://nassaqapp.com")

    ok = send_password_reset_email("user@example.com", "مستخدم", "tok-abc-123")
    assert ok is True
    assert len(resend_spy) == 1
    html = resend_spy[0]["html"]
    assert "https://nassaqapp.com/reset-password?token=tok-abc-123" in html
    assert "localhost" not in html


def test_password_reset_email_aborts_on_localhost_base_in_production(clean_url_env, resend_spy):
    from engines.email_service import send_password_reset_email

    clean_url_env.setenv("ENVIRONMENT", "production")
    clean_url_env.setenv("APP_URL", "http://localhost:5000")

    ok = send_password_reset_email("user@example.com", "مستخدم", "tok-abc-123")
    assert ok is False
    assert resend_spy == []  # send was never attempted


def test_password_reset_email_aborts_when_config_missing_in_production(clean_url_env, resend_spy):
    from engines.email_service import send_password_reset_email

    clean_url_env.setenv("ENVIRONMENT", "production")

    ok = send_password_reset_email("user@example.com", "مستخدم", "tok-abc-123")
    assert ok is False
    assert resend_spy == []


def test_workspace_archived_email_aborts_on_localhost_base_in_production(clean_url_env, resend_spy):
    from engines.email_service import send_workspace_archived_email

    clean_url_env.setenv("ENVIRONMENT", "production")
    clean_url_env.setenv("APP_URL", "http://localhost:5000")

    ok = send_workspace_archived_email(
        "user@example.com", "مستخدم", "مساحتي", "2026-08-01", 30,
    )
    assert ok is False
    assert resend_spy == []


def test_parent_invitation_email_rejects_localhost_link_in_production(clean_url_env, resend_spy):
    from engines.email_service import send_parent_invitation_email

    clean_url_env.setenv("ENVIRONMENT", "production")

    ok = send_parent_invitation_email(
        to_email="parent@example.com",
        parent_name="ولي الأمر",
        teacher_name="المعلم",
        student_name="الطالب",
        invite_link="http://localhost:5000/parent-invitations/accept?token=raw",
    )
    assert ok is False
    assert resend_spy == []


def test_parent_invitation_email_sends_with_public_link(clean_url_env, resend_spy):
    from engines.email_service import send_parent_invitation_email

    clean_url_env.setenv("ENVIRONMENT", "production")

    ok = send_parent_invitation_email(
        to_email="parent@example.com",
        parent_name="ولي الأمر",
        teacher_name="المعلم",
        student_name="الطالب",
        invite_link="https://nassaqapp.com/parent-invitations/accept?token=raw",
    )
    assert ok is True
    assert len(resend_spy) == 1
    assert "https://nassaqapp.com/parent-invitations/accept?token=raw" in resend_spy[0]["html"]


def test_mfa_otp_email_has_no_links_and_still_sends(clean_url_env, resend_spy):
    """The OTP mail embeds no URL — it must keep working with no URL config."""
    from engines.email_service import send_mfa_email_otp

    clean_url_env.setenv("ENVIRONMENT", "production")

    ok = send_mfa_email_otp("user@example.com", "مستخدم", "123456")
    assert ok is True
    assert len(resend_spy) == 1
    assert "localhost" not in resend_spy[0]["html"]
