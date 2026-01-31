import re
import json
import sys
import glob
from difflib import SequenceMatcher
import os

def load_bibliography(path="bibliography.json"):
    with open(path, "r") as f:
        data = json.load(f)
        if isinstance(data, list):
            # Convert list of objects to dict for internal audit logic
            return {item['citation']: item['reference'] for item in data if 'citation' in item and 'reference' in item}
        return data

def normalize_title(title):
    """Normalize title for softer matching (ignore case/punctuation)."""
    return re.sub(r'[^a-zA-Z0-9]', '', title).lower()

def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def audit_special_issue(file_path, bibliography):
    print(f"\n🔍 AUDITING: {file_path}")
    
    with open(file_path, "r") as f:
        content = f.read()

    # --- 1. Audit "In This Issue" List (Title Integrity) ---
    print(f"\n--- Checking 'In This Issue' Titles ---")
    
    # Regex to find lines like: * **Author et al. (Year)**, "Title"
    list_pattern = r'\*\s*\*\*(.*?)\*\*[, s]*"(.*?)"'
    listed_papers = re.findall(list_pattern, content)
    
    total_listed = len(listed_papers)
    perfect_matches = 0
    fuzzy_matches = 0
    hallucinations = 0
    
    # Create a set of all real titles from DB for checking
    # The DB values are citations strings, we need to extract titles roughly
    # Standard format: Author (Year). Title. Journal...
    # We will try to match the quoted title against the full DB string
    
    for author_key, quoted_title in listed_papers:
        is_found = False
        
        # Check against all DB entries
        for db_key, db_entry in bibliography.items():
            # Check if the Quoted Title appears inside the DB Entry
            # We ignore case and minor spacing
            if normalize_title(quoted_title) in normalize_title(db_entry):
                perfect_matches += 1
                is_found = True
                break
        
        if not is_found:
            # Fallback: Check for high similarity (Typo detection)
            best_sim = 0
            for db_key, db_entry in bibliography.items():
                sim = similarity(normalize_title(quoted_title), normalize_title(db_entry))
                if sim > best_sim:
                    best_sim = sim
            
            if best_sim > 0.85:
                print(f"⚠️  Fuzzy Match ({int(best_sim*100)}%): '{quoted_title}'")
                fuzzy_matches += 1
            else:
                print(f"❌ HALLUCINATION DETECTED: '{quoted_title}'")
                hallucinations += 1

    # --- 2. Audit Inline Citations (Citation Validity) ---
    print(f"\n--- Checking Inline Citations ---")
    
    # Regex for (Author et al., Year)
    citation_pattern = r'\([a-zA-Z\s\-]+et al\., \d{4}[a-z]?\)'
    found_citations = re.findall(citation_pattern, content)
    
    valid_citations = 0
    invalid_citations = 0
    
    for cit in found_citations:
        # DB Keys are usually "(Author et al., Year)"
        if cit in bibliography:
            valid_citations += 1
        else:
            # Check for simple year mismatches or "et al" formatting
            print(f"❌ Invalid Citation Key: {cit}")
            invalid_citations += 1

    # --- Report Card ---
    print(f"\n📊 REPORT CARD")
    print(f"------------------------------------------------")
    print(f"Titles Audited:      {total_listed}")
    print(f"  ✅ Exact Matches:  {perfect_matches}")
    print(f"  ⚠️  Fuzzy Matches:  {fuzzy_matches}")
    print(f"  ❌ Hallucinations: {hallucinations}")
    
    if total_listed > 0:
        hallucination_rate = (hallucinations / total_listed) * 100
        print(f"  ➤ Title Accuracy:  {100 - hallucination_rate:.1f}%")
    
    print(f"\nCitations Audited:   {len(found_citations)}")
    print(f"  ✅ Valid Keys:     {valid_citations}")
    print(f"  ❌ Invalid Keys:   {invalid_citations}")
    
    if len(found_citations) > 0:
        citation_score = (valid_citations / len(found_citations)) * 100
        print(f"  ➤ Citation Score:  {citation_score:.1f}%")
    print(f"------------------------------------------------")

if __name__ == "__main__":
    bib = load_bibliography()
    
    # Default to checking the most recent special issue
    files = glob.glob("special_issue_*.md")
    files.sort(key=os.path.getmtime, reverse=True)
    
    if files:
        target = files[0]
        if len(sys.argv) > 1:
            target = sys.argv[1]
        audit_special_issue(target, bib)
    else:
        print("No special issue files found.")
