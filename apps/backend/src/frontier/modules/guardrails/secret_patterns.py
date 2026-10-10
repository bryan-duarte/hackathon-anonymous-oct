import re

from frontier.modules.guardrails.schemas import SecretMatch, SecretPattern

SECRET_PATTERNS = (
    SecretPattern(label="AWS access key", regex=re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    SecretPattern(
        label="GitHub token",
        regex=re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})\b"),
    ),
    SecretPattern(
        label="API secret key", regex=re.compile(r"\bsk-(?:[A-Za-z0-9]+-)*[A-Za-z0-9_-]{20,}")
    ),
    SecretPattern(label="Slack token", regex=re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    SecretPattern(label="Stripe live key", regex=re.compile(r"\b[rs]k_live_[A-Za-z0-9]{20,}")),
    SecretPattern(label="Google API key", regex=re.compile(r"\bAIza[0-9A-Za-z_-]{35}")),
    SecretPattern(
        label="JSON Web Token",
        regex=re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    ),
    SecretPattern(
        label="private key",
        regex=re.compile(
            r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----"
            r".*?(?:-----END (?:[A-Z]+ )*PRIVATE KEY-----|\Z)",
            re.DOTALL,
        ),
    ),
    SecretPattern(
        label="URL with an embedded password",
        regex=re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@]+:[^\s:/@<>${}*]{3,}@[^\s/]+"),
    ),
)


def find_secrets(text: str) -> list[SecretMatch]:
    return [
        SecretMatch(label=pattern.label, start=match.start(), end=match.end())
        for pattern in SECRET_PATTERNS
        for match in pattern.regex.finditer(text)
    ]
