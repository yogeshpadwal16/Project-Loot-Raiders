#!/usr/bin/env python3
"""
Loot Raiders Mirror Pipeline Health Checker CLI
Executes the modular diagnostic test suite and outputs a status report.
"""
import os
import sys
import subprocess

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

def main():
    print("\n==========================================================================")
    print("LOOT RAIDERS PIPELINE HEALTH CHECKER")
    print("==========================================================================\n")
    
    # Resolve the project root directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Propagate environment variables and override PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = base_dir
    env["PYTHONIOENCODING"] = "utf-8"
    
    # Build command utilizing the same python interpreter (within .venv)
    cmd = [sys.executable, "-m", "deal_engine.mirroring.diagnostic"]
    
    try:
        # Run diagnostic suite
        result = subprocess.run(cmd, env=env, check=False)
        sys.exit(result.returncode)
    except Exception as e:
        print(f"Error: Failed to execute pipeline diagnostics: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
