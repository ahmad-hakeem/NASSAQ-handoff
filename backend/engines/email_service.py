import os
import logging
from html import escape as _h
import resend

logger = logging.getLogger("nassaq.email")

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "noreply@nassaqapp.com")
APP_URL = os.environ.get("APP_URL", "")

LOGO_URL = "https://customer-assets.emergentagent.com/job_f5ea20bb-5cf5-462f-a7f0-958201e27f89/artifacts/q04svb5j_Nassaq%20LinkedIn%20Logo%20White.png"


def _get_app_url() -> str:
    if APP_URL:
        return APP_URL.rstrip("/")
    domain = os.environ.get("REPLIT_DEPLOYMENT_URL") or os.environ.get("REPLIT_DEV_DOMAIN", "")
    if domain:
        if not domain.startswith("http"):
            domain = f"https://{domain}"
        return domain.rstrip("/")
    return "http://localhost:5000"


def send_password_reset_email(to_email: str, user_name: str, reset_token: str) -> bool:
    if not RESEND_API_KEY:
        logger.error("RESEND_API_KEY not configured — cannot send password reset email")
        return False

    resend.api_key = RESEND_API_KEY
    reset_link = f"{_get_app_url()}/reset-password?token={reset_token}"

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
        result = resend.Emails.send({
            "from": f"نَسَّق NASSAQ <{FROM_EMAIL}>",
            "to": [to_email],
            "subject": "إعادة تعيين كلمة المرور — نَسَّق",
            "html": html,
        })
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
        result = resend.Emails.send({
            "from": f"نَسَّق NASSAQ <{FROM_EMAIL}>",
            "to": [to_email],
            "subject": f"رمز التحقق: {code} — نَسَّق",
            "html": html,
        })
        logger.info(f"MFA OTP email sent to {to_email}, id={result.get('id', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send MFA OTP email to {to_email}: {e}")
        return False


def send_admin_password_reset_notification(to_email: str, user_name: str, admin_name: str) -> bool:
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured — skipping admin reset notification")
        return False

    resend.api_key = RESEND_API_KEY
    login_link = f"{_get_app_url()}/login"

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
        result = resend.Emails.send({
            "from": f"نَسَّق NASSAQ <{FROM_EMAIL}>",
            "to": [to_email],
            "subject": "تم تغيير كلمة المرور — نَسَّق",
            "html": html,
        })
        logger.info(f"Admin reset notification sent to {to_email}, id={result.get('id', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send admin reset notification to {to_email}: {e}")
        return False
