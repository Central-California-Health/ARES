import json
import os
import sys
import datetime
from typing import Dict, Any

# Add project root to path to import snapshot
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    from snapshot import save_snapshot, reset_workspace
except ImportError:
    save_snapshot = None
    reset_workspace = None
    print("Warning: Could not import snapshot.py. Auto-archiving disabled.")

class StateManager:
    def __init__(self, filename: str = "simulation_state.json"):
        self.filename = filename

    def save_state(self, offset: int, current_time: datetime.datetime, agent_names: list):
        state = {
            "offset": offset,
            "current_time": current_time.isoformat(),
            "agents": agent_names,
            "last_updated": datetime.datetime.now().isoformat()
        }
        with open(self.filename, "w") as f:
            json.dump(state, f, indent=4)
        print(f"Simulation state saved to {self.filename} (Offset: {offset})")

    def load_state(self) -> Dict[str, Any]:
        if not os.path.exists(self.filename):
            return None
        
        try:
            with open(self.filename, "r") as f:
                state = json.load(f)
            
            # Parse time back to datetime object
            state["current_time"] = datetime.datetime.fromisoformat(state["current_time"])
            return state
        except Exception as e:
            print(f"Error loading state: {e}")
            return None

    def clear_state(self):
        # Use centralized reset if available
        if reset_workspace:
            print("Using snapshot.reset_workspace to clear state...")
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"pre_reset_{timestamp}"
            reset_workspace(archive_name)
            return

        print("Snapshot module not available. Using fallback manual clearing...")
        # Fallback manual clearing (if snapshot module failed to load)
        if os.path.exists(self.filename):
            try:
                os.remove(self.filename)
                print("Previous simulation state cleared.")
            except Exception as e:
                print(f"Error removing {self.filename}: {e}")
        
        # Also clear other living JSON files for a fresh start
        files_to_clear = [
            "living_knowledge_graph.json",
            "living_protocols.json",
            "feedback_history.json",
            "claims_matrix.json",
            "bibliography.json",
            "living_meta_analysis.md",
            "output_log.txt",
            "living_investigation_log.md"
        ]
        
        for f in files_to_clear:
            if os.path.exists(f):
                try:
                    os.remove(f)
                    print(f"Removed {f}")
                except Exception as e:
                    print(f"Error removing {f}: {e}")
