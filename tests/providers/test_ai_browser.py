import pytest
import httpx
import json

from lifeos.ai import EventExtraction, extract_event, transcribe, speak
from lifeos.whatsapp import WhatsAppWorker
from lifeos.providers import ProviderError
from types import SimpleNamespace


@pytest.mark.asyncio
async def test_ai_missing_credentials_fail_explicitly():
    for call in (
        extract_event("meeting moved", "", "gpt-4.1-mini", "UTC"),
        transcribe(b"audio", "clip.webm", ""),
        speak("hello", ""),
    ):
        with pytest.raises(ProviderError, match="OpenAI"):
            await call


def test_extraction_rejects_invalid_times():
    with pytest.raises(ValueError):
        EventExtraction(
            event_type="meeting_change",
            title="Move",
            new_time="31:90",
            old_time=None,
            date="2026-09-13",
            flight=None,
            confidence=0.9,
        )


@pytest.mark.asyncio
async def test_whatsapp_non_allowlisted_contact_fails_before_browser():
    worker = WhatsAppWorker(
        SimpleNamespace(whatsapp_enabled=True, whatsapp_contact="Family", whatsapp_profile_dir="private")
    )
    with pytest.raises(ProviderError, match="allowlisted"):
        await worker.send("Attacker", "secret", "key")


@pytest.mark.asyncio
async def test_whatsapp_disabled_fails_before_browser():
    worker = WhatsAppWorker(SimpleNamespace(whatsapp_enabled=False))
    with pytest.raises(ProviderError, match="disabled"):
        await worker.send("Family", "hello", "key")


@pytest.mark.asyncio
async def test_openai_extraction_stt_and_tts_http_contract(monkeypatch):
    original = httpx.AsyncClient

    def handler(request):
        assert request.headers["authorization"] == "Bearer test-key"
        if request.url.path.endswith("/responses"):
            body = json.loads(request.content)
            assert body["store"] is False
            assert body["text"]["format"]["strict"] is True
            assert "tools" not in body
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "output": [
                        {
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": json.dumps(
                                        {
                                            "event_type": "meeting_change",
                                            "title": "Meeting moved",
                                            "date": "2026-09-15",
                                            "new_time": "14:00",
                                            "old_time": None,
                                            "flight": None,
                                            "confidence": 0.95,
                                        }
                                    ),
                                }
                            ]
                        }
                    ],
                },
            )
        if request.url.path.endswith("/transcriptions"):
            assert "multipart/form-data" in request.headers["content-type"]
            assert b"gpt-4o-mini-transcribe" in request.content
            return httpx.Response(200, json={"text": "Meeting moved to two PM"})
        assert json.loads(request.content)["model"] == "gpt-4o-mini-tts"
        return httpx.Response(200, content=b"MP3 fixture", headers={"content-type": "audio/mpeg"})

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)
    )
    result = await extract_event(
        "Meeting moved to two PM September 15, 2026", "test-key", "gpt-4.1-mini", "UTC"
    )
    assert result["new_time"] == "14:00"
    assert await transcribe(b"recording", "clip.webm", "test-key") == "Meeting moved to two PM"
    assert await speak("Approved updates completed", "test-key") == b"MP3 fixture"


@pytest.mark.asyncio
async def test_openai_refusal_does_not_fabricate_event(monkeypatch):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(
                    200, json={"output": [{"content": [{"type": "refusal", "refusal": "No"}]}]}
                )
            ),
            **kw,
        ),
    )
    with pytest.raises(ProviderError, match="no valid event"):
        await extract_event("bad input", "test-key", "gpt-4.1-mini", "UTC")
