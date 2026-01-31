import json
import os
import re
from dotenv import load_dotenv
from src.database.connection import Database

# Load env for DB creds
load_dotenv()

LIVING_META_PATH = "living_meta_analysis.md"
SPECIAL_ISSUE_GLOB = "special_issue_*.md"

def find_citation_context(text, author_pattern, window=500):
    """Finds the paragraph surrounding a citation."""
    matches = []
    # Regex for (Author et al., Year) or just Author et al.
    regex = re.compile(rf"({author_pattern}.*?\))", re.IGNORECASE)
    
    for m in regex.finditer(text):
        start = max(0, m.start() - window)
        end = min(len(text), m.end() + window)
        snippet = text[start:end]
        # Clean up snippet to nearest newline if possible
        matches.append(snippet.strip())
    
    if not matches:
        return None
    return matches[0]  # Return the first match

def run_comparator():
    print("🔌 Connecting to Database...")
    db = Database()
    
    # 1. Define the Target (Precise Title Match)
    target_author = "Jiang"
    target_year = "2025"
    target_title_fragment = "Effect of echocardiography on prognosis"
    
    print(f"\n🎯 TARGETING: {target_author} ({target_year}) - '{target_title_fragment}'")
    
    # 2. Get Raw Source from DB
    print("   Querying DB for raw paper...")
    # Search specifically for the title fragment
    papers = db.fetch_papers(keywords=[target_title_fragment], limit=5)
    
    source_paper = None
    for p in papers:
        authors = str(p.get('authors', '')).lower()
        if target_author.lower() in authors:
            source_paper = p
            break
            
    if not source_paper:
        print("❌ Paper not found in DB.")
        return

    print(f"\n📄 FOUND SOURCE PAPER (ID: {source_paper['id']})")
    print(f"   Title: {source_paper['title']}")
    print(f"   Authors: {source_paper['authors']}")
    print(f"   Abstract: {source_paper['abstract'][:300]}...\n")
    
    # 3. Get "Living Meta-Analysis" Take
    print("🔍 Searching Living Meta-Analysis...")
    with open(LIVING_META_PATH, "r") as f:
        meta_text = f.read()
    
    # We search for the specific paper snippet in the meta-analysis
    meta_match = re.search(r"(Jiang.*?2025.*?Echocardiography.*?)(\n\n|\Z)", meta_text, re.DOTALL | re.IGNORECASE)
    if meta_match:
        meta_take = meta_match.group(1)
    else:
        # Fallback: finding close proximity
        meta_take = find_citation_context(meta_text, "Jiang", window=600)

    # 4. Get "Special Issue" Take
    # Explicitly target the correct file where we saw the valid critique
    target_file = "special_issue_advancing_precision_in_hypertension__from_pathophysiology_to_personalized_management_and_outcomes_20260122_1858.md"
    
    print(f"🔍 Reading Specific Special Issue: {target_file}")
    special_take = None
    special_file = target_file
    
    if os.path.exists(target_file):
        with open(target_file, "r") as f:
            content = f.read()
            # Find the Critical Analysis section mentioning the paper
            # We look for the bolded citation
            match = re.search(r"Consider \*\*Jiang et al\. \(2025\)\*\*.*?(?=\n\n)", content, re.DOTALL)
            if match:
                special_take = match.group(0)
            else:
                special_take = find_citation_context(content, target_author)
    else:
         print(f"❌ Target file not found: {target_file}")
    
    # 5. The Head-to-Head
    print("\n" + "="*60)
    print("🥊 HEAD-TO-HEAD COMPARISON")
    print("="*60)
    
    print(f"\n--- SOURCE (The Truth) ---\nTitle: {source_paper['title']}\nAbstract: {source_paper['abstract'][:400]}...")
    
    print("\n--- AGENT A: Living Meta-Analysis (The Summarizer) ---")
    if meta_take:
        print(f"...{meta_take}...")
    else:
        print("(No specific mention found)")
        
    print("\n--- AGENT B: The Investigator (The Critic) ---")
    if special_take:
        print(f"Source File: {special_file}")
        print(f"...{special_take}...")
    else:
        print("(No critical mention found)")
        
    print("\n" + "="*60)
    print("🗳  YOUR VOTE")
    vote = input("Who analyzed it better? (A/B/Tie): ").lower()
    
    if vote:
        print("✅ Vote recorded.")
        # Logic to save vote would go here

if __name__ == "__main__":
    run_comparator()
