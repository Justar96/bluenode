Perfect—here’s the **drop‑in module + seed set** you asked for. It gives you:

* a **schema‑true function‑call generator** (vLLM Structured Outputs),
* a **runner/verifier** that actually executes `ast-grep` and `ripgrep` and normalizes results,
* a **grader** with file‑IoU and span‑F1,
* **adversarial, multi‑lang seed blueprints** + tiny **fixtures** so you can verify end‑to‑end immediately,
* a **quickstart** that materializes corpora, runs + grades, and emits an **xLAM‑style dataset** for SFT/RFT.

**Download:** [codesearch_gym.zip](sandbox:/mnt/data/codesearch_gym.zip)

---

## What’s inside (short and sharp)

```
codesearch_gym/
  __init__.py
  schemas.py                # JSON Schema for tool calls (+ optional composite plan)
  runner.py                 # run_ast_grep / run_ripgrep → normalized findings
  grader.py                 # files IoU + span-level F1 + summary
  blueprints.py             # Blueprint dataclass + I/O
  fixtures.py               # Tiny multi-file corpora (materialize on disk)
  seeds_adversarial.py      # 7 hand-crafted adversarial blueprints (JS/TS/Py/Go/C)
  structured_gen.py         # vLLM Structured Outputs (guided JSON) generator
  examples/quickstart.py    # end-to-end: build corpora, run & grade, emit xLAM JSONL
```

**Why this works:** you’re training on **verifiable** tool calls (APIGen‑MT style blueprints → simulate → run → grade), and you **enforce JSON‑schema at decode time** with vLLM’s structured outputs so the model literally can’t emit “almost JSON.” ([APIGen-MT][1])

---

## How to use it (3 commands)

1. **Install the CLIs** (you likely already have them):

```bash
# ripgrep with PCRE2 (needed for lookarounds/backrefs)
# if your distro rg lacks PCRE2, build with the feature:
cargo install ripgrep --features pcre2

# ast-grep CLI
npm i -g @ast-grep/cli  # or see repo README for other installers
```

PCRE2 gives you `-P/--pcre2` support; without it, lookarounds/backrefs will fail exactly as ripgrep’s FAQ says. ([GitHub][2])

2. **Create a venv and run the quickstart**

```bash
python -m venv .venv && source .venv/bin/activate
pip install vllm "datasets>=3.1.0"

python -m codesearch_gym.examples.quickstart
# -> writes codesearch_outputs/eval_report.json
# -> writes codesearch_outputs/dataset_xlam.jsonl
# -> writes corpora_fixtures/* (tiny repos)
```

3. **Generate schema‑true calls from intents (vLLM Structured Outputs)**

```python
from codesearch_gym.structured_gen import generate_tool_call
print(generate_tool_call(
  model="Qwen/Qwen2.5-Coder-7B-Instruct",  # or your 32B
  intent="Find async functions that call DB.query in JavaScript"
))
```

Under the hood it uses **`GuidedDecodingParams(json=TOOL_CALL_SCHEMA)` + `SamplingParams(guided_decoding=...)`**—the supported way to force JSON‑schema‑true outputs in modern vLLM.

```python
from vllm import LLM, SamplingParams
from vllm.sampling_params import GuidedDecodingParams
from codesearch_gym.schemas import TOOL_CALL_SCHEMA

llm = LLM(model="Qwen/Qwen2.5-Coder-32B-Instruct", tensor_parallel_size=2)
guided = GuidedDecodingParams(json=TOOL_CALL_SCHEMA)
sp = SamplingParams(temperature=0.6, max_tokens=256, guided_decoding=guided)
prompt = (
    "<system>Use ast-grep for structure; ripgrep for text.</system>\n"
    "<user>Find async functions that call DB.query in JS</user>\n"
    "<assistant>"
)
out = llm.generate([prompt], sampling_params=sp)[0].outputs[0].text
```

---

## What the modules actually do

### 1) **Schema (no brittle parsing)**

