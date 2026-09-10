---
name: rules-authority-escalation
description: Detect a Magic Rules-authority question and package it for Sol High instead of adjudicating it.
---

# Rules Authority Escalation

Use the moment a task turns on what the Rules MEAN (as opposed to what the
code DOES). You are not Rules authority; GPT-5.6 Sol High is.

## Procedure

1. Detect: the dispute is about correct Magic behavior under the Comprehensive
   Rules / Oracle / Rulings — not about a defect location, log reading, or
   repair ordering (those stay with `foundry-adjudicator`).
2. Freeze: state the exact disputed behavior and the exact cards, zones,
   timestamps, and choices involved. Preserve `UNKNOWN`; do not vote.
3. Gather: cite the engine code path, the relevant CR/Oracle text, and any
   ruling — as evidence attachments, never as conclusions.
4. Gate: write an `AUTHORITY_GATE` entry (question, options, evidence refs,
   what is blocked) into `.foundry/WORKSTREAM_STATE.yaml` and stop the Rules
   line of inquiry. Continue only unrelated technical work.

## Rules

- `AGENTS.md` §2 (Rules Authority) is already privileged; do not restate it.
- Never teach the model to BE Rules authority; this skill exists to route
  around that failure mode.
- A technical guess about a Rules question is still a guess: `UNKNOWN`.
- Do not duplicate large chunks of `AGENTS.md` here; reference, don't copy.
