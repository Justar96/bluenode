### Next step

Run the quickstart to sanity‑check, then point your data generator to **emit exactly this schema**, wire the **Runner + Grader** into your filter, and add 50–100 more adversarial blueprints (multi‑lang, PCRE2 tricks, comment/string traps). Once your **span‑F1 ≥ 0.95** on the verified split, start the GRPO pass.

If you want me to extend the seed set (regex gotchas, TS decorators, Rust macros, SQL in heredocs) or add a **DPO preference miner** for “clean vs spammy” queries, I’ll drop in an extra seeds module and a preference sampler.