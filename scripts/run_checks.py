# scripts/run_checks.py
import sys
import os
import re
import subprocess
import py_compile

def print_cyan(text):
    print(f"\033[96m{text}\033[0m")

def print_green(text):
    print(f"\033[92m{text}\033[0m")

def print_red(text):
    print(f"\033[91m{text}\033[0m")

def install_hook():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    git_dir = os.path.join(project_root, ".git")
    if not os.path.exists(git_dir):
        print_red("[Hook Installer] Not a git repository or running outside root directory.")
        return False
        
    hook_dir = os.path.join(git_dir, "hooks")
    os.makedirs(hook_dir, exist_ok=True)
    hook_path = os.path.join(hook_dir, "pre-commit")
    
    # Write shell pre-commit hook script (compatible with bash/git bash on Windows)
    hook_content = f"""#!/bin/sh
python "{os.path.join(project_root, 'scripts', 'run_checks.py')}"
"""
    try:
        with open(hook_path, "w", newline="\n") as f:
            f.write(hook_content)
        try:
            os.chmod(hook_path, 0o755)
        except Exception:
            pass
        print_green("[Hook Installer] Git pre-commit hook successfully installed/updated.")
        return True
    except Exception as e:
        print_red(f"[Hook Installer] Failed to write git hook: {e}")
        return False

def scan_secrets():
    print_cyan("\n=== 1. SECRET SCANNING ===")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Secret detection pattern rules
    secret_patterns = {
        "Telegram Bot Token": re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{35}\b"),
        "General Secret Key": re.compile(r"(?i)(secret_key|api_key|private_key|api_secret)\s*=\s*['\"][A-Za-z0-9_+\-/]{16,}['\"]"),
        "YOUR_ Placeholders": re.compile(r"\bYOUR_(TELEGRAM|BOT|API|DB)_[A-Z0-9_]+\b")
    }

    try:
        res = subprocess.run("git diff --cached --name-only", shell=True, capture_output=True, text=True)
        files = [f.strip() for f in res.stdout.split("\n") if f.strip()]
    except Exception:
        files = []

    if not files:
        print_cyan("No staged files found via git. Scanning all python source files instead.")
        for root, _, filenames in os.walk(project_root):
            if "venv" in root or ".venv" in root or ".git" in root or "tests" in root or "scratch" in root:
                continue
            for f in filenames:
                if f.endswith((".py", ".env", ".json")):
                    rel_path = os.path.relpath(os.path.join(root, f), project_root)
                    files.append(rel_path)

    secrets_detected = False
    for filepath in files:
        # Normalize path delimiters for cross-platform matches
        norm_path = filepath.replace("\\", "/")
        
        # Skip gitignored patterns, temporary folders, databases, and assets
        skip_patterns = [".env", "scratch/", "tests/", ".git/", "venv/", ".venv/", "__pycache__", ".db", ".ttf", ".session"]
        if any(x in norm_path for x in skip_patterns):
            continue
            
        abs_path = os.path.join(project_root, filepath)
        if not os.path.exists(abs_path) or os.path.isdir(abs_path):
            continue
        try:
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                
            for rule_name, pattern in secret_patterns.items():
                # Avoid flagging developer default keys and settings
                if rule_name == "YOUR_ Placeholders" and any(x in norm_path for x in ["settings.py", "mirror_config.py", "sessions_config.json", "generate_session_string.py", "network_fallback.py"]):
                    continue
                if rule_name == "General Secret Key" and any(x in norm_path for x in ["network_fallback.py", "settings.py"]):
                    continue
                    
                matches = pattern.findall(content)
                if matches and ".env.example" not in norm_path and "settings.json" not in norm_path:
                    for m in matches:
                        print_red(f"[FAIL] Potential {rule_name} detected in {filepath}: {m}")
                        secrets_detected = True
        except Exception as read_err:
            print_red(f"Error scanning {filepath}: {read_err}")

    if secrets_detected:
        print_red("[FAIL] Secret scanning detected leaks. Committing blocked.")
        return False
    print_green("[PASS] No secret leaks detected in target files.")
    return True

def run_lint_checks():
    print_cyan("\n=== 2. LINT & STATIC SYNTAX CHECKS ===")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    try:
        res = subprocess.run("flake8 --version", shell=True, capture_output=True)
        if res.returncode == 0:
            print_cyan("Running flake8 lint checks...")
            res_lint = subprocess.run("flake8 --exclude=venv,.venv,__pycache__ --max-line-length=127 .", shell=True)
            if res_lint.returncode != 0:
                print_red("[FAIL] flake8 checks did not pass.")
                return False
            print_green("[PASS] flake8 check passed.")
            return True
    except Exception:
        pass

    print_cyan("flake8 not found in path. Running Python py_compile check...")
    syntax_error = False
    for root, _, filenames in os.walk(project_root):
        if "venv" in root or ".venv" in root or ".git" in root:
            continue
        for filename in filenames:
            if filename.endswith(".py"):
                filepath = os.path.join(root, filename)
                try:
                    py_compile.compile(filepath, doraise=True)
                except py_compile.PyCompileError as e:
                    print_red(f"[SYNTAX ERROR] {filepath}: {e}")
                    syntax_error = True
                    
    if syntax_error:
        print_red("[FAIL] Syntax verification failed.")
        return False
    print_green("[PASS] Syntax verification passed.")
    return True

def run_tests():
    print_cyan("\n=== 3. AUTOMATED TEST SUITE ===")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_script = os.path.join(project_root, "run_all_tests.py")
    if not os.path.exists(test_script):
        print_red(f"[FAIL] test runner script not found at: {test_script}")
        return False
        
    res = subprocess.run([sys.executable, test_script])
    if res.returncode != 0:
        print_red("[FAIL] Automated unit test suite failed.")
        return False
    print_green("[PASS] Test suite passed successfully.")
    return True

def main():
    print("==================================================")
    print("   PROJECT LOOT RAIDERS - PRE-COMMIT AUDIT HOOK   ")
    print("==================================================")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--install":
        install_hook()
        sys.exit(0)
        
    install_hook()
    
    if not scan_secrets():
        sys.exit(1)
        
    if not run_lint_checks():
        sys.exit(1)
        
    if not run_tests():
        sys.exit(1)
        
    print_green("\n[SUCCESS] PRE-COMMIT CHECKS PASSED PERFECTLY!")
    sys.exit(0)

if __name__ == "__main__":
    main()
