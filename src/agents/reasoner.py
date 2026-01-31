from .llm import LLM

class ReasonerAgent:
    def __init__(self, llm: LLM):
        self.llm = llm
        self.name = "Dr. Logic"

    def reason(self, prompt: str, context: str = "") -> str:
        """
        Applies recursive/chain-of-thought reasoning to a problem.
        Designed for models like DeepSeek R1 that excel at 'thinking'.
        """
        
        system_message = """You are Dr. Logic, a specialized reasoning engine.
Your goal is NOT just to answer, but to THINK recursively.
1. Break down the problem.
2. Identify potential contradictions or logical fallacies.
3. Self-correct if your initial thought path is flawed.
4. Synthesize a final answer only after rigorous internal debate.
"""
        
        enhanced_prompt = f"""
        {prompt}
        
        {f"CONTEXT:\n{context}" if context else ""}
        
        ***
        REASONING INSTRUCTIONS:
        - Use a "Chain of Thought" approach.
        - Explicitly state your assumptions.
        - If you encounter conflicting evidence, pause and analyze the source/methodology (Epistemic Check).
        - Output your final answer clearly after your reasoning trace.
        ***
        """
        
        # We assume the underlying LLM (DeepSeek R1) handles the <think> tags or internal monologue 
        # naturally, or we encourage it via the prompt.
        return self.llm.generate(enhanced_prompt, system_message=system_message, temperature=0.6)
