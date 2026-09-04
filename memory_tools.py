import subprocess
import os

MEMORY_FILE = "jarvis_memory.md"

def remember_fact(fact: str):
    """Appends a new memory to the local file and pushes to GitHub."""
    # 1. Append the fact
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"- {fact}\n")
        
    # 2. Auto-commit and push to GitHub (requires git configured with a Personal Access Token or SSH)
    try:
        subprocess.run(["git", "add", MEMORY_FILE], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", f"JARVIS Memory Update: {fact[:30]}..."], check=True, capture_output=True)
        subprocess.run(["git", "push"], check=True, capture_output=True)
        print("[JARVIS]: Memory saved and pushed to GitHub.")
    except Exception as e:
        print(f"[JARVIS Error]: Git sync failed: {e}")

def load_memories() -> str:
    """Reads all memories to inject into the system prompt."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return "No prior memories recorded."