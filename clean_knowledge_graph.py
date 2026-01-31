import json

def clean_knowledge_graph(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)

    corrections = 0
    for entry in data:
        check = entry.get("epistemic_check", {})
        claim = check.get("title_claim_type", "").lower()
        design = check.get("study_design_type", "").lower()
        current_severity = check.get("gap_severity", "")

        new_severity = current_severity

        # Rule 1: Associative + Observational = LOW
        if "associat" in claim and "observational" in design:
            new_severity = "Low"
        
        # Rule 2: Causal + Observational = HIGH
        elif "causal" in claim and "observational" in design:
            new_severity = "High"

        # Rule 3: RCT = LOW (generally)
        elif "rct" in design or "random" in design:
            new_severity = "Low"
        
        # Update if changed (case-insensitive check)
        if new_severity.lower() != current_severity.lower():
            print(f"Fixing {entry.get('study_citation')}: {current_severity} -> {new_severity}")
            check["gap_severity"] = new_severity
            corrections += 1

    if corrections > 0:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ Successfully corrected {corrections} entries in {file_path}")
    else:
        print("✅ No errors found in knowledge graph.")

if __name__ == "__main__":
    clean_knowledge_graph("living_knowledge_graph.json")