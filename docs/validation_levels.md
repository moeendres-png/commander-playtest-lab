# Validation levels

Every result carries one runtime validation level:

| Level | Meaning |
|---|---|
| `structural_only` | Fast abstract simulator only |
| `tactical_oracle` | Deterministic local tactical fixture/oracle |
| `external_rules_engine` | Real XMage or Forge execution after a valid handshake |

Legacy card registries retain `tactical_validated` and
`rules_engine_validated`, but runtime reports use the three values above.

The Tactical Oracle is suitable for offline contract development, deterministic
fixtures and Structural Simulator differential checks. It is not an external
engine and cannot satisfy the release gate.

Promotion to `external_rules_engine` requires preserved evidence containing the
provider identity, exact version, capability handshake, input, event log and
normalized result. No status is inferred from filenames or configuration.
