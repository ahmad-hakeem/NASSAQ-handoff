import os
import logging
from html import escape as _h
import resend

from services.email_client import deliver_resend_email

logger = logging.getLogger("nassaq.email")

from config import (
    PublicUrlConfigError,
    get_public_app_url,
    is_dev_environment,
    is_public_base_url,
)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "noreply@nassaqapp.com")

LOGO_URL = "https://customer-assets.emergentagent.com/job_f5ea20bb-5cf5-462f-a7f0-958201e27f89/artifacts/q04svb5j_Nassaq%20LinkedIn%20Logo%20White.png"


def _get_app_url() -> str:
    """Public base URL for every recipient-facing link.

    Delegates to the centralized, validated resolver in ``config``.
    Raises :class:`PublicUrlConfigError` in non-development environments
    when the configuration is missing or points at localhost — callers
    that send email must go through :func:`_safe_link_base` instead so
    the send is aborted loudly rather than crashing the request.
    """
    return get_public_app_url()


def _safe_link_base(email_kind: str):
    """Runtime safety belt: resolve the link base or abort the send.

    Returns the validated base URL, or ``None`` when the configuration
    is invalid — in which case the caller MUST NOT send the email.
    """
    try:
        return _get_app_url()
    except PublicUrlConfigError as e:
        logger.critical(
            f"EMAIL SEND BLOCKED ({email_kind}): recipient-facing link base is "
            f"misconfigured — {e}"
        )
        return None


