"""
Start the trading engine.
Usage: python start_trading.py
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import subprocess
import time
from pathlib import Path

def start():
    engine = Path(__file__).parent / "live_engine.py"
    
    print("=" * 50)
    print("AI TRADING ENGINE")
    print("=" * 50)
    print("")
    print("Starting in background...")
    print("To stop: Ctrl+C or close this window")
    print("")
    
    try:
        subprocess.run([sys.executable, str(engine), "--interval", "15"])
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    start()
