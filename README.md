# Tau proof bundle — two real bugs, reproducible without the native engine

Everything here runs on plain CPython 3.11/3.12 with two pip packages. No tau-lang
build, no native binding, no node, no network. Both proofs were produced on the
VPS that found them; the transcripts in `transcripts/` are the raw output.

| Bug | Severity | Status at HEAD `a54a346` |
|---|---|---|
| #164 — a signed **decline** vote on a rule update is counted as an **approval** at block apply | consensus / governance | reproduced, fixed in PR #168 |
| #108 — at **254 interned addresses** a node can never allocate the 255th, and never recovers on its own | consensus / liveness (hard deadlock) | reproduced, root cause + fix shape posted |

---

## 1. Setup (5 commands)

### Windows (CMD)

```cmd
git clone https://github.com/IDNI/tau-testnet tau-testnet
cd tau-testnet
git checkout a54a346
python -m venv .venv
.venv\Scripts\python -m pip install -r C:\path\to\tau-proof\requirements-min.txt
set PYTHONPATH=%CD%
.venv\Scripts\python C:\path\to\tau-proof\repro_164_decline_vote.py
.venv\Scripts\python C:\path\to\tau-proof\repro_108_deadlock.py
```

### Linux / macOS

```bash
git clone https://github.com/IDNI/tau-testnet tau-testnet
cd tau-testnet && git checkout a54a346
python3 -m venv .venv
.venv/bin/pip install -r requirements-min.txt
export PYTHONPATH=$PWD
.venv/bin/python ../tau-proof/repro_164_decline_vote.py; echo "exit=$?"
.venv/bin/python ../tau-proof/repro_108_deadlock.py
```

`requirements-min.txt` is exactly:

```
blake3
py_arkworks_bls12381
```

Both ship Windows wheels for CPython 3.11/3.12, so no compiler is needed.

---

## 2. What you should see on the UNPATCHED checkout (`a54a346`)

`repro_164_decline_vote.py` — **exit code 1**, meaning vulnerable:

```
repo HEAD: a54a346
threshold: 1

A block-apply NO-vote: admitted=True submitted=True promoted_to_scheduled=True
A votes recorded for uid: 1
B mempool NO-vote:     admitted=False submitted=False promoted=False
C block-apply YES-vote: admitted=True submitted=True promoted=True

RESULT: VULNERABLE — decline counted as approval
```

Line A is the bug: a vote that says **no** promoted the update to `scheduled`.
Line B is the control that proves the mempool path already refuses the same vote,
so the two paths disagree.

`repro_108_deadlock.py`:

```
repo HEAD: a54a346

width_for_count(254) = 8 | usable_ceiling(8)  = 254
width_for_count(255) = 16 | usable_ceiling(16) = 65534

1) allocator     -> AllocatorCapacityExceeded | id 255 exceeds bv[8] usable range
2) intern_value  -> ShrinkUnavailable | intern failed: id 255 exceeds bv[8] usable range
3) NOT HANDLED   -> ShrinkUnavailable | intern failed: id 255 exceeds bv[8] usable range
4) control       -> ShrinkWidthOverflow caught then re-raised in test mode
```

Line 2 is the log line quoted in issue #108, byte for byte.

---

## 3. Prove the #164 fix (optional)

```bash
git checkout -b fix/164 origin/main
git am tau-164-fix-pr168.patch          # or: gh pr checkout 168
```

Re-run `repro_164_decline_vote.py` — now **exit code 0**:

```
repo HEAD: cbe7c80

A block-apply NO-vote: admitted=True submitted=False promoted_to_scheduled=False
A votes recorded for uid: 0
B mempool NO-vote:     admitted=False submitted=False promoted=False
C block-apply YES-vote: admitted=True submitted=True promoted=True

RESULT: SAFE — decline is a no-op, approval path unchanged
```

And the repository's own tests:

```bash
python -m pytest tests/test_governance.py -q
# 23 passed
```

---

## 4. Why #108 is a deadlock and not a hiccup

1. `width_for_count(254) == 8` because `_max_usable_id(8) == 254`, so a node that
   already holds 254 addresses picks the width that is already full.
2. Growing to bv[16] requires `count > 254`, which cannot happen while id 255
   cannot be allocated. Chicken and egg.
3. A restart does not help: `set_shrink_width_from_db()` recomputes 8 from
   `get_max_shrink_id() == 254`.
4. The only recovery path, `tau_manager.reexec_on_width_overflow()`, catches
   `ShrinkWidthOverflow` only. `AllocatorCapacityExceeded` is flattened into
   `ShrinkUnavailable` by the generic `except Exception` in `intern_value`, so the
   re-exec never fires and admission keeps answering `ADMISSION_UNAVAILABLE`.
5. Transfers between already-known addresses still pass — which is exactly the
   222/231 split reported in the issue.

---

## 5. Files

| File | Purpose |
|---|---|
| `repro_164_decline_vote.py` | decline-vote-as-approval; exit 1 = vulnerable, 0 = safe |
| `repro_108_deadlock.py` | 254-address width deadlock; prints the exact #108 log line |
| `requirements-min.txt` | the only two pip packages needed |
| `tau-164-fix-pr168.patch` | the fix under review as PR #168 |
| `run_all.sh` / `run_all.cmd` | runs both repros and shows exit codes |
| `transcripts/164-unpatched-a54a346.txt` | raw output, vulnerable |
| `transcripts/164-patched-pr168.txt` | raw output, fixed |
| `transcripts/108-unpatched-a54a346.txt` | raw output, deadlock |
| `transcripts/108-patched-pr168.txt` | unchanged by the #164 patch (different bug) |
