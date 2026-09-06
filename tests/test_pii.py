from app.utils.pii import redact_pii


def test_redact_email_and_phone():
    text = "Contact ali@example.com or 03001234567"
    redacted = redact_pii(text)
    assert "ali@example.com" not in redacted
    assert "03001234567" not in redacted
    assert "[REDACTED_EMAIL]" in redacted
    assert "[REDACTED_PHONE]" in redacted
