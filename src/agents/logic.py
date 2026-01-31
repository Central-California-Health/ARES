import json
import os
import datetime
from .llm import LLM

class DrLogic:
    def __init__(self, llm: LLM = None):
        self.llm = llm if llm else LLM()
        self.kg_file = "living_knowledge_graph.json"
        self.output_file = "living_logic_manifesto.md"

    def run_analysis(self):
        print("🧠 Dr. Logic: Initiating 'So What?' Causal Analysis...")

        # 1. Load Data
        if not os.path.exists(self.kg_file):
            print(f"❌ Error: {self.kg_file} not found. Dr. Logic needs data to think.")
            return

        with open(self.kg_file, "r") as f:
            try:
                knowledge_graph = json.load(f)
            except Exception as e:
                print(f"❌ Error parsing {self.kg_file}: {e}")
                return

        if not knowledge_graph:
            print("⚠️ Knowledge Graph is empty. Nothing to analyze.")
            return

        # 2. Batch/Chunk the Data (if too large)
        # For now, we'll try to feed a summarized version or a large batch.
        # Let's extract just the "Claims" and "Variables" to save tokens.
        
        claims_summary = []
        for entry in knowledge_graph:
            # Entry structure depends on Dr. Matrix, but usually has 'claims', 'variables', 'study_title'
            title = entry.get('study_title', 'Unknown Study')
            citation = entry.get('study_citation', 'Unknown')
            
            # Formatting the claims for the prompt
            # Assuming 'claims' is a list of strings or dicts
            raw_claims = entry.get('claims', [])
            if isinstance(raw_claims, list):
                claims_text = "; ".join([str(c) for c in raw_claims])
            else:
                claims_text = str(raw_claims)
            
            # Extract variables if available
            variables = entry.get('variables', {})
            indep = variables.get('independent_variables', [])
            dep = variables.get('dependent_variables', [])
            
            claims_summary.append(f"- Study: {citation}\n  Claims: {claims_text}\n  Variables: {indep} -> {dep}")

        # Limit to reasonable context size (e.g., last 50 studies if too many)
        # The user mentioned "cycles of chunks", but for V1 let's do the most recent/relevant set.
        context_str = "\n".join(claims_summary[-50:]) 

        # 3. The "So What?" Prompt
        prompt = f"""
        You are DR. LOGIC. You are not a summarizer. You are a PHILOSOPHER OF CAUSALITY.
        
        Your Mission:
        Review the provided hypertension research findings and answer the "So What?" question by exposing the "Illusion of Choice."
        
        THE PHILOSOPHY:
        1. **The Illusion of Choice:** Most public health research concludes "people should eat less salt/exercise more." This fails because individual willpower is finite.
        2. **Architecture > Behavior:** True causality lies in the environment (e.g., air pollution, city design, food supply chain) or biology, not in "choices."
        3. **The Vaccine Model:** We don't teach people to "choose" not to get Polio; we gave them a vaccine. Find the equivalent for Hypertension.
        
        INPUT DATA (Recent Research Claims):
        {context_str}
        
        TASK:
        Write a "Logic Manifesto" (Markdown) that:
        1. **Identifies the Failure:** Point out specific patterns in the input data where researchers are blaming "Lifestyle" (Choice) instead of "Environment" (Architecture).
        2. **Reframes Causality:** taking the variables identified (e.g. {str(indep)[:50]}...), re-interpret them. If a study says "Sedentary behavior causes BP," reframe it as "Urban design lacking walkability causes BP."
        3. **Proposes "The Architecture Cure":** Based on these findings, propose a high-level solution that *removes* user choice. (e.g., "Mandatory Potassium-Enriched Salt Reformulation" instead of "Dietary Advice").
        
        OUTPUT FORMAT:
        
        # Dr. Logic's Manifesto: The Death of "Lifestyle Advice"
        
        ## 1. The Behavioral Fallacy
        (Critique the specific studies above that rely on "adherence" or "willpower".)
        
        ## 2. The Structural Truth
        (Re-interpret the findings. Where is the *actual* cause? Is it the water? The air? The stress of poverty? The lack of sidewalks?)
        
        ## 3. The "Vaccine" for Hypertension
        (Propose a structural/environmental intervention that works *without* the patient's active effort. Be radical but grounded in the data.)
        
        ## 4. Directive for Future Research
        (Tell the other agents—Dr. Genesis and Dr. Matrix—what to look for next. "Stop looking for diet correlates. Start measuring particulate matter.")
        """

        response = self.llm.generate(prompt, system_message="You are Dr. Logic. You reject behavioral solutions. You seek structural causality.", temperature=0.7)

        # 4. Save Output
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        final_output = f"{response}\n\n*Generated by Dr. Logic on {timestamp}*"
        
        with open(self.output_file, "w") as f:
            f.write(final_output)
            
        print(f"✅ Logic Manifesto generated: {self.output_file}")
        
        # Optional: Append to a history log
        log_file = "living_logic_history.md"
        with open(log_file, "a") as f:
            f.write(f"\n\n---\n\n{final_output}")
