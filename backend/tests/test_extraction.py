from app.extraction import fallback_extract, parse_eml, parse_pasted

SAMPLE_EML = b"""\
From: Jane Doe <jane@doebodyshop.com>
To: hello@estimoto.io
Subject: Interested in Estimoto for our shop
Content-Type: text/plain

Hi, we run a 3-bay collision shop and want a demo.
Call me at (555) 123-4567.
"""


def test_parse_eml_headers_and_body():
    parsed = parse_eml(SAMPLE_EML)
    assert parsed.sender_name == "Jane Doe"
    assert parsed.sender_email == "jane@doebodyshop.com"
    assert parsed.subject == "Interested in Estimoto for our shop"
    assert "3-bay collision shop" in parsed.body


def test_parse_pasted_with_headers():
    parsed = parse_pasted(
        "From: Bob Smith <bob@smithauto.com>\nSubject: Demo request\n\nWe want pricing."
    )
    assert parsed.sender_email == "bob@smithauto.com"
    assert parsed.sender_name == "Bob Smith"
    assert parsed.subject == "Demo request"


def test_parse_pasted_bare_text_finds_email():
    parsed = parse_pasted("Please reach out to mike@garage99.com about your product")
    assert parsed.sender_email == "mike@garage99.com"


def test_fallback_extract_full():
    ex = fallback_extract(parse_eml(SAMPLE_EML))
    assert ex.method == "fallback"
    assert ex.name == "Jane Doe"
    assert ex.email == "jane@doebodyshop.com"
    assert ex.phone == "(555) 123-4567"
    assert ex.company == "Doebodyshop"
    assert ex.intent == "Interested in Estimoto for our shop"


def test_fallback_derives_name_from_email_and_skips_generic_domains():
    parsed = parse_pasted("contact john.smith@gmail.com for details")
    ex = fallback_extract(parsed)
    assert ex.name == "John Smith"
    assert ex.company == ""  # gmail is not a company


def test_extract_logs_when_claude_fails(monkeypatch, caplog):
    import logging

    from app import extraction
    from app.config import Settings

    monkeypatch.setattr(extraction, "get_settings", lambda: Settings(anthropic_api_key="key"))

    def boom(parsed):
        raise RuntimeError("api down")

    monkeypatch.setattr(extraction, "claude_extract", boom)

    with caplog.at_level(logging.WARNING):
        ex = extraction.extract(parse_pasted("From: Jane <jane@shop.com>\n\nhello"))

    assert ex.method == "fallback"
    assert any("extraction" in r.message.lower() for r in caplog.records)


def test_claude_extract_parses_forced_tool_use(monkeypatch):
    """The Claude path itself, with the SDK mocked at the client boundary."""
    from types import SimpleNamespace

    from app import extraction
    from app.config import Settings

    monkeypatch.setattr(extraction, "get_settings", lambda: Settings(anthropic_api_key="key"))

    tool_block = SimpleNamespace(
        type="tool_use",
        input={
            "name": "Jane Doe",
            "email": "jane@doebodyshop.com",
            "phone": "555-123-4567",
            "company": "Doe Body Shop",
            "intent": "Wants a demo for a 3-bay shop",
            "estimated_value": 4800,
        },
    )
    fake_response = SimpleNamespace(content=[SimpleNamespace(type="text"), tool_block])

    class FakeClient:
        def __init__(self, api_key):
            assert api_key == "key"
            self.messages = SimpleNamespace(create=self._create)

        def _create(self, **kwargs):
            assert kwargs["tool_choice"] == {"type": "tool", "name": "record_lead"}
            return fake_response

    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)

    ex = extraction.extract(parse_eml(SAMPLE_EML))
    assert ex.method == "claude"
    assert ex.name == "Jane Doe"
    assert ex.company == "Doe Body Shop"
    assert ex.estimated_value == 4800
