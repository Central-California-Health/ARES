import json
import glob
import os
import re
from .llm import LLM

class DrMatrix:
    def __init__(self):
        self.llm = LLM()

    def extract_claims(self, text_chunk):
        """
        Orchestrates the System 2 Cognitive Architecture:
        1. Draft (System 1): Fast extraction.
        2. Audit (System 2): Slow, rigorous check for logic errors.
        3. Refine (Correction): Fixes if necessary.
        """
        # Step 1: Generate Draft
        draft_json = self._generate_draft(text_chunk)
        
        # Step 2: Audit Draft
        critique = self._audit_draft(draft_json, text_chunk)
        
        if "PASS" in critique:
            return self._enforce_deterministic_logic(draft_json)
        else:
            print(f"⚠️ Dr. Matrix System 2 triggered! Refining draft based on critique: {critique}")
            # Step 3: Refine
            refined_json = self._refine_draft(draft_json, critique, text_chunk)
            return self._enforce_deterministic_logic(refined_json)

    def _extract_json(self, text):
        """
        Robustly extracts JSON from a string that might contain preamble or markdown.
        Ensures the result is a LIST of dictionaries.
        """
        try:
            # 1. Look for a list [ ... ]
            # Use non-greedy match for the inner content to avoid capturing too much if multiple lists exist
            list_match = re.search(r'\[\s*\{.*\}\s*\]', text, re.DOTALL)
            if list_match:
                json_str = list_match.group(0)
                try:
                    data = json.loads(json_str)
                    if isinstance(data, list):
                        return json.dumps(data)
                except:
                    pass
            
            # 2. Look for a single object { ... } and wrap it in a list
            obj_match = re.search(r'\{.*\}', text, re.DOTALL)
            if obj_match:
                json_str = obj_match.group(0)
                try:
                    data = json.loads(json_str)
                    if isinstance(data, dict):
                        return json.dumps([data])
                    elif isinstance(data, list):
                        return json.dumps(data)
                except:
                    pass
        except:
            pass
        
        # Fallback to cleaning markdown blocks
        cleaned = text.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
            
        try:
            data = json.loads(cleaned)
            if isinstance(data, list):
                return json.dumps(data)
            return json.dumps([data])
        except:
            return "[]"

    def _enforce_deterministic_logic(self, json_str):
        """
        Hard-coded logic to override LLM hallucinations on severity.
        """
        try:
            # Clean JSON string first
            json_str = self._extract_json(json_str)
            data = json.loads(json_str)
            
            if not isinstance(data, list):
                data = [data]

            for entry in data:
                if not isinstance(entry, dict): continue
                check = entry.get("epistemic_check", {})
                if not isinstance(check, dict):
                    check = {}
                    entry["epistemic_check"] = check

                claim = str(check.get("title_claim_type", "")).lower()
                design = str(check.get("study_design_type", "")).lower()
                intervention = str(check.get("intervention_type", "")).lower()
                data_source = str(check.get("data_source_type", "")).lower()
                
                # Rule 1: The "Illusion of Choice" Trap (Behavioral + Self-Reported = HIGH RISK)
                if "behavioral" in intervention and "self-reported" in data_source:
                    check["gap_severity"] = "High"

                # Rule 2: Associative + Observational = LOW
                elif "associat" in claim and "observational" in design:
                    check["gap_severity"] = "Low"
                
                # Rule 3: Causal + Observational = HIGH
                elif "causal" in claim and "observational" in design:
                    check["gap_severity"] = "High"

                # Rule 4: RCT = LOW (generally, unless caught by Rule 1)
                elif "rct" in design or "random" in design:
                    check["gap_severity"] = "Low"

            return json.dumps(data)
        except:
            return "[]"

    def _generate_draft(self, text_chunk):
        prompt = f"""
        You are DR. MATRIX, a rigorous scientific auditor.
        
        TASK:
        Extract structured data for the study described in the INPUT TEXT below.
        
        CRITICAL RULES:
        1. **Metadata**: The Title, Authors, and Citation are at the VERY TOP of the input under "### STUDY IDENTIFICATION ###". You MUST extract them exactly.
        2. **Narrative Extraction**:
           - **Title Claim**: Interpret what the title *implies* (e.g., "Implies a causal link between X and Y" or "Suggests an association").
           - **Methodology**: Briefly describe what was actually done (e.g., "Retrospective cohort study using medical records...").
           - **Findings**: Summarize what the data actually showed (e.g., "Found a significant correlation (p<0.05)...").
        3. **Epistemic Check (The "Truth" Filter)**: 
           - **Study Design**: If the Title contains "Randomized", "Randomised", "RCT", or "Trial", the Design MUST be "RCT". Otherwise, default to "Observational".
           - **Causal Claims**: Look for words like "Effect", "Impact", "Improves", "Efficacy", "Effectiveness", "Causes" in the Title.
           - **Agency Check (Illusion of Choice)**: 
             - **Intervention Type**: "Behavioral" (Depends on patient willpower/choice, e.g., diet, exercise, adherence) OR "Structural" (Passive/Biological, e.g., drug, surgery, air quality, policy).
             - **Data Source**: "Self-Reported" (Surveys, recall) OR "Objective" (Labs, measurements, records).
           - **Severity Logic**:
             - Causal Title + Behavioral Intervention + Self-Reported Data = **HIGH** Severity (Methodological Flaw: Illusion of Choice).
             - Causal Title + Observational Design = **HIGH** Severity (Title-Bait).
             - Associative/Predictive Title + Observational Design = **LOW** Severity (Accurate).
             - Causal Title + RCT + Objective Data = **LOW** Severity (Accurate).
        
        OUTPUT FORMAT (Return ONLY a JSON list of one or more objects):
        [
          {{
            "study_citation": "Surname et al. (Year)",
            "study_title": "EXACT TITLE FROM INPUT",
            "authors": ["Author 1", "Author 2"],
            "title_claims_narrative": "What the title claims/implies...",
            "study_methodology_summary": "What they actually did...",
            "actual_findings_narrative": "What they actually found...",
            "epistemic_check": {{
                "title_claim_type": "Causal" or "Associative",
                "study_design_type": "RCT" or "Observational",
                "intervention_type": "Behavioral" or "Structural",
                "data_source_type": "Self-Reported" or "Objective",
                "gap_severity": "High" | "Medium" | "Low"
            }}
          }}
        ]
        
        DO NOT SUMMARIZE. Respond ONLY with the JSON.
        
        ---
        INPUT TEXT:
        {text_chunk[:30000]}
        """
        
        response = self.llm.generate(prompt, temperature=0.0)
        return self._extract_json(response)

    def _audit_draft(self, draft_json, text_chunk):
        """
        Self-Correction Step: Checks for logic errors.
        """
        audit_prompt = f"""
        You are the SENIOR AUDITOR reviewing a Junior Analyst's extraction.
        
        JUNIOR ANALYST'S JSON:
        {draft_json}
        
        ---
        AUDIT TASK:
        Verify the JSON against the Input Text and Logic Rules provided below.
        
        CHECKLIST:
        1. **Design Consistency Rule**:
           - IF Title contains "Randomized"/"Randomised" BUT Design is "Observational", FAIL. (Must be RCT).
        2. **Logic Check (The "Dean Rule" & "Agency Rule")**: 
           - **False Positive Check**: DID the analyst mark "High" severity for an "Observational" study with an "Associative" title? -> FAIL (Should be Low).
           - **False Negative Check**: DID the analyst mark "Low" severity for an "Observational" study with a "Causal" title (Effect, Impact, Improve)? -> FAIL (Should be High).
           - **Illusion of Choice Check**: DID the analyst mark "Low" severity for a study with "Behavioral" intervention AND "Self-Reported" data? -> FAIL (Should be High).
        3. **Narrative & Metadata Check**:
           - Are 'authors', 'title_claims_narrative', 'study_methodology_summary', and 'actual_findings_narrative' present and populated? -> FAIL if missing or empty.
        4. **Formatting**: Is it valid JSON?
        
        OUTPUT:
        - If clear: Return "PASS".
        - If errors found: Return a short explanation of the error (e.g., "FAIL: Randomized title listed as Observational").
        
        DO NOT SUMMARIZE THE TEXT.
        
        ---
        INPUT TEXT:
        {text_chunk[:30000]}
        """
        return self.llm.generate(audit_prompt, temperature=0.0)

    def _refine_draft(self, draft_json, critique, text_chunk):
        refine_prompt = f"""
        You are DR. MATRIX. Fix the JSON based on the Senior Auditor's critique.
        
        ORIGINAL JSON:
        {draft_json}
        
        CRITIQUE:
        {critique}
        
        TASK:
        Return the CORRECTED JSON based on the INPUT TEXT below.
        Return ONLY a JSON list of objects.
        Ensure 'intervention_type' and 'data_source_type' are correctly classified.
        
        DO NOT SUMMARIZE. Respond ONLY with the JSON.
        
        ---
        INPUT TEXT:
        {text_chunk[:30000]}
        """
        response = self.llm.generate(refine_prompt, temperature=0.0)
        return self._extract_json(response)

def main():
    target_file = "special_issue_advancing_precision_in_hypertension__from_pathophysiology_to_personalized_management_and_outcomes_20260122_1858.md"
    
    if not os.path.exists(target_file):
        print(f"Target file {target_file} not found.")
        return

    print(f"🕵️  Dr. Matrix is scanning: {target_file}")
    
    with open(target_file, "r") as f:
        content = f.read()

    matrix = DrMatrix()
    json_output = matrix.extract_claims(content)
    
    try:
        data = json.loads(json_output)
        output_path = "claims_matrix.json"
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"✅ Extraction complete! Saved to {output_path}")
        print(json.dumps(data, indent=2))
    except json.JSONDecodeError:
        print("❌ LLM output invalid JSON. Raw output:")
        print(json_output)

if __name__ == "__main__":
    main()