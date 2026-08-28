#!/usr/bin/env python3
"""
CI Security and Secret Leak Audit
Scans repository for exposed API keys, tokens, and credentials.
"""
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run_ci_security_audit() -> bool:
    token_pat = re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{35}\b")
    key_pat = re.compile(r"(?i)(api[_-]?key|secret[_-]?key|private[_-]?key)\s*[:=]\s*['\"][A-Za-z0-9+/=_-]{16,}['\"]")
    private_key_pat = re.compile(r"-----BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY-----")

    leaks = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Exclude directories
        dirs[:] = [d for d in dirs if d not in ('.git', 'venv', '.venv', '__pycache__', 'node_modules', 'scratch', 'chroma_db', 'OmniRoute')]
        for f in files:
            if f.endswith(('.py', '.yml', '.yaml', '.sh', '.ps1', '.json', '.md')):
                if f in ('.env', '.env.example', 'settings.json', 'TELEGRAM_STRING_SESSION.txt') or 'test_' in f or f == 'ci_security_audit.py' or f == 'quality_gate.py':
                    continue
                path = os.path.join(root, f)
                rel_path = os.path.relpath(path, PROJECT_ROOT)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                        content = fp.read()
                        if token_pat.search(content):
                            leaks.append(f"Telegram Bot Token pattern in {rel_path}")
                        if key_pat.search(content):
                            if not any(k in content for k in ['YOUR_', 'test_']):
                                leaks.append(f"API secret key pattern in {rel_path}")
                        if private_key_pat.search(content):
                            leaks.append(f"Private Key block in {rel_path}")
                except Exception:
                    pass

    if leaks:
        print("[FAIL] Potential secret leaks detected:")
        for l in leaks:
            print(f"  - {l}")
        return False
    print("[PASS] Secret scan clean - zero leaks detected in codebase.")
    return True

if __name__ == "__main__":
    if not run_ci_security_audit():
        sys.exit(1)
    sys.exit(0)
