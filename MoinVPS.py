import json
import subprocess
import time
import os  # Added for file operations
import fcntl  # Added for file locking

active_tasks = {}

def process_new_task(added):
    ip = added.get('ip')
    port = added.get('port')
    time_val = added.get('time')

    if ip and port and time_val:
        key = (ip, str(port), str(time_val))
        if key not in active_tasks:
            print(f"[+] New task added: IP={ip}, Port={port}, Time={time_val}")
            try:
                process = subprocess.Popen(['./Moin', ip, str(port), str(time_val), '900'])
                print(f"[+] Launched binary: ./Moin {ip} {port} {time_val} 900 (PID: {process.pid})")
            except Exception as e:
                print(f"[!] Failed to launch binary: {e}")
            active_tasks[key] = int(time_val)
        else:
            pass
    else:
        print("[!] Task received but missing ip, port, or time values")

def main_loop():
    while True:
        try:
            tasks = []
            if os.path.isfile('tasks.json'):
                with open('tasks.json', 'a+') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Acquire exclusive lock
                    f.seek(0)
                    if f.read(1):  # Check if file is not empty
                        f.seek(0)
                        tasks = json.load(f)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock

            if isinstance(tasks, list):
                for task in tasks:
                    if isinstance(task, dict) and 'ip' in task and 'port' in task and 'time' in task:
                        process_new_task(task)

            tasks_to_delete = []
            for key in list(active_tasks.keys()):
                active_tasks[key] -= 1
                if active_tasks[key] <= 0:
                    ip, port, orig_time = key
                    print(f"[+] Time expired for task: IP={ip}, Port={port}, Original Time={orig_time}")
                    try:
                        with open('tasks.json', 'a+') as f:
                            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Acquire exclusive lock
                            f.seek(0)
                            tasks = []
                            if f.read(1):  # Check if file is not empty
                                f.seek(0)
                                tasks = json.load(f)
                            remaining_tasks = [t for t in tasks if not (t.get('ip') == ip and str(t.get('port')) == port and str(t.get('time')) == orig_time)]
                            f.seek(0)
                            f.truncate()
                            json.dump(remaining_tasks, f, indent=4)
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock
                        print(f"[+] Removed task from tasks.json: IP={ip}, Port={port}, Time={orig_time}")
                    except Exception as e:
                        print(f"[!] Failed to remove task from tasks.json: {e}")
                    tasks_to_delete.append(key)

            for key in tasks_to_delete:
                active_tasks.pop(key, None)

            time.sleep(1)
        except Exception as e:
            print(f"[!] General error: {e}")
            time.sleep(1)

if __name__ == '__main__':
    main_loop()