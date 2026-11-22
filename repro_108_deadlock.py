"""PROOF 1 — Tau issue #108: the 254-address width deadlock is permanent.

Pure Python. No native tau engine, no node, no network.
Requires: blake3, py_arkworks_bls12381  (see requirements-min.txt)

What it shows, step by step:
  1. width_for_count(254) == 8, and bv[8] can only express ids 1..254.
  2. A 255th distinct address cannot be allocated at bv[8].
  3. intern_value flattens that recoverable error into ShrinkUnavailable,
     producing the exact log line reported in the issue.
  4. The node's only "widen the width" recovery path (reexec_on_width_overflow)
     does NOT catch it -> admission answers ADMISSION_UNAVAILABLE forever.
  5. Control: the same wrapper DOES catch ShrinkWidthOverflow, so the path works
     for the case it was written for.

Run (Linux/macOS):
    PYTHONPATH=/path/to/tau-testnet python3 repro_108_deadlock.py
Run (Windows CMD):
    set PYTHONPATH=C:\\path\\to\\tau-testnet
    python repro_108_deadlock.py
"""
import subprocess
import sys

import tau_allocator
import tau_shrink
import tau_manager

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

print()
print("width_for_count(254) =", tau_shrink.width_for_count(254),
      "| usable_ceiling(8)  =", tau_allocator.usable_ceiling(8))
print("width_for_count(255) =", tau_shrink.width_for_count(255),
      "| usable_ceiling(16) =", tau_allocator.usable_ceiling(16))
print()

snap = tau_allocator.MappingSnapshot(
    epoch=1, committed={f"k{i}": i for i in range(1, 255)}
)
exhausted = tau_allocator.Allocator(snap, width=8, label="repro")

# 1) the allocator refuses the 255th address
try:
    exhausted.id_for("brand-new-address")
    print("1) UNEXPECTED: allocated")
except tau_allocator.AllocatorCapacityExceeded as exc:
    print("1) allocator     ->", type(exc).__name__, "|", exc)

# 2) intern_value turns it into "unavailable" (the #108 log line, verbatim)
with tau_shrink.speculative_allocation(exhausted):
    try:
        tau_shrink.intern_value("ab" * 48, 384)
    except Exception as exc:
        print("2) intern_value  ->", type(exc).__name__, "|", exc)

# 3) the recovery path does not catch it
tau_manager.tau_test_mode = True
with tau_shrink.speculative_allocation(exhausted):
    try:
        with tau_manager.reexec_on_width_overflow():
            tau_shrink.intern_value("cd" * 48, 384)
        print("3) UNEXPECTED: recovery handled it")
    except tau_shrink.ShrinkWidthOverflow as exc:
        print("3) handled as width overflow (node would re-exec):", exc)
    except Exception as exc:
        print("3) NOT HANDLED   ->", type(exc).__name__, "|", exc)

# 4) control: the wrapper does catch the case it was written for
try:
    with tau_manager.reexec_on_width_overflow():
        raise tau_shrink.ShrinkWidthOverflow("synthetic")
    print("4) control: swallowed (unexpected)")
except tau_shrink.ShrinkWidthOverflow:
    print("4) control       -> ShrinkWidthOverflow caught then re-raised in test mode")

print()
print("CONCLUSION: at 254 interned addresses the node has no path to bv[16].")
print("width_for_count(254) recomputes 8 on every restart, id 255 never fits,")
print("and the capacity error never reaches the re-exec recovery.")
