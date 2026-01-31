import os
import sys
import psycopg2
import datetime
from dotenv import load_dotenv

# Add project root to path to import snapshot
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    from snapshot import save_snapshot
except ImportError:
    save_snapshot = None
    print("Warning: Could not import snapshot.py. Auto-archiving disabled.")

load_dotenv()

def reset_db():
    # 1. Archive current state before deletion
    if save_snapshot:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"pre_reset_{timestamp}"
        print(f"Archiving current state to experiments/{archive_name}...")
        save_snapshot(archive_name)

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "research_contents"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "password"),
        port=os.getenv("DB_PORT", "5432")
    )
    cur = conn.cursor()
    
    tables = ["agent_insights", "agent_reports", "agent_memories"]
    for table in tables:
        try:
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
            print(f"Dropped table {table}")
        except Exception as e:
            print(f"Error dropping {table}: {e}")
            
    conn.commit()
    conn.close()
    print("Database tables reset successfully.")

    # Also clear the JSON storage files to ensure a clean slate
    json_files = [
        "living_knowledge_graph.json",
        "living_protocols.json",
        "feedback_history.json",
        "claims_matrix.json",
        "bibliography.json",
        "simulation_state.json"
    ]
    
    print("Clearing JSON storage files...")
    for json_file in json_files:
        if os.path.exists(json_file):
            try:
                os.remove(json_file)
                print(f"Removed {json_file}")
            except Exception as e:
                print(f"Error removing {json_file}: {e}")
        else:
            print(f"{json_file} not found (skipping).")

if __name__ == "__main__":
    reset_db()
