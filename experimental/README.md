# DO NOT USE THESE

> **WARNING**: These modules are EXPERIMENTAL, UNSUPPORTED, and NOT production-ready. **Do not use them in any code path that matters.**

These modules are NOT supported for use. They are kept for reference and historical purposes only. If you need this functionality, fork the project and maintain your own copy with the appropriate safety review.

## consciousness/
Self-model, curiosity, autonomy, growth journal, consciousness loop.
These modules implement self-awareness and self-modification. They are:
- Non-deterministic
- Mostly untested
- Not safe for any path that touches vehicle control decisions
- Included for research and inspiration only

## evolution/
Experience mining, skill genesis, meta-cognition, prompt optimization.
These modules modify the agent's own behavior based on experience. They are:
- Self-modifying (writes to skill registry and prompt store)
- The antithesis of ISO 26262 "freedom from unacceptable risk"
- Do NOT wire these into any safety-critical pipeline

## When to use
- Personal learning projects
- Research on self-evolving agents
- Reading the code to understand what's possible

## When NOT to use
- Production autonomous driving systems
- Any path that influences a vehicle control decision
- Anything that requires deterministic behavior
- Any production code path in this project (enforced by `tests/test_no_experimental_imports.py`)

These modules are NOT supported for use. They are kept for reference and historical purposes only. If you need this functionality, fork the project and maintain your own copy with the appropriate safety review.
