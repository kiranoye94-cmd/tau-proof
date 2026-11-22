"""PROOF 2 — Tau issue #164: a signed decline vote counts as approval.

Pure Python. No native tau engine, no node, no network.
Requires: blake3, py_arkworks_bls12381.

On an UNPATCHED checkout (a54a346) the block-apply path promotes an update on a
signed approve=False vote, while the mempool path refuses the same vote. Output:

    A block-apply NO-vote: admitted=True submitted=True promoted_to_scheduled=True
    A votes recorded for uid: 1

On a PATCHED checkout (PR #168) the same inputs give:

    A block-apply NO-vote: admitted=True submitted=False promoted_to_scheduled=False
    A votes recorded for uid: 0

Exit code is 0 when the decline vote is NOT counted (safe), 1 when it is counted
(vulnerable), so the script doubles as a regression check.

Run:
    PYTHONPATH=/path/to/tau-testnet python3 repro_164_decline_vote.py
"""
import subprocess
import sys

from consensus.governance import (
    ConsensusLifecycleManager,
    ConsensusRuleUpdate,
    ConsensusRuleVote,
)

PK_HEX = "aa" * 48
PK_BYTES = bytes.fromhex(PK_HEX)


def fresh():
    manager = ConsensusLifecycleManager(active_validators=[PK_HEX])
    update = ConsensusRuleUpdate(rule_revisions=["o1[t]:bv[1]"], activate_at_height=10)
    assert manager.submit_update(update), "update not submitted"
    return manager, update.update_id


def _repo_head():
    import os
    repo = os.environ.get("PYTHONPATH", "").split(os.pathsep)[0] or "."
    try:
        out = subprocess.run(["git", "-C", repo, "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True).stdout.strip()
        return out or "(not a git checkout)"
    except Exception as exc:
        return f"(unavailable: {exc})"


print("python:", sys.version.split()[0], "| platform:", sys.platform)
print("repo HEAD:", _repo_head())
print("threshold:", ConsensusLifecycleManager(active_validators=[PK_HEX]).approval_threshold)
print()

# A — block-apply path, signed decline
manager, uid = fresh()
decline = ConsensusRuleVote(update_id=uid, approve=False)
admitted = manager.can_admit_vote(decline, PK_BYTES, is_mempool=False)
submitted = manager.submit_vote(decline, PK_BYTES)
promoted = (uid not in manager.pending_updates) and any(
    entry[1] == uid for entry in manager.scheduled_updates
)
print(f"A block-apply NO-vote: admitted={admitted} submitted={submitted} "
      f"promoted_to_scheduled={promoted}")
print(f"A votes recorded for uid: {len(manager.votes.get(uid, ()))}")

# B — mempool path, same signed decline (must be refused)
manager2, uid2 = fresh()
decline2 = ConsensusRuleVote(update_id=uid2, approve=False)
admitted2 = manager2.can_admit_vote(decline2, PK_BYTES, is_mempool=True)
submitted2 = manager2.submit_vote(decline2, PK_BYTES) if admitted2 else False
promoted2 = uid2 not in manager2.pending_updates
print(f"B mempool NO-vote:     admitted={admitted2} submitted={submitted2} promoted={promoted2}")

# C — control: a genuine approval must still work
manager3, uid3 = fresh()
approve = ConsensusRuleVote(update_id=uid3, approve=True)
admitted3 = manager3.can_admit_vote(approve, PK_BYTES, is_mempool=False)
submitted3 = manager3.submit_vote(approve, PK_BYTES)
promoted3 = uid3 not in manager3.pending_updates
print(f"C block-apply YES-vote: admitted={admitted3} submitted={submitted3} promoted={promoted3}")
print()

vulnerable = admitted and submitted and promoted
print("RESULT:", "VULNERABLE — decline counted as approval" if vulnerable
      else "SAFE — decline is a no-op, approval path unchanged")
sys.exit(1 if vulnerable else 0)
