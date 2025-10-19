"""Schema-guided tool call generation using vLLM Structured Outputs.

Dual-mode generator:
- offline: use vLLM LLM API with GuidedDecodingParams(json=TOOL_CALL_SCHEMA)
- online: use OpenAI-compatible client with extra_body={"guided_json": TOOL_CALL_SCHEMA}

Exports:
- generate_tool_call
- generate_tool_calls_batch
- create_vllm_generator
- build_tool_use_prompt
- validate_and_repair_tool_call
- RECOMMENDED_MODELS
- DEFAULT_SAMPLING_PARAMS
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from .runner import validate_pcre2_requirement
from .schemas import TOOL_CALL_SCHEMA, validate_tool_call

# Model recommendations (kept small and factual; detailed docs live in docs/MODEL_COMPARISON.md)
RECOMMENDED_MODELS: dict[str, dict[str, Any]] = {
    "qwen2.5-coder-32b": {
        "name": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "description": "Primary recommendation: strong function-calling, fits 2×48GB, solid performance",
        "hardware": "2×L40S (48GB each) with tensor_parallel_size=2",
        "vllm_parser": "hermes",
        "context_length": 32768,
    },
    "qwen2.5-coder-14b": {
        "name": "Qwen/Qwen2.5-Coder-14B-Instruct",
        "description": "Smaller variant for single GPU development/testing",
        "hardware": "1×L40S (48GB)",
        "vllm_parser": "hermes",
        "context_length": 32768,
    },
    "glm-4-9b": {
        "name": "THUDM/glm-4-9b-chat",
        "description": "GLM-4 open-source with strong function-calling and long context",
        "hardware": "1×L40S (48GB)",
        "context_length": 131072,
    },
    "llama-3.1-70b-awq": {
        "name": "hugging-quants/Meta-Llama-3.1-70B-Instruct-AWQ-INT4",
        "description": "Quantized Llama: high quality with INT4",
        "hardware": "2×L40S (48GB each) with quantization",
        "context_length": 131072,
        "quantization": "awq",
    },
}


DEFAULT_SAMPLING_PARAMS: dict[str, Any] = {
    "temperature": 0.6,
    "max_tokens": 512,
    "top_p": 0.95,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
}


def _try_import_vllm() -> tuple[Any, Any, Any]:
    """Return (LLM, SamplingParams, GuidedDecodingParams) or (None, None, None) if unavailable.

    Implemented lazily to keep vLLM optional.
    """
    try:
        from vllm import LLM, SamplingParams  # type: ignore
        from vllm.sampling_params import GuidedDecodingParams  # type: ignore

        return LLM, SamplingParams, GuidedDecodingParams
    except Exception:
        return None, None, None


def build_tool_use_prompt(
    intent: str, system_prompt: str | None = None, format: str = "chat"
) -> str:
    """Build a minimal prompt instructing proper tool choice and arguments.

    - chat format uses <system>/<user> wrappers compatible with many chat-tuned models
    - completion format returns a plain instruction + intent
    """
    default_system = (
        "You are a code search expert. Use ast-grep for structural patterns (functions, classes, AST). "
        "Use ripgrep for text/literal searches (strings, comments, logs). Choose the right tool and provide valid arguments. "
        "For ripgrep, enable PCRE2 (-P) when using lookarounds/backreferences; for ast-grep, specify the language."
    )
    sys_msg = system_prompt or default_system
    if format == "completion":
        return f"{sys_msg}\nIntent: {intent}\nRespond with a JSON object only."
    return (
        f"<system>{sys_msg}</system>\n"
        f"<user>{intent}</user>\n"
        f"<assistant>"  # models often expect the assistant role to start emitting JSON
    )


def create_vllm_generator(
    model_name: str,
    tensor_parallel_size: int = 1,
    gpu_memory_utilization: float = 0.9,
    dtype: str = "auto",
    trust_remote_code: bool = True,
    guided_decoding_backend: str = "xgrammar",
) -> Any:
    """Create and return a configured vLLM LLM instance.

    Note: guided_decoding_backend is forwarded to the LLM constructor if supported by the vLLM version.
    """
    LLM, _, _ = _try_import_vllm()
    if LLM is None:  # pragma: no cover - exercised in environments without vLLM
        raise ImportError('vLLM is not installed. Install with `pip install -e ".[vllm]"`.')
    # Pass through common parameters; ignore backend if unsupported in current vLLM
    try:
        return LLM(
            model=model_name,
            tensor_parallel_size=tensor_parallel_size,
            gpu_memory_utilization=gpu_memory_utilization,
            dtype=dtype,
            trust_remote_code=trust_remote_code,
            guided_decoding_backend=guided_decoding_backend,  # some versions accept this
        )
    except TypeError:
        # Fallback without backend arg
        return LLM(
            model=model_name,
            tensor_parallel_size=tensor_parallel_size,
            gpu_memory_utilization=gpu_memory_utilization,
            dtype=dtype,
            trust_remote_code=trust_remote_code,
        )


def _coerce_model(model: Any | None) -> str | None:
    if isinstance(model, str):
        return model
    return None


def _parse_and_validate(raw: str) -> tuple[dict[str, Any] | None, bool, str | None]:
    try:
        obj = json.loads(raw)
    except Exception as e:
        return None, False, f"JSON parse error: {e}"
    valid, err = validate_tool_call(obj)
    return (obj if valid else obj), valid, err


def validate_and_repair_tool_call(
    call_dict: dict[str, Any],
) -> tuple[dict[str, Any], bool, list[str]]:
    """Attempt common repairs to a tool call; return (repaired, was_repaired, notes)."""
    repaired = json.loads(json.dumps(call_dict))
    notes: list[str] = []

    name = repaired.get("name")
    args = repaired.get("arguments")
    if not isinstance(args, dict):
        return repaired, False, ["arguments not an object"]

    # Normalize language aliases for ast-grep
    if name == "ast_grep_search":
        lang = args.get("language")
        alias_map = {
            "js": "javascript",
            "ts": "typescript",
            "py": "python",
            "c++": "cpp",
            "c#": "csharp",
        }
        if isinstance(lang, str) and lang.lower() in alias_map:
            args["language"] = alias_map[lang.lower()]
            notes.append("mapped language alias")

    # Defaults and PCRE2 auto-fix for ripgrep
    if name == "ripgrep_search":
        if "case_sensitive" not in args:
            args["case_sensitive"] = False
            notes.append("defaulted case_sensitive=False")
        if "pcre2" not in args:
            args["pcre2"] = False
            notes.append("defaulted pcre2=False")
        pat = args.get("pattern")
        if isinstance(pat, str):
            need_pcre2, _ = validate_pcre2_requirement(pat)
            if need_pcre2 and not bool(args.get("pcre2")):
                args["pcre2"] = True
                notes.append("auto-enabled pcre2 for lookaround/backref")

    repaired["arguments"] = args
    valid, err = validate_tool_call(repaired)
    return repaired, (len(notes) > 0 and valid), ([] if err is None else [err]) + notes


def generate_tool_call(
    intent: str,
    model: Any | None = None,
    temperature: float = DEFAULT_SAMPLING_PARAMS["temperature"],
    max_tokens: int = DEFAULT_SAMPLING_PARAMS["max_tokens"],
    top_p: float = DEFAULT_SAMPLING_PARAMS["top_p"],
    mode: str = "offline",
    client: Any | None = None,
    system_prompt: str | None = None,
) -> tuple[dict[str, Any] | None, str, bool, str | None]:
    """Generate a single schema-true tool call from a natural language intent.

    Returns (tool_call_dict_or_None, raw_output, is_valid, error_message_or_None)
    """
    prompt = build_tool_use_prompt(intent, system_prompt=system_prompt, format="chat")

    if mode == "offline":
        LLM, SamplingParams, GuidedDecodingParams = _try_import_vllm()
        # Support passing either a ready LLM instance or a model name
        llm = model
        if isinstance(model, str):  # lazy create
            if LLM is None:
                return None, "", False, "vLLM not installed"
            llm = create_vllm_generator(model)
        if llm is None:
            # Default to recommended primary model name if not provided
            default_name = RECOMMENDED_MODELS["qwen2.5-coder-32b"]["name"]
            if LLM is None:
                return None, "", False, "vLLM not installed"
            llm = create_vllm_generator(default_name)

        # Build sampling params or a lightweight dict if vLLM isn't available (for tests)
        guided = None
        sp = None
        if GuidedDecodingParams is not None and SamplingParams is not None:
            guided = GuidedDecodingParams(json=TOOL_CALL_SCHEMA)
            sp = SamplingParams(
                temperature=temperature, max_tokens=max_tokens, top_p=top_p, guided_decoding=guided
            )
        else:
            sp = {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "guided_decoding": {"json": TOOL_CALL_SCHEMA},
            }
        try:
            result = llm.generate([prompt], sampling_params=sp)  # type: ignore[attr-defined]
        except Exception as e:  # pragma: no cover - depends on runtime env
            return None, "", False, f"generation error: {e}"

        # Normalize vLLM outputs structure
        try:
            raw = result[0].outputs[0].text  # type: ignore[index]
        except Exception:
            # Some stubs may return strings directly
            raw = getattr(result, "text", "") if isinstance(result, object) else ""

        obj, valid, err = _parse_and_validate(raw)
        if isinstance(obj, dict):
            obj2, repaired, notes = validate_and_repair_tool_call(obj)
            valid2, err2 = validate_tool_call(obj2)
            if valid2 and (repaired or obj2 != obj or not valid):
                return obj2, raw, True, None
            if not valid2 and not valid:
                return obj, raw, False, err or ("; ".join(notes + ([err2] if err2 else [])) or None)
        return obj, raw, valid, err

    # online mode
    if client is None:
        return None, "", False, "client is required for online mode"
    # OpenAI-compatible API
    messages = [
        {"role": "system", "content": system_prompt or "You are a code search expert."},
        {"role": "user", "content": intent},
    ]
    try:
        resp = client.chat.completions.create(  # type: ignore[attr-defined]
            model=_coerce_model(model) or "",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body={"guided_json": TOOL_CALL_SCHEMA},
        )
        # OpenAI-style
        raw = resp.choices[0].message.content  # type: ignore[index]
    except Exception as e:  # pragma: no cover
        return None, "", False, f"online generation error: {e}"

    obj, valid, err = _parse_and_validate(raw)
    if isinstance(obj, dict):
        obj2, repaired, notes = validate_and_repair_tool_call(obj)
        valid2, err2 = validate_tool_call(obj2)
        if valid2 and (repaired or obj2 != obj or not valid):
            return obj2, raw, True, None
        if not valid2 and not valid:
            return obj, raw, False, err or ("; ".join(notes + ([err2] if err2 else [])) or None)
    return obj, raw, valid, err


def generate_tool_calls_batch(
    intents: Sequence[str],
    model: Any | None = None,
    temperature: float = DEFAULT_SAMPLING_PARAMS["temperature"],
    max_tokens: int = DEFAULT_SAMPLING_PARAMS["max_tokens"],
    top_p: float = DEFAULT_SAMPLING_PARAMS["top_p"],
    mode: str = "offline",
    client: Any | None = None,
    system_prompt: str | None = None,
    batch_size: int | None = None,
) -> list[tuple[dict[str, Any] | None, str, bool, str | None]]:
    """Batch generation helper. For offline vLLM, uses a single llm.generate call.

    Online mode loops sequentially (most OpenAI-compatible servers don't support batch in one call).
    """
    results: list[tuple[dict[str, Any] | None, str, bool, str | None]] = []
    if not intents:
        return results

    if mode == "offline":
        LLM, SamplingParams, GuidedDecodingParams = _try_import_vllm()
        llm = model
        if isinstance(model, str):
            if LLM is None:
                # Fallback to per-intent calls to surface a clear error per item
                return [
                    generate_tool_call(
                        i,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        mode=mode,
                        client=client,
                        system_prompt=system_prompt,
                    )
                    for i in intents
                ]
            llm = create_vllm_generator(model)
        if llm is None:
            default_name = RECOMMENDED_MODELS["qwen2.5-coder-32b"]["name"]
            if LLM is None:
                return [
                    generate_tool_call(
                        i,
                        model=llm,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        mode=mode,
                        client=client,
                        system_prompt=system_prompt,
                    )
                    for i in intents
                ]
            llm = create_vllm_generator(default_name)

        prompts = [
            build_tool_use_prompt(it, system_prompt=system_prompt, format="chat") for it in intents
        ]
        if GuidedDecodingParams is not None and SamplingParams is not None:
            guided = GuidedDecodingParams(json=TOOL_CALL_SCHEMA)
            sp = SamplingParams(
                temperature=temperature, max_tokens=max_tokens, top_p=top_p, guided_decoding=guided
            )
        else:
            sp = {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "guided_decoding": {"json": TOOL_CALL_SCHEMA},
            }
        try:
            outs = llm.generate(prompts, sampling_params=sp)  # type: ignore[attr-defined]
        except Exception as e:  # pragma: no cover
            return [(None, "", False, f"generation error: {e}") for _ in intents]

        for out in outs:
            try:
                raw = out.outputs[0].text  # type: ignore[index]
            except Exception:
                raw = getattr(out, "text", "")
            obj, valid, err = _parse_and_validate(raw)
            if isinstance(obj, dict):
                obj2, repaired, _ = validate_and_repair_tool_call(obj)
                valid2, err2 = validate_tool_call(obj2)
                if valid2 and (repaired or obj2 != obj or not valid):
                    results.append((obj2, raw, True, None))
                    continue
            results.append((obj, raw, valid, err))
        return results

    # online mode sequential
    for it in intents:
        results.append(
            generate_tool_call(
                intent=it,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                mode=mode,
                client=client,
                system_prompt=system_prompt,
            )
        )
    return results
