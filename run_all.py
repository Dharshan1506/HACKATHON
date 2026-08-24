import sys
import os
import time
import subprocess
import webbrowser

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    root_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(root_dir, "backend")
    frontend_dir = os.path.join(root_dir, "frontend")

    print("=" * 65)
    print("  PackSure AI – Legal Metrology Compliance Checker")
    print("  Launching Full-Stack Application (Backend + Frontend)")
    print("=" * 65)

    # 1. Start Backend FastAPI Server
    print("\n[1/2] Starting Python FastAPI Backend on http://localhost:8000 ...")
    backend_proc = subprocess.Popen(
        [sys.executable, "run.py"],
        cwd=backend_dir
    )

    # 2. Start Frontend Vite Dev Server
    print("[2/2] Starting React + TypeScript + Tailwind Frontend on http://localhost:5173 ...")
    frontend_cmd = "npm run dev" if os.name != "nt" else "cmd /c npm run dev"
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=frontend_dir,
        shell=True
    )

    # Wait 2 seconds and open browser
    time.sleep(2)
    print("\n" + "=" * 65)
    print("  PackSure AI is live!")
    print("  Frontend URL: http://localhost:5173")
    print("  Backend API:  http://localhost:8000/api")
    print("  Swagger Docs: http://localhost:8000/docs")
    print("  Press Ctrl+C in this terminal to stop both servers.")
    print("=" * 65 + "\n")

    try:
        webbrowser.open("http://localhost:5173")
        # Keep runner alive
        backend_proc.wait()
        frontend_proc.wait()
    except KeyboardInterrupt:
        print("\nStopping PackSure AI servers...")
        backend_proc.terminate()
        frontend_proc.terminate()
        print("Servers stopped successfully. Goodbye!")

if __name__ == "__main__":
    main()
