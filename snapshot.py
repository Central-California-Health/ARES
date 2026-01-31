import os
import shutil
import sys
import datetime
import glob

EXPERIMENTS_DIR = "experiments"
FILES_TO_BACKUP = [
    "feedback_history.json",
    "simulation_state.json",
    "living_meta_analysis.md",
    "output_log.txt",
    "living_knowledge_graph.json",
    "living_protocols.json",
    "human_audit_log.csv",
    "claims_matrix.json",
    "bibliography.json",
    "living_investigation_log.md",
    "living_logic_manifesto.md",
    "living_logic_history.md",
    "living_discussions.json",
    "claims_matrix_verified.json"
]

def save_snapshot(tag_name=None):
    """
    Creates a snapshot of the current system state.
    """
    if not tag_name:
        # Default to timestamp if no name provided
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        tag_name = f"snapshot_{timestamp}"
    
    # Create the target directory
    target_dir = os.path.join(EXPERIMENTS_DIR, tag_name)
    if os.path.exists(target_dir):
        print(f"Error: Snapshot '{tag_name}' already exists.")
        return

    os.makedirs(target_dir)
    print(f"Creating snapshot: {target_dir}")

    # 1. Backup specific configuration/state files
    for filename in FILES_TO_BACKUP:
        if os.path.exists(filename):
            shutil.copy2(filename, target_dir)
            print(f"  - Archived: {filename}")
        else:
            print(f"  - Warning: {filename} not found (skipping)")

    # 2. Backup all Special Issues (Markdown files starting with 'special_issue_')
    special_issues = glob.glob("special_issue_*.md")
    if special_issues:
        print(f"  - Archiving {len(special_issues)} Special Issue files...")
        for si in special_issues:
            shutil.copy2(si, target_dir)
    
    # 3. Backup Investigation Reports
    reports = glob.glob("investigation_report_*.md")
    if reports:
        print(f"  - Archiving {len(reports)} Investigation Reports...")
        for report in reports:
            shutil.copy2(report, target_dir)

    print(f"\nSnapshot '{tag_name}' saved successfully.")

def reset_workspace(tag_name=None):
    """
    Archives the current state and then deletes the files to reset the workspace.
    """
    print("\n[RESET] Starting Workspace Reset...")
    
    # 1. Archive First
    save_snapshot(tag_name)
    
    print("[RESET] Deleting files from workspace...")
    
    # 2. Delete static files
    for filename in FILES_TO_BACKUP:
        if os.path.exists(filename):
            try:
                os.remove(filename)
                if os.path.exists(filename):
                     print(f"  - WARNING: Failed to delete {filename} (File still exists)")
                else:
                     print(f"  - Deleted: {filename}")
            except Exception as e:
                print(f"  - Error deleting {filename}: {e}")

    # 3. Delete Special Issues
    special_issues = glob.glob("special_issue_*.md")
    for si in special_issues:
        try:
            os.remove(si)
            print(f"  - Deleted: {si}")
        except Exception as e:
            print(f"  - Error deleting {si}: {e}")

    # 4. Delete Investigation Reports
    reports = glob.glob("investigation_report_*.md")
    for report in reports:
        try:
            os.remove(report)
            print(f"  - Deleted: {report}")
        except Exception as e:
            print(f"  - Error deleting {report}: {e}")

    print("[RESET] Workspace reset complete.")

def list_snapshots():
    """Lists all existing snapshots."""
    if not os.path.exists(EXPERIMENTS_DIR):
        print("No experiments directory found.")
        return
    
    snapshots = sorted(os.listdir(EXPERIMENTS_DIR))
    print(f"Found {len(snapshots)} snapshots:")
    for snap in snapshots:
        print(f"  - {snap}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python snapshot.py [save <name> | list]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "save":
        name = sys.argv[2] if len(sys.argv) > 2 else None
        save_snapshot(name)
    elif command == "list":
        list_snapshots()
    else:
        print(f"Unknown command: {command}")
