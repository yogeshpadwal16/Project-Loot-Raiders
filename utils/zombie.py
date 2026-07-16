import os
import logging

def run_zombie_cleanup():
    try:
        import psutil
        my_pid = os.getpid()
        parent_pid = os.getppid()
        terminated_list = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                pinfo = proc.info
                pid = pinfo['pid']
                name = pinfo['name']
                cmdline = pinfo['cmdline']
                
                if pid in (my_pid, parent_pid):
                    continue
                    
                # Terminate other python processes executing loot_scraper
                if name and 'python' in name.lower():
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
            logging.info(f"Automated startup zombie cleanup executed. Terminated: {', '.join(terminated_list)}")
    except Exception as e:
        logging.warning(f"Startup zombie cleanup warning: {e}")
