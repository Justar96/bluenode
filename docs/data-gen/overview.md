tar — sharp plan, but you’ve got a few landmines and a lot of untapped upside. Here’s a **2025-tight** refinement to make xLAM‑2‑3B *surgically* good at function‑calling for **ast-grep** and **ripgrep**, built on the newest research and the realities of your 2× L40S box.

---

## 0) Brutal honesty first (hardware, libs, models)

* **Don’t plan on Llama‑3.1‑70B in bf16 on 2×48 GB.** Raw weights alone need ~140 GB; you’ll only get it to run with **int4/awq/gptq** and careful KV/cache/batching tricks. It’s doable, but not “fits perfectly.” Use **Qwen2.5‑Coder‑32B‑Instruct** as your high‑quality generator, and keep 70B only as **INT4 AWQ** for occasional diversity passes if you really want it. ([VLLM Docs][1])
* **vLLM has first‑class structured outputs + quantization.** Use **vLLM ≥ 0.10** (0.11 is current) and its **Structured Outputs** (xgrammar/Guidance backend) for schema‑true function calls; enable **AWQ/GPTQ** when you need the 70B. Also, xLAM’s own model cards recommend **vLLM ≥ 0.6.5** (older note, still compatible). ([Release Alert][2])
* **xLAM is already optimized for tool use.** If you can start from **xLAM‑2‑3B‑fc‑r** instead of a general base, you’ll need less data to nail function calls. It was trained with **APIGen‑MT** (multi‑turn, verifiable blueprints) and leads **BFCL v3** cohorts. ([Hugging Face][3])

---

## 1) Replace “Magpie‑only” with **Blueprint → Sim → Verify** (APIGen‑MT style)

Magpie is good for diversity, but to build a tool‑use specialist you need **verifiable targets**. Adopt **APIGen‑MT’s two‑phase pattern** and adapt it to code search:

**Phase A — Blueprint (verifiable task spec)**
Generate a *machine‑checkable* spec:

* `intent`: natural language task (“find async functions that call DB.*”)
* `tool`: {`ast_grep_search` | `ripgrep_search`}
* `arguments`: full JSON for tool (pattern, language, paths, file_types, flags like `--pcre2`)
* `corpus`: repo snapshot + language mix for the task
* `ground_truth`: **command to run + expected findings** (files, line ranges, captures)

**Phase B — Simulated conversation**
Turn the blueprint into a realistic multi‑turn dialog where an agent reasons, picks the tool, issues the function call, maybe iterates (narrow paths, add flags), and converges. **Accept only runs that reproduce the blueprint’s ground truth**. This is how APIGen‑MT gets its reliability on τ‑bench/BFCL; do the same for code search. ([apigen-mt.github.io][4])

> Why this matters: BFCL v3 and τ‑bench reward **correct calls, multi‑step tool use, and consistency**. Blueprints make your reward **verifiable** (compile, run, compare). ([Gorilla][5])

---

## 2) Build a **CodeSearch Gym** (execution‑grounded reward)

Create a small harness that can **run both tools**, capture outputs, and grade them:

* **ast‑grep**: validate pattern parses (tree‑sitter), run with `--json`, confirm match counts, and enforce language correctness.

  * Use the official **Pattern Syntax** doc for pattern DSL rules and meta‑variables (`$A`, `$$$ARGS`). Build lint checks so the dataset never teaches illegal patterns. ([ast-grep.github.io][6])
* **ripgrep**: validate regex flavor. If the query uses **lookarounds/backrefs**, force `--pcre2/-P` or mark it invalid if PCRE2 isn’t available in that build. Teach the model this choice explicitly. ([GitHub][7])

**Reward signals (for RL/RFT later):**

* `R_parse`: pattern compiles (1/0)
* `R_scope`: correct files/paths/types targeted (IoU over file sets)
* `R_find`: F1 over expected match spans (filename, line, column)
* `R_effort`: gentle penalty for redundant calls (prefer: 1 good call)
* `R_safety`: refuse/clarify when the request needs PCRE2 but isn’t enabled

This is **GRPO‑friendly** (verifiable, binary/graded). It’s exactly the setup GRPO thrives on. ([arXiv][8])

---

## 3) Data you actually need (balanced, adversarial, realistic)

Curate three buckets and balance ~40/40/20:

1. **Atomic “single‑shot” tasks** (tool‑choice + correct args)

   * Structural vs textual: functions/classes/imports/log calls/SQL strings.
   * Languages: py/js/ts/rust/go/java/csharp/cpp; include multi‑language repos.
   * Typical flags: `--type`, `--iglob`, `--context`, `--hidden`, `--follow`, `--json`. ([GitHub][9])

