import json
from types import SimpleNamespace
from typing import Any

from codesearch_gym.structured_gen import (
    DEFAULT_SAMPLING_PARAMS,
    RECOMMENDED_MODELS,
    build_tool_use_prompt,
    generate_tool_call,
    validate_and_repair_tool_call,
)


class DummyOut:
    def __init__(self, text: str) -> None:
        self.outputs = [SimpleNamespace(text=text)]


class DummyLLM:
    def __init__(self) -> None:
        self.last_prompts = None
        self.last_params = None

    def generate(self, prompts, sampling_params=None):  # type: ignore[no-untyped-def]
        self.last_prompts = prompts
        self.last_params = sampling_params
        # Default to ast-grep valid JSON
        payload = {
            "name": "ast_grep_search",
            "arguments": {
                "pattern": "function $NAME($$$ARGS) { $$$BODY }",
                "language": "javascript",
            },
        }
        return [DummyOut(json.dumps(payload))]


def test_build_tool_use_prompt_chat_format():
    p = build_tool_use_prompt("Find React useEffect hooks")
    assert p.startswith("<system>") and "<user>" in p and p.endswith("<assistant>")


def test_validate_and_repair_pcre2_requirement():
    tool = {
        "name": "ripgrep_search",
        "arguments": {"pattern": r"(?<=TODO:)\\w+", "pcre2": False},
    }
    repaired, repaired_flag, notes = validate_and_repair_tool_call(tool)
    assert repaired["arguments"]["pcre2"] is True
    assert any("pcre2" in n for n in notes)


def test_generate_tool_call_offline_with_dummy_llm(monkeypatch):
    # Bypass vLLM import and use DummyLLM directly
    llm = DummyLLM()
    call, raw, valid, err = generate_tool_call(
        intent="Find functions in JS",
        model=llm,
        temperature=0.2,
        mode="offline",
    )
    assert valid and err is None
    assert isinstance(call, dict) and call.get("name") == "ast_grep_search"


def test_generate_tool_call_online_mode_minimal():
    class DummyClient:
        def __init__(self) -> None:
            self.last_extra_body: dict[str, Any] | None = None

        class _Chat:
            class _Completions:
                def __init__(self, outer) -> None:  # type: ignore[no-untyped-def]
                    self._outer = outer

                def create(self, **kwargs):  # type: ignore[no-untyped-def]
                    # capture extra_body with guided_json
                    self._outer.last_extra_body = kwargs.get("extra_body")
                    payload = {
                        "name": "ripgrep_search",
                        "arguments": {"pattern": "TODO", "case_sensitive": False},
                    }
                    return SimpleNamespace(
                        choices=[
                            SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))
                        ]
                    )

            def __init__(self, outer) -> None:  # type: ignore[no-untyped-def]
                self.completions = DummyClient._Chat._Completions(outer)

        def __init_subclass__(cls) -> None:
            pass

        @property
        def chat(self):  # type: ignore[no-untyped-def]
            return DummyClient._Chat(self)

    client = DummyClient()
    call, raw, valid, err = generate_tool_call(
        intent="Find TODO comments",
        mode="online",
        client=client,
        temperature=0.0,
        model="unused",
    )
    assert valid and err is None
    assert client.last_extra_body and "guided_json" in client.last_extra_body
    assert isinstance(call, dict) and call.get("name") == "ripgrep_search"


def test_build_tool_use_prompt_completion_format():
    p = build_tool_use_prompt("Find printf in C", format="completion")
    assert "Intent:" in p and p.endswith("Respond with a JSON object only.")


def test_repair_language_alias():
    tool = {
        "name": "ast_grep_search",
        "arguments": {"pattern": "function $NAME($$$ARGS) { $$$BODY }", "language": "js"},
    }
    repaired, repaired_flag, notes = validate_and_repair_tool_call(tool)
    assert repaired["arguments"]["language"] == "javascript"


def test_recommended_models_structure():
    assert "qwen2.5-coder-32b" in RECOMMENDED_MODELS
    qwen = RECOMMENDED_MODELS["qwen2.5-coder-32b"]
    assert "name" in qwen and "hardware" in qwen


def test_default_sampling_params_contains_expected_keys():
    for k in ("temperature", "max_tokens", "top_p"):
        assert k in DEFAULT_SAMPLING_PARAMS
