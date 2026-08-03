import sys
import traceback
import threading

print("=== ACTIVE THREADS ===")
for thread in threading.enumerate():
    print(f"Thread: {thread.name} (Daemon: {thread.daemon}, Alive: {thread.is_alive()})")