2. **Adversarial + ambiguity**

   * *Regex vs structure traps*: cases where naive regex hits comments/strings, but AST pattern avoids noise; or where AST cannot express a literal you want (→ ripgrep).
   * **PCRE2** necessities (lookarounds/backrefs) vs **default engine** limits.
   * “Too many hits” → **narrow paths/types**; “empty hits” → **fix anchors**. ([GitHub][7])

3. **Multi‑turn reductions** (BFCL‑style)

   * Start broad (`ripgrep` across repo), then **switch** to `ast-grep` to structurally filter; or the reverse (structure first, then `ripgrep` to find literals adjacent to AST nodes).
   * Include corrections after a wrong first call (graded negative → positive). ([Gorilla][10])

**Source repos:** prefer permissive‑licensed, many languages, known patterns (e.g., Django, FastAPI, React, Kubernetes submodules, tox, ripgrep/ast‑grep repos themselves). Keep snapshots in a content‑addressed cache (avoid churn).

**Doc conditioning:** feed **ast‑grep’s LLM‑optimized docs (`/llms.txt` / `llms-full.txt`)** and **ripgrep GUIDE/FAQ** to the generator so the synthetic instructions use **real flags & syntax**. ([ast-grep.github.io][11])

---

## 4) Generation stack (modernized)

Keep **Magpie** for breadth, but only to seed *intents*. Then **ground** them with blueprints + verification.

* **Intent generation**: Magpie (prompt‑free),  temperature 0.7–0.9, short outputs. ([arXiv][12])
* **Blueprint filling**: a constrained generator that maps intents → `{tool, arguments, corpus}`, with legality checks using the **docs** and your Gym.
* **Conversation synthesis**: CoT‑Self‑Instruct 2025 to add reasoning and multi‑turn variants, but **strip raw chain‑of‑thought from public outputs**; keep a **latent “think”** field for training with process supervision or latent rationale methods. ([arXiv][13])

> If you still want visible `<think>` in the dataset, do it in a **rationales split** that’s never shipped in prod. Latent/implicit rationales + verifiable rewards are safer and generalize better.

---

## 5) Format for **schema‑true** function calls (no more brittle parsing)

Switch to **JSON‑schema‑guided decoding** at generation time and train on exactly that format. vLLM makes this easy.

**Tool schemas (final):**

```json
{
  "type":"object",
  "properties":{
    "name":{"type":"string","enum":["ast_grep_search","ripgrep_search"]},
    "arguments":{
      "type":"object",
      "oneOf":[
        {
          "properties":{
            "pattern":{"type":"string","minLength":1},
            "language":{"type":"string","enum":["python","javascript","typescript","rust","go","java","cpp","csharp"]},
            "paths":{"type":"array","items":{"type":"string"}}
          },
          "required":["pattern","language"]
        },
        {
          "properties":{
            "pattern":{"type":"string","minLength":1},
            "file_types":{"type":"array","items":{"type":"string"}},
            "paths":{"type":"array","items":{"type":"string"}},
            "case_sensitive":{"type":"boolean"},
            "pcre2":{"type":"boolean"},
            "context_lines":{"type":"integer","minimum":0}
          },
          "required":["pattern"]
        }
      ]
    }
  },
  "required":["name","arguments"]
}
```

At serve‑time and during data gen, **enforce schema with vLLM Structured Outputs** and xLAM’s tool‑parser plugin. This obliterates the “JSON almost valid” problem. ([VLLM Docs][14])

---

## 6) Training recipe (simple, then sharp)

**Stage 1 — SFT‑Strict (1–3 epochs)**

* Train on verified trajectories only.
* Loss on tool JSON **and** minimal natural language (only what you’ll keep at inference).
* Mix 60% atomic, 25% adversarial, 15% multi‑turn.

**Stage 2 — RFT (GRPO) with verifiable rewards (2–4 days on 2×L40S)**

* Rollouts in the CodeSearch Gym. Reward = `α·R_parse + β·R_find + γ·R_scope − δ·R_effort − ζ·errors`.
* Add a small preference set (DPO/ORPO) of **better vs worse** tool calls (e.g., correct `--pcre2` vs missing it; targeted `--type` vs glob‑spamming). GRPO handles the verifiable core; DPO/ORPO polishes **style**. ([arXiv][8])

**Stage 3 — Short SFT polish on “hard negatives”**

* Mine failures (false positives, wrong tool) → synthesize minimal counterexamples with explanations, retrain 0.2–0.5 epoch.

