# INTERNAL-NOTES.md

> **One-page warning sheet for first-day engineers.**
> Read this before you touch anything. It is advisory only and is not a
> substitute for the full README, `docs/architecture.md`, or `CLAUDE.md`.

---

## 1. Welcome — what Nonull is and isn't

Nonull is an **internal ADAS engineering assistant** — a Python framework
for autonomous-driving teams to review code, run safety checks, generate
scenarios, and coordinate multi-agent workflows. **It is not a
certified safety product.** The bundled "safety layer" gives
*advisory* risk hints and check templates based on ISO 26262 / MISRA /
ASPICE **patterns**, but it does **not** implement ASIL-D processes
(no MC/DC coverage, no formal verification, no SEooC, no
"freedom from interference"). **Never** wire Nonull into any path
that influences a vehicle control decision, and never use it to
replace a certified safety mechanism. This is advisory only.

---

## 2. First install

Three commands, in order:

```bash
# 1. Install the package (editable mode, after git clone)
pip install -e .

# 2. Copy the env template and fill in your LLM key
cp .env.example .env
# (on Windows PowerShell: Copy-Item .env.example .env, then edit .env)

# 3. Run it
python -m nonull
```

If `pip install -e .` complains about missing wheels, double-check
your Python version (3.10+ is required) and read `requirements.txt`
for the exact dependency pins.

---

## 3. Setting up an LLM

Nonull talks to LLMs through a thin adapter layer. The env vars live
in `.env` and are loaded at startup:

| Env var                  | Purpose                                                                 |
|--------------------------|-------------------------------------------------------------------------|
| `NONULL_LLM_API_KEY`     | **Required** for agent mode. Your API key.                              |
| `NONULL_LLM_PROVIDER`    | `openai` (default), `anthropic`, `azure`, `ollama`, etc.                 |
| `NONULL_LLM_MODEL`       | Model id, e.g. `gpt-4o`, `claude-3-5-sonnet-...`, `qwen2.5-coder:7b`.   |
| `NONULL_LLM_API_BASE`    | Optional base URL for self-hosted / proxy endpoints.                    |

**Where to get keys:**

- **OpenAI** — https://platform.openai.com/api-keys
- **Anthropic** — https://console.anthropic.com/settings/keys
- **Azure OpenAI** — Azure portal → your OpenAI resource → "Keys and Endpoint"
- **Ollama (local)** — no key needed; just run `ollama serve` locally

**Providers officially supported** (covered by the default adapter):
OpenAI, Anthropic, Azure OpenAI, Ollama. Other OpenAI-compatible
endpoints usually work by setting `NONULL_LLM_API_BASE`.

**Without a key?** The CLI still boots — slash commands
(`/help`, `/clear`, `/history`, `/session`, `/stats`) all work.
You just can't run the LLM agent. On startup you'll see:

```
(Agent mode disabled — set NONULL_LLM_API_KEY to enable)
```

---

## 4. What if my LLM doesn't work

The three issues you will hit on day one, in order of frequency:

1. **Wrong key.** The adapter will return `401 Unauthorized` or
   `Invalid API key`. Double-check `.env` (no quotes around the key,
   no trailing whitespace). Re-run `python -m nonull` after editing.

2. **Wrong provider / model mismatch.** If you set
   `NONULL_LLM_PROVIDER=anthropic` but paste an OpenAI key (or vice
   versa), you'll get a confusing auth or schema error. Match the
   provider to the key, and the model id to that provider's catalog.

3. **No internet / proxy issues.** Corporate networks often block
   `api.openai.com` or `api.anthropic.com`. Symptoms: a hung CLI,
   `TimeoutError`, or `ConnectionError`. Fix: configure
   `HTTPS_PROXY` / `HTTP_PROXY` env vars, or ask IT to allowlist
   the endpoint. For fully offline work, run **Ollama** locally and
   point `NONULL_LLM_API_BASE` at it.

If none of those match, run with `LOG_LEVEL=DEBUG` and paste the
traceback into an issue (see §7).

---

## 5. The 3 workflows every new engineer will use

All three are demonstrated under `examples/`. They share the same
`SkillRegistry` + `Orchestrator` plumbing, so once you understand
one, you understand all three.

### 5.1 Code review (`examples/code_review.py`)

The bread-and-butter workflow. You hand it a code snippet
(C/C++/Python), and the agent runs MISRA-style checks, bug
hunting, and optimization hints through the `code_*` skills.

```python
from core import Nonull
agent = Nonull()
result = agent.run_sync("审查这段 AEB 制动函数的边界条件")
print(result["output"])
```

### 5.2 Scenario coverage (`examples/safety_analysis.py`)

For HARA / scenario-engineering work. The agent pulls from the
`scenario_engine` (36 built-in scenarios) and the `safety_*`
skills to flag missing test coverage and ASIL-relevant risks.

### 5.3 Multi-agent workflow (`examples/multi_agent_workflow.py`)

DAG-based task decomposition. The orchestrator fans the task out
to up to 8 sub-agents in parallel, then reconciles their outputs.
Use this when a single agent's context window isn't enough, or
when you want to compare Conservative / Sporty / Veteran persona
opinions on the same code.

For a one-shot demo that wires skills + workflow together, see
`examples/skill_workflow.py`.

There is a smoke-test that protects this public entrypoint from
breaking: `tests/test_skill_workflow_integration.py`. It imports
`examples/skill_workflow.py`, verifies `run_aeb_review_workflow` is
defined, auto-discovers the real `SkillRegistry`, checks the
`code_review` skill is registered, and pins the
`Orchestrator.run_with_skills` signature. If you change the example
or the orchestrator's public method shape, this test is the first
thing CI will yell about.

---

## 6. Known limitations

Nonull is intentionally bounded. Things it **cannot** do:

- **Certify anything.** No ASIL-D, no ISO 26262 compliance, no
  ASPICE. The safety layer is *advisory*. See the disclaimer at
  the top of `README.md` and `safety.disclaimer: "advisory_only"`
  in `config/config.yaml`.
- **Drive a vehicle.** This is a developer assistant. It will
  not output throttle / brake / steering commands, and no part
  of the codebase is validated for real-time control loops.
- **Replace human review.** Treat all suggestions (MISRA hints,
  ASIL ratings, optimization tips) as a starting point for human
  review, not as authoritative.
- **Self-modify in production.** The `experimental/` directory
  (self-evolution, self-awareness) is **off by default** and must
  stay that way for any safety-adjacent path.
- **Guarantee determinism.** LLM outputs are stochastic; the
  memory backend is in-memory by default. For reproducible runs,
  pin a model + temperature and read `docs/architecture.md` §5.4
  on swap-in backends.
- **Run without network forever.** Cloud LLM providers require
  internet. Use Ollama for offline-only environments.

See the **"Important Disclaimer"** section at the top of
`README.md` for the full, binding warning.

---

## 7. Where to ask for help

1. **Search the docs first.** Most day-one questions are
   answered in `docs/快速上手指南.md`, `docs/一页纸速览.md`, or
   `docs/architecture.md`.
2. **Search existing issues.** Someone has probably hit it.
3. **Open a new issue** at:
   **https://github.com/<your-org>/Nonull/issues**
   Include: your OS, Python version, the exact command you ran,
   and the full traceback (`LOG_LEVEL=DEBUG` output).
4. **For safety / certification questions** — escalate internally
   first. Do **not** open a public issue for things that touch
   vehicle control decisions.

---

> **Reminder: this is an advisory document.** If anything in here
> conflicts with the `README.md` disclaimer or `CLAUDE.md` safety
> rules, the README and CLAUDE.md win.
