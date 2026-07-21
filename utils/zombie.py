import os
import logging
import time

def run_zombie_cleanup(max_age_seconds: float = None):
    try:
        import psutil
        my_pid = os.getpid()
        parent_pid = os.getppid()
        terminated_list = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            try:
                pinfo = proc.info
                pid = pinfo['pid']
                name = pinfo['name']
                cmdline = pinfo['cmdline']
                create_time = pinfo.get('create_time')
                
                if pid in (my_pid, parent_pid):
                    continue
                    
                # If periodic cleanup (max_age_seconds is set), check process age
                if max_age_seconds is not None and create_time is not None:
                    age = time.time() - create_time
                    if age < max_age_seconds:
                        continue
                        
                # Terminate other python processes executing loot_scraper (only on startup cleanup)
                if max_age_seconds is None and name and 'python' in name.lower():
                    if cmdline and any('loot_scraper.py' in arg for arg in cmdline):
                        proc.kill()
                        terminated_list.append(f"Python (PID {pid})")
                        continue
                        
                # Terminate zombie webdrivers / browser sessions
                if name and ('chromedriver' in name.lower() or 'chrome' in name.lower()):
                    proc.kill()
                    terminated_list.append(f"{name} (PID {pid})")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        if terminated_list:
            cleanup_type = "Periodic age-based" if max_age_seconds is not None else "Automated startup"
            logging.info(f"{cleanup_type} zombie cleanup executed. Terminated: {', '.join(terminated_list)}")
    except Exception as e:
        logging.warning(f"Zombie cleanup warning: {e}")
