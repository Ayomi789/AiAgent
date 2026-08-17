"""Probe subpackage: HTTP-level security checks.

- passive: security headers, cookie flags, server banner (no payloads).
- active: injected payloads against discovered forms — reflected XSS, SSTI,
  SQL injection, login auth bypass, exposed endpoints, and IDOR/object
  enumeration on id-parameter links.

Both are deterministic and run before the LLM loop, so findings appear on
every run regardless of model behaviour.
"""
