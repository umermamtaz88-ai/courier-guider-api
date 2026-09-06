import re

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+92|0)?3\d{9}\b")
CNIC_RE = re.compile(r"\b\d{5}-\d{7}-\d\b")


def redact_pii(text: str) -> str:
    """Redact common PII patterns before logging or external LLM calls."""
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = CNIC_RE.sub("[REDACTED_CNIC]", text)
    return text
