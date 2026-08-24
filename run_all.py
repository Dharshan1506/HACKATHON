import sys
import os
import time
import socket
import subprocess
import webbrowser
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def kill_process_on_port(port: int):
    if os.name == 'nt':
        try:
            # Find PID listening on port
            cmd = f'netstat -ano | findstr :{port}'
            output = subprocess.check_output(cmd, shell=True).decode()
            for line in output.strip().split('\n'):
                if 'LISTENING' in line:
                    parts = line.strip().split()
                    pid = parts[-1]
                    if pid and pid != '0':
                        subprocess.run(f'taskkill /F /PID {pid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

def wait_for_backend(url="http://127.0.0.1:8000/api/health", timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(root_dir, "backend")
    frontend_dir = os.path.join(root_dir, "frontend")

    print("=" * 65)
    print("  PackSure AI – Legal Metrology Compliance Checker")
    print("  Full-Stack Runner & Diagnostics for VS Code")
    print("=" * 65)

    # Free ports if previously occupied
    if is_port_in_use(8000):
        print("Note: Port 8000 in use, freeing port...")
        kill_process_on_port(8000)
        time.sleep(1)

    # 1. Start FastAPI Backend
    print("\n[1/2] Launching FastAPI Backend on http://localhost:8000 ...")
    backend_proc = subprocess.Popen(
        [sys.executable, "run.py"],
        cwd=backend_dir
    )

    # 2. Start Vite + React Frontend
    print("[2/2] Launching Vite + React Frontend on http://localhost:5173 ...")
    frontend_cmd = "npm run dev" if os.name != "nt" else "cmd /c npm run dev"
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=frontend_dir,
        shell=True
    )

    print("\nWaiting for services to become ready...")
    backend_ready = wait_for_backend()

    if backend_ready:
        print("✓ Backend API is online & healthy!")
    else:
        print("Notice: Backend is taking time to initialize models...")

    print("\n" + "=" * 65)
    print("  PackSure AI is live!")
    print("  Frontend UI:  http://localhost:5173")
    print("  Backend API:  http://localhost:8000/api")
    print("  API Docs:     http://localhost:8000/docs")
    print("  Press Ctrl+C in this terminal to stop both servers.")
    print("=" * 65 + "\n")

    try:
        webbrowser.open("http://localhost:5173")
        # Keep process running
        while True:
            # Check if child process crashed
            b_ret = backend_proc.poll()
            f_ret = frontend_proc.poll()
            if b_ret is not None:
                print(f"Backend process exited with code {b_ret}")
                break
            if f_ret is not None:
                print(f"Frontend process exited with code {f_ret}")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping PackSure AI servers...")
    finally:
        try:
            backend_proc.terminate()
            frontend_proc.terminate()
        except Exception:
            pass
        print("PackSure AI services shut down cleanly. Goodbye!")

if __name__ == "__main__":
    main()
