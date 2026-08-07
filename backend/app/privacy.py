"""The Art. 13/14 privacy notice, served from the API.

Server-rendered rather than a React route on purpose. The bundle is mounted with
`html=True` and the app keeps all its state in the query string, so there are no
client-side routes — a `/privacy` handled in React would 404 on a direct hit,
and a direct hit is the only kind this URL gets: it goes in the Google OAuth
consent screen, in alert emails, and in replies to removal requests.

The wording is deliberately specific about the uncomfortable part. Most of the
personal data here belongs to people who never submitted it and do not know the
app exists, which is exactly the case Art. 14 is written for.
"""
from __future__ import annotations

import html

from app import config


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _controller_block() -> str:
    name = _esc(config.CONTROLLER_NAME)
    contact = _esc(config.PRIVACY_CONTACT)
    if not (name and contact):
        # Says so plainly instead of inventing a plausible-looking controller.
        missing = " and ".join(
            n for n, v in (("CONTROLLER_NAME", name), ("PRIVACY_CONTACT", contact))
            if not v
        )
        return (
            '<p class="warn"><strong>This deployment has not been '
            "configured with a data controller.</strong> "
            f"Set <code>{missing}</code> in the environment. Until then there "
            "is no valid way to exercise the rights described below, which "
            "means this instance should not be publicly reachable.</p>"
        )
    return (
        f"<p>The controller for this processing is <strong>{name}</strong>. "
        f'For anything on this page, including any request below, write to '
        f'<a href="mailto:{contact}">{contact}</a>.</p>'
    )


def _sources() -> str:
    subs = ", ".join(f"r/{_esc(s)}" for s in config.SUBREDDITS)
    return subs or "the configured subreddits"


def _retention() -> str:
    if config.RETENTION_DAYS <= 0:
        return (
            "<p>This deployment currently has automatic deletion switched off "
            "(<code>RETENTION_DAYS=0</code>), so posts are kept until removed "
            "by hand or until the original is deleted on Reddit.</p>"
        )
    return (
        f"<p>Posts and everything derived from them are deleted automatically "
        f"once the post is <strong>{config.RETENTION_DAYS} days</strong> old. "
        "The map already hides anything past 30 days, but hiding is not "
        "erasing, so the daily job deletes the rows outright.</p>"
    )


