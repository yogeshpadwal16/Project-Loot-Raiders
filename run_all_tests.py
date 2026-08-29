import unittest
import sys
import os

def main():
    # 1. Project root directory setup
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)
    
    # 2. Isolate tests from .env overrides
    env_path = os.path.join(project_root, ".env")
    env_tmp_path = os.path.join(project_root, ".env.tmp")
    
    has_env = os.path.exists(env_path)
    if has_env:
        try:
            os.rename(env_path, env_tmp_path)
            print("[Test Runner] Temporarily isolated .env configuration.")
        except Exception as e:
            print(f"[Test Runner] Failed to isolate .env: {e}")
            
    # 3. Discover and run all unittest files inside tests/
    print(f"[Test Runner] Initiating test discovery in {os.path.join(project_root, 'tests')}...")
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=os.path.join(project_root, "tests"),
        pattern="test_*.py",
        top_level_dir=project_root
    )
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 4. Restore .env file
    if has_env and os.path.exists(env_tmp_path):
        try:
            os.rename(env_tmp_path, env_path)
            print("[Test Runner] Restored .env configuration.")
        except Exception as e:
            print(f"[Test Runner] Failed to restore .env: {e}")
            
    # 5. Exit with appropriate status code
    if not result.wasSuccessful():
        print("\n" + "=" * 70)
        print("FAILURES & ERRORS SUMMARY:")
        print("=" * 70)
        for test, err in result.failures:
            print(f"\n[FAILURE] {test}:\n{err}")
        for test, err in result.errors:
            print(f"\n[ERROR] {test}:\n{err}")
        print("=" * 70)
        print(f"[Test Runner] Execution failed: {len(result.failures)} failures, {len(result.errors)} errors.")
        sys.exit(1)
    else:
        print("[Test Runner] Execution completed successfully. All tests passed.")
        sys.exit(0)

if __name__ == "__main__":
    main()