---

## 7) Evaluation (don’t wing it)

* **BFCL v3** for function‑calling correctness and multi‑step/multi‑turn capability. Integrate **bfcl‑eval** (pip) in CI. Track **overall, single‑turn, multi‑turn**. ([Gorilla][5])
* **τ‑bench** for agent reliability (pass@k) — your multi‑turn reduction skills will carry over. ([arXiv][15])
* **Your in‑domain suite**:

  * **Tool‑choice accuracy** (ast‑grep vs ripgrep)
  * **Argument exact‑match** (flags, pattern string edit distance)
  * **Regex/AST legality rate**
  * **Findings F1** on held‑out corpora

---

## 8) Concrete deltas to your script

### A) Replace loose CoT with **latent/trace + schema‑decoding**

* Generate with vLLM **Structured Outputs** and train to that exact schema. No free‑text JSON. ([VLLM Docs][14])

### B) Add a **Runner/Verifier** and make it part of filtering

* For each sample, actually run the tool (`ast-grep --json`, `rg --json`) and **store outputs + exit codes**. Reject samples that don’t reproduce. Use **PCRE2 checks** for ripgrep (require `-P` when needed). ([GitHub][7])

### C) Add **adversarial generators**

* Regex patterns with lookarounds/backrefs → must set `pcre2=true`.
* AST patterns that look like strings → force `ast-grep` and show why regex would over‑match (comments/strings).
* Multi‑language traps (same identifiers in TS/JS vs Go) → require `language` and `paths`.

### D) Version bumps

* Torch/Py versions as you like, but **vLLM ≥ 0.10** and **transformers ≥ 4.46** are safe calls today; xLAM model cards mention **≥ 4.46.1 / vLLM ≥ 0.6.5** minimum. ([Hugging Face][3])

---

## 9) Mini implementation sketch (just the new parts)

**Runner (verifier)**

```python
import json, subprocess, shlex, tempfile, os, pathlib, re

def run_ast_grep(pattern, language, paths):
    cmd = ["ast-grep", "-p", pattern, "-l", language, "--json"]
    for p in paths or []:
        cmd += ["--path", p]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    ok = (proc.returncode in (0,1))  # 0 matches found, 1 no matches
    return ok, proc.stdout, proc.stderr

def run_ripgrep(pattern, file_types=None, paths=None, case_sensitive=False, pcre2=False, context_lines=None):
    cmd = ["rg", pattern, "--json"]
    if pcre2: cmd.append("-P")
    if not case_sensitive: cmd.append("-S")  # smart-case; model can toggle
    for t in (file_types or []): cmd += ["-t", t]
    if context_lines is not None: cmd += ["-C", str(context_lines)]
    for p in (paths or []): cmd.append(p)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return (proc.returncode in (0,1)), proc.stdout, proc.stderr
```

**Schema‑guided generation (vLLM)**

```python
# vLLM structured outputs (xgrammar / guidance backend). See docs for exact API.
# Pass the JSON Schema above as the constraint when generating the assistant's tool call.
# This enforces perfect JSON and valid enums at decode time.
# https://docs.vllm.ai/en/latest/features/structured_outputs.html
```

([VLLM Docs][14])

**Filtering**

* Reject if `ast-grep` parse fails (stderr contains “Pattern code must be valid” signals per docs). ([ast-grep.github.io][6])
* Reject ripgrep samples that use lookaround/backrefs without `-P`; the **FAQ** is your rulebook. ([GitHub][7])

---

## 10) Practical knobs that move the needle

* **Teach the model the “tool axis”:** Add an explicit `tool_choice_explanation` field (short) *only in training*, not inference, that contrasts the two tools (“structure vs text”). This improves choice accuracy without forcing visible CoT.
* **Hard negatives > more data:** A few hundred **painfully specific** counterexamples (e.g., JS template literals with `${}` that break naive regex; Python decorators changing function sync/async semantics) will lift real‑world accuracy more than 5k bland samples.
* **Doc‑aware synthesis:** Use **ast‑grep /llms.txt** and the **ripgrep GUIDE/FAQ** as system context while generating blueprints so patterns/flags are canonical. ([ast-grep.github.io][11])

---

## 11) What to change from your current plan

* **Stop training the model to output free‑form JSON**; enforce schemas during generation and finetune. ([VLLM Docs][14])
* **Don’t trust LLM‑only self‑check**; always run the tool and grade the output.
* **Don’t assume 70B fits** without quantization; if you keep it, mount INT4 AWQ/GPTQ under vLLM. ([VLLM Docs][1])

