import sys
import os
import json

# Ensure we can import from src
sys.path.append(os.getcwd())

from src.agents.matrix import DrMatrix

def test_matrix_flow():
    print("🧪 Starting Dr. Matrix Data Flow Test...")
    
    # 1. Mock Data that mimics EXACTLY what Researcher._run_advanced_analysis produces
    mock_paper = {
        "title": "Effect of Sodium Reduction on Hypertension in Elderly Patients",
        "authors": ["Smith", "Doe", "Johnson"],
        "published_at": "2025-05-12",
        "abstract": "We conducted a randomized controlled trial to see if sodium reduction helps.",
    }
    
    citation_key = "Smith et al. (2025)"
    authors_str = "Smith, Doe, Johnson"
    pub_date = "2025"
    summary = "The study shows reducing sodium lowers BP."
    sections_text = "\n\n### METHODS\nWe recruited 500 patients (N=500). Randomized them to Low Sodium vs Normal Sodium.\n\n### RESULTS\nBP dropped by 5mmHg."
    
    # CORRECT FORMAT matching Researcher.py
    input_text = f"""
### STUDY IDENTIFICATION ###
Title: {mock_paper['title']}
Citation: {citation_key}
Authors: {authors_str}
Date: {pub_date}
###########################

Abstract: {mock_paper['abstract']}
Summary: {summary}
{sections_text}
"""
    
    print("\n📝 MOCK INPUT TEXT:")
    print("-" * 20)
    print(input_text)
    print("-" * 20)
    
    matrix = DrMatrix()
    
    # TEST CASE 1: Happy Path
    print("\n🕵️  Test 1: Happy Path Extraction...")
    try:
        json_output = matrix.extract_claims(input_text)
        print("\n✅ OUTPUT JSON:")
        print(json_output)
        
        data = json.loads(json_output)
        if len(data) > 0:
            item = data[0]
            if item.get("study_title") == mock_paper["title"]:
                print("🎉 SUCCESS: Title matched perfectly.")
            else:
                print("⚠️  WARNING: Mismatch in extracted metadata.")
        else:
            print("❌ FAILURE: Empty JSON returned.")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

    # TEST CASE 2: Forced Refinement (System 2)
    # We manually invoke internal methods to force a mismatch scenario
    print("\n🕵️  Test 2: Forced Refinement (Unhappy Path)...")
    
    bad_draft = [{
        "study_citation": "Wrong Citation",
        "study_title": "The WRONG Title",
        "sample_size": "N=0",
        "variables": {"independent": "?", "dependent": "?"},
        "epistemic_check": {"gap_severity": "Low"}
    }]
    bad_draft_json = json.dumps(bad_draft)
    
    print("   > Invoking Audit on BAD draft...")
    critique = matrix._audit_draft(bad_draft_json, input_text)
    print(f"   > Critique: {critique}")
    
    if "PASS" not in critique:
        print("   > Audit correctly failed. Testing Refinement with Context...")
        try:
            # THIS CALL will fail if my fix is not applied (missing text_chunk arg)
            refined_json = matrix._refine_draft(bad_draft_json, critique, input_text)
            print(f"   > Refined JSON: {refined_json}")
            
            refined_data = json.loads(refined_json)
            if refined_data[0].get("study_title") == mock_paper["title"]:
                print("🎉 SUCCESS: Refinement loop fixed the title using context.")
            else:
                print("❌ FAILURE: Refinement loop failed to fix the title.")
        except TypeError as e:
             print(f"❌ FAILURE: Signature Mismatch (Fix not applied?): {e}")
        except Exception as e:
             print(f"❌ FAILURE: Refinement Error: {e}")
    # TEST CASE 3: Very Long Input (Testing Truncation Fix)
    print("\n🕵️  Test 3: Very Long Input (Testing Truncation Fix)...")
    long_filler = "This is some filler text to bloat the input. " * 3000 # ~120k characters
    long_input_text = f"""
### STUDY IDENTIFICATION ###
Title: {mock_paper['title']}
Citation: {citation_key}
Authors: {authors_str}
Date: {pub_date}
###########################

Abstract: {mock_paper['abstract']}
Summary: {summary}
{sections_text}

{long_filler}
"""
    try:
        json_output = matrix.extract_claims(long_input_text)
        print("\n✅ OUTPUT JSON (Long Input):")
        print(json_output)
        
        data = json.loads(json_output)
        if len(data) > 0:
            if data[0].get("study_title") == mock_paper["title"]:
                print("🎉 SUCCESS: Title matched even with 120k+ chars of filler at the end.")
            else:
                 # If it failed, check if it's because of the FAIL message
                print(f"⚠️  WARNING: Mismatch or FAIL message returned: {json_output[:100]}")
        else:
            print("❌ FAILURE: Empty JSON returned.")
    except Exception as e:
        print(f"❌ ERROR in Test 3: {e}")

if __name__ == "__main__":
    test_matrix_flow()