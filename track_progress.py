import json
import os
import datetime

def main():
    history_file = "feedback_history.json"
    
    if not os.path.exists(history_file):
        print("No feedback history found. Run 'publish_special_issue.py' first.")
        return

    try:
        with open(history_file, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading history: {e}")
        return

    print("\n📈 SYSTEM LEARNING TRAJECTORY")
    print("==================================================================================")
    print(f"{ 'Run':<4} | {'Date':<16} | {'Crit':<4} | {'Synth':<5} | {'Voice':<5} | {'Editor Feedback (Snippet)'}")
    print("----------------------------------------------------------------------------------")

    # Sort by date just in case
    data.sort(key=lambda x: x['date'])

    for i, entry in enumerate(data):
        date_str = entry['date'].split('T')[0]
        scores = entry.get('scores', {})
        
        crit = scores.get('criticality', 0)
        synth = scores.get('synthesis', 0)
        voice = scores.get('voice', 0)
        
        # Truncate feedback for display
        feedback = entry.get('critique', "")
        if len(feedback) > 50:
            feedback = feedback[:47] + "..."
            
        print(f"{i+1:<4} | {date_str:<16} | {crit:<4} | {synth:<5} | {voice:<5} | {feedback}")

    print("==================================================================================")
    
    # Calculate Improvement
    if len(data) > 1:
        first = data[0]['scores'].get('criticality', 0)
        last = data[-1]['scores'].get('criticality', 0)
        diff = last - first
        trend = "IMPROVED" if diff > 0 else "STAGNANT" if diff == 0 else "REGRESSED"
        print(f"\n📊 TREND ANALYSIS: Criticality has {trend} by {abs(diff)} points.")
        if trend == "IMPROVED":
            print("   (Proof of Recursive Learning!)")

if __name__ == "__main__":
    main()
