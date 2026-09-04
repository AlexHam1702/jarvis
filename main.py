import sys
import time
import subprocess
import os

def launch_jarvis():
    # Use the active virtual environment's Python executable
    py_exec = sys.executable
    project_dir = os.path.dirname(os.path.abspath(__file__))

    print("============================================")
    print("      INITIALIZING JARVIS SUBSYSTEMS        ")
    print("============================================")

    processes = []

    try:
        # 1. Start FastAPI Ollama Bridge
        print("[1/3] Starting Server (server.py)...")
        server_p = subprocess.Popen([py_exec, "server.py"], cwd=project_dir)
        processes.append(server_p)

        # Allow the Uvicorn server a brief buffer to bind port 8000
        time.sleep(2.0)

        # 2. Start Voice Agent (Whisper, OpenWakeWord, Edge-TTS)
        print("[2/3] Starting Voice Agent (voice_agent.py)...")
        voice_p = subprocess.Popen([py_exec, "voice_agent.py"], cwd=project_dir)
        processes.append(voice_p)

        # 3. Start Vision Thread (YOLO & OpenCV window)
        print("[3/3] Starting Desk Recognition (desk_recognition.py)...")
        vision_p = subprocess.Popen([py_exec, "desk_recognition.py"], cwd=project_dir)
        processes.append(vision_p)

        print("\nAll systems online. Say 'Hey Jarvis' to interact, or press Ctrl+C here to shutdown.")

        # Keep main supervisor running while children operate
        while True:
            for p in processes:
                if p.poll() is not None:
                    # One of the processes crashed or closed
                    print(f"\n[Warning] Subprocess {p.args[1]} exited with code {p.returncode}")
                    raise KeyboardInterrupt
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down all JARVIS processes...")
        for p in processes:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    p.kill()
        print("Shutdown complete.")

if __name__ == "__main__":
    launch_jarvis()