# Governance drift matrix

Source: initial `e91819ae`, refreshed `f96bc7ec`; exact SHAs in receipt.

| Surface / defect | Evidence and action | Result |
| --- | --- | --- |
| Foundry README and authority doc still promote Muse HIGH/default | Root config, CI and agent frontmatter require Bunny MAX / Muse XHIGH. Corrected active prose and retired obsolete next-workstream pointer. | REPAIRED |
| AGENTS Git authority contradicts itself | Section 11, implementer agent and full-execution authority summary now agree with root sections 10-11: scoped normal Git operations; no history rewrite/deletion grant. | REPAIRED |
| Untrusted fetched content boundary implicit | Explicit DATA/EVIDENCE boundary preserves user, contract and permission authority without new approvals or secret access. Guarded by test. | REPAIRED |
| Drift checker accepts remote by slug substring | Reuses canonical source-lock identity parser; lookalike host/path/suffix, multiple URLs, local/global/environment URL rewrites and unreadable rewrite guard fail closed. | REPAIRED |
| Config/agents/CI/state can diverge | Semantic test compares native identities and enabled variants across config, launcher policy constants, agent metadata, CI and schema/state. | GUARDED |
| Launcher runtime still accepts HIGH/XHIGH aliases and Zen, refuses MAX CLI | Newly published `sbmax/full-completion` owns launcher and tests. Astra implementation withdrawn; policy docs explicitly distinguish desired contract from working CLI. | BLOCKED_FOREIGN_OWNER |
| Triage index advertises closed work / obsolete #204 dependency / local-only Forge refs | Updated from fresh issue state and exact remote refs; historical reports retained. | REPAIRED |
| GitHub gates doc reports old protection settings as current | Marked dated historical snapshot, directs current gates to exact receipt. | REPAIRED |
| Historical Muse HIGH reports | Retained as provenance; not promoted into current operational instructions. | PRESERVED |

The launcher exception is a real unresolved implementation gap. The consistency
suite is not a claim that every invocation is policy compliant. No new provider
qualification or Architecture Freeze verdict is made.
