"""Playwright browser driver — the agent's hands.

Provides a simplified page model (text, links, inputs, buttons) that the LLM
can reason about, plus click/fill/submit/screenshot actions and capture of
console errors, page errors, and failed requests for evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from playwright.async_api import async_playwright


@dataclass
class PageSnapshot:
    """A simplified view of the current page for the LLM."""

    url: str
    title: str
    status: int | None
    text: str
    links: list[str]  # formatted as "text -> href"
    inputs: list[dict[str, str]]
    buttons: list[str]

    def summarize(self, max_text: int = 1500) -> str:
        lines = [f"URL: {self.url}", f"HTTP STATUS: {self.status}", f"TITLE: {self.title}"]
        if self.text:
            lines.append("PAGE TEXT:\n" + self.text[:max_text])
        if self.links:
            lines.append("LINKS: " + ", ".join(self.links[:30]))
        if self.inputs:
            labels = []
            for inp in self.inputs:
                labels.append(inp.get("name") or inp.get("id") or inp.get("placeholder") or inp.get("type"))
            lines.append("INPUTS: " + "; ".join(labels))
        if self.buttons:
            lines.append("BUTTONS: " + ", ".join(self.buttons[:20]))
        return "\n".join(lines)


class Browser:
    """Async wrapper around a Playwright Chromium page.

    Uses the system Edge (channel="msedge") by default so no browser download
    is needed; pass channel="chromium" if you installed Playwright's browser.
    """

    def __init__(
        self,
        headless: bool = True,
        channel: str = "msedge",
        timeout_ms: int = 30000,
    ) -> None:
        self.headless = headless
        self.channel = channel
        self.timeout_ms = timeout_ms
        self._pw = None
        self._browser = None
        self._context = None
        self.page = None
        self.console_errors: list[str] = []
        self.page_errors: list[str] = []
        self.request_failures: list[tuple[str, str]] = []

    async def __aenter__(self) -> "Browser":
        await self.start()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.stop()

    async def start(self) -> None:
        self._pw = await async_playwright().start()
        kwargs = {"headless": self.headless}
        if self.channel:
            kwargs["channel"] = self.channel
        self._browser = await self._pw.chromium.launch(**kwargs)
        self._context = await self._browser.new_context(ignore_https_errors=True)
        self.page = await self._context.new_page()
        self._last_status: int | None = None
        self.page.on("console", self._on_console)
        self.page.on("pageerror", lambda err: self.page_errors.append(str(err)))
        self.page.on(
            "requestfailed",
            lambda req: self.request_failures.append((req.url, str(req.failure))),
        )
        self.page.on(
            "response",
            lambda resp: self._remember_status(resp) if resp.request.is_navigation_request() else None,
        )

    def _remember_status(self, resp: object) -> None:
        status = getattr(resp, "status", None)
        if status:
            self._last_status = int(status)

    def _on_console(self, msg: object) -> None:
        if getattr(msg, "type", None) in ("error", "warning"):
            self.console_errors.append(f"[{msg.type}] {msg.text}")

    async def navigate(self, url: str) -> PageSnapshot:
        resp = await self.page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        if resp is not None:
            self._last_status = resp.status
        return await self.snapshot()

    async def snapshot(self) -> PageSnapshot:
        data = await self.page.evaluate(
            """() => {
                const clean = (t) => (t || '').replace(/\\s+/g, ' ').trim();
                const text = clean(document.body ? document.body.innerText : '');
                const rawLinks = [...document.querySelectorAll('a')]
                    .map(a => ({text: clean(a.innerText) || '(no text)',
                                href: a.getAttribute('href')}))
                    .filter(l => l.href).slice(0, 40);
                const inputs = [...document.querySelectorAll('input, select, textarea')]
                    .map(i => ({name: i.name || '', type: i.type || '',
                                placeholder: i.placeholder || '', id: i.id || ''}));
                const buttons = [...document.querySelectorAll('button')]
                    .map(b => clean(b.innerText)).filter(Boolean).slice(0, 40);
                return {text: text.slice(0, 5000), rawLinks, inputs, buttons};
            }"""
        )
        links = [f"{l['text']} -> {l['href']}" for l in data.pop("rawLinks")]
        return PageSnapshot(
            url=self.page.url,
            title=await self.page.title(),
            status=self._last_status,
            links=links,
            **data,
        )

    async def click(self, target: str) -> str:
        """Click a link/button by its visible text, or any element with that text."""
        page = self.page
        for role in ("link", "button"):
            loc = page.get_by_role(role, name=target, exact=False).first
            if await loc.count():
                await loc.click(timeout=self.timeout_ms)
                return f"clicked {role} '{target}'"
        loc = page.locator(f"text={target}").first
        if await loc.count():
            await loc.click(timeout=self.timeout_ms)
            return f"clicked element with text '{target}'"
        raise ValueError(f"no clickable element matching '{target}'")

    async def fill(self, field: str, value: str) -> str:
        """Fill an input matched by label text, name, id, or placeholder."""
        page = self.page
        loc = page.get_by_label(field).first
        if await loc.count():
            await loc.fill(value)
            return f"filled '{field}'"
        for attr in ("name", "id", "placeholder"):
            loc = page.locator(f"input[{attr}='{field}']").first
            if await loc.count():
                await loc.fill(value)
                return f"filled '{field}'"
        raise ValueError(f"no input matching '{field}'")

    async def submit(self) -> PageSnapshot:
        """Submit the first form on the page."""
        loc = self.page.locator("form button[type=submit]").first
        if await loc.count():
            await loc.click(timeout=self.timeout_ms)
        else:
            await self.page.keyboard.press("Enter")
        await self.page.wait_for_load_state("domcontentloaded")
        return await self.snapshot()

    async def screenshot(self, path: str) -> str:
        await self.page.screenshot(path=path)
        return path

    async def current_url(self) -> str:
        return self.page.url

    async def stop(self) -> None:
        for closer in (self._context, self._browser):
            try:
                if closer is not None:
                    await closer.close()
            except Exception:
                pass
        if self._pw is not None:
            try:
                await self._pw.stop()
            except Exception:
                pass
