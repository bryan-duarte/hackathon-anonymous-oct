import pytest

from frontier.modules.guardrails.secret_patterns import find_secrets

FAKE_GITHUB_TOKEN = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
FAKE_JWT = (
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
)


@pytest.mark.parametrize(
    ("text", "expected_label"),
    [
        ("aws_access_key_id = AKIAIOSFODNN7EXAMPLE", "AWS access key"),
        (f"export GITHUB_TOKEN={FAKE_GITHUB_TOKEN}", "GitHub token"),
        ("OPENROUTER_API_KEY=sk-or-v1-0123456789abcdef0123456789", "API secret key"),
        ("SLACK=xoxb-1234567890-abcdefghij", "Slack token"),
        ("stripe: sk_live_" + "4eC39HqLyjWDarjtT1zdp7dc", "Stripe live key"),
        ("maps key AIza" + "SyD-9tSrke72PouQMnMX-a7eZSW0jkFMBWY", "Google API key"),
        (f"Authorization: Bearer {FAKE_JWT}", "JSON Web Token"),
        ("-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----", "private key"),
        (
            "DATABASE_URL=postgres://admin:hunter22@db.internal:5432/app",
            "URL with an embedded password",
        ),
    ],
)
def test_detects_well_known_credential_formats(text: str, expected_label: str) -> None:
    assert [match.label for match in find_secrets(text)] == [expected_label]


@pytest.mark.parametrize(
    "text",
    [
        "Set GITHUB_TOKEN=<GITHUB_TOKEN> in the environment",
        "OPENROUTER_API_KEY=${OPENROUTER_API_KEY}",
        "the key looks like sk-... and lives in vault",
        "DATABASE_URL=postgres://admin:${DB_PASSWORD}@db.internal/app",
        "DATABASE_URL=postgres://db.internal:5432/app",
        "Migrate the Flask 1.x service at https://legacy.example.com to FastAPI",
    ],
)
def test_ignores_placeholders_and_plain_text(text: str) -> None:
    assert find_secrets(text) == []


def test_reports_match_span_for_redaction() -> None:
    text = f"token: {FAKE_GITHUB_TOKEN} end"

    [match] = find_secrets(text)

    assert text[match.start : match.end] == FAKE_GITHUB_TOKEN
