# GATE 2 — THREAT MODEL
**Target:** IDNI/tau-testnet · **Pinned commit:** `a54a346` · **Date:** 2026-11-22

Gate 2 requires four concrete elements per threat. A threat missing any element is
rejected here and never becomes a hypothesis. Both threats below are carried from
Gate 1 entries 1–4 and 7–12.

---

## THREAT 1 — decline vote tallied as approval

**Attacker capability**
Controls a block proposer (own validator slot, or a bribed/compromised proposer), and
possesses **one** validator signature over `approve=false` for the target update. The
signature can be harvested from any source that lets a validator express dissent: a
wallet "reject" action, a governance UI, a co-signing flow. The attacker does not need
the validator's key at block-building time — only the already-signed transaction.

**Trust boundary violated**
`mempool validation` → `block-apply validation` (`consensus/engine.py:2634` calls
`can_admit_vote(..., is_mempool=False)`). The same transaction is judged by two different
code paths, and the stricter judgement exists only on the path the attacker does not have
to use.

**Assumption broken**
The code assumes that because `approve=false` is refused by the mempool, admission
(`consensus/admission.py:875`, *"v1 explicit disapproval explicitly rejected"*) and gossip,
the block-apply path may stay permissive and delegate to `submit_vote` as a "soft no-op".
`submit_vote` (`consensus/governance.py:749`) does not implement that no-op: it tallies the
voter without reading `vote.approve`, and `_check_approval_promotion` counts
`len(self.votes[uid])`. The assumption "permissive block path is harmless" holds only if
the tally ignores the field — which it does not.

**Expected observable effect (measured)**
`manager.scheduled_updates` gains the update while `pending_updates` loses it, at 1 genuine
approval against a threshold of 2 (3 validators). Later `process_height_transitions(height)`
activates the rule revisions and any `host_contract_patch` on every node. Measured in
`poc_164_quorum_by_decline.py`: `tally used by code: 2`, `still pending: False`,
`scheduled: True`. After the fix: `tally: 1`, `still pending: True`, `scheduled: False`.

---

## THREAT 2 — address-interning width deadlock

**Attacker capability**
None required. Any ordinary user who sends a transfer involving an address the node has
not yet seen, once that node holds 254 distinct interned addresses. This is a
stress/aging condition, not an attack primitive.

**Trust boundary violated**
Persistent store → execution width: `db.get_max_shrink_id()` feeds `width_for_count()`
(`tau_shrink.py:81`) which sets the process width, which feeds `plan.width`
(`tau_admission.py:303`) which bounds `Allocator.id_for` (`tau_allocator.py:212`). The
boundary assumes the persistent high-water mark always leaves room for the next id; at
exactly `2^8 - 2` it does not.

**Assumption broken**
Two assumptions fail together:
1. *"Growth happens by re-exec."* True only for `ShrinkWidthOverflow`; the capacity error
   is a different class and `reexec_on_width_overflow` (`tau_manager.py:474-481`) does not
   catch it.
2. *"A fresh process picks a wider width."* `width_for_count(254) == 8` because
   `_max_usable_id(8) == 254` — a restart recomputes the width that is already full. The
   growth condition (`count > 254`) is unreachable while id 255 cannot be allocated.

**Expected observable effect (measured)**
`AllocatorCapacityExceeded: id 255 exceeds bv[8] usable range` at the allocator,
flattened by `intern_value` into `ShrinkUnavailable: intern failed: id 255 exceeds bv[8]
usable range` — byte-for-byte the string quoted in issue #108's node log — and propagated
past the recovery wrapper as `NOT HANDLED`. Upstream this is `ADMISSION_UNAVAILABLE`, i.e.
every new-address transaction is refused, permanently, while transfers between already-known
addresses keep working (matching the 222/231 split in the issue).

---

## Gate 2 checklist
| Threat | Attacker capability | Boundary violated | Assumption broken | Observable effect | Gate |
|---|---|---|---|---|---|
| T1 decline→approval | proposer slot + 1 signed decline | mempool vs block-apply validation | permissive block path is harmless | update scheduled at 1/2 approvals | **PASS 4/4** |
| T2 width deadlock | none (any user, aging node) | store → width → plan → allocator | width can always grow by re-exec + restart | permanent `ADMISSION_UNAVAILABLE`, exact #108 log line | **PASS 4/4** |

A threat that fails any one element is rejected. Both are complete.

---

## What Gate 2 deliberately excludes

| Candidate threat | Why excluded |
|---|---|
| Cross-validator vote replay / double counting | `submit_vote` returns `False` on a duplicate in `self.votes[uid]`; verified in the control path of the PoC |
| Forged vote from a non-validator | `submit_vote` returns `False` for a pubkey outside `active_validators` (`_normalize_voter` + set check) |
| "No vote counts as a yes" inside `engine.apply` after the fix | patch makes it a no-op, but the *engine-level* acceptance (rule actually running in the native evaluator) was not exercised — RECON GAP-1 |
| 254-address condition reachable by attacker to censor a specific user | not a distinct threat: it refuses *all* new addresses, so there is no targeted-censorship primitive to model |

---

## Carry-forward from Gate 1 gaps

| Gap | Effect on these threats |
|---|---|
| GAP-1 native engine not built | T1 is stated at lifecycle/tally level. The claim "the rule then executes on every node" rests on `process_height_transitions` → `scheduled_updates` semantics read from source, not on an engine run. Stated as such in the report. |
| GAP-2 no long-running node | T2's permanence claim rests on `width_for_count` recomputation at startup (source-verified) plus the measured exception chain, not on an observed restart loop. |
| GAP-3 no known decline-vote client | T1's severity is preconditioned. Gate 2 records the precondition; Gate 4 must not upgrade severity past it. |

## Gate 2 verdict

**PASS** — two threats, four concrete elements each, no generic placeholders. The
boundary and the broken assumption are both anchored to `file:line` evidence gathered in
Gate 1, and each expected effect is already measured, not projected.

Next gate (Gate 3 — hypothesis) may only restate these as falsifiable sentences; it may not
introduce a new mechanism.