def render() -> str:
    contact = _esc(config.PRIVACY_CONTACT)
    mail_link = (
        f'<a href="mailto:{contact}">{contact}</a>' if contact else "the controller"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Privacy — FriendMap NL</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<style>
  @font-face {{
    font-family: "Inter"; font-style: normal; font-weight: 400 700;
    font-display: swap; src: url("/fonts/inter-latin.woff2") format("woff2");
  }}
  :root {{ color-scheme: light; }}
  body {{
    margin: 0; padding: 3rem 1.25rem 6rem;
    background: #FAF6F0; color: #3A342E;
    font: 400 16px/1.65 Inter, system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
  }}
  main {{ max-width: 46rem; margin: 0 auto; }}
  h1 {{ font-size: 1.85rem; line-height: 1.2; color: #2B2622; margin: 0 0 .35rem; }}
  h2 {{ font-size: 1.1rem; color: #2B2622; margin: 2.4rem 0 .6rem; }}
  p, li {{ margin: 0 0 .85rem; }}
  ul {{ padding-left: 1.15rem; }}
  a {{ color: #1F5A4F; }}
  code {{
    background: #F5F0E6; border: 1px solid #DCD3C4; border-radius: 4px;
    padding: .05em .35em; font-size: .9em;
  }}
  .lede {{ color: #4A443E; font-size: 1.05rem; }}
  .muted {{ color: #7A7168; font-size: .9rem; }}
  .warn {{
    background: #F8E9D6; border: 1px solid #E3C9A6; color: #8A5A22;
    border-radius: 8px; padding: .9rem 1rem;
  }}
  .box {{
    background: #FFFDFA; border: 1px solid #E7E0D6;
    border-radius: 10px; padding: 1rem 1.15rem; margin: 1.2rem 0;
  }}
  hr {{ border: 0; border-top: 1px solid #E7E0D6; margin: 2.5rem 0; }}
</style>
</head>
<body>
<main>
<p class="muted"><a href="/">&larr; back to the map</a></p>
<h1>Privacy</h1>
<p class="lede">FriendMap NL collects public posts from Dutch friend-finding
subreddits and plots them on a map. Most of the personal data here therefore
belongs to people who did not submit it to us and may not know this site
exists. This page explains what is held, why, and how to have it removed.</p>

{_controller_block()}

<h2>1. Data about people whose posts appear on the map</h2>
<p><strong>Where it comes from.</strong> The public Atom feeds of
{_sources()}. Nothing is collected from private messages, from logged-in
sessions, or from anywhere requiring an account.</p>
<p><strong>What is held.</strong> The post's title and text as published, its
permalink and timestamp, and fields a language model extracts from that text:
approximate age, gender as stated, the place named, language, up to four
interest tags from a fixed list, and a one-sentence summary.</p>
<p><strong>What is deliberately not held.</strong></p>
<ul>
  <li><strong>The Reddit username is never published by this site.</strong> It
  is stored only to group a person's own posts together and to detect reposts,
  and it is stripped from every API response. Where a stable per-person
  identifier is needed it is a keyed HMAC, not a reversible hash of the name.</li>
  <li><strong>No special-category data.</strong> The interest vocabulary
  deliberately excludes health, mental health, sexuality, religion, ethnicity
  and political opinion, even though posts sometimes mention them. Inferring
  those from a public post and storing them as a queryable tag is a different
  act from noting that someone likes coffee.</li>
  <li>No addresses. Location is city-level at best, and is taken from what the
  person wrote — never inferred from an IP address or anything else.</li>
</ul>
<p><strong>Why.</strong> To let people looking for friends in the Netherlands
find each other, which is the stated purpose of the posts themselves.</p>
<p><strong>Legal basis.</strong> Legitimate interests, Art. 6(1)(f) GDPR. The
balancing test is written up in the repository as
<code>docs/legitimate-interest-assessment.md</code>. In short: the posts are
already public and were written to be found, the site adds no contact
capability, it is excluded from search engines, and anyone can have their
entry removed on request. If you object, your entry is removed — we do not
ask you to justify the objection.</p>
<p><strong>Accuracy.</strong> The structured fields are produced by a language
model and are sometimes wrong. Low-confidence extractions are flagged
internally. The original post text is always shown alongside, and every card
links to the original, so the source can be checked. Corrections are welcome
at {mail_link}.</p>

<h2>2. Data about people who sign in</h2>
<p>Signing in is optional; the whole map is browsable without it. If you do
sign in with Google we store the opaque Google account identifier, your email
address, display name and avatar URL, plus whatever you create: your saved
people, your private notes, your own profile fields for match ranking, and
your saved searches. <strong>No passwords are stored</strong> — there are
none.</p>
<p>Notes and saved lists are private to your account and are never shown to
the people they refer to, or to anyone else. <strong>Legal basis:</strong>
Art. 6(1)(b), performance of the service you asked for.</p>
<p>You can delete your account and everything attached to it from your account
page, at any time, without asking anyone.</p>

<h2>3. Cookies</h2>
<p>One cookie, <code>friendmap_session</code>, which keeps you signed in. It is
signed, <code>HttpOnly</code>, <code>SameSite=Lax</code> and
<code>Secure</code>. There are no analytics, no advertising, no tracking
pixels, and no third-party scripts or fonts — the page makes no request you did
not ask for, which is why there is no consent banner.</p>

<h2>4. Who else sees the data</h2>
<ul>
  <li><strong>NVIDIA</strong> (NIM inference API) — post text is sent for
  extraction. United States.</li>
  <li><strong>Render</strong> — hosting and the database. EU region
  (Frankfurt).</li>
  <li><strong>Resend</strong> — sends alert emails, if you asked for any. It
  receives your email address and the digest. United States.</li>
  <li><strong>GitHub</strong> — runs the scheduled ingest job and stores the
  container image. United States.</li>
</ul>
<p>Transfers to the United States rely on the EU–US Data Privacy Framework
where the provider is certified, and otherwise on Standard Contractual
Clauses. The data is never sold, and never shared for advertising.</p>

<h2>5. Retention</h2>
{_retention()}
<p>If the original post is deleted or removed on Reddit, this site notices
within about a day and drops it. A removal you request is also recorded so that
the daily scrape does not simply put it back.</p>

<h2>6. Your rights</h2>
<p>You have the right of access, rectification, erasure, restriction,
objection, and data portability. In particular:</p>
<div class="box">
  <p><strong>To have your post removed from the map:</strong> either delete the
  original post on Reddit — it disappears from here within a day — or write to
  {mail_link} with the link to the post. A requested removal is permanent: the
  entry is suppressed so later scrapes cannot re-add it.</p>
  <p style="margin:0"><strong>To get a copy of your data</strong> (signed-in
  accounts): use the export on your account page, or ask at {mail_link}.</p>
</div>
<p>No decision with a legal or similarly significant effect is made about
anyone automatically. The extraction only sorts and displays public posts; it
grants and denies nothing.</p>
<p>If you think this processing is unlawful you can complain to your
supervisory authority. In the Netherlands that is the
<a href="https://autoriteitpersoonsgegevens.nl/">Autoriteit
Persoonsgegevens</a>.</p>

<hr>
<p class="muted">This notice describes a self-hosted deployment of the
open-source FriendMap NL project. Its behaviour is verifiable in the source.</p>
</main>
</body>
</html>
"""
