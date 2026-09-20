import type { Finding } from "./types";

export const findingsMore: Finding[] = [
  {
    id: "FND-1046",
    severity: "medium",
    title: "Content-Security-Policy allows 'unsafe-inline' scripts",
    category: "Security Misconfiguration",
    target: "app.example.com",
    path: "/*",
    status: "verified",
    confidence: "high",
    cvss: "5.3",
    cwe: "CWE-693",
    owasp: "A05:2021 — Security Misconfiguration",
    detected: "2026-09-19 09:39:12",
    runId: "run_8f31c2",
    evidenceCount: 1,
    summary:
      "The Content-Security-Policy response header includes 'unsafe-inline' in the script-src directive, which neutralises the primary mitigation against cross-site scripting.",
    verification:
      "Headers were collected across 24 responses spanning 9 routes. Every HTML response carried the same policy. A benign inline script was injected into the DOM during verification and executed without being blocked by the browser.",
    reproduction: [
      "Request any HTML page from the target and inspect the content-security-policy header.",
      "Confirm script-src contains 'unsafe-inline'.",
      "Execute a benign inline script in the page context.",
      "Observe that no CSP violation is reported and the script runs.",
    ],
    impact:
      "Cross-site scripting vulnerabilities in the application cannot be mitigated by the policy, increasing the effective severity of any injection flaw.",
    recommendation:
      "Remove 'unsafe-inline' from script-src, migrate inline scripts to external files with cryptographic nonces or hashes, and report violations to a reporting endpoint before enforcing the policy.",
    evidence: {
      request:
        "GET / HTTP/2\nHost: app.example.com\nUser-Agent: ATA-Testing-Agent/2.4 (authorized-assessment)\nX-ATA-Run-Id: run_8f31c2",
      response:
        "HTTP/2 200 OK\ncontent-type: text/html; charset=utf-8\ncontent-security-policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'\nx-frame-options: SAMEORIGIN\nx-content-type-options: nosniff\n\n# Directive analysis\n#   script-src -> 'unsafe-inline' present (finding)\n#   object-src -> missing (recommendation)\n#   frame-ancestors -> missing (recommendation)",
      dom:
        "<!-- Verification snippet injected into the page context -->\n<script nonce=\"ata-verify\">\n  // Executed successfully with no CSP violation event\n  console.info(\"csp-inline-execution: permitted\");\n</script>\n\n<!-- document.querySelector('meta[http-equiv]') -> null -->",
      console:
        "[09:39:11.742] INFO  header-collector.js:31  24 responses collected\n[09:39:11.804] DEBUG csp-parser.js:12        directive script-src parsed\n[09:39:11.812] WARN  csp-parser.js:44         'unsafe-inline' present in script-src\n[09:39:11.901] INFO  verifier.js:91           inline script executed without violation",
      network: [
        { method: "GET", path: "/", status: 200, type: "document", size: "14.2 kB", time: "88 ms", state: "ok" },
        { method: "GET", path: "/login", status: 200, type: "document", size: "11.8 kB", time: "91 ms", state: "ok" },
        { method: "GET", path: "/search", status: 200, type: "document", size: "18.4 kB", time: "112 ms", state: "ok" },
      ],
    },
  },
  {
    id: "FND-1047",
    severity: "medium",
    title: "Session cookie missing SameSite attribute on legacy route",
    category: "Session Management",
    target: "app.example.com",
    path: "/legacy/report",
    status: "verified",
    confidence: "high",
    cvss: "4.8",
    cwe: "CWE-1275",
    owasp: "A05:2021 — Security Misconfiguration",
    detected: "2026-09-19 09:49:44",
    runId: "run_8f31c2",
    evidenceCount: 2,
    summary:
      "The session cookie issued by the legacy reporting route omits the SameSite attribute, allowing the browser to attach it to cross-site requests.",
    verification:
      "Set-Cookie headers were captured from 11 routes. The modern application sets SameSite=Lax consistently; the legacy reporting route issues the same session identifier without the attribute.",
    reproduction: [
      "Clear cookies and navigate to /legacy/report.",
      "Inspect the Set-Cookie header in the authentication response.",
      "Confirm the SameSite attribute is absent.",
      "Compare with the response from the root route, which sets SameSite=Lax.",
    ],
    impact:
      "Increases exposure to cross-site request forgery against the legacy reporting endpoints, particularly in older browsers that default to SameSite=None.",
    recommendation:
      "Set SameSite=Lax (or Strict for sensitive flows) on all cookies, migrate the legacy route to the shared session configuration, and add header assertions to the integration test suite.",
    evidence: {
      request:
        "GET /legacy/report HTTP/2\nHost: app.example.com\nUser-Agent: ATA-Testing-Agent/2.4 (authorized-assessment)\nX-ATA-Run-Id: run_8f31c2",
      response:
        "HTTP/2 200 OK\nset-cookie: session_id=s%3Alegacy_9f2c...; Path=/; HttpOnly\nset-cookie: csrf_token=x7Q...; Path=/; SameSite=Strict\n\n# Attribute matrix (11 routes sampled)\n#   HttpOnly     -> present on 11/11\n#   Secure       -> present on 11/11\n#   SameSite     -> present on 10/11  (missing: /legacy/report)",
      dom:
        "document.cookie (non-HttpOnly surface):\n  csrf_token=x7Q...\n  lang=en-US\n\n// session_id correctly hidden from JavaScript via HttpOnly",
      console:
        "[09:49:43.602] INFO  header-collector.js:31  11 routes sampled\n[09:49:43.688] WARN  cookie-parser.js:22     SameSite attribute missing on /legacy/report\n[09:49:43.690] INFO  verifier.js:91           configuration delta confirmed",
      network: [
        { method: "GET", path: "/legacy/report", status: 200, type: "document", size: "9.4 kB", time: "102 ms", state: "ok" },
        { method: "GET", path: "/", status: 200, type: "document", size: "14.2 kB", time: "88 ms", state: "ok" },
      ],
    },
  },
  {
    id: "FND-1048",
    severity: "medium",
    title: "Verbose stack trace exposed on API error response",
    category: "Information Disclosure",
    target: "app.example.com",
    path: "/api/v1/reports/export",
    status: "verified",
    confidence: "high",
    cvss: "5.3",
    cwe: "CWE-209",
    owasp: "A05:2021 — Security Misconfiguration",
    detected: "2026-09-19 09:51:20",
    runId: "run_8f31c2",
    evidenceCount: 2,
    summary:
      "Malformed export requests return a full server-side stack trace including framework version, file system paths, and internal host names.",
    verification:
      "A malformed date range parameter triggered an unhandled exception. The 500 response included 41 lines of stack trace referencing internal module paths and the database host name.",
    reproduction: [
      "Send GET /api/v1/reports/export?from=not-a-date.",
      "Observe HTTP 500 with content-type application/json.",
      "Inspect the error object for the stack field.",
      "Note framework version and internal path disclosure.",
    ],
    impact:
      "Accelerates reconnaissance by revealing technology versions, directory structure, and internal infrastructure details that support targeted exploitation.",
    recommendation:
      "Return generic error identifiers to clients, log full diagnostics server-side with correlation ids, and validate input before it reaches the exception boundary.",
    evidence: {
      request:
        "GET /api/v1/reports/export?from=not-a-date&to=2026-09-19 HTTP/2\nHost: app.example.com\nAccept: application/json\nX-ATA-Run-Id: run_8f31c2",
      response:
        "HTTP/2 500 Internal Server Error\ncontent-type: application/json\nx-request-id: 9a1c4f22\n\n{\n  \"error\": \"InternalServerError\",\n  \"message\": \"RangeError: Invalid time value\",\n  \"stack\": \"RangeError: Invalid time value\\n    at parseRange (/srv/app/services/report.js:88:19)\\n    at ExportController.run (/srv/app/controllers/export.js:41:22)\\n  ... 38 more frames\",\n  \"runtime\": \"node v20.11.1\",\n  \"db_host\": \"db-primary.internal.example.com\"\n}",
      dom: "// JSON error response — DOM capture not applicable.",
      console:
        "[09:51:19.882] INFO  http-client.js:144   response 500 (204ms)\n[09:51:19.884] WARN  disclosure-check.js:18 stack trace detected in response body\n[09:51:19.885] WARN  disclosure-check.js:26 internal hostname detected\n[09:51:19.886] INFO  verifier.js:91         information disclosure confirmed",
      network: [
        { method: "GET", path: "/api/v1/reports/export?from=not-a-date", status: 500, type: "fetch", size: "2.8 kB", time: "204 ms", state: "error" },
        { method: "GET", path: "/api/v1/reports/export?from=2026-09-01", status: 200, type: "fetch", size: "12.4 kB", time: "188 ms", state: "ok" },
      ],
    },
  },
  {
    id: "FND-1049",
    severity: "medium",
    title: "Rate limiting absent on password reset endpoint",
    category: "Broken Authentication",
    target: "app.example.com",
    path: "/api/v1/auth/reset-password",
    status: "verified",
    confidence: "medium",
    cvss: "5.9",
    cwe: "CWE-307",
    owasp: "A07:2021 — Identification and Authentication Failures",
    detected: "2026-09-19 09:53:02",
    runId: "run_8f31c2",
    evidenceCount: 2,
    summary:
      "The password reset endpoint accepts unlimited requests from a single source without throttling, enabling credential spraying and user-enumeration attempts.",
    verification:
      "The agent issued 40 requests at 2 req/sec within the authorized rate limit. All 40 returned HTTP 200 with identical timing, and no 429 response or backoff signal was observed.",
    reproduction: [
      "Send 40 POST requests to /api/v1/auth/reset-password at 2 req/sec.",
      "Record the status code and latency for each response.",
      "Observe that all responses return HTTP 200 without throttling.",
      "Compare with /api/v1/auth/login, which returns 429 after 10 attempts.",
    ],
    impact:
      "Enables automated abuse of the reset flow, account-lockout evasion, and large-scale user enumeration.",
    recommendation:
      "Apply per-account and per-IP rate limits with exponential backoff, return uniform responses to prevent enumeration, and monitor reset-volume anomalies.",
    evidence: {
      request:
        "POST /api/v1/auth/reset-password HTTP/2\nHost: app.example.com\ncontent-type: application/json\nX-ATA-Run-Id: run_8f31c2\n\n{ \"email\": \"test-account@example.com\" }\n\n# Test series: 40 requests @ 2 req/sec\n# Status distribution: 200 x40, 429 x0\n# Mean latency: 118 ms (std dev 6.4 ms)",
      response:
        "HTTP/2 200 OK\ncontent-type: application/json\nx-request-id: 2f8a1c40\nretry-after: (absent)\nx-ratelimit-limit: (absent)\nx-ratelimit-remaining: (absent)\n\n{ \"status\": \"accepted\", \"message\": \"Reset instructions sent\" }\n\n# Comparison endpoint /api/v1/auth/login:\n#   x-ratelimit-limit: 10\n#   429 returned after threshold",
      dom:
        "// JSON API response — DOM capture not applicable.\n{\n  \"requests_sent\": 40,\n  \"throttled_responses\": 0,\n  \"retry_after_headers\": 0,\n  \"consistent_latency\": true\n}",
      console:
        "[09:52:41.118] INFO  throttle-test.js:24   series started (40 requests)\n[09:52:58.402] DEBUG throttle-test.js:61   40/40 complete\n[09:52:58.403] WARN  throttle-test.js:72   no 429 responses observed\n[09:52:58.404] INFO  verifier.js:91         rate-limit absence confirmed",
      network: [
        { method: "POST", path: "/api/v1/auth/reset-password", status: 200, type: "fetch", size: "74 B", time: "118 ms", state: "ok" },
        { method: "POST", path: "/api/v1/auth/login", status: 429, type: "fetch", size: "62 B", time: "41 ms", state: "blocked" },
      ],
    },
  },
  {
    id: "FND-1050",
    severity: "low",
    title: "Directory listing enabled on static asset bucket",
    category: "Security Misconfiguration",
    target: "assets.example.com",
    path: "/uploads/2026/",
    status: "verified",
    confidence: "high",
    cvss: "3.7",
    cwe: "CWE-548",
    owasp: "A05:2021 — Security Misconfiguration",
    detected: "2026-09-19 09:55:18",
    runId: "run_8f31c2",
    evidenceCount: 1,
    summary:
      "The static asset origin returns an XML object listing for the uploads prefix, disclosing file names and upload timestamps.",
    verification:
      "A GET request to the uploads prefix returned an S3-style listing document containing 214 object keys. No sensitive file types were observed in the listing.",
    reproduction: [
      "Request GET https://assets.example.com/uploads/2026/.",
      "Observe an XML listing response with object keys.",
      "Confirm the listing is accessible without authentication.",
    ],
    impact:
      "Reveals file naming conventions and upload patterns that support further reconnaissance. No direct data exposure was confirmed.",
    recommendation:
      "Disable public listing on the storage bucket, serve assets through the application layer, and audit existing object permissions.",
    evidence: {
      request:
        "GET /uploads/2026/ HTTP/2\nHost: assets.example.com\nUser-Agent: ATA-Testing-Agent/2.4 (authorized-assessment)\nX-ATA-Run-Id: run_8f31c2",
      response:
        "HTTP/2 200 OK\ncontent-type: application/xml\ncontent-length: 24880\n\n<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<ListBucketResult>\n  <Name>example-prod-uploads</Name>\n  <Prefix>uploads/2026/</Prefix>\n  <KeyCount>214</KeyCount>\n  <Contents>\n    <Key>uploads/2026/09/invoice-8821.pdf</Key>\n    <LastModified>2026-09-18T14:22:11Z</LastModified>\n  </Contents>\n</ListBucketResult>",
      dom: "// XML response — DOM capture not applicable.",
      console:
        "[09:55:17.221] INFO  http-client.js:144   response 200 (92ms, 24880B)\n[09:55:17.223] WARN  listing-check.js:14   bucket listing detected (214 keys)\n[09:55:17.224] INFO  verifier.js:91         configuration confirmed",
      network: [
        { method: "GET", path: "/uploads/2026/", status: 200, type: "document", size: "24.3 kB", time: "92 ms", state: "ok" },
      ],
    },
  },
  {
    id: "FND-1051",
    severity: "low",
    title: "Cookie set without Secure flag on staging subdomain",
    category: "Session Management",
    target: "staging.example.com",
    path: "/",
    status: "triaged",
    confidence: "medium",
    cvss: "3.1",
    cwe: "CWE-614",
    owasp: "A05:2021 — Security Misconfiguration",
    detected: "2026-09-19 09:57:41",
    runId: "run_8f31c2",
    evidenceCount: 1,
    summary:
      "The staging subdomain sets a preference cookie over HTTPS without the Secure flag, allowing transmission over plaintext HTTP.",
    verification:
      "The Set-Cookie header was captured from the staging origin. The production origin sets the Secure flag correctly on the equivalent cookie.",
    reproduction: [
      "Request https://staging.example.com/ and inspect Set-Cookie.",
      "Confirm the Secure attribute is absent.",
    ],
    impact: "Limited to the staging environment; could expose preference data on untrusted networks.",
    recommendation:
      "Align staging cookie configuration with production and enforce HTTPS-only transport via HSTS on all subdomains.",
    evidence: {
      request: "GET / HTTP/2\nHost: staging.example.com\nX-ATA-Run-Id: run_8f31c2",
      response:
        "HTTP/2 200 OK\nset-cookie: prefs=eyJ0aGVtZSI6ImRhcmsi...; Path=/; HttpOnly\n\n# Secure flag absent\n# HSTS header absent on staging origin",
      dom: "// Not applicable — header-level finding.",
      console:
        "[09:57:40.602] WARN  cookie-parser.js:31   Secure flag absent on staging.example.com\n[09:57:40.603] INFO  verifier.js:91         header state recorded",
      network: [{ method: "GET", path: "/", status: 200, type: "document", size: "8.2 kB", time: "74 ms", state: "ok" }],
    },
  },
  {
    id: "FND-1052",
    severity: "low",
    title: "Subresource Integrity missing on third-party scripts",
    category: "Security Misconfiguration",
    target: "app.example.com",
    path: "/",
    status: "verified",
    confidence: "high",
    cvss: "3.4",
    cwe: "CWE-353",
    owasp: "A05:2021 — Security Misconfiguration",
    detected: "2026-09-19 09:59:12",
    runId: "run_8f31c2",
    evidenceCount: 1,
    summary:
      "Two third-party script tags are loaded without Subresource Integrity attributes, leaving the page exposed to compromised CDN content.",
    verification:
      "The agent parsed all script elements across 9 routes and confirmed two external scripts lack integrity attributes.",
    reproduction: [
      "Load the application root and inspect external script tags.",
      "Confirm the integrity attribute is absent on two elements.",
    ],
    impact: "A compromised third-party host could inject arbitrary code into the application origin.",
    recommendation: "Add integrity and crossorigin attributes to all third-party resources, or self-host the assets.",
    evidence: {
      request: "GET / HTTP/2\nHost: app.example.com\nX-ATA-Run-Id: run_8f31c2",
      response:
        "HTTP/2 200 OK\ncontent-type: text/html; charset=utf-8\n\n<script src=\"https://cdn.metrics.io/tag.js\"></script>\n<script src=\"https://cdn.widgets.io/embed.v2.js\"></script>\n\n# integrity attribute absent on both elements\n# crossorigin attribute absent on both elements",
      dom:
        "document.querySelectorAll(\"script[src^='http']\")\n  -> 2 elements\n  -> 0 with integrity attribute\n  -> 0 with crossorigin attribute",
      console:
        "[09:59:11.402] INFO  dom-scan.js:22        2 external scripts without integrity\n[09:59:11.403] INFO  verifier.js:91         configuration recorded",
      network: [
        { method: "GET", path: "/", status: 200, type: "document", size: "14.2 kB", time: "88 ms", state: "ok" },
        { method: "GET", path: "https://cdn.metrics.io/tag.js", status: 200, type: "script", size: "42 kB", time: "122 ms", state: "ok" },
      ],
    },
  },
  {
    id: "FND-1053",
    severity: "low",
    title: "Referrer policy permits origin disclosure on documentation routes",
    category: "Information Disclosure",
    target: "app.example.com",
    path: "/docs/*",
    status: "triaged",
    confidence: "medium",
    cvss: "2.6",
    cwe: "CWE-200",
    owasp: "A01:2021 — Broken Access Control",
    detected: "2026-09-19 10:01:38",
    runId: "run_8f31c2",
    evidenceCount: 1,
    summary:
      "Documentation pages use a referrer policy of 'origin', which discloses the application origin to external destinations from sensitive routes.",
    verification:
      "Referrer-Policy headers were collected across 24 responses. Documentation routes return 'origin' while the rest of the application returns 'strict-origin-when-cross-origin'.",
    reproduction: [
      "Request a documentation page and inspect the Referrer-Policy header.",
      "Compare with the header returned by the application root.",
    ],
    impact: "Minor information disclosure to third-party destinations.",
    recommendation:
      "Standardise the Referrer-Policy header across all routes to 'strict-origin-when-cross-origin' or stricter.",
    evidence: {
      request: "GET /docs/getting-started HTTP/2\nHost: app.example.com\nX-ATA-Run-Id: run_8f31c2",
      response:
        "HTTP/2 200 OK\nreferrer-policy: origin\n\n# Application root returns:\n# referrer-policy: strict-origin-when-cross-origin",
      dom: "document.referrer -> \"https://app.example.com/docs/getting-started\"",
      console:
        "[10:01:37.221] INFO  header-collector.js:31  24 responses collected\n[10:01:37.222] INFO  verifier.js:91         policy delta recorded",
      network: [{ method: "GET", path: "/docs/getting-started", status: 200, type: "document", size: "16.8 kB", time: "94 ms", state: "ok" }],
    },
  },
  {
    id: "FND-1054",
    severity: "info",
    title: "Server technology disclosed via response headers",
    category: "Information Disclosure",
    target: "app.example.com",
    path: "/*",
    status: "verified",
    confidence: "high",
    cvss: "0.0",
    cwe: "CWE-200",
    owasp: "A05:2021 — Security Misconfiguration",
    detected: "2026-09-19 09:38:04",
    runId: "run_8f31c2",
    evidenceCount: 1,
    summary: "The server header discloses the reverse-proxy vendor and framework across all responses.",
    verification:
      "Header collection across 24 responses returned a consistent server header identifying the proxy technology and an X-Powered-By header naming the application framework.",
    reproduction: ["Request any route and inspect the Server and X-Powered-By response headers."],
    impact: "Low-level reconnaissance value only; version disclosure can assist targeted scanning.",
    recommendation: "Minimise header disclosure, disable X-Powered-By, and keep the proxy patched to current releases.",
    evidence: {
      request: "GET / HTTP/2\nHost: app.example.com\nX-ATA-Run-Id: run_8f31c2",
      response:
        "HTTP/2 200 OK\nserver: cloudflare\nx-powered-by: Next.js\n\n# x-powered-by can be disabled via next.config.js",
      dom: "// Not applicable — header-level finding.",
      console:
        "[09:38:03.118] INFO  header-collector.js:31  24 responses collected\n[09:38:03.119] INFO  verifier.js:91         disclosure recorded",
      network: [{ method: "GET", path: "/", status: 200, type: "document", size: "14.2 kB", time: "88 ms", state: "ok" }],
    },
  },
  {
    id: "FND-1055",
    severity: "info",
    title: "Robots.txt discloses administrative path prefixes",
    category: "Information Disclosure",
    target: "app.example.com",
    path: "/robots.txt",
    status: "verified",
    confidence: "high",
    cvss: "0.0",
    cwe: "CWE-200",
    owasp: "A05:2021 — Security Misconfiguration",
    detected: "2026-09-19 09:38:22",
    runId: "run_8f31c2",
    evidenceCount: 1,
    summary: "The robots.txt file lists disallowed path prefixes that map to internal administrative interfaces.",
    verification:
      "The file was fetched and parsed; four disallowed prefixes were confirmed to resolve to live routes.",
    reproduction: [
      "Request GET /robots.txt and review the Disallow entries.",
      "Confirm each prefix resolves to an existing route.",
    ],
    impact: "Assists route discovery. No direct exposure.",
    recommendation: "Avoid disclosing sensitive path structure in robots.txt; enforce access controls instead.",
    evidence: {
      request: "GET /robots.txt HTTP/2\nHost: app.example.com\nX-ATA-Run-Id: run_8f31c2",
      response:
        "HTTP/2 200 OK\ncontent-type: text/plain\n\nUser-agent: *\nDisallow: /admin/\nDisallow: /internal/\nDisallow: /api/v1/debug\nDisallow: /legacy/\n\nSitemap: https://app.example.com/sitemap.xml",
      dom: "// Not applicable — text resource.",
      console:
        "[09:38:21.402] INFO  http-client.js:144   response 200 (62ms)\n[09:38:21.403] INFO  verifier.js:91         4 prefixes resolved",
      network: [{ method: "GET", path: "/robots.txt", status: 200, type: "document", size: "0.4 kB", time: "62 ms", state: "ok" }],
    },
  },
];
