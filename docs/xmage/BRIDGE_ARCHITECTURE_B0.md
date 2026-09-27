\# XMage Bridge Architecture B0



\## Baselines



Commander Playtest Lab:

07daba21696e1202bb2f3b68be12ce475bf8294b



XMage:

77d7646da6958fdf8125ee7c8f4aabd130d21d4c



XMage version:

1.4.61



Lab protocol:

2.0.0



\## Decision



The production XMage JSONL bridge is owned by the Commander Playtest Lab

and lives under:



engine-bridge/



XMage remains pinned external engine source under:



vendor/engine-source/xmage



The bridge initially embeds XMage engine APIs directly rather than starting

the full XMage network server.



\## Process model



The bridge JSONL loop and XMage GAME execution must run on separate threads.



XMage HumanPlayer blocks the GAME thread while awaiting player responses.

JSONL requests provide those responses from the bridge/control thread.



\## Native XMage surfaces



Deck import:

DeckCardLists -> Deck.load(...)



Commander:

CommanderFreeForAll / CommanderFreeForAllMatch



Partner legality:

AbstractCommander



Mulligan:

MulliganType.LONDON / LondonMulligan



State:

Game / GameState / Player



Playable actions:

Player.getPlayable(...)

Player.getPlayableOptions(...)



Choices:

PlayerQueryEvent



Responses:

HumanPlayer.setResponseUUID(...)

HumanPlayer.setResponseString(...)

HumanPlayer.setResponseBoolean(...)

HumanPlayer.setResponseInteger(...)

HumanPlayer.setResponseManaType(...)

HumanPlayer.sendPlayerAction(...)



\## Maven strategy



The Lab-owned bridge uses XMage Maven artifacts from the exact pinned source.



CI must install the pinned XMage reactor into the job-local Maven repository

before building engine-bridge.



Do not use systemPath dependencies.



\## Capability rollout



\### B1

Process + JSONL + version + capabilities + shutdown.



Gameplay capabilities remain false.



\### B2

Real deck import.



\### B3

Real Commander multiplayer game creation/start/mulligan.



\### B4

Game state, playable/legal actions, submissions, priority, targets,

modes, triggers and concede.



\### B5

Event log and replay.



\### B6

Semantic external-engine acceptance and project-critical interaction gate.



\## Evidence boundary



B1 does not make the provider production-ready.



NO\_PROVIDER\_READY remains current until the real external acceptance policy

passes.



Structural Simulation and Tactical Oracle are not XMage evidence.



\## Known gaps



\- Exact normal single-priority-pass mapping must be resolved before B4.

\- Event-log/replay mapping must be resolved before B5.

\- external-engine-integration.yml currently references

&#x20; scripts/run\_external\_phase851.py, which is absent and must be addressed

&#x20; before B6.

