import base64
import hashlib
import json
from io import BytesIO

import pytest

import sentinel.extract as extract
import sentinel.llm as llm  # the shared transport annotate_image posts through

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png-bytes-for-test"


def _resp(payload: dict):
    class R(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    return R(json.dumps(payload).encode())


def _azure_ok(text: str) -> dict:
    return {"choices": [{"finish_reason": "stop", "message": {"content": text, "refusal": None}}]}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "sentinel-judge")
    monkeypatch.setattr(extract, "CACHE_DIR", tmp_path / "extract")


@pytest.fixture
def png_file(tmp_path):
    path = tmp_path / "promo.png"
    path.write_bytes(PNG_BYTES)
    return path


def test_wire_shape(env, png_file, monkeypatch):
    captured = {}

    def fake(req, timeout):
        captured["body"] = json.loads(req.data)
        captured["req"] = req
        return _resp(_azure_ok("[headline · large · bold] DRIVE AWAY TODAY"))

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake)
    result = extract.annotate_image(png_file)
    assert result == "[headline · large · bold] DRIVE AWAY TODAY"

    body = captured["body"]
    assert body["model"] == "sentinel-judge"
    assert body["temperature"] == 0
    assert "response_format" not in body

    content = body["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": extract.ANNOTATE_PROMPT}
    assert content[1]["type"] == "image_url"
    url = content[1]["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    b64 = url.split(",", 1)[1]
    assert base64.b64decode(b64) == PNG_BYTES

    assert captured["req"].get_header("Api-key") == "test-key"


def test_cache_hit_skips_network(env, png_file, monkeypatch):
    monkeypatch.setattr(
        llm.urllib.request, "urlopen", lambda req, timeout: _resp(_azure_ok("annotated text"))
    )
    first = extract.annotate_image(png_file)

    def boom(req, timeout):
        raise AssertionError("network hit on cached call")

    monkeypatch.setattr(llm.urllib.request, "urlopen", boom)
    second = extract.annotate_image(png_file)
    assert first == second == "annotated text"


def test_cache_key_is_model_and_prompt_scoped(env, png_file, monkeypatch):
    """An entry cached under the pre-fix bytes-only key must NOT be served after the fix."""
    calls = []

    def fake(req, timeout):
        calls.append(1)
        return _resp(_azure_ok("fresh annotation"))

    stale_key = hashlib.sha256(PNG_BYTES).hexdigest()  # old key scheme: file bytes only
    cache_dir = extract.CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / (stale_key + ".txt")).write_text("stale annotation", encoding="utf-8")

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake)
    result = extract.annotate_image(png_file)

    assert calls == [1]  # stale entry was a miss -> re-annotated over the network
    assert result == "fresh annotation"  # the stale annotation was never served


def test_unsupported_extension_raises_systemexit(env, tmp_path):
    path = tmp_path / "promo.jp2"
    path.write_bytes(b"not really jp2")
    with pytest.raises(SystemExit, match=r"convert to png first \('jp2' unsupported by the vision API\)"):
        extract.annotate_image(path)


# refusal / empty-choices / non-stop finish_reason are llm.chat_content's contract now — tested once, in test_llm.py
