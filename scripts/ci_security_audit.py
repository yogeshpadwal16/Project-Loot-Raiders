#!/usr/bin/env python3
"""
CI Security and Secret Leak Audit
Scans repository for exposed API keys, tokens, credentials, and private keys.
Fail-closed for high-confidence secrets while allowing explicit safe placeholders.
"""
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# High-confidence credential regex patterns
TELEGRAM_TOKEN_PATTERN = re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{35}\b")
GENERIC_API_KEY_PATTERN = re.compile(r"(?i)(api[_-]?key|secret[_-]?key|private[_-]?key|access[_-]?token|auth[_-]?token)\s*[:=]\s*['\"][A-Za-z0-9+/=_-]{16,}['\"]")
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN (RSA|OPENSSH|EC|DSA|PGP) PRIVATE KEY-----")
AWS_KEY_PATTERN = re.compile(r"\b(AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b")
GITHUB_TOKEN_PATTERN = re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36}\b")

# Explicit safe placeholder identifiers
SAFE_PLACEHOLDER_PREFIXES = [
    "YOUR_", "YOUR-", "MOCK_", "mock_", "TEST_", "test_", "FAKE_", "fake_",
    "EXAMPLE_", "example_", "<SECRET_", "${{", "os.environ", "process.env"
]

def is_safe_placeholder(matched_str: str, file_context: str) -> bool:
    """Determines if a matched string is an explicit, non-secret placeholder or mock."""
    if any(p in matched_str for p in SAFE_PLACEHOLDER_PREFIXES):
        return True
    if "<SECRET_REDACTED>" in matched_str or "<MASKED>" in matched_str:
        return True
    return False

def run_ci_security_audit(target_dir: str = PROJECT_ROOT) -> bool:
    violations = []
    scanned_files_count = 0

    for root, dirs, files in os.walk(target_dir):
        # Exclude internal/virtual directories
        dirs[:] = [d for d in dirs if d not in ('.git', 'venv', '.venv', '__pycache__', 'node_modules', 'scratch', 'chroma_db', 'OmniRoute')]

        for f in files:
            if f.endswith(('.py', '.yml', '.yaml', '.sh', '.ps1', '.json', '.md', '.txt', '.ts', '.tsx', '.js')):
                if f in ('ci_security_audit.py', 'quality_gate.py'):
                    continue

                filepath = os.path.join(root, f)
                rel_path = os.path.relpath(filepath, PROJECT_ROOT)
                scanned_files_count += 1

                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as fp:
                        content = fp.read()

                        # 1. Telegram Bot Token Audit
                        tg_matches = TELEGRAM_TOKEN_PATTERN.findall(content)
                        for m in tg_matches:
                            if not is_safe_placeholder(m, content):
                                masked = f"{m[:6]}...{m[-4:]}"
                                violations.append(f"Telegram Bot Token pattern in {rel_path} (Fingerprint: {masked})")

                        # 2. Generic API Key / Secret Key Audit
                        key_matches = GENERIC_API_KEY_PATTERN.findall(content)
                        for m in key_matches:
                            if not is_safe_placeholder(m, content):
                                violations.append(f"Generic API/Secret key pattern in {rel_path}")

                        # 3. Private Key Block Audit
                        if PRIVATE_KEY_PATTERN.search(content):
                            violations.append(f"Private Key block detected in {rel_path}")

                        # 4. AWS Access Key Audit
                        aws_matches = AWS_KEY_PATTERN.findall(content)
                        for m in aws_matches:
                            if not is_safe_placeholder(m, content):
                                masked = f"{m[:4]}...{m[-4:]}"
                                violations.append(f"AWS Access Key in {rel_path} (Fingerprint: {masked})")

                        # 5. GitHub Personal Access Token Audit
                        gh_matches = GITHUB_TOKEN_PATTERN.findall(content)
                        for m in gh_matches:
                            if not is_safe_placeholder(m, content):
                                masked = f"{m[:4]}...{m[-4:]}"
                                violations.append(f"GitHub Token in {rel_path} (Fingerprint: {masked})")

                except Exception as e:
                    violations.append(f"Could not read {rel_path}: {e}")

    if violations:
        print(f"[FAIL] {len(violations)} Security violation(s) detected:")
        for v in violations:
            print(f"  - {v}")
        return False

    print(f"[PASS] Secret scan clean - zero leaks detected across {scanned_files_count} files.")
    return True

if __name__ == "__main__":
    if not run_ci_security_audit():
        sys.exit(1)
    sys.exit(0)
