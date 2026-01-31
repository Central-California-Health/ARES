import json
import datetime
from collections import defaultdict
import statistics

def parse_history(filepath):
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    # Sort by date
    data.sort(key=lambda x: x['date'])
    
    # Buckets
    meta_analysis_scores = []
    special_issue_scores = []
    
    for entry in data:
        dt = datetime.datetime.fromisoformat(entry['date'])
        target = entry['target_file']
        
        # Normalize scores (handle different rubric versions if any)
        # We see 'criticality' in some, 'organization' in others (which are older or different logic).
        # The manuscript focuses on 'criticality'.
        scores = entry.get('scores', {})
        
        # If 'criticality' is missing, it might be the 'Organization/Clarity' rubric. 
        # We will track Criticality/Synthesis specifically for the paper's argument.
        if 'criticality' in scores:
            crit = scores['criticality']
            synth = scores['synthesis']
            
            record = {
                'date': dt,
                'criticality': crit,
                'synthesis': synth,
                'file': target
            }
            
            if "living_meta_analysis" in target:
                meta_analysis_scores.append(record)
            else:
                special_issue_scores.append(record)

    return meta_analysis_scores, special_issue_scores

def print_stats(name, records):
    if not records:
        print(f"--- {name}: No Data ---")
        return

    print(f"--- {name} (N={len(records)}) ---")
    
    # Group by Date (Day)
    by_day = defaultdict(list)
    for r in records:
        day_str = r['date'].strftime("%Y-%m-%d")
        by_day[day_str].append(r['criticality'])
    
    print(f"{ 'Date':<12} | {'Avg Criticality':<15} | {'Min':<5} | {'Max':<5} | {'Count':<5}")
    print("-" * 55)
    
    for day, scores in sorted(by_day.items()):
        avg = statistics.mean(scores)
        print(f"{day:<12} | {avg:<15.2f} | {min(scores):<5} | {max(scores):<5} | {len(scores):<5}")
    print("\n")

if __name__ == "__main__":
    ma, si = parse_history("feedback_history.json")
    print("ANALYSIS OF CRITICALITY SCORES\n")
    print_stats("Living Meta-Analysis Updates", ma)
    print_stats("Special Issue Publications", si)