def send_password_reset_email(to_email: str, user_name: str, reset_token: str) -> bool:
    if not RESEND_API_KEY:
        logger.error("RESEND_API_KEY not configured — cannot send password reset email")
        return False

    base = _safe_link_base("password_reset")
    if base is None:
        return False

    resend.api_key = RESEND_API_KEY
    reset_link = f"{base}/reset-password?token={reset_token}"

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:'Segoe UI',Tahoma,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:40px 0;">
    <tr><td align="center">
      <table width="500" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:linear-gradient(135deg,#1a1f36 0%,#2d3561 100%);padding:32px;text-align:center;">
            <img src="{LOGO_URL}" alt="NASSAQ" width="160" style="margin-bottom:8px;" />
            <p style="color:#64d9d6;font-size:14px;margin:0;">منصة إدارة المدارس الذكية</p>
          </td>
        </tr>
        <tr>
          <td style="padding:32px;">
            <h2 style="color:#1a1f36;font-size:20px;margin:0 0 16px;">إعادة تعيين كلمة المرور</h2>
            <p style="color:#555;font-size:15px;line-height:1.8;margin:0 0 24px;">
              مرحباً {user_name}،<br/>
              تلقينا طلباً لإعادة تعيين كلمة المرور الخاصة بحسابك. اضغط على الزر أدناه لتعيين كلمة مرور جديدة.
            </p>
            <div style="text-align:center;margin:32px 0;">
              <a href="{reset_link}" style="display:inline-block;background:linear-gradient(135deg,#64d9d6,#36b5b0);color:#1a1f36;font-weight:bold;font-size:16px;padding:14px 40px;border-radius:12px;text-decoration:none;">
                تعيين كلمة مرور جديدة
              </a>
            </div>
            <div style="background:#f8f9fb;border-radius:12px;padding:16px;margin:24px 0;">
              <p style="color:#888;font-size:13px;margin:0;line-height:1.8;">
                ⏰ هذا الرابط صالح لمدة <strong>ساعة واحدة</strong> فقط.<br/>
                🔒 إذا لم تطلب إعادة التعيين، تجاهل هذا الإيميل.
              </p>
            </div>
            <hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />
            <p style="color:#aaa;font-size:12px;text-align:center;margin:0;">
              نَسَّق &copy; {2026} — جميع الحقوق محفوظة
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    try:
        result = deliver_resend_email({
            "from": f"نَسَّق NASSAQ <{FROM_EMAIL}>",
            "to": [to_email],
            "subject": "إعادة تعيين كلمة المرور — نَسَّق",
            "html": html,
        }, kind="password_reset")
        logger.info(f"Password reset email sent to {to_email}, id={result.get('id', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send password reset email to {to_email}: {e}")
        return False


def send_mfa_email_otp(to_email: str, user_name: str, code: str, expires_in_minutes: int = 10) -> bool:
    """Send the 6-digit one-time MFA code to the user's mailbox.

    Returns True if the email provider accepted the message. The handler
    that calls this MUST ignore False and continue with the verify flow
    so the OTP row is still consumable from the user's recovery devices
    (e.g. they can read the code from their backup mail). Logs the
    failure for ops to investigate.
    """
    if not RESEND_API_KEY:
        logger.error("RESEND_API_KEY not configured — cannot send MFA OTP email")
        return False

    resend.api_key = RESEND_API_KEY
    # HTML-escape the display name — full_name is user-controlled and is
    # interpolated into a Resend HTML body (no auto-escaping). Without
    # this, an attacker who set their own full_name to malicious HTML
    # would receive a malformed/styled message in their own inbox; not
    # a privilege issue, but it would break the layout for everyone.
    safe_name = _h(user_name or to_email, quote=True)
    pretty_code = f"{code[0:3]} {code[3:6]}" if len(code) == 6 else code

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:'Segoe UI',Tahoma,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:40px 0;">
    <tr><td align="center">
      <table width="500" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:linear-gradient(135deg,#1a1f36 0%,#2d3561 100%);padding:32px;text-align:center;">
            <img src="{LOGO_URL}" alt="NASSAQ" width="160" style="margin-bottom:8px;" />
            <p style="color:#64d9d6;font-size:14px;margin:0;">منصة إدارة المدارس الذكية</p>
          </td>
        </tr>
        <tr>
          <td style="padding:32px;">
            <h2 style="color:#1a1f36;font-size:20px;margin:0 0 8px;">رمز تسجيل الدخول</h2>
            <p style="color:#888;font-size:13px;margin:0 0 24px;">Sign-in verification code</p>
            <p style="color:#555;font-size:15px;line-height:1.8;margin:0 0 16px;">
              مرحباً {safe_name}،<br/>
              استخدم الرمز التالي لإكمال تسجيل الدخول إلى حسابك في نَسَّق:
            </p>
            <div style="background:#f8f9fb;border:1px solid #e7e9f0;border-radius:14px;padding:24px;margin:16px 0;text-align:center;">
              <div style="color:#1a1f36;font-size:34px;letter-spacing:10px;font-weight:bold;font-family:'Courier New',monospace;direction:ltr;">{pretty_code}</div>
              <div style="color:#888;font-size:12px;margin-top:8px;direction:ltr;">Your verification code</div>
            </div>
            <div style="background:#fff7ed;border-radius:12px;padding:16px;margin:24px 0;">
              <p style="color:#92400e;font-size:13px;margin:0;line-height:1.8;">
                ⏰ صالح لمدة <strong>{expires_in_minutes} دقائق</strong> فقط — Valid for {expires_in_minutes} minutes.<br/>
                🔒 إذا لم تطلب تسجيل الدخول، تجاهل هذا الإيميل وقم بتغيير كلمة المرور فوراً.
              </p>
            </div>
            <hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />
            <p style="color:#aaa;font-size:12px;text-align:center;margin:0;">
              نَسَّق &copy; {2026} — جميع الحقوق محفوظة
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    try:
        result = deliver_resend_email({
            "from": f"نَسَّق NASSAQ <{FROM_EMAIL}>",
            "to": [to_email],
            "subject": f"رمز التحقق: {code} — نَسَّق",
            "html": html,
        }, kind="mfa_email_otp")
        logger.info(f"MFA OTP email sent to {to_email}, id={result.get('id', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send MFA OTP email to {to_email}: {e}")
        return False


def send_workspace_archived_email(
    to_email: str,
    user_name: str,
    workspace_name: str,
    reactivation_deadline: str,
    reactivation_window_days: int = 30,
    download_url: str = "",
    download_expires_at: str = "",
) -> bool:
    """Notify the Independent-Teacher that their workspace has been
    archived (soft-deleted) and that their data was downloaded to their
    browser during the archive flow. Includes the reactivation deadline.
    Best-effort: returns False if Resend is not configured or rejects
    the message — the caller MUST NOT undo the archive on a False return.
    """
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured — skipping workspace archived email")
        return False

    base = _safe_link_base("workspace_archived")
    if base is None:
        return False

    resend.api_key = RESEND_API_KEY
    safe_name = _h(user_name or to_email, quote=True)
    safe_workspace = _h(workspace_name or "", quote=True)
    safe_deadline = _h(reactivation_deadline, quote=True)

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:'Segoe UI',Tahoma,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:linear-gradient(135deg,#1a1f36 0%,#2d3561 100%);padding:32px;text-align:center;">
            <img src="{LOGO_URL}" alt="NASSAQ" width="160" style="margin-bottom:8px;" />
            <p style="color:#64d9d6;font-size:14px;margin:0;">منصة إدارة المدارس الذكية</p>
          </td>
        </tr>
        <tr>
          <td style="padding:32px;">
            <h2 style="color:#1a1f36;font-size:20px;margin:0 0 8px;">تم أرشفة مساحة عملك</h2>
            <p style="color:#888;font-size:13px;margin:0 0 24px;">Your workspace has been archived</p>
            <p style="color:#555;font-size:15px;line-height:1.8;margin:0 0 16px;">
              مرحباً {safe_name}،<br/>
              تم أرشفة مساحة العمل <strong>{safe_workspace}</strong> بناءً على طلبك.
              لن تتمكّن من تسجيل الدخول إليها حتى يتم استرجاعها.
            </p>
            <div style="background:#f8f9fb;border-radius:12px;padding:20px;margin:20px 0;">
              <p style="color:#1a1f36;font-size:14px;margin:0 0 8px;font-weight:bold;">📥 نسخة البيانات المُصدَّرة</p>
              <p style="color:#666;font-size:13px;margin:0;line-height:1.7;">
                تم تنزيل نسخة كاملة من بياناتك تلقائياً إلى متصفحك عند تأكيد الأرشفة.
                إذا لم يكتمل التنزيل، يمكنك تسجيل الدخول لإعادة تفعيل مساحتك وتصدير البيانات مجدداً.
              </p>
            </div>
            <div style="background:#fff7ed;border-radius:12px;padding:16px;margin:20px 0;">
              <p style="color:#92400e;font-size:14px;margin:0;line-height:1.8;">
                ⏳ <strong>مهلة الاسترجاع:</strong> لديك {reactivation_window_days} يوماً لاسترجاع المساحة.<br/>
                آخر موعد للاسترجاع: <strong>{safe_deadline}</strong>.<br/>
                بعد هذا التاريخ ستُحذف بياناتك نهائياً ولا يمكن استرجاعها.
              </p>
            </div>
            <div style="text-align:center;margin:24px 0;">
              <a href="{base}/login" style="display:inline-block;background:#1a1f36;color:#ffffff;font-weight:bold;font-size:14px;padding:12px 28px;border-radius:10px;text-decoration:none;">
                تسجيل الدخول للاسترجاع
              </a>
            </div>
            <hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />
            <p style="color:#aaa;font-size:12px;text-align:center;margin:0;">
              نَسَّق &copy; {2026} — جميع الحقوق محفوظة
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    try:
        result = deliver_resend_email({
            "from": f"نَسَّق NASSAQ <{FROM_EMAIL}>",
            "to": [to_email],
            "subject": "تم أرشفة مساحة عملك — نَسَّق",
            "html": html,
        }, kind="workspace_archived")
        logger.info(f"Workspace archived email sent to {to_email}, id={result.get('id', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send workspace archived email to {to_email}: {e}")
        return False


def send_workspace_reactivation_reminder_email(
    to_email: str,
    user_name: str,
    workspace_name: str,
    reactivation_deadline: str,
    days_left: int,
) -> bool:
    """Reminder email sent ~3 days before the 30-day reactivation
    window closes. After the deadline the workspace is flagged for
    hard-deletion and reactivation 410s.
    """
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured — skipping reactivation reminder email")
        return False

    base = _safe_link_base("workspace_reactivation_reminder")
    if base is None:
        return False

    resend.api_key = RESEND_API_KEY
    safe_name = _h(user_name or to_email, quote=True)
    safe_workspace = _h(workspace_name or "", quote=True)
    safe_deadline = _h(reactivation_deadline, quote=True)
    days_label = f"{int(days_left)}"

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:'Segoe UI',Tahoma,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:linear-gradient(135deg,#1a1f36 0%,#2d3561 100%);padding:32px;text-align:center;">
            <img src="{LOGO_URL}" alt="NASSAQ" width="160" style="margin-bottom:8px;" />
            <p style="color:#64d9d6;font-size:14px;margin:0;">منصة إدارة المدارس الذكية</p>
          </td>
        </tr>
        <tr>
          <td style="padding:32px;">
            <h2 style="color:#1a1f36;font-size:20px;margin:0 0 8px;">تذكير: مهلة استرجاع مساحة العمل تقترب</h2>
            <p style="color:#888;font-size:13px;margin:0 0 24px;">Reminder: workspace reactivation window is closing</p>
            <p style="color:#555;font-size:15px;line-height:1.8;margin:0 0 16px;">
              مرحباً {safe_name}،<br/>
              مساحة العمل <strong>{safe_workspace}</strong> ما زالت مؤرشفة.
              تبقّى لديك <strong>{days_label}</strong> يوم/أيام لاسترجاعها قبل الحذف النهائي.
            </p>
            <div style="background:#fee2e2;border-radius:12px;padding:16px;margin:20px 0;">
              <p style="color:#991b1b;font-size:14px;margin:0;line-height:1.8;">
                ⚠️ آخر موعد للاسترجاع: <strong>{safe_deadline}</strong>.<br/>
                بعد هذا التاريخ ستُحذف بياناتك نهائياً ولا يمكن استعادتها.
              </p>
            </div>
            <div style="text-align:center;margin:24px 0;">
              <a href="{base}/login" style="display:inline-block;background:linear-gradient(135deg,#64d9d6,#36b5b0);color:#1a1f36;font-weight:bold;font-size:15px;padding:14px 36px;border-radius:12px;text-decoration:none;">
                تسجيل الدخول لاسترجاع المساحة
              </a>
            </div>
            <hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />
            <p style="color:#aaa;font-size:12px;text-align:center;margin:0;">
              نَسَّق &copy; {2026} — جميع الحقوق محفوظة
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    try:
        result = deliver_resend_email({
            "from": f"نَسَّق NASSAQ <{FROM_EMAIL}>",
            "to": [to_email],
            "subject": f"تذكير: تبقّى {days_label} يوم لاسترجاع مساحة عملك — نَسَّق",
            "html": html,
        }, kind="workspace_reactivation_reminder")
        logger.info(f"Workspace reactivation reminder sent to {to_email}, id={result.get('id', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send reactivation reminder email to {to_email}: {e}")
        return False


def send_workspace_auto_export_email(
    to_email: str,
    user_name: str,
    workspace_name: str,
    download_url: str = "",
    download_expires_at: str = "",
) -> bool:
    """Notify the Independent-Teacher that the weekly auto-export ran
    successfully and is available to download from their account settings.
    Best-effort: returns False if Resend is not configured or rejects
    the message — the caller MUST stamp the row regardless so the next
    hourly tick doesn't pick the workspace up again inside the same
    weekly slot (the 6h idempotency guard is what prevents that).
    """
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured — skipping workspace auto-export email")
        return False

    base = _safe_link_base("workspace_auto_export")
    if base is None:
        return False

    resend.api_key = RESEND_API_KEY
    safe_name = _h(user_name or to_email, quote=True)
    safe_workspace = _h(workspace_name or "", quote=True)

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:'Segoe UI',Tahoma,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:linear-gradient(135deg,#1a1f36 0%,#2d3561 100%);padding:32px;text-align:center;">
            <img src="{LOGO_URL}" alt="NASSAQ" width="160" style="margin-bottom:8px;" />
            <p style="color:#64d9d6;font-size:14px;margin:0;">منصة إدارة المدارس الذكية</p>
          </td>
        </tr>
        <tr>
          <td style="padding:32px;">
            <h2 style="color:#1a1f36;font-size:20px;margin:0 0 8px;">النسخة الاحتياطية الأسبوعية جاهزة</h2>
            <p style="color:#888;font-size:13px;margin:0 0 24px;">Your weekly workspace backup is ready</p>
            <p style="color:#555;font-size:15px;line-height:1.8;margin:0 0 16px;">
              مرحباً {safe_name}،<br/>
              تم إنشاء النسخة الاحتياطية الأسبوعية لمساحة العمل
              <strong>{safe_workspace}</strong> بنجاح.
            </p>
            <div style="background:#f8f9fb;border-radius:12px;padding:20px;margin:20px 0;">
              <p style="color:#1a1f36;font-size:14px;margin:0 0 8px;font-weight:bold;">📥 تنزيل النسخة الاحتياطية</p>
              <p style="color:#666;font-size:13px;margin:0 0 16px;line-height:1.7;">
                لتنزيل نسخة بياناتك، سجّل الدخول إلى حسابك وانتقل إلى إعدادات مساحة العمل.
              </p>
              <div style="text-align:center;">
                <a href="{base}/account-settings" style="display:inline-block;background:linear-gradient(135deg,#64d9d6,#36b5b0);color:#1a1f36;font-weight:bold;font-size:15px;padding:12px 28px;border-radius:10px;text-decoration:none;">
                  تنزيل من إعدادات الحساب
                </a>
              </div>
            </div>
            <p style="color:#888;font-size:12px;line-height:1.7;margin:16px 0 0;">
              يمكنك إيقاف النسخ الاحتياطي الأسبوعي في أي وقت من إعدادات مساحة العمل.
            </p>
            <hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />
            <p style="color:#aaa;font-size:12px;text-align:center;margin:0;">
              نَسَّق &copy; {2026} — جميع الحقوق محفوظة
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    try:
        result = deliver_resend_email({
            "from": f"نَسَّق NASSAQ <{FROM_EMAIL}>",
            "to": [to_email],
            "subject": "النسخة الاحتياطية الأسبوعية جاهزة — نَسَّق",
            "html": html,
        }, kind="workspace_auto_export")
        logger.info(f"Workspace auto-export email sent to {to_email}, id={result.get('id', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send workspace auto-export email to {to_email}: {e}")
        return False


def send_workspace_erasure_final_export_email(
    to_email: str,
    user_name: str,
    workspace_name: str,
    erasure_deadline: str,
    erasure_window_days: int = 7,
    download_url: str = "",
    download_expires_at: str = "",
) -> bool:
    """Notify the Independent-Teacher that their workspace has been
    queued for permanent erasure (Task #276 — GDPR right-to-be-forgotten).

    Informs the user that their data export was downloaded to their
    browser during the erasure-request flow and provides the erasure
    deadline. Reactivation is NOT possible during the erasure grace
    window. Best-effort: returns False on send failure; the caller MUST
    NOT undo the erasure stamp on a False return because the in-app
    dialog already surfaced the deadline.
    """
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured — skipping workspace erasure email")
        return False

    # NOTE: this template intentionally embeds NO app link (the export was
    # already downloaded in-browser), so no link-base resolution is needed.
    resend.api_key = RESEND_API_KEY
    safe_name = _h(user_name or to_email, quote=True)
    safe_workspace = _h(workspace_name or "", quote=True)
    safe_deadline = _h(erasure_deadline, quote=True)

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:'Segoe UI',Tahoma,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:linear-gradient(135deg,#1a1f36 0%,#2d3561 100%);padding:32px;text-align:center;">
            <img src="{LOGO_URL}" alt="NASSAQ" width="160" style="margin-bottom:8px;" />
            <p style="color:#64d9d6;font-size:14px;margin:0;">منصة إدارة المدارس الذكية</p>
          </td>
        </tr>
        <tr>
          <td style="padding:32px;">
            <h2 style="color:#991b1b;font-size:20px;margin:0 0 8px;">تم تأكيد حذف حسابك نهائيًا</h2>
            <p style="color:#888;font-size:13px;margin:0 0 24px;">Your workspace has been queued for permanent deletion</p>
            <p style="color:#555;font-size:15px;line-height:1.8;margin:0 0 16px;">
              مرحباً {safe_name}،<br/>
              تم تسجيل طلب الحذف النهائي لمساحة العمل <strong>{safe_workspace}</strong>.
              ستُحذف جميع البيانات نهائيًا خلال {erasure_window_days} يومًا، ولن يكون بالإمكان استرجاع المساحة بعد ذلك.
            </p>
            <div style="background:#f8f9fb;border-radius:12px;padding:20px;margin:20px 0;">
              <p style="color:#1a1f36;font-size:14px;margin:0 0 8px;font-weight:bold;">📥 نسخة البيانات المُصدَّرة</p>
              <p style="color:#666;font-size:13px;margin:0;line-height:1.7;">
                تم تنزيل نسخة كاملة من بياناتك تلقائياً إلى متصفحك عند تأكيد طلب الحذف.
                احتفظ بهذه النسخة — لن يكون بالإمكان استرجاع البيانات بعد {safe_deadline}.
              </p>
            </div>
            <div style="background:#fee2e2;border-radius:12px;padding:16px;margin:20px 0;">
              <p style="color:#991b1b;font-size:14px;margin:0;line-height:1.8;">
                ⚠️ <strong>موعد الحذف النهائي:</strong> {safe_deadline}.<br/>
                لا يمكن إلغاء طلب الحذف أو إعادة تفعيل المساحة خلال هذه المهلة.
              </p>
            </div>
            <hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />
            <p style="color:#aaa;font-size:12px;text-align:center;margin:0;">
              نَسَّق &copy; {2026} — جميع الحقوق محفوظة
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    try:
        result = deliver_resend_email({
            "from": f"نَسَّق NASSAQ <{FROM_EMAIL}>",
            "to": [to_email],
            "subject": "تأكيد طلب الحذف النهائي لحسابك — نَسَّق",
            "html": html,
        }, kind="workspace_erasure_final_export")
        logger.info(f"Workspace erasure email sent to {to_email}, id={result.get('id', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send workspace erasure email to {to_email}: {e}")
        return False


def send_admin_password_reset_notification(to_email: str, user_name: str, admin_name: str) -> bool:
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured — skipping admin reset notification")
        return False

    base = _safe_link_base("admin_password_reset_notification")
    if base is None:
        return False

    resend.api_key = RESEND_API_KEY
    login_link = f"{base}/login"

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:'Segoe UI',Tahoma,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:40px 0;">
    <tr><td align="center">
      <table width="500" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:linear-gradient(135deg,#1a1f36 0%,#2d3561 100%);padding:32px;text-align:center;">
            <img src="{LOGO_URL}" alt="NASSAQ" width="160" style="margin-bottom:8px;" />
          </td>
        </tr>
        <tr>
          <td style="padding:32px;">
            <h2 style="color:#1a1f36;font-size:20px;margin:0 0 16px;">تم تغيير كلمة المرور</h2>
            <p style="color:#555;font-size:15px;line-height:1.8;margin:0 0 24px;">
              مرحباً {user_name}،<br/>
              تم إعادة تعيين كلمة المرور الخاصة بحسابك بواسطة المدير ({admin_name}).
              ستحتاج إلى تغيير كلمة المرور عند تسجيل الدخول التالي.
            </p>
            <div style="text-align:center;margin:24px 0;">
              <a href="{login_link}" style="display:inline-block;background:linear-gradient(135deg,#64d9d6,#36b5b0);color:#1a1f36;font-weight:bold;font-size:16px;padding:14px 40px;border-radius:12px;text-decoration:none;">
                تسجيل الدخول
              </a>
            </div>
            <hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />
            <p style="color:#aaa;font-size:12px;text-align:center;margin:0;">
              نَسَّق &copy; {2026} — جميع الحقوق محفوظة
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    try:
        result = deliver_resend_email({
            "from": f"نَسَّق NASSAQ <{FROM_EMAIL}>",
            "to": [to_email],
            "subject": "تم تغيير كلمة المرور — نَسَّق",
            "html": html,
        }, kind="admin_password_reset_notification")
        logger.info(f"Admin reset notification sent to {to_email}, id={result.get('id', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send admin reset notification to {to_email}: {e}")
        return False


def send_parent_invitation_email(
    to_email: str,
    parent_name: str,
    teacher_name: str,
    student_name: str,
    invite_link: str,
    expires_at: str = "",
) -> bool:
    """Deliver an Independent-Teacher parent-invitation activation link.

    Task #843: when an IT creates a student with a deliverable guardian
    email, the canonical §6.2 invite token is dispatched here so the
    guardian gets a real portal-access path (accept link → set password →
    auto-linked). The raw token is embedded in ``invite_link`` by the
    caller and must NEVER be logged. Best-effort: returns False if Resend
    is not configured or rejects the message; the caller MUST NOT roll
    back the invitation on a False return (the teacher can still copy the
    link from the success screen).
    """
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured — skipping parent invitation email")
        return False

    # Runtime safety belt: the caller builds the link, but a localhost /
    # non-public activation link must never reach a real guardian.
    if not is_dev_environment() and not is_public_base_url(invite_link):
        logger.critical(
            "EMAIL SEND BLOCKED (parent_invitation): invite link is not "
            "publicly reachable — check APP_URL/FRONTEND_URL configuration."
        )
        return False

    resend.api_key = RESEND_API_KEY
    safe_parent = _h(parent_name or "ولي الأمر", quote=True)
    safe_teacher = _h(teacher_name or "", quote=True)
    safe_student = _h(student_name or "", quote=True)

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:'Segoe UI',Tahoma,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:linear-gradient(135deg,#1a1f36 0%,#2d3561 100%);padding:32px;text-align:center;">
            <img src="{LOGO_URL}" alt="NASSAQ" width="160" style="margin-bottom:8px;" />
            <p style="color:#64d9d6;font-size:14px;margin:0;">منصة إدارة المدارس الذكية</p>
          </td>
        </tr>
        <tr>
          <td style="padding:32px;">
            <h2 style="color:#1a1f36;font-size:20px;margin:0 0 8px;">دعوة لتفعيل حساب ولي الأمر</h2>
            <p style="color:#888;font-size:13px;margin:0 0 24px;">Activate your parent portal account</p>
            <p style="color:#555;font-size:15px;line-height:1.8;margin:0 0 16px;">
              مرحباً {safe_parent}،<br/>
              قام المعلّم <strong>{safe_teacher}</strong> بتسجيل الطالب
              <strong>{safe_student}</strong> ودعوتك للوصول إلى حسابك في
              منصة نَسَّق لمتابعة بيانات ابنك/ابنتك.
            </p>
            <div style="text-align:center;margin:32px 0;">
              <a href="{invite_link}" style="display:inline-block;background:linear-gradient(135deg,#64d9d6,#36b5b0);color:#1a1f36;font-weight:bold;font-size:16px;padding:14px 40px;border-radius:12px;text-decoration:none;">
                تفعيل الحساب والدخول
              </a>
            </div>
            <div style="background:#f8f9fb;border-radius:12px;padding:16px;margin:24px 0;">
              <p style="color:#888;font-size:13px;margin:0;line-height:1.8;">
                ⏰ هذا الرابط صالح لمدة محدودة فقط.<br/>
                🔒 إذا لم تكن تتوقع هذه الدعوة، يمكنك تجاهل هذا الإيميل.
              </p>
            </div>
            <hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />
            <p style="color:#aaa;font-size:12px;text-align:center;margin:0;">
              نَسَّق &copy; {2026} — جميع الحقوق محفوظة
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    try:
        result = deliver_resend_email({
            "from": f"نَسَّق NASSAQ <{FROM_EMAIL}>",
            "to": [to_email],
            "subject": "دعوة لتفعيل حساب ولي الأمر — نَسَّق",
            "html": html,
        }, kind="parent_invitation")
        logger.info(f"Parent invitation email sent to {to_email}, id={result.get('id', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send parent invitation email to {to_email}: {e}")
        return False
