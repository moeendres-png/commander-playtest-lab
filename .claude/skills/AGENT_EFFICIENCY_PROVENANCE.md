# Agent Efficiency — source provenance

Integrated: 2026-10-05

| Component | Source lock | License / posture | Local use |
| --- | --- | --- | --- |
| repo-map | AnastasiyaW/codex-claude-code-config@cdcb11dfd8065e657c0a80acb2fdf67527382017 / tree f76e41994292045cf877909e40772d171e01b78c | MIT | mapper vendored byte-identically; active skill adapted |
| Context7 | upstash/context7@f2eef4f49da71a758c91cf6cb97640c8b262ef81 / tree 718d6644e7b3d8b35f088b6f73cbea4ceafbaac3 | MIT | upstream find-docs skill retained; active skill pins ctx7@0.5.13 |
| Serena | oraios/serena@b4a83eec1097042f34a09985783c9491f99919c4 | external process; Serena app GPL-3.0-or-later | project MCP pinned to commit, read-only, no memories |
| RTK | rtk-ai/rtk@c356374fc1c9cff132c02484d2b9195c796b8e8f | external binary; Apache-2.0 | optional fail-open Claude Bash compressor hook |
| Repomix | yamadashy/repomix@8d6429121e98ed178e4d3a975c2bdbbecc958c4a / tree c47f5f081a9134bdd88672226e914425361d54f9 | MIT | on-demand, runtime pinned repomix@1.18.1 |

Progressive-disclosure and context-engineering policy is original project
material. External research informed the design, but GPL/no-license source text
was not copied into active project skills.

These components optimize discovery/context only. They do not alter Source Truth,
Rules authority, qualification semantics or evidence classifications.
