import os
import sys
import glob
import json
import datetime
from dotenv import load_dotenv
from src.agents.llm import LLM

# Load environment variables
load_dotenv()

def evaluate_report(file_path):
    print(f"\n🧐 EVALUATING QUALITY: {file_path}")
    
    with open(file_path, "r") as f:
        content = f.read()

    # --- Judge Configuration ---
    # Check if specific Judge credentials are set in .env
    judge_api_key = os.getenv("JUDGE_LLM_API_KEY")
    judge_base_url = os.getenv("JUDGE_LLM_BASE_URL")
    judge_model = os.getenv("JUDGE_LLM_MODEL")

    if judge_api_key and not judge_api_key.startswith("AIza"):
        print(f"⚖️  Using Specialized Judge Model: {judge_model or 'Default'}")
        llm = LLM(api_key=judge_api_key, base_url=judge_base_url, model=judge_model)
    else:
        # Use a specific high-quality local model for judging if available
        judge_local_model = os.getenv("SMART_LLM_MODEL", os.getenv("JUDGE_LLM_MODEL", "command-r:latest"))
        print(f"⚖️  Using Local Judge Model: {judge_local_model}")
        llm = LLM(model=judge_local_model)
    
    if "living_meta_analysis" in file_path:
        print("🔹 Mode: Living Meta-Analysis Audit (Lighter Touch)")
        prompt = f"""
        You are a Knowledge Base Curator auditing a "Living Meta-Analysis".
        This document is a continuous stream of themes and findings accumulated over time.
        
        Your task is to provide a 'Health Check' on the document's structure and clarity.
        Do NOT be overly critical of methodology or specific paper details. Focus on the organization.
        
        ---
        DRAFT CONTENT:
        {content[:12000]}  # Truncate if too long (larger context for meta-analysis)
        ---
        
        RUBRIC:
        
        1. **Organization (1-5)**:
           - 1: Messy, random list of facts.
           - 5: Well-structured by distinct themes/headings.
           
        2. **Clarity (1-5)**:
           - 1: Confusing, jargon-heavy without explanation.
           - 5: Easy to read, clear summaries.
           
        3. **Integration (1-5)**:
           - 1: Feels like distinct, disjointed updates pasted together.
           - 5: Feels like a single, cohesive document.
        
        ---
        
        OUTPUT FORMAT (JSON ONLY):
        {{
            "scores": {{
                "organization": <int>,
                "clarity": <int>,
                "integration": <int>
            }},
            "hallucination_warning": false,
            "critique": "A brief 1-sentence observation on the document's state."
        }}
        """
    else:
        print("🔹 Mode: Special Issue Critique (Rigorous)")
        prompt = f"""
        You are a Senior Academic Editor evaluating a draft "Special Issue Editorial" written by a junior editor.
        
        Your task is to Grade this draft based on the following strict rubric. 
        
        ---
        DRAFT CONTENT:
        {content[:12000]}  # Truncate if too long
        ---
        
        RUBRIC:
        
        1. **Synthesis (1-5)**: 
           - 1: Just lists summaries of papers one by one.
           - 3: Groups papers by theme but lacks deep connection.
           - 5: True synthesis. Identifies patterns, contrasts findings (e.g., "While X found A, Y found B"), and builds a cohesive narrative.
           
        2. **Criticality (1-5)**:
           - 1: Uncritically accepts all findings. Positive vibes only.
           - 3: Mentions generic limitations (e.g., "sample size").
           - 5: Identifies specific methodological nuance, contradictions between papers, or specific gaps in the evidence base.
           
        3. **Editorial Voice (1-5)**:
           - 1: Robotic, repetitive, or casual.
           - 5: Authoritative, academic, precise, and visionary.
           
        4. **Hallucination Check (Pass/Fail)**:
           - Does the text refer to papers NOT listed in the "In This Issue" or "Cited Works" sections? (Subjective check).
        
        ---
        
        OUTPUT FORMAT (JSON ONLY):
        {{
            "scores": {{
                "synthesis": <int>,
                "criticality": <int>,
                "voice": <int>
            }},
            "hallucination_warning": <bool>,
            "critique": "A brief 2-sentence qualitative critique of the writing."
        }}
        """
    
    try:
        response = llm.generate(prompt, system_message="You are a critical, fair academic evaluator.", temperature=0.0)
        
        # Clean up JSON if LLM adds markdown formatting
        clean_json = response.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean_json)
        
        scores = result["scores"]
        print(f"\n📊 QUALITY REPORT CARD")
        print(f"------------------------------------------------")
        if "synthesis" in scores:
            print(f"🔹 Synthesis Score:   {scores['synthesis']}/5")
            print(f"🔹 Criticality Score: {scores['criticality']}/5")
            print(f"🔹 Editorial Voice:   {scores['voice']}/5")
        else:
            print(f"🔹 Organization:      {scores.get('organization', 0)}/5")
            print(f"🔹 Clarity:           {scores.get('clarity', 0)}/5")
            print(f"🔹 Integration:       {scores.get('integration', 0)}/5")
        print(f"------------------------------------------------")
        print(f"⚠️  Hallucination Risk: {'HIGH' if result['hallucination_warning'] else 'Low'}")
        print(f"\n📝 Feedback:\n\"{result['critique']}\" ")
        print(f"------------------------------------------------")

        # --- SAVE FEEDBACK FOR AGENTS ---
        feedback_entry = {
            "date": datetime.datetime.now().isoformat(),
            "target_file": file_path,
            "scores": scores,
            "critique": result["critique"],
            "hallucination_warning": result["hallucination_warning"]
        }
        
        history_file = "feedback_history.json"
        history = []
        if os.path.exists(history_file):
            try:
                with open(history_file, "r") as f:
                    history = json.load(f)
            except:
                history = []
        
        history.append(feedback_entry)
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)
        print(f"✅ Feedback saved to {history_file}")

        # --- SHOW TREND ANALYSIS (BAKED-IN TRACKING) ---
        if len(history) > 1 and "criticality" in scores:
            prev_entry = history[-2]
            # Ensure previous entry was also a special issue (has criticality)
            if "criticality" in prev_entry.get("scores", {}):
                prev_crit = prev_entry["scores"].get("criticality", 0)
                curr_crit = scores.get("criticality", 0)
                diff = curr_crit - prev_crit
                
                trend_icon = "➡️"
                if diff > 0: trend_icon = "↗️ IMPROVED"
                elif diff < 0: trend_icon = "↘️ REGRESSED"
                
                print(f"\n📈 LEARNING TRAJECTORY")
                print(f"   Criticality: {prev_crit} -> {curr_crit} ({trend_icon})")
                if diff > 0:
                    print(f"   (The system successfully adapted to previous feedback!)")
        
    except Exception as e:
        print(f"Evaluation failed: {e}")
        print("Raw Response:", response)

if __name__ == "__main__":
    # Default to checking the most recent special issue
    files = glob.glob("special_issue_*.md")
    files.sort(key=os.path.getmtime, reverse=True)
    
    if files:
        target = files[0]
        if len(sys.argv) > 1:
            target = sys.argv[1]
        evaluate_report(target)
    else:
        print("No special issue files found.")
