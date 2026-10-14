# Free and subscription executors, 2026-10-13

Research for the Owner after the OpenCode Go quota proved unusable. These findings come from
web sources checked on 2026-10-13. Each one carries its confidence: **verified** (official
page or a live check), **reported** (third-party or user reports), **open** (not answered).
Prices, model lists and limits change often, so re-check before acting on any of them.

## 1. OpenCode Zen free tier

**Live catalog, verified** (`https://opencode.ai/zen/v1/models`, 2026-10-13): 86 models, of
which these are free: `big-pickle`, `cat-jam-free`, `jev-1.13-free`, `ling-3.1-flash-free`,
`longcat-2.5-preview-free`, `mimo-v2.6-flash-free`, `muse-spark-1.2-contributor-free`,
`muse-spark-1.3-contributor-free`, `nemotron-3.5-lightning-free`, `space-bunny-free`,
`step-5-preview-free`.
- Some models the docs still list are gone from the catalog: Exo, MiMo-V2.5, Ling 3.0 Fin and
  Nemotron 3 Ultra.
- The docs call every free model "free for a limited time". Any of them can disappear, which
  is why the registry's live catalog check before selection matters.

**Data use, verified** (Zen docs):
- Zero-retention, no training: Step 5 Preview Free, Space Bunny Free, LongCat 2.5 Preview
  Free. Cat Jam Free and Jev 1.13 Free fall under the same general policy, with no listed
  exception.
- Used for training or logged: Big Pickle, MiMo, Ling, Nemotron and Muse Spark Contributor.
  Nemotron says "do not submit personal or confidential data".

**Limits, reported:** user reports put the free cap at about 200 requests per day per account,
resetting daily, and say a paid Zen balance does not lift it (anomalyco/opencode #33495,
#15585). No maintainer has confirmed a number, and no reset time is documented.

**What follows for this project:**
1. **Stay on Step 5 Preview Free.** It is in the live catalog, it is zero-retention, and it is
   the profile already qualified here. Switching only makes sense once Step leaves the catalog.
2. **The cap counts requests, not tokens.** Every tool call of an agent turn is a model
   request, so about 200 requests a day is a few medium tasks, not a campaign. To get the
   most out of it:
   - send fewer, larger steps: one full dispatch per `docs/foundry-execution/EXECUTOR_PROMPTING.md`;
   - batch reads instead of single-file round trips;
   - leave mechanical checks (lint, tests, grep) to deterministic scripts rather than the model;
   - run one Step job at a time, and use it for execution only, never for coordination.
3. **Fallback candidates** (zero-retention, in the catalog): Space Bunny Free, LongCat 2.5
   Preview Free. Activating one needs a new Owner instruction and a registry change.
   - The registry knows exactly two profiles (`step`, `deepseek`), so a third profile is a
     structural change.
   - There is still no automatic fallback.
4. **Avoid the data-collecting free models** (Big Pickle, MiMo, Ling, Nemotron, Muse Spark) for
   work that carries Owner data or credentials, even though the repository is public.

## 2. GitHub Copilot coding agent

**Verified** (GitHub docs and changelog):
- Copilot reads `AGENTS.md` at the root and in subdirectories, plus `CLAUDE.md`, `GEMINI.md`
  and `.github/copilot-instructions.md`. The repository's existing `AGENTS.md` and `CLAUDE.md`
  already reach it, so no separate instructions file is needed. A copy would only drift from
  the canonical one.
- Its environment comes from `.github/workflows/copilot-setup-steps.yml`. The file must be on the
  default branch and hold a single job named `copilot-setup-steps`. Only `steps`,
  `permissions`, `runs-on`, `services`, `snapshot` and `timeout-minutes` (at most 59) are
  honoured.
- The setup steps run before the agent's firewall closes the network.

**Added on 2026-10-13:** `copilot-setup-steps.yml`.
- It installs the hash-locked Python dependencies and the project (ruff, mypy, pytest), plus
  Temurin 17 for the bridge.
- It does not build the XMage engine jar, which needs the pinned fork and a large Maven
  download. Engine-backed rows stay with CI.

**Reported:**
- Since June 2026, GitHub meters premium agent use in "AI Credits".
- Self-service sign-up for new Pro/Pro+ is reported paused since 2026-04-20.
- Whether the Free plan includes the coding agent is unclear. Check the Owner's plan before
  relying on it.

## 3. Google AI plan: Antigravity, Jules, AI Studio

**Verified** (Antigravity docs, Gemini CLI announcement):
- Gemini CLI is retired for individual accounts; Antigravity CLI (`agy`) replaces it.
- The workspace rules Antigravity reads are `AGENTS.md`, `GEMINI.md` or `.agents/rules/*.md`, at
  the root or in subdirectories.
- The existing `AGENTS.md` already reaches it, so no extra file is needed.
- Reported gap: one report says Antigravity driven through its ACP server loads no rule files
  (pingdotgg/t3code #15283). Use `agy` directly.

**Plan limits, verified** (Google One plans page): Google AI Plus lists Antigravity and Jules
only as "Limited". Expanded limits in AI Studio, Antigravity and Jules start at AI Pro.

**Gemini 4 Argon, reported** (press, 2026-09-30 announcement):
- First released to Google's "Fairwind" cyber-defender programme.
- Wider access is planned first for paid API customers and **Google AI Ultra**.
- **A Google AI Plus plan should not be expected to include Argon** until Google says so.
- As of 2026-10-08 one source reports it is not yet callable through the Gemini API.

**Jules:** reads `AGENTS.md`. Its setup script is entered in the Jules UI, not in the
repository. It can run the same two `pip install` lines as `copilot-setup-steps.yml`.

## Sources

- OpenCode Zen docs: https://opencode.ai/docs/zen/ ; live catalog https://opencode.ai/zen/v1/models
- Free-cap reports: https://github.com/anomalyco/opencode/issues/33495 , https://github.com/anomalyco/opencode/issues/15585
- Copilot AGENTS.md support: https://github.blog/changelog/2025-08-28-copilot-coding-agent-now-supports-agents-md-custom-instructions
- Copilot environment: https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/customize-the-agent-environment
- Gemini CLI to Antigravity CLI: https://github.com/google-gemini/gemini-cli/discussions/27274
- Antigravity rules: https://antigravity.google/docs/rules/
- Google AI plans: https://one.google.com/about/google-ai-plans/
- Gemini 4 Argon: https://inc42.com/?p=574374 , https://www.khaleejtimes.com/business/google-announces-gemini-4-flagship-ai-model-after-months-of-delays-2
