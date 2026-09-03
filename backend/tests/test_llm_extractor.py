"""
Tests for services.llm_extractor's JSON-parsing/repair path (issue #7) — the
LLM client itself is mocked so these run offline with no network calls.
"""
import services.llm_extractor as extractor


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content):
        self._content = content

    def create(self, **kwargs):
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content):
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content):
        self.chat = _FakeChat(content)


def _fake_get_client(content):
    return lambda: (_FakeClient(content), "fake-model")


def test_extract_graph_parses_clean_json(monkeypatch):
    raw = '{"entities": [{"id": "UltrasonicSensor", "label": "Ultrasonic Sensor", "type": "sensor"}], "relations": []}'
    monkeypatch.setattr(extractor, "_get_client", _fake_get_client(raw))

    result = extractor.extract_graph_from_requirements([{"id": "REQ-001", "text": "x"}])
    assert result["entities"][0]["id"] == "UltrasonicSensor"
    assert result["relations"] == []


def test_extract_graph_strips_markdown_fences(monkeypatch):
    raw = '```json\n{"entities": [], "relations": [{"source": "REQ-001", "target": "Driver", "type": "mentions"}]}\n```'
    monkeypatch.setattr(extractor, "_get_client", _fake_get_client(raw))

    result = extractor.extract_graph_from_requirements([{"id": "REQ-001", "text": "x"}])
    assert result["relations"][0]["target"] == "Driver"


def test_extract_graph_falls_back_on_invalid_json(monkeypatch):
    monkeypatch.setattr(extractor, "_get_client", _fake_get_client("not valid json at all"))

    result = extractor.extract_graph_from_requirements([{"id": "REQ-001", "text": "x"}])
    assert result == {"entities": [], "relations": []}


def test_extract_graph_falls_back_when_no_client(monkeypatch):
    monkeypatch.setattr(extractor, "_get_client", lambda: (None, None))

    result = extractor.extract_graph_from_requirements([{"id": "REQ-001", "text": "x"}])
    assert result == {"entities": [], "relations": []}


def test_extract_graph_falls_back_on_client_exception(monkeypatch):
    class _BoomClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    raise RuntimeError("provider is down")

    monkeypatch.setattr(extractor, "_get_client", lambda: (_BoomClient(), "fake-model"))

    result = extractor.extract_graph_from_requirements([{"id": "REQ-001", "text": "x"}])
    assert result == {"entities": [], "relations": []}
