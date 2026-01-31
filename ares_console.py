import sys
import os
import re
from src.database.connection import Database

# Re-using logic from human_audit_comparator but wrapped in a nice console
LIVING_META_PATH = "living_meta_analysis.md"

def find_citation_context(text, author_pattern, window=600):
    """Finds the paragraph surrounding a citation."""
    regex = re.compile(rf"({author_pattern}.*?\))", re.IGNORECASE)
    for m in regex.finditer(text):
        start = max(0, m.start() - window)
        end = min(len(text), m.end() + window)
        return text[start:end].strip()
    return None

def run_audit_session():
    print("\n⚖️  ARES HEAD-TO-HEAD AUDITOR")
    print("--------------------------------")
    print("Compare: [A] Living Meta-Analysis vs. [B] Special Issue Critique")
    
    # 1. Ask user for target
    target_author = input("\nEnter Target Author (e.g. Jiang): ").strip()
    target_kw = input("Enter Topic Keyword (e.g. Echocardiography): ").strip()
    
    if not target_author: return

    # 2. Connect DB
    print("\n🔌 Connecting to Database...")
    db = Database()
    
    # 3. Find Source
    papers = db.fetch_papers(keywords=[target_kw], limit=10)
    source_paper = None
    for p in papers:
        authors = str(p.get('authors', '')).lower()
        if target_author.lower() in authors:
            source_paper = p
            break
            
    if not source_paper:
        print(f"❌ Could not find paper by '{target_author}' with keyword '{target_kw}' in DB.")
        return

    print(f"\n📄 SOURCE FOUND: {source_paper['title']}")
    print(f"   Abstract: {source_paper['abstract'][:300]}...\n")

    # 4. Agent A (Compiler)
    print("🔍 Scanning Agent A (Living Meta-Analysis)...")
    with open(LIVING_META_PATH, "r") as f:
        meta_text = f.read()
    
    # Try to find specific context
    meta_take = None
    match = re.search(rf"({target_author}.*?{target_kw}.*?)(\n\n|\Z)", meta_text, re.DOTALL | re.IGNORECASE)
    if match:
        meta_take = match.group(1)
    else:
        meta_take = find_citation_context(meta_text, target_author)

    # 5. Agent B (Meta-Reviewer)
    print("🔍 Scanning Agent B (Special Issues)...")
    import glob
    files = glob.glob("special_issue_*.md")
    files.sort(key=os.path.getmtime, reverse=True)
    
    special_take = None
    special_file = ""
    
    for fpath in files:
        with open(fpath, "r") as f:
            content = f.read()
            # Match Author AND Keyword to ensure it's the right paper
            if target_author in content and target_kw in content:
                # Extract the paragraph
                match = re.search(rf"(\*\*\({target_author}.*?\)\*\*.*?)( \n\n)", content, re.DOTALL)
                if match:
                    special_take = match.group(1)
                else:
                    special_take = find_citation_context(content, target_author)
                special_file = fpath
                break
    
    # 6. Display Comparison
    print("\n" + "="*60)
    print(f"🥊 HEAD-TO-HEAD: {source_paper['title']}")
    print("="*60)
    
    print("\n--- AGENT A (The Compiler) ---")
    if meta_take:
        print(f"...{meta_take}...")
    else:
        print("❌ FAILED TO SYNTHESIZE (Only listed in bibliography or missed).")

    print("\n--- AGENT B (The Critic) ---")
    if special_take:
        print(f"Source: {special_file}")
        print(f"...{special_take}...")
    else:
        print("❌ NO CRITIQUE FOUND.")

    print("\n" + "="*60)
    
    # 7. Record Vote
    vote = input("🏆 Winner? (A/B): ").upper()
    comment = input("📝 Reason: ")
    
    # Save log
    with open("human_audit_log.csv", "a") as log:
        log.write(f"{target_author},{vote},{comment}\n")
    print("✅ Vote Saved.")

if __name__ == "__main__":
    while True:
        run_audit_session()
        if input("\nAudit another? (y/n): ").lower() != 'y':
            break
