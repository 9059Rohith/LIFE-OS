"""Opt-in browser worker restricted to one operator-configured conversation.

The operator must sign in manually in the dedicated persistent profile. DOM drift
fails closed. No QR/login automation, session export, or authentication bypass.
"""

import asyncio
import re
from pathlib import Path

from .providers import ProviderError


OUTGOING_RECORDS = """() => {
  const records = new Map();
  for (const node of document.querySelectorAll('#main .message-out[data-id]')) {
    records.set(node.getAttribute('data-id'), {
      id: node.getAttribute('data-id'), text: node.innerText,
      sent: !!node.querySelector('[data-icon="msg-check"], [data-icon="msg-dblcheck"]'),
      pending: !!node.querySelector('[data-icon="msg-time"]')
    });
  }
  for (const message of document.querySelectorAll('#main [data-testid="msg-container"]')) {
    if (!message.querySelector('[data-icon="tail-out"]')) continue;
    const node = message.closest('[data-id]');
    const id = node?.getAttribute('data-id');
    const text = message.querySelector('[data-testid="selectable-text"]')?.textContent;
    if (!id || !text) continue;
    const label = (node.querySelector('[data-testid="msg-meta"] [aria-label]')?.getAttribute('aria-label') || '').trim().toLowerCase();
    records.set(id, {id, text, sent: ['sent', 'delivered', 'read'].includes(label),
      pending: ['pending', 'sending', 'waiting'].includes(label)});
  }
  return Array.from(records.values());
}"""


