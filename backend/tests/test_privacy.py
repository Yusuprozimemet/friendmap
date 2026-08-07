"""The privacy notice and the data export.

The notice is a legal obligation rendered as HTML, so what's asserted here is
that it states the things Art. 13/14 require it to state — and that it refuses
to invent a controller when none is configured.
"""
from __future__ import annotations

from app import config, privacy


def test_notice_is_served(client):
    r = client.get("/privacy")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_notice_is_reachable_without_signing_in(client):
    """It goes in the Google consent screen and in emails to strangers."""
    assert client.get("/privacy").status_code == 200


def test_notice_is_not_indexable(client):
    """Required to be reachable, not required to be crawled."""
    assert "noindex" in client.get("/privacy").headers["x-robots-tag"]


def _flat(html: str) -> str:
    """Lowercased with runs of whitespace collapsed.

    The notice is hand-wrapped prose, so phrases like "Autoriteit
    Persoonsgegevens" span a newline in the source.
    """
    return " ".join(html.split()).lower()


def test_notice_covers_the_mandatory_ground(client):
    body = _flat(client.get("/privacy").text)
    for required in [
        "legitimate interest",      # Art. 6(1)(f) — the basis for the map data
        "art. 6(1)(f)",
        "retention",
        "erasure",
        "portability",
        "autoriteit persoonsgegevens",   # the supervisory authority
        "nvidia",                   # processors must be named
        "resend",
        "render",
        "special-category",         # what is deliberately not collected
        "username is never published",
    ]:
        assert required in body, f"privacy notice does not mention {required!r}"


def test_notice_names_the_sources(client):
    body = client.get("/privacy").text
    for sub in config.SUBREDDITS:
        assert f"r/{sub}" in body


def test_notice_admits_when_no_controller_is_configured(client):
    """A notice naming the wrong person is worse than one saying it isn't set.

    The tests run with these unset, which is the default.
    """
    assert config.CONTROLLER_NAME == ""
    body = client.get("/privacy").text
    assert "has not been configured with a data controller" in _flat(body)
    assert "CONTROLLER_NAME" in body


def test_notice_shows_the_controller_when_configured():
    original = (config.CONTROLLER_NAME, config.PRIVACY_CONTACT)
    try:
        config.CONTROLLER_NAME = "A Real Person"
        config.PRIVACY_CONTACT = "privacy@example.com"
        body = privacy.render()
        assert "A Real Person" in body
        assert 'href="mailto:privacy@example.com"' in body
        assert "has not been" not in body
    finally:
        config.CONTROLLER_NAME, config.PRIVACY_CONTACT = original


def test_controller_values_are_html_escaped():
    """These come from the environment and land in markup."""
    original = (config.CONTROLLER_NAME, config.PRIVACY_CONTACT)
    try:
        config.CONTROLLER_NAME = '<script>alert(1)</script>'
        config.PRIVACY_CONTACT = 'a"b@example.com'
        body = privacy.render()
        assert "<script>alert(1)</script>" not in body
        assert "&lt;script&gt;" in body
        assert 'a"b@example.com' not in body
    finally:
        config.CONTROLLER_NAME, config.PRIVACY_CONTACT = original


def test_notice_states_the_retention_period():
    original = config.RETENTION_DAYS
    try:
        config.RETENTION_DAYS = 180
        assert "180 days" in privacy.render()
        # And is honest when the operator switched it off.
        config.RETENTION_DAYS = 0
        body = privacy.render()
        assert "switched off" in body
        assert "180 days" not in body
    finally:
        config.RETENTION_DAYS = original


def test_notice_makes_no_automated_decision_claim(client):
    """Art. 22 only bites on decisions with legal effect; say so plainly."""
    assert "no decision with a legal" in _flat(client.get("/privacy").text)


# --- export ---------------------------------------------------------------

def test_export_requires_signing_in(client):
    assert client.get("/api/me/export").status_code in (401, 403)
