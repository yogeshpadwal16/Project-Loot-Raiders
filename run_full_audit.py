# run_full_audit.py
import subprocess
import sys
import os

def run_step(command, description):
    print(f"\n[AUDIT STEP] {description}...")
    result = subprocess.run(command, shell=True)
    if result.returncode != 0:
        print(f"[FAIL] {description}")
        return False
    print(f"[PASS] {description}")
    return True

def main():
    print("==================================================")
    print(" PROJECT LOOT RAIDERS - FULL PIPELINE AUDIT ")
    print("==================================================")
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(project_root, ".env")
    env_tmp_path = os.path.join(project_root, ".env.tmp")
    
    has_env = os.path.exists(env_path)
    if has_env:
        try:
            os.rename(env_path, env_tmp_path)
            print("[Audit] Temporarily isolated .env configuration.")
        except Exception as e:
            print(f"[Audit] Failed to isolate .env: {e}")
            
    steps = [
        ("python check_health.py", "Health & Network Diagnostics"),
        ("python check_db.py", "Database Integrity Check"),
        ("python -m unittest discover -s tests", "Automated Test Suite"),
    ]
    
    success = True
    try:
        for cmd, desc in steps:
            if not run_step(cmd, desc):
                print("\n[FAIL] SYSTEM AUDIT FAILED! Resolve issues before committing.")
                success = False
                break
    finally:
        if has_env and os.path.exists(env_tmp_path):
            try:
                os.rename(env_tmp_path, env_path)
                print("[Audit] Restored .env configuration.")
            except Exception as e:
                print(f"[Audit] Failed to restore .env: {e}")
                
    if not success:
        sys.exit(1)
        
    print("\n[SUCCESS] ALL CHECKS PASSED PERFECTLY!")
    sys.exit(0)

if __name__ == "__main__":
    main()