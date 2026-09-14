"""Local DOM contract fixture. This is not a live WhatsApp account test."""

from types import SimpleNamespace

import pytest
from playwright.async_api import async_playwright

from lifeos.providers import ProviderError
from lifeos.whatsapp import WhatsAppWorker


HTML = """
<input role="textbox" aria-label="Search input textbox">
<div id="pane-side"><button title="Family">Family</button></div>
<main id="main">
  <header><span title="Family">Family</span></header>
  <div contenteditable="true" role="textbox" aria-label="Type a message"></div>
  <button aria-label="Send" onclick="sendMessage()">Send</button>
</main>
<script>
function sendMessage() {
  const editor = document.querySelector('[contenteditable]');
  const message = document.createElement('div');
  message.className = 'message-out';
  message.dataset.id = 'outgoing-1';
  message.textContent = editor.textContent;
  const receipt = document.createElement('span');
  receipt.dataset.icon = 'msg-check';
  message.appendChild(receipt);
  document.querySelector('#main').appendChild(message);
  editor.textContent = '';
}
</script>
"""

CURRENT_HTML = """
<input role="textbox" aria-label="Search or start a new chat">
<div id="pane-side"><button title="Family">Family</button></div>
<main id="main">
  <header><span data-testid="conversation-info-header-chat-title">Family</span></header>
  <div data-testid="conversation-compose-box-input" contenteditable="true" role="textbox" aria-label="Type a message to Family"></div>
  <button aria-label="Send" onclick="sendMessage()">Send</button>
</main>
<script>
function sendMessage() {
  const editor = document.querySelector('[contenteditable]');
  const record = document.createElement('div'); record.dataset.id = 'current-outgoing-1';
  const container = document.createElement('div'); container.dataset.testid = 'msg-container';
  const tail = document.createElement('span'); tail.dataset.icon = 'tail-out'; container.appendChild(tail);
  const text = document.createElement('span'); text.dataset.testid = 'selectable-text'; text.textContent = editor.textContent; container.appendChild(text);
  const meta = document.createElement('div'); meta.dataset.testid = 'msg-meta';
  const read = document.createElement('span'); read.setAttribute('aria-label', ' Read '); meta.appendChild(read); container.appendChild(meta);
  record.appendChild(container); document.querySelector('#main').appendChild(record); editor.textContent = '';
}
</script>
"""


@pytest.mark.asyncio
async def test_conversation_recognizes_current_whatsapp_search_label():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.set_content(HTML.replace("Search input textbox", "Search or start a new chat"))
        worker = WhatsAppWorker(SimpleNamespace())
        worker._context, worker._page = context, page
        try:
            assert await worker._conversation("Family") is page
            assert await page.locator(".message-out").count() == 0
        finally:
            await worker.close()
            await browser.close()


@pytest.mark.asyncio
async def test_browser_send_and_readback_use_new_message_identity():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.set_content(HTML)
        worker = WhatsAppWorker(SimpleNamespace(whatsapp_enabled=True, whatsapp_contact="Family"))
        worker._context, worker._page = context, page
        result = await worker.send("Family", "Leave at 03:45", "action-key")
        assert result["id"] == "outgoing-1"
        assert (await worker.verify(result))["verified"]
        await worker.close()
        await browser.close()


@pytest.mark.asyncio
async def test_browser_preserves_existing_draft():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.set_content(HTML)
        await page.get_by_role("textbox", name="Type a message").fill("My unsent draft")
        worker = WhatsAppWorker(SimpleNamespace(whatsapp_enabled=True, whatsapp_contact="Family"))
        worker._context, worker._page = context, page
        with pytest.raises(ProviderError, match="existing draft"):
            await worker.send("Family", "Automated message", "key")
        assert await page.locator(".message-out").count() == 0
        assert await page.get_by_role("textbox", name="Type a message").inner_text() == "My unsent draft"
        await worker.close()
        await browser.close()


@pytest.mark.asyncio
async def test_current_whatsapp_markup_verifies_one_outgoing_message_and_read_receipt():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.set_content(CURRENT_HTML)
        worker = WhatsAppWorker(SimpleNamespace(whatsapp_enabled=True, whatsapp_contact="Family"))
        worker._context, worker._page = context, page
        try:
            result = await worker.send("Family", "LIFEOS test", "current-key")
            assert result["id"] == "current-outgoing-1"
            assert (await worker.verify(result))["verified"]
            recent = await worker.read_recent("Family")
            assert recent["items"][0]["content"] == "LIFEOS test"
            assert recent["items"][0]["outgoing"] is True
            assert await page.locator('[data-testid="msg-container"]').count() == 1
        finally:
            await worker.close()
            await browser.close()


@pytest.mark.asyncio
async def test_reopening_selected_chat_works_after_search_field_disappears():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.set_content(CURRENT_HTML.replace('chat-title">Family</span>', 'chat-title">Other</span>'))
        await page.evaluate("""() => document.querySelector('#pane-side button').addEventListener('click', () => {
            document.querySelector('[aria-label="Search or start a new chat"]').remove();
            document.querySelector('[data-testid="conversation-info-header-chat-title"]').textContent = 'Family';
        })""")
        worker = WhatsAppWorker(SimpleNamespace())
        worker._context, worker._page = context, page
        try:
            assert await worker._conversation("Family") is page
            assert await page.get_by_role("textbox", name="Search or start a new chat").count() == 0
            assert await worker._conversation("Family") is page
        finally:
            await worker.close()
            await browser.close()
