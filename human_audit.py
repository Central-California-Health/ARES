import json
import os
import random
import sys

FEEDBACK_FILE = "feedback_history.json"
AUDIT_LOG = "human_audit_results.json"

def load_data():
    if not os.path.exists(FEEDBACK_FILE):
        print(f"Error: {FEEDBACK_FILE} not found.")
        return []
    with open(FEEDBACK_FILE, "r") as f:
        return json.load(f)

def load_file_content(filepath, limit=2000):
    """Reads the first N chars of the file to give context."""
    if not os.path.exists(filepath):
        return "[File not found]"
    with open(filepath, "r") as f:
        return f.read(limit) + "\n...[truncated]..."

def run_audit():
    history = load_data()
    
    # Filter for "Special Issues" (High value targets) that haven't been audited
    candidates = [h for h in history if "special_issue" in h.get("target_file", "") and h.get("scores", {{}}).get("criticality", 0) >= 4]
    
    # Shuffle to reduce order bias
    random.shuffle(candidates)
    
    print(f"\n🕵️  ARES HUMAN AUDIT TOOL")
    print(f"Found {len(candidates)} high-criticality claims to verify.")
    print("---------------------------------------------------")
    
    results = []
    if os.path.exists(AUDIT_LOG):
        with open(AUDIT_LOG, "r") as f:
            results = json.load(f)

    for i, entry in enumerate(candidates[:5]):  # Do 5 at a time
        filepath = entry['target_file']
        score = entry['scores']['criticality']
        critique = entry['critique']
        
        print(f"\n[{i+1}/5] AUDITING: {filepath}")
        print(f"🤖 AI Criticality Score: {score}/5")
        print(f"🗣  AI Critique: \"{critique}\"")
        
        # Show a snippet of the file to see the actual text
        print("\n--- EXTRACT FROM AGENT'S WORK ---")
        content = load_file_content(filepath)
        # Try to find the "Limitations" or "Critical Analysis" section
        if "Critical Analysis" in content:
            start = content.find("Critical Analysis")
            print(content[start:start+1000])
        else:
            print(content[:1000])
        print("-----------------------------------")
        
        choice = input("\nIs the AI's critique valid? (y/n/skip): ").lower().strip()
        
        if choice == 'y':
            comment = input("Optional comment (Why is it valid?): ")
            results.append({
                "file": filepath,
                "ai_score": score,
                "human_verdict": "valid",
                "comment": comment,
                "timestamp": entry["date"]
            })
            print("✅ Marked as VALID.")
        elif choice == 'n':
            comment = input("Why is it invalid? ")
            results.append({
                "file": filepath,
                "ai_score": score,
                "human_verdict": "invalid",
                "comment": comment,
                "timestamp": entry["date"]
            })
            print("❌ Marked as INVALID.")
        else:
            print("⏭  Skipped.")

    # Save results
    with open(AUDIT_LOG, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Audit saved to {AUDIT_LOG}. You have verified {len(results)} items total.")

if __name__ == "__main__":
    run_audit()
