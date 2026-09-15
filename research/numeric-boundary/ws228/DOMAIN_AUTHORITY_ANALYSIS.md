# Domain Authority Analysis (WS228)

## Question

Is an authoritative Core interval itself a legal decision-domain object —
i.e. can the Lab losslessly project a Core-supplied [min, max] without
becoming a second Rules engine?

## Proven premises (pinned XMage 1.4.61)

1. Interface shape: Player.announceX(int min, int max, ...) and
   getAmount(int min, int max, ...) take plain int bounds. No step, stride,
   sentinel, option-list, or decline parameter exists in the signature.
   Javadoc: "Set the value for X in spells and abilities."
2. Reference acceptance semantics (HumanPlayer bytecode, javap -c):
   degenerate min>=max returns min; otherwise loop { prompt; read Integer;
   null -> re-prompt; value<min -> re-prompt; value>max -> re-prompt; else
   accept }. Every integer in the closed interval is individually
   acceptable; nothing outside is. Identical loops for announceX and
   getAmount.
3. Multi-leg semantics (MultiAmountType.isGoodValues bytecode): size match
   AND per-leg inclusive [min_i, max_i] AND total band
   [totalMin, totalMax]. Joint integer lattice with unit per-leg stride.
4. Bridge projection (XmageFullGameActionProjection:317-342) enforces
   exactly inclusive-range membership, requires numeric presence for
   numeric classes, and rejects numeric_choice where no bounds were
   authorized. It never invents values.
5. The Lab adapter receives numeric_min/numeric_max verbatim from the
   bridge (XmageFullGamePlayer.chooseNumber:1220-1222; target_amount
   346-347; multi legs 957-958).

## Verdict

"Core authoritatively supplies a contiguous inclusive integer interval and
Lab losslessly projects that interval" is PROVEN for announce_x, amount,
and each multi_amount leg (per-leg), and for the target_amount companion.
Therefore:

- Membership validation of a pilot-returned integer against the exact
  Core-supplied [min, max] is PROJECTION, not legislation. It adds no Rules
  content: the accepted set equals the Core-accepted set by construction.
- Full integer enumeration of a proven-contiguous interval is likewise
  projection (design A is Rules-correct, performance aside).
- What WOULD be a second Rules engine: inventing bounds, clamping,
  nearest-legal substitution, midpoint/random/min/max fallbacks, per-leg
  sequentialization presented as joint semantics, or pilot-side legality
  filtering (requested-option filtering that reconstructs legality).

## Strict condition (no exceptions)

Full enumeration is FORBIDDEN wherever contiguity/unit-stride is not
proven. Proven today: announce_x, amount, multi_amount legs,
target_amount companion. Any future numeric class (or any engine path
whose callback contract is not int-[min,max]) must prove contiguity first
or use the range-native design (B), which never enumerates and therefore
never needs the contiguity premise for CORRECTNESS of the offered set —
only membership validation against the transmitted bounds, which the
projection already performs.

Note on B vs contiguity: design B returns one pilot-chosen integer and
validates membership in [min,max]. If a future engine path authorized a
non-contiguous set but transmitted only [min,max], B's validation would be
weaker than true legality — but final authority remains the native
submission (engine accepts/rejects the callback return), and the bridge
MUST then transmit the true domain shape (explicit allow-list or
predicate id). S6 keeps the inclusive-interval descriptor ONLY for the
four proven classes; any other class keeps current behavior (fail closed
or explicit disposition).

## Feasibility proof for the bridge multi_amount sequentializer (F-RULES-02b context)

Per-leg recomputed bounds min=max(c.min, totalMin-alloc-remMaxAfter),
max=min(c.max, totalMax-alloc-remMinAfter) preserve exact feasibility:
for any chosen c in [min,max], the residual interval
[totalMin-alloc-c, totalMax-alloc-c] meets [remMinAfter, remMaxAfter]
(both inequalities hold by construction; contiguity of remaining legs
makes the intersection realizable). So sequentialization never
dead-ends and never offers an infeasible leg value — it is strategy-poor
(no joint expression) but not legality-breaking. S6 still restores the
joint decision because strategy poverty at scale IS a discretionary
narrowing of the pilot's lawful choice space.
