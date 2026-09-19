"""Legal layer for a hosted Sentinel: Terms of Service and abuse contact.

A public testing tool needs two legal anchors:

- **Terms of Service** the user affirmatively accepts — authorized testing
  only, account termination for abuse, no warranty. The acceptance is
  recorded per user against a version, and re-acceptance is demanded when
  the terms change. Signup cannot complete without the consent checkbox,
  and scanning cannot start while acceptance is missing or stale.
- **Abuse contact** — a published, reachable channel (email + /abuse page)
  so hosts, registrars, and targets have somewhere to go. This is what
  keeps them on your side when someone reports misuse.

Local single-user mode is unaffected: terms only gate logged-in accounts,
and the bootstrap token (operator/CI) bypasses the scan gate entirely.
"""

from __future__ import annotations

import os

# Bump whenever the terms change materially. Every account that accepted an
# older version is asked to re-accept before their next scan starts.
TERMS_VERSION = "1.0.0"

TERMS_TEXT = """Sentinel — Terms of Service (v{version})

1. Authorized testing only. You may scan a website or application only if
   you own it or have explicit, documented permission from its owner to
   test it. Every scan requires an affirmative declaration to this effect,
   and every report records who declared it, when, and from where.

2. No attacking. Sentinel looks for evidence of vulnerabilities and broken
   functionality. It must not be used to disrupt, degrade, or gain
   unauthorized access to any system. Denial-of-service testing, spam,
   phishing, credential stuffing, and data exfiltration beyond what a scan
   target exposes to the agent are prohibited.

3. Rate and scope limits. Scans are rate-limited and scoped to the target's
   origin. Attempts to bypass scope controls, private-network protections,
   quotas, or authentication are prohibited and will terminate access.

4. Your reports are your responsibility. Findings belong to the account
   that ran the scan. Do not publish vulnerabilities in third-party
   systems without that system owner's consent.

5. Account termination. Accounts used against these terms may be suspended
   immediately, with their scan history retained for abuse investigation.

6. No warranty. Sentinel is provided as-is. A clean report is not a
   guarantee of security, and a finding is not a guarantee of
   exploitability. You remain responsible for your own systems.

7. Privacy. Scan reports are visible to the account that ran the scan and
   to this deployment's administrators. We do not sell scan data.

8. Abuse contact. To report misuse of this deployment, use the contact
   channel listed at /abuse. Reports are reviewed promptly.
""".strip()


def terms_html() -> str:
    """The terms as pre-rendered HTML (text kept plain for easy editing)."""
    import html as _html

    parts = []
    for block in TERMS_TEXT.format(version=TERMS_VERSION).split("\n\n"):
        esc = _html.escape(block)
        if block.startswith("Sentinel —"):
            parts.append(f"<h1>{esc}</h1>")
        elif block[0].isdigit() and ". " in block[:4]:
            title, _, rest = block.partition(". ")
            parts.append(
                f"<h2>{_html.escape(title)}.</h2><p>{_html.escape(rest)}</p>"
            )
        else:
            parts.append(f"<p>{esc}</p>")
    return "\n".join(parts)


def abuse_contact() -> tuple[str, str]:
    """(email, url) for abuse reports — env-configurable, sane fallbacks."""
    email = os.environ.get("SENTINEL_ABUSE_EMAIL", "").strip()
    url = os.environ.get("SENTINEL_ABUSE_URL", "").strip()
    return email, url