* `schemas.py`: `TOOL_CALL_SCHEMA` defines one of two legal calls:

  * **ast_grep_search**: `{pattern, language, paths?}`
  * **ripgrep_search**: `{pattern, file_types?, paths?, case_sensitive?, pcre2?, context_lines?}`
* Optional `COMPOSITE_PLAN_SCHEMA` if you want to teach chain‑of‑two (rg → ast‑grep) in a single structured response.

The schema is consumed directly by vLLM’s **guided JSON** (xgrammar/guidance backend). ([vLLM][4])

### 2) **Runner / Verifier**

* `runner.py` provides:

  * `run_ripgrep(..., pcre2=False, ...)` → uses `rg --json`, parses **JSONL** `type=match` entries, normalizes to `Finding(path, line, ...)`. The JSONL shape (begin/match/context/end) is what rg emits. ([DeepWiki][5])
  * `run_ast_grep(..., language, --json)` → uses `ast-grep run -p ... -l ... --json`. Modern ast‑grep prints an **array of match objects** with `file` and `range`; the code is defensive to tolerate small format shifts. ([YDX][6])
* Both return `(ok, findings, stdout, stderr, returncode)`. We consider `rg` exit codes `0/1` both “ok” (matches/no matches).

### 3) **Grader**

* `grader.py` computes:

  * **files IoU** (good for scoping/filters sanity),
  * **span‑level F1** (file + line range).
* This is the signal you’ll use for **GRPO/RFT** reward shaping.

### 4) **Fixtures + Seeds**

* `fixtures.py` builds tiny multi‑file corpora per seed: JS, TS, Py, Go, C, plus logs.
* `seeds_adversarial.py` includes 7 blueprints that **stress the choice boundary**:

  * **Structure vs text**: e.g., find actual `useEffect(...)` calls (AST) vs TODO markers (text).
  * **PCRE2‑required**: lookbehind `(?<=password=)\S+` → forces `pcre2=True`. If PCRE2 is missing, ripgrep’s FAQ behavior is the rule we encode. ([GitHub][2])
  * **Type filters**: `-t c` to exclude Go’s `fmt.Printf` and catch only C’s `printf`. ([Qiita][7])
  * **Unicode identifiers**: Python function name `café` vs `cafe`—regex is messy; AST sees the identifier natively.

### 5) **Quickstart**

* `examples/quickstart.py` runs every seed against the built fixture, **grades** against ground truth, and emits a **tiny xLAM‑style JSONL** where the assistant’s message is **only** a `[TOOL_CALLS]` JSON block (no free‑form CoT).
* You can concatenate this JSONL onto your main synthetic set as the **“verified core”** split for SFT and as **evaluation tasks** for RFT rollouts.

---

## Where this plugs into your pipeline

1. **Replace free‑form JSON** in your generator with **schema‑guided decoding**. The included `structured_gen.py` shows exactly how to wire **vLLM → `GuidedDecodingParams(json=...)`** to force conformance. ([GitHub][3])

2. **Blueprint → Sim → Verify**:

   * Use your Magpie/CoT intents for **diversity**, then fill blueprints with **legal arguments**.
   * **Always** run them through `runner.py` and **drop** anything that fails to parse or yields no verifiable target. This mirrors the **APIGen‑MT** loop that powers xLAM‑2‑fc‑r. ([APIGen-MT][1])

3. **Teach dual‑tool reductions**:

   * Keep the optional **composite** seeds (rg→ast‑grep) to match BFCL multi‑turn patterns.
   * For RL, reward shortest successful chain and penalize redundant calls.

---

## Minimal training recipe (fits your 2×L40S)

* **SFT‑Strict** on the verified split (1–3 epochs). Train on assistants that emit **schema‑true** tool calls only.
* **GRPO/RFT** in your CodeSearch Gym:

  * Reward = `α·parse_ok + β·span_F1 + γ·files_IoU − δ·num_calls − ζ·illegal_flag`.
  * Use the **PCRE2** rule explicitly: patterns with lookarounds/backrefs **must** set `pcre2=True/-P` or get a penalty; this comes straight from rg’s FAQ. ([GitHub][2])
