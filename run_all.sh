#!/usr/bin/env bash
# Run both Tau proofs. Needs PYTHONPATH pointing at the tau-testnet checkout.
set -u
cd "$(dirname "$0")"
if [ -z "${PYTHONPATH:-}" ]; then
  echo "[X] PYTHONPATH is not set. Example: export PYTHONPATH=/path/to/tau-testnet"
  exit 2
fi
PY=${PY:-python3}

echo "=== #164 decline vote counted as approval ==="
"$PY" repro_164_decline_vote.py
echo "[exit=$?]  (1 = vulnerable, 0 = fixed)"
echo
echo "=== #108 254-address width deadlock ==="
"$PY" repro_108_deadlock.py
echo "[exit=$?]"
