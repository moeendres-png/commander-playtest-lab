# Bridge design

Preferred strategy remains a narrowly scoped in-process or test-harness bridge using real XMage requests and state objects. The existing protocol is JSONL 1.0.0 over stdin/stdout and forbids Tactical Oracle-derived actions or state. The provider-specific Java implementation remains absent and must not be represented as complete.
