import os
import sys
import time
import subprocess

# Loop duration: 16 minutes (960 seconds)
LOOP_DURATION = 960
START_TIME = time.time()
SLEEP_INTERVAL = 120 # 2 minutes

def run_git_push():
    try:
        if not os.path.isdir(".git"):
            print("Not a git repository. Skipping git sync.")
            return

        # Ensure safe.directory is configured to prevent dubious ownership fatal error (exit code 128)
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", "*"], capture_output=True)

        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if status.returncode != 0:
            print(f"Git status returned non-zero code {status.returncode}. Skipping git push.")
            return

        changes = status.stdout.strip()
        if changes:
            # Filter changes to only stage relevant JSON files
            has_relevant_changes = False
            for line in changes.split('\n'):
                line_clean = line.strip()
                if any(x in line_clean for x in ["deals_history.json", "omega_history.json", "selectors.json"]):
                    has_relevant_changes = True
                    break
            
            if has_relevant_changes:
                print("Detected changes in data files. Staging and committing...")
                subprocess.run(["git", "config", "--global", "user.name", "github-actions[bot]"], capture_output=True)
                subprocess.run(["git", "config", "--global", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], capture_output=True)
                for f in ["dashboard/deals_history.json", "omega_history.json", "selectors.json"]:
                    if os.path.exists(f):
                        subprocess.run(["git", "add", f], capture_output=True)

                staged_check = subprocess.run(["git", "diff", "--staged", "--quiet"], capture_output=True)
                if staged_check.returncode == 0:
                    print("No staged changes found to commit. Skipping.")
                    return

                commit_res = subprocess.run(
                    ["git", "commit", "-m", "Auto-update deals feed in loop: " + time.strftime("%Y-%m-%d %H:%M:%S")],
                    capture_output=True, text=True
                )
                if commit_res.returncode != 0:
                    print(f"Git commit skipped or failed: {commit_res.stderr.strip()}")
                    return

                push_res = subprocess.run(["git", "push"], capture_output=True, text=True)
                if push_res.returncode == 0:
                    print("Changes pushed successfully.")
                else:
                    print(f"Git push skipped or failed: {push_res.stderr.strip()}")
            else:
                print("Changes detected, but none are tracked JSON files. Skipping git push.")
        else:
            print("No data changes detected. Skipping git push.")
    except Exception as e:
        print(f"Error during git push: {e}")

print("Starting Continuous Scraper Loop Runner (2-minute intervals, 16-minute max duration)...")
while time.time() - START_TIME < LOOP_DURATION:
    iter_start = time.time()
    print(f"\n--- Starting Scrape Iteration at {time.strftime('%H:%M:%S')} ---")
    
    # Run the scraper single-run
    subprocess.run([sys.executable, "loot_scraper.py", "--single-run"])
    
    # Push changes if any new deals were found
    run_git_push()
    
    elapsed = time.time() - iter_start
    sleep_time = max(10, SLEEP_INTERVAL - elapsed)
    
    # Check if we have enough time for another iteration
    if (time.time() - START_TIME) + sleep_time + 60 > LOOP_DURATION:
        print("Not enough time left for another iteration. Exiting loop.")
        break
        
    print(f"Iteration completed in {elapsed:.2f}s. Sleeping for {sleep_time:.2f}s...")
    time.sleep(sleep_time)

print("Loop duration complete. Exiting cleanly.")
