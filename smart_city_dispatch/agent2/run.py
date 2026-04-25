"""
Run Agent 2 — Dispatcher Service

Entry point for starting the monitor and exposing the trigger function.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from smart_city_dispatch.agent2.monitor import start_monitor
from smart_city_dispatch.agent2.dispatch_agent import run_dispatch_agent

def trigger_dispatch():
    """Trigger a manual dispatch cycle."""
    return run_dispatch_agent()

if __name__ == "__main__":
    print("🏙️  Agent 2 Online. Starting monitor loop...")
    start_monitor()
