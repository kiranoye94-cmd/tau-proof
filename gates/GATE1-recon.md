# GATE 1 — RECON
**Target:** IDNI/tau-testnet · **Pinned commit:** `a54a346` · **Date:** 2026-11-22

Gate 1 is the recon gate from `gate-validation-pipeline`. Nothing in Gate 2 may be
read as a finding until this checklist is complete or explicitly gapped.

---

## 1. Scope pin

| Item | Value | Source |
|---|---|---|
| Program page | https://tau.net/bounty-program | operator instruction |
| Repository in scope | https://github.com/IDNI/tau-testnet | program page + repo README |
| Commit audited | `a54a346` (`fix(admission): refuse u, this and non-i/o streams in rule text`) | `git rev-parse origin/main` at audit time |
| Language of the finding | Python host (`consensus/`, `tau_*.py`) | repo layout |
| Deployed contract address | none — this is a protocol client, not a contract | README:5 |
| Out of scope for these findings | no web app, no API, no hosted endpoint | n/a |

Quoted scope-defining text (README.md):

> *"A live, working blockchain whose state transitions and consensus rules are governed by
> **Tau formal logic**. A Python host handles networking, storage, and cryptography
> (BLS12-381 signatures); a separate Tau logic program … is the ultimate arbiter of block
> validity, proposer eligibility, transfers, and fees."* — README:5

> *"**Tau-driven consensus** — block validity (`o6`) and proposer eligibility (`o7`) come
> from living, governance-votable Tau rules."* — README:7

> *"**On-chain PoA validator set** — proposers must be in the active validator set; the set
> changes only through governance with a configurable vote quorum."* — README:8

The third line is what makes a mis-tallied governance vote an in-scope integrity issue:
the rule set is consensus, and the quorum is the only thing standing between a proposal
and a consensus change.

---

## 2. Entry-point enumeration (file:line, from source)

| # | Entry point | File:line | Auth surface | Note |
|---|---|---|---|---|
| 1 | `consensus_rule_vote` tx in block apply | `consensus/engine.py:2631-2643` | validator signature on tx; `is_mempool=False` | the path used by the #164 PoC |
| 2 | `lifecycle_mgr.can_admit_vote` | `consensus/governance.py:711-747` | active-validator check only when `is_mempool=True` | asymmetric by design |
| 3 | `lifecycle_mgr.submit_vote` | `consensus/governance.py:749-786` | re-checks validator; tallies | tallies `len(self.votes[uid])` |
| 4 | `_check_approval_promotion` | `consensus/governance.py:791-798` | none | counts set size, not approvals |
| 5 | Mempool gate for the same vote | `consensus/admission.py:875` | `is_mempool=True` | returns *"v1 explicit disapproval explicitly rejected"* |
| 6 | `transfer_vote` tx (control: handled correctly) | `consensus/engine.py:2435-2450` → `approvals.can_admit_vote` | signer == voter, approver set | `prospective_rule_change_slots` writes `entry.declined`, not `voted` |
| 7 | `Allocator.id_for` | `tau_allocator.py:212-228` | none (local id space) | raises `AllocatorCapacityExceeded` at 255 |
| 8 | `tau_shrink.intern_value` | `tau_shrink.py:267-300` | none | flattening point for #108 |
| 9 | `width_for_count` (process width) | `tau_shrink.py:81-86` | none | no headroom above `2^W-2` |
| 10 | `set_shrink_width_from_db` | `tau_shrink.py:108-140` | none | recomputes the same width on restart |
| 11 | `reexec_on_width_overflow` (recovery) | `tau_manager.py:474-481` | none | catches `ShrinkWidthOverflow` only |
| 12 | Representation plan reuse | `tau_admission.py:249-274` | none | committed `plan.width` is reused |

Entry 6 is listed deliberately as a negative control: the same class of bug in the
transfer-vote path does **not** exist, which is evidence the #164 asymmetry is an
oversight rather than intended design.

