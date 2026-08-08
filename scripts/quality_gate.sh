#!/usr/bin/env bash
# Project Loot Raiders - Quality Gate Shell Executable Wrapper
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"
cd "$PROJECT_ROOT"

export PYTHONPATH="."
python3 "$SCRIPT_DIR/quality_gate.py"
exit $?
