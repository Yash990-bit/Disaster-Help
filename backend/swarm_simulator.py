"""
Emergency Swarm Simulator — High-Velocity Call Generator
Sends 10+ calls in a burst to test triage, deduplication, and priority.
"""

import requests
import time
import concurrent.futures

API_URL = "http://localhost:8001/process-call"

CALLS = [
    # --- INCIDENT A: SONIPAT BUS STAND (Large Fire) ---
    "Huge fire at Sonipat Bus Stand! It's spreading fast!",
    "Help! I'm at the Bus Stand and there was a massive explosion in the gas line!",
    "There is a chemical smell at the Bus Stand fire, I think a tanker is leaking.",
    "Bus Stand is on fire! Please send ambulances and fire trucks!",
    
    # --- INCIDENT B: ATLAS CHOWK (Traffic Accident) ---
    "Car crash at Atlas Chowk, someone is injured.",
    "Major accident at Atlas Chowk, two cars collided.",
    "Please send police to Atlas Chowk, there is a big crowd around a crash.",
    
    # --- INCIDENT C: SECTOR 14 (Medical) ---
    "My neighbor collapsed at Sector 14, he isn't breathing!",
    
    # --- INCIDENT D: CITY MALL (Disturbance) ---
    "Group of people fighting at the City Mall entrance.",
]

def send_call(transcript):
    try:
        res = requests.post(API_URL, json={"transcript": transcript}, timeout=10)
        print(f"[SWARM] Sent: {transcript[:40]}... -> Status: {res.status_code}")
    except Exception as e:
        print(f"[ERROR] Failed to send: {e}")

def run_swarm():
    print("🚀 STARTING EMERGENCY SWARM SIMULATOR...")
    print(f"Sending {len(CALLS)} calls in a burst to {API_URL}\n")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(send_call, CALLS)
    
    print("\n✅ SWARM BURST COMPLETE.")
    print("Check your dashboard to see deduplication and priority dispatch in action!")

if __name__ == "__main__":
    run_swarm()
