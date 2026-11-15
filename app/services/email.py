import os
import smtplib
from email.message import EmailMessage


def _smtp_configured():
    return bool(os.environ.get("SMTP_HOST"))


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send email. If SMTP is not configured, print to console and return True."""
    from_addr = os.environ.get("SMTP_FROM", "ElderCare <no-reply@example.com>")
    if not _smtp_configured():
        print("=" * 60)
        print(f"[EMAIL] to={to_email}")
        print(f"[EMAIL] subject={subject}")
        print(body)
        print("=" * 60)
        return True

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15) as server:
                if user:
                    server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                if use_tls:
                    server.starttls()
                if user:
                    server.login(user, password)
                server.send_message(msg)
        return True
    except Exception as exc:
        print(f"[EMAIL ERROR] {exc}")
        return False