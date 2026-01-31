import json
import os

class FeedbackManager:
    def __init__(self, history_file="feedback_history.json"):
        self.history_file = history_file

    def get_recent_history(self, n=3):
        """Retrieves the last n feedback entries."""
        if not os.path.exists(self.history_file):
            return []
        
        try:
            with open(self.history_file, "r") as f:
                history = json.load(f)
            if not history:
                return []
            return history[-n:]
        except:
            return []

    def generate_improvement_prompt(self):
        """
        Analyzes past performance (last 3 runs) and returns a string of instructions 
        to inject into the Agent's prompt. Implements hysteresis to prevent regression.
        """
        recent_history = self.get_recent_history(n=3)
        if not recent_history:
            return ""

        # Use the most recent critique for immediate context
        last_entry = recent_history[-1]
        critique = last_entry.get("critique", "")
        
        # Analyze trends over the last 3 runs
        low_criticality_count = sum(1 for h in recent_history if h.get("scores", {}).get("criticality", 0) < 4)
        last_criticality = last_entry.get("scores", {}).get("criticality", 3)
        
        instructions = ["\n**Directives from Senior Editor (Based on performance history):**"]
        
        # 1. Criticality Check (with Hysteresis)
        # If we failed ANY time recently, keep the pressure on.
        if low_criticality_count > 0:
            if last_criticality < 3:
                instructions.append("- **URGENT:** Your critical analysis is failing. You MUST explicitly discuss study limitations (sample size, design flaws) and contradictions.")
            else:
                instructions.append("- **MAINTENANCE REQUIRED:** Your criticality score has been volatile. You must CONSISTENTLY challenge findings to maintain high scores.")
        elif last_criticality < 5:
             instructions.append("- **Improvement:** Continue to sharpen your critique. Don't just list findings; challenge them.")

        # 2. Synthesis Check
        last_synthesis = last_entry.get("scores", {}).get("synthesis", 3)
        if last_synthesis < 3:
            instructions.append("- **URGENT:** Stop listing papers sequentially. Group findings by CONCEPT or MECHANISM.")
        
        # 3. Specific Critique
        if critique:
            instructions.append(f"- **Editor's Note:** \"{critique}\" - Address this in your current draft.")

        return "\n".join(instructions) + "\n"
