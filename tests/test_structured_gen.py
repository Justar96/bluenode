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


def test_generate_tool_calls_batch_multiple_intents():
    """Verify multiple intents are processed and outputs aligned."""
    from codesearch_gym.structured_gen import generate_tool_calls_batch

    class BatchDummyLLM:
        def generate(self, prompts, sampling_params=None):  # type: ignore[no-untyped-def]
            # Return different payloads for each prompt
            results = []
            for i, _ in enumerate(prompts):
                if i % 2 == 0:
                    payload = {
                        "name": "ast_grep_search",
                        "arguments": {"pattern": f"pattern_{i}", "language": "javascript"},
                    }
                else:
                    payload = {
                        "name": "ripgrep_search",
                        "arguments": {"pattern": f"pattern_{i}", "case_sensitive": False},
                    }
                results.append(DummyOut(json.dumps(payload)))
            return results

    llm = BatchDummyLLM()
    intents = ["intent_0", "intent_1", "intent_2", "intent_3"]
    results = generate_tool_calls_batch(intents, model=llm, mode="offline")

    assert len(results) == 4
    # Verify outputs are aligned with inputs
    for i, (call, raw, valid, err) in enumerate(results):
        assert valid and err is None
        assert isinstance(call, dict)
        assert f"pattern_{i}" in call["arguments"]["pattern"]


def test_generate_tool_calls_batch_respects_batch_size():
    """Mock DummyLLM.generate to capture call counts with batch_size."""
    from codesearch_gym.structured_gen import generate_tool_calls_batch

    class BatchCountingLLM:
        def __init__(self) -> None:
            self.call_count = 0
            self.batch_sizes: list[int] = []

        def generate(self, prompts, sampling_params=None):  # type: ignore[no-untyped-def]
            self.call_count += 1
            self.batch_sizes.append(len(prompts))
            results = []
            for _ in prompts:
                payload = {
                    "name": "ast_grep_search",
                    "arguments": {"pattern": "test", "language": "javascript"},
                }
                results.append(DummyOut(json.dumps(payload)))
            return results

    llm = BatchCountingLLM()
    intents = ["intent_" + str(i) for i in range(10)]
    results = generate_tool_calls_batch(intents, model=llm, mode="offline", batch_size=3)

    assert len(results) == 10
    # Verify the LLM was called multiple times with correct batch sizes
    assert llm.call_count == 4  # 10 intents with batch_size=3: 3+3+3+1=10
    assert llm.batch_sizes == [3, 3, 3, 1]


def test_create_vllm_generator_fallback_no_backend():
    """Patch _try_import_vllm to raise TypeError on backend arg and assert fallback."""
    from unittest.mock import Mock, patch
    from codesearch_gym.structured_gen import create_vllm_generator

    class MockLLM:
        def __init__(self, model, tensor_parallel_size=1, gpu_memory_utilization=0.9, dtype="auto", trust_remote_code=True, guided_decoding_backend=None):  # type: ignore[no-untyped-def]
            if guided_decoding_backend is not None:
                raise TypeError("unexpected keyword argument 'guided_decoding_backend'")
            self.model = model
            self.tensor_parallel_size = tensor_parallel_size

    with patch("codesearch_gym.structured_gen._try_import_vllm", return_value=(MockLLM, None, None)):
        llm = create_vllm_generator("test-model")
        assert llm.model == "test-model"
        assert llm.tensor_parallel_size == 1


def test_generate_tool_call_online_api_error():
    """Simulate client error and assert graceful error handling."""
    from codesearch_gym.structured_gen import generate_tool_call

    class ErrorClient:
        class _Chat:
            class _Completions:
                def create(self, **kwargs):  # type: ignore[no-untyped-def]
                    raise RuntimeError("API connection failed")

            def __init__(self) -> None:
                self.completions = ErrorClient._Chat._Completions()

        @property
        def chat(self):  # type: ignore[no-untyped-def]
            return ErrorClient._Chat()

    client = ErrorClient()
    call, raw, valid, err = generate_tool_call(
        intent="Find test functions",
        mode="online",
        client=client,
        model="test-model",
    )
    assert not valid
    assert call is None
    assert err is not None
    assert "online generation error" in err


def test_sampling_params_temperature_passthrough():
    """Inspect DummyLLM.last_params to ensure temperature/top_p/max_tokens propagate."""
    llm = DummyLLM()
    call, raw, valid, err = generate_tool_call(
        intent="Find functions",
        model=llm,
        mode="offline",
        temperature=0.8,
        max_tokens=256,
        top_p=0.9,
    )
    assert valid
    # Verify sampling params were passed
    assert llm.last_params is not None
    if isinstance(llm.last_params, dict):
        assert llm.last_params["temperature"] == 0.8
        assert llm.last_params["max_tokens"] == 256
        assert llm.last_params["top_p"] == 0.9
    else:
        # vLLM SamplingParams object
        assert llm.last_params.temperature == 0.8
        assert llm.last_params.max_tokens == 256
        assert llm.last_params.top_p == 0.9


def test_generate_timeout_or_cuda_error():
    """Raise an exception in DummyLLM.generate and verify error handling."""
    from codesearch_gym.structured_gen import generate_tool_call

    class ErrorLLM:
        def generate(self, prompts, sampling_params=None):  # type: ignore[no-untyped-def]
            raise RuntimeError("CUDA out of memory")

    llm = ErrorLLM()
    call, raw, valid, err = generate_tool_call(
        intent="Find functions",
        model=llm,
        mode="offline",
    )
    assert not valid
    assert call is None
    assert err is not None
    assert "generation error" in err


def test_generate_tool_call_online_mode_requires_model():
    """Verify online mode rejects empty or None model."""
    from codesearch_gym.structured_gen import generate_tool_call

    class DummyClient:
        pass

    # Test with None model
    call, raw, valid, err = generate_tool_call(
        intent="Find test functions",
        mode="online",
        client=DummyClient(),
        model=None,
    )
    assert not valid
    assert call is None
    assert err == "model is required for online mode"

    # Test with empty string model
    call, raw, valid, err = generate_tool_call(
        intent="Find test functions",
        mode="online",
        client=DummyClient(),
        model="",
    )
    assert not valid
    assert call is None
    assert err == "model is required for online mode"