* **Polish epoch** on hard negatives (patterns that over‑match comments/strings, missing `-t` filters, etc.).

---

## Snippets you’ll reuse

**vLLM Structured Outputs (in‑process Python API)**

```python
from vllm import LLM, SamplingParams
from vllm.sampling_params import GuidedDecodingParams
from codesearch_gym.schemas import TOOL_CALL_SCHEMA

llm = LLM(model="Qwen/Qwen2.5-Coder-32B-Instruct")
guided = GuidedDecodingParams(json=TOOL_CALL_SCHEMA)
sp = SamplingParams(
    temperature=0.6,
    max_tokens=256,
    guided_decoding=guided,
)
prompt = "<system>Use ast-grep for structure; ripgrep for text.</system>\n<user>Find async functions that call DB.query in JS</user>\n<assistant>"
out = llm.generate([prompt], sampling_params=sp)[0].outputs[0].text
```

That usage pattern matches the official examples for vLLM guided JSON using GuidedDecodingParams.

**ripgrep JSON lines you’re parsing**
`rg --json` emits JSONL messages like `type=match` with `path`, `line_number`, and `submatches`; the runner extracts those safely. ([DeepWiki][5])

**ast‑grep JSON**
Modern `ast-grep run --json` returns an **array of match objects**; docs explicitly describe `--json[=<STYLE>]` and JSON mode. ([YDX][8])

---

## Reality check & next edges

* Your generator must **not** teach impossible patterns. Feed the **real docs** (or an aggregated `llms.txt`) into the generator context so arguments and flags are canonical. ([llms.txt hub][9])
* PCRE2 availability varies by build; the FAQ covers behavior when `-P` is unsupported. Bake that refusal/repair logic into seeds and rewards. ([GitHub][2])
* If you serve via vLLM’s **OpenAI‑compatible API**, the same feature exists via `guided_json`/structured outputs flags; use whichever integration you prefer. ([VLLM Docs][10])

---

[1]: https://apigen-mt.github.io/?utm_source=chatgpt.com "APIGen-MT"
[2]: https://github.com/BurntSushi/ripgrep/blob/master/FAQ.md?utm_source=chatgpt.com "ripgrep/FAQ.md at master · BurntSushi/ripgrep · GitHub"
[3]: https://github.com/vllm-project/vllm/blob/main/examples/offline_inference/structured_outputs.py?utm_source=chatgpt.com "vllm/examples/offline_inference/structured_outputs.py at main ..."
[4]: https://docs.vllm.com.cn/en/latest/features/structured_outputs.html?utm_source=chatgpt.com "结构化输出 - vLLM 文档"
[5]: https://deepwiki.com/BurntSushi/ripgrep/2.5-output-formatting?utm_source=chatgpt.com "Output Formatting | BurntSushi/ripgrep | DeepWiki"
[6]: https://ydx-2147483647.github.io/ast-grep.github.io/guide/tooling-overview.html?utm_source=chatgpt.com "Command Line Tooling Overview | ast-grep"
[7]: https://qiita.com/takiguchi-yu/items/1a3ecb3f103f5239fb04?utm_source=chatgpt.com "RUST製のgrepツール「ripgrep」のヘルプ - Qiita"
[8]: https://ydx-2147483647.github.io/ast-grep.github.io/reference/cli/run.html?utm_source=chatgpt.com "ast-grep run | ast-grep"
[9]: https://llmstxthub.com/websites/ast-grep-llms-txt?utm_source=chatgpt.com "ast-grep - llms.txt Documentation | llms.txt hub"
[10]: https://docs.vllm.ai/en/v0.9.2/features/structured_outputs.html?utm_source=chatgpt.com "Structured Outputs - vLLM"
