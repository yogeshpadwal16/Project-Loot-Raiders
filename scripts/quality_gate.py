#!/usr/bin/env python3
"""
Project Loot Raiders - Executable Quality Gate Script
Verifies:
1. Python Syntax & Compilation
2. Full Unit Test Suite Execution
3. Security & Secret Leak Audit
"""

import os
import sys
import re
import unittest
import compileall

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def print_banner(title):
    print(f"\n==========================================================================")
    print(f"  {title}")
    print(f"==========================================================================")

def run_syntax_check():
    print_banner("1. SYNTAX & COMPILATION CHECK")
    success = compileall.compile_dir(PROJECT_ROOT, maxlevels=5, quiet=1)
    if success:
        print(" [PASS] All Python files compiled successfully without syntax errors.")
        return True
    else:
        print(" [FAIL] Syntax errors detected in Python files.")
        return False

def run_unit_tests():
    print_banner("2. UNIT & INTEGRATION TEST SUITE")
    sys.path.insert(0, PROJECT_ROOT)
    loader = unittest.TestLoader()
    tests_dir = os.path.join(PROJECT_ROOT, "tests")
    suite = loader.discover(tests_dir, pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)

    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)
    passed = total - failures - errors - skipped

    print(f"\nTest Summary:")
    print(f"  Total: {total} | Passed: {passed} | Failures: {failures} | Errors: {errors} | Skipped: {skipped}")

    if result.wasSuccessful():
        print(" [PASS] All unit tests executed cleanly.")
        return True, passed, failures, errors, skipped
    else:
        print(" [FAIL] Test failures or errors detected.")
        return False, passed, failures, errors, skipped

def run_security_audit():
    print_banner("3. SECURITY & SECRET LEAK AUDIT")
    # Token regex pattern
    token_pattern = re.compile(r'\b\d{8,11}:[A-Za-z0-9_-]{35}\b')
    sensitive_keys = re.compile(r'(?i)(api[_-]?key|secret[_-]?key|private[_-]?key)\s*[:=]\s*["\'][A-Za-z0-9+/=_-]{16,}["\']')

    violations = []

    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Exclude directories
        dirs[:] = [d for d in dirs if d not in ('.git', 'venv', '.venv', '__pycache__', 'chroma_db', 'scratch', 'OmniRoute', 'node_modules')]
        for file in files:
            if file.endswith(('.py', '.json', '.yml', '.yaml', '.sh', '.ps1', '.md', '.txt')):
                # Skip .env, settings.json, and test mock files
                if file in ('.env', '.env.example', 'settings.json', 'TELEGRAM_STRING_SESSION.txt') or 'test_' in file or file == 'quality_gate.py':
                    continue
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        m = token_pattern.search(content)
                        if m:
                            rel_path = os.path.relpath(filepath, PROJECT_ROOT)
                            violations.append(f"Hardcoded Telegram Bot Token in: {rel_path} -> match '{m.group(0)}'")
                        m_key = sensitive_keys.search(content)
                        if m_key:
                            rel_path = os.path.relpath(filepath, PROJECT_ROOT)
                            violations.append(f"Potential hardcoded API secret key in: {rel_path} -> match '{m_key.group(0)}'")
                except Exception:
                    pass

    if not violations:
        print(" [PASS] Zero hardcoded bot tokens or secret keys detected.")
        return True
    else:
        print(" [FAIL] Security violations detected:")
        for v in violations:
            print(f"   - {v}")
        return False

def main():
    print("Running Project Loot Raiders Quality Gate...")
    syntax_ok = run_syntax_check()
    tests_ok, passed, failures, errors, skipped = run_unit_tests()
    sec_ok = run_security_audit()

    print_banner("QUALITY GATE FINAL RESULT")
    if syntax_ok and tests_ok and sec_ok:
        print(" STATUS: PASSED - All quality gates satisfied cleanly.")
        sys.exit(0)
    else:
        print(" STATUS: FAILED - Please resolve errors above before committing/deploying.")
        sys.exit(1)

if __name__ == "__main__":
    main()