---

## 12) Quick environment notes (you can copy/paste)

```bash
# Python 3.11 ok
pip install "vllm>=0.10.0" "transformers>=4.46.1" "datasets>=3.1.0"
# Optional quantization backends if you experiment with 70B
pip install autoawq optimum gptqmodel
# xLAM parser plugin guidance (use your 3B model)
# https://huggingface.co/Salesforce/xLAM-2-3b-fc-r
```

Use `--structured-output` (xgrammar) and `--tool-call-parser xlam` when serving with vLLM. ([Hugging Face][16])

---

## 13) Sanity‑check targets

* **BFCL v3 overall ≥ xLAM‑2‑3B‑fc‑r baseline**, multi‑turn category especially. ([Hugging Face][3])
* **In‑domain**:

  * Tool‑choice accuracy ≥ **97%** on atomic tasks
  * Argument exact‑match ≥ **95%**
  * Illegal pattern rate ≤ **1%**
  * Findings F1 ≥ **0.95** on held‑out repos

---

### Sources you’re building on

* **Magpie** (prompt‑free synthesis). ([arXiv][12])
* **CoT‑Self‑Instruct (2025)** (reasoning‑first synthetic). ([arXiv][13])
* **APIGen‑MT** (multi‑turn blueprints → verified trajectories) powering xLAM‑2‑fc‑r. ([apigen-mt.github.io][4])
* **BFCL v3** (function‑calling benchmark) & **τ‑bench** (agent consistency). ([Gorilla][5])
* **vLLM structured outputs & quantization** (schema‑true decoding, AWQ/GPTQ). ([VLLM Docs][14])
* **ast‑grep docs (pattern syntax)** and **ripgrep GUIDE/FAQ** (PCRE2 caveats). ([ast-grep.github.io][6])

---

## Where to push next

Add a **“dual‑tool” composite function** that lets the model chain `ripgrep → ast‑grep` (or vice‑versa) inside one plan, then train a small policy to prefer the shortest successful chain. This mirrors BFCL multi‑step and pays dividends on τ‑bench‑style tasks.


[1]: https://docs.vllm.ai/en/latest/features/quantization/index.html?utm_source=chatgpt.com "Quantization - vLLM"
[2]: https://releasealert.dev/github/vllm-project/vllm?utm_source=chatgpt.com "Releases · vllm-project/vllm - GitHub | Release Alert"
[3]: https://huggingface.co/Salesforce/xLAM-2-3b-fc-r "Salesforce/xLAM-2-3b-fc-r · Hugging Face"
[4]: https://apigen-mt.github.io/ "APIGen-MT"
[5]: https://gorilla.cs.berkeley.edu/leaderboard.html?utm_source=chatgpt.com "Berkeley Function Calling Leaderboard V3 (aka Berkeley Tool ..."
[6]: https://ast-grep.github.io/guide/pattern-syntax.html "Pattern Syntax | ast-grep"
[7]: https://github.com/BurntSushi/ripgrep/blob/master/FAQ.md?utm_source=chatgpt.com "ripgrep/FAQ.md at master · BurntSushi/ripgrep · GitHub"
[8]: https://arxiv.org/abs/2503.06639?utm_source=chatgpt.com "Reinforcement Learning with Verifiable Rewards: GRPO's ..."
[9]: https://github.com/BurntSushi/ripgrep/blob/master/GUIDE.md?utm_source=chatgpt.com "ripgrep/GUIDE.md at master · BurntSushi/ripgrep · GitHub"
[10]: https://gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html?utm_source=chatgpt.com "BFCL V3 • Multi-Turn & Multi-Step Function Calling"
[11]: https://ast-grep.github.io/ "ast-grep | structural search/rewrite tool for many languages"
[12]: https://arxiv.org/abs/2406.08464?utm_source=chatgpt.com "[2406.08464] Magpie: Alignment Data Synthesis from Scratch ..."
[13]: https://arxiv.org/abs/2507.23751?utm_source=chatgpt.com "CoT-Self-Instruct: Building high-quality synthetic prompts for ..."
[14]: https://docs.vllm.ai/en/latest/features/structured_outputs.html?utm_source=chatgpt.com "Structured Outputs - vLLM"
[15]: https://arxiv.org/abs/2406.12045?utm_source=chatgpt.com "$τ$-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains"
[16]: https://huggingface.co/Salesforce/Llama-xLAM-2-70b-fc-r/blob/main/README.md?utm_source=chatgpt.com "README.md · Salesforce/Llama-xLAM-2-70b-fc-r at main"