class WhatsAppWorker:
    def __init__(self, settings):
        self.settings = settings
        self._lock = asyncio.Lock()
        self._playwright = None
        self._context = None
        self._page = None

    async def close(self):
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()

    @staticmethod
    async def _selected_chat_matches(page, contact: str) -> bool:
        header = page.locator("#main header")
        titled = header.get_by_title(contact, exact=True)
        if await titled.count() == 1:
            return (await titled.inner_text()).strip() == contact
        named = header.locator('[data-testid="conversation-info-header-chat-title"]')
        return await named.count() == 1 and (await named.inner_text()).strip() == contact

    async def _conversation(self, contact):
        if not self._context:
            try:
                from playwright.async_api import async_playwright
            except ImportError as exc:
                raise ProviderError(
                    "Install Playwright and Chromium for the WhatsApp worker", "BROWSER_AUTOMATION_ERROR"
                ) from exc
            profile = Path(getattr(self.settings, "whatsapp_profile_dir", ""))
            if not str(profile) or str(profile) == "." or not profile.is_dir():
                raise ProviderError(
                    "Create a dedicated, manually signed-in WhatsApp browser profile", "AUTHENTICATION_ERROR"
                )
            self._playwright = await async_playwright().start()
            self._context = await self._playwright.chromium.launch_persistent_context(
                str(profile.resolve()),
                headless=getattr(self.settings, "whatsapp_headless", True),
                accept_downloads=False,
            )
            self._context.set_default_timeout(10000)
            self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
            # WhatsApp Web can keep its document load pending while the signed-in
            # application is usable. The visible search box below is the actual
            # readiness check, so navigation only needs to commit.
            await self._page.goto("https://web.whatsapp.com/", wait_until="commit", timeout=60000)
        page = self._page
        if await self._selected_chat_matches(page, contact):
            return page
        search = page.get_by_role(
            "textbox", name=re.compile(r"^(Search input textbox|Search or start a new chat)$")
        )
        try:
            await search.wait_for(state="visible", timeout=60000)
        except Exception as exc:
            raise ProviderError(
                "WhatsApp login required or UI changed; sign in manually in the configured profile",
                "AUTHENTICATION_ERROR",
            ) from exc
        await search.fill(contact)
        candidate = page.locator("#pane-side").get_by_title(contact, exact=True)
        await candidate.first.wait_for(state="visible", timeout=30000)
        if await candidate.count() != 1:
            raise ProviderError(
                "WhatsApp conversation is ambiguous; manual review required", "AUTHORIZATION_ERROR"
            )
        await candidate.click()
        try:
            await page.locator("#main header").get_by_text(contact, exact=True).first.wait_for(
                state="visible", timeout=10000
            )
        except Exception as exc:
            raise ProviderError(
                "WhatsApp conversation identity could not be verified", "AUTHORIZATION_ERROR"
            ) from exc
        if not await self._selected_chat_matches(page, contact):
            raise ProviderError("WhatsApp conversation identity could not be verified", "AUTHORIZATION_ERROR")
        return page

    async def check(self, contact: str):
        async with self._lock:
            page = await self._conversation(contact)
            composer = page.locator('#main [data-testid="conversation-compose-box-input"]')
            if await composer.count() != 1:
                composer = page.locator("#main").get_by_role("textbox", name="Type a message", exact=True)
            if (
                await composer.count() != 1
                or await composer.get_attribute("role") != "textbox"
                or await composer.get_attribute("contenteditable") != "true"
                or await composer.get_attribute("aria-label")
                not in {"Type a message", "Type a message to " + contact}
            ):
                raise ProviderError("WhatsApp composer identity could not be verified", "AUTHORIZATION_ERROR")
            return True

    async def read_recent(self, contact: str):
        async with self._lock:
            page = await self._conversation(contact)
            items = await page.evaluate("""() => Array.from(document.querySelectorAll('#main [data-testid="msg-container"]'))
                .slice(-25).map(node => {
                  const text = node.querySelector('[data-testid="selectable-text"]')?.textContent?.trim();
                  const message = node.closest('[data-id]');
                  const outgoing = !!node.querySelector('[data-icon="tail-out"]');
                  const status = message?.querySelector('[data-testid="msg-meta"] [aria-label]')?.getAttribute('aria-label')?.trim() || '';
                  return text && message ? {id:message.getAttribute('data-id'), content:text.slice(0,4000), outgoing, status:status.slice(0,30)} : null;
                }).filter(Boolean)""")
            return {"application": "whatsapp", "title": contact, "items": items}

    async def send(self, contact: str, body: str, key: str):
        if not getattr(self.settings, "whatsapp_enabled", False):
            raise ProviderError("WhatsApp browser worker is disabled", "AUTHORIZATION_ERROR")
        if not contact or contact != getattr(self.settings, "whatsapp_contact", ""):
            raise ProviderError("WhatsApp contact is not allowlisted", "AUTHORIZATION_ERROR")
        if not body.strip() or len(body) > 4000:
            raise ProviderError("WhatsApp message must contain 1–4000 characters", "VALIDATION_ERROR")
        async with self._lock:
            sent = False
            try:
                page = await self._conversation(contact)
                composer = page.locator('#main [data-testid="conversation-compose-box-input"]')
                if await composer.count() != 1:
                    composer = page.locator("#main").get_by_role("textbox", name="Type a message", exact=True)
                if (
                    await composer.count() != 1
                    or await composer.get_attribute("role") != "textbox"
                    or await composer.get_attribute("contenteditable") != "true"
                    or await composer.get_attribute("aria-label")
                    not in {"Type a message", "Type a message to " + contact}
                ):
                    raise ProviderError("WhatsApp composer identity could not be verified", "AUTHORIZATION_ERROR")
                if (await composer.inner_text()).strip():
                    raise ProviderError(
                        "WhatsApp contains an existing draft; clear it manually before executing",
                        "CONFLICT_DETECTED",
                    )
                before = {n["id"] for n in await page.evaluate(OUTGOING_RECORDS)}
                await composer.fill(body)
                button = page.locator("#main").get_by_role("button", name="Send", exact=True)
                sent = True  # Any failure from the click onward is an uncertain mutation.
                await button.click()
                await page.wait_for_function(
                    "({before, body}) => (" + OUTGOING_RECORDS + ")().some(n => !before.includes(n.id) && n.text.includes(body))",
                    arg={"before": list(before), "body": body},
                    timeout=15000,
                )
                candidates = await page.evaluate(OUTGOING_RECORDS)
                matches = [n for n in candidates if n["id"] not in before and body in n["text"]]
                if len(matches) != 1:
                    raise ProviderError(
                        "UNCERTAIN: WhatsApp message identity could not be reconciled",
                        "VERIFICATION_ERROR",
                        True,
                    )
                return {"id": matches[0]["id"], "contact": contact, "body": body, "idempotency_key": key}
            except ProviderError:
                raise
            except Exception as exc:
                raise ProviderError(
                    "UNCERTAIN: verify WhatsApp before retry"
                    if sent
                    else "WhatsApp interface unavailable; no send was attempted",
                    "BROWSER_AUTOMATION_ERROR",
                    sent,
                ) from exc

    async def verify(self, result):
        async with self._lock:
            page = await self._conversation(result["contact"])
            records = await page.evaluate(OUTGOING_RECORDS)
            matches = [
                n
                for n in records
                if n["id"] == result["id"] and result["body"] in n["text"] and n["sent"] and not n["pending"]
            ]
            return {
                "verified": len(matches) == 1,
                "detail": "WhatsApp outgoing message and sent indicator read from the conversation"
                if matches
                else "WhatsApp send not confirmed; manual review required",
                "provider_id": result["id"],
            }