---

## 3. Trust boundaries

| Boundary | Crossing | What is assumed at the crossing |
|---|---|---|
| validator key → block inclusion | a signed vote tx is carried by a proposer | the tally reflects what each signer meant |
| mempool validation → block-apply validation | same tx validated by two different functions | both paths agree on validity |
| DB intern table → allocator width | `high_water` → `width_for_count` | width can always express the next id |
| process width → representation plan | `_current_shrink_width` → `plan.width` | committed plan is never narrower than what the node can type |
| interned id → engine stream type | persisted id → `bv[W]` typing | an id, once persisted, stays expressible |

---

## 4. Dependency / version inventory

| Component | Version | Relevance |
|---|---|---|
| CPython | 3.11.15 (VPS), 3.14.4 (operator PC) | both reproduce the defects |
| `blake3` | 1.0.11 | state hashing |
| `py_arkworks_bls12381` | 0.5.0 | validator signatures |
| tau-lang (native) | pin `c3ea334` per issue reports | **not built here** — see RECON GAP-1 |
| Docker image | `Dockerfile.standalone` | official path for running the engine |

---

## 5. Saturation census (dedupe gate)

Live counts at audit time:

| Metric | Count |
|---|---|
| Issues total | 85 |
| Issues open | 43 |
| PRs total | 83 |
| PRs open | 46 |

Per-family dedupe check:

| Family | Search | Hits | Duplicate verdict |
|---|---|---|---|
| Signed decline counted as approval | `vote in:title`, `approv in:title` | **#164** (open, by jimb000o) + **#168** (open, this fix) | not duplicated by any other fix |
| Address interning / width | `width OR intern OR allocator` | **#108** (open) · related closed: #91 (width errors), #69 (shrink typing clash), #70 (advisory evaluator) | #108 not covered by any merged fix |

Conclusion: both defects are single-source in the tracker. Neither has a competing fix PR,
so submitting work on them is not a duplicate. `#91` closed a *different* width problem
(error surfacing), and `#69` closed the *typing clash* case — neither added headroom at
`width_for_count` nor reclassified `AllocatorCapacityExceeded`.

---

## 6. Deployment integrity

- No contract bytecode to hash: the target is a protocol client. The equivalent check is
  *"does the pinned source reproduce the observed behaviour?"* — done at `a54a346`, on two
  operating systems, with the raw transcripts stored (`transcripts/`).
- The #108 symptom comes from a **running node's log** in the issue, not from a deployment
  we control. We reproduce the *code path that produces that exact log string*; we do not
  reproduce the 29-hour node. That distinction is carried into Gate 2.

---

## RECON GAPs (carried forward as risks, not hidden)

```
RECON GAP-1: native tau-lang engine (pin c3ea334) was not built — the VPS has 2 vCPU and
  the toolchain (ninja, libcurl, exact Python pin) is not provisioned. Consequence: any
  claim that requires the engine to actually type/execute a rule is out of reach here.
  Risk carried to Gate 2: the #164 finding is stated at lifecycle/tally level, not at
  "engine accepted a rule it should have refused" level.

RECON GAP-2: no long-running node. The 254-address state is constructed directly against
  `Allocator`/`intern_value` rather than reached by 29 hours of traffic. Risk carried to
  Gate 2: the *permanence* claim rests on `width_for_count` being recomputed from
  `get_max_shrink_id()` at startup (source-verified), not on an observed restart loop.

RECON GAP-3: no evidence of a decline-vote-emitting client in the wild was found in this
  repo. If none exists, #164 is latent. Risk carried to Gate 2: severity depends on a
  precondition that is not currently satisfied by v1 clients.
```

## Gate 1 verdict

**PASS** — scope pinned to a commit, 12 entry points enumerated with `file:line`, trust
boundaries mapped, dependencies inventoried, saturation census with per-family dedupe
recorded, deployment-integrity substitute defined. Three gaps declared and carried forward.
