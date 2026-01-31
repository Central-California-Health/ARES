import os
import json
from .llm import LLM

class DrGenesis:
    def __init__(self):
        self.llm = LLM()

    def design_study(self, special_issue_content):
        print("🧬 Dr. Genesis (System 2): Initiating Recursive Research Design...")
        
        # Step 1: Draft (The Creative Leap)
        draft_protocol = self._design_study_draft(special_issue_content)
        
        # Step 2: Peer Review (The Constraint Check)
        review = self._review_protocol(draft_protocol)
        
        if "PASS" in review:
            return draft_protocol
        else:
            print(f"🧐 IRB/Peer Review requested changes. Refining protocol...")
            # Step 3: Finalize (The Polished Grant Proposal)
            return self._finalize_protocol(draft_protocol, review)

    def _design_study_draft(self, special_issue_content):
        prompt = f"""
        You are DR. GENESIS, an elite "Research Architect" agent.
        Your goal is to design the *perfect* future scientific study (The "Gold Standard Protocol").
        
        INPUT CONTEXT (Recent "Special Issue" Critique):
        {special_issue_content[:20000]}
        
        ---
        
        TASK:
        1. Identify the "Agency Gap": Previous studies often rely on "Individual Choice" (e.g., diet adherence, exercise) which introduces behavioral bias.
        2. Design a new study that *solves* this by removing user agency. The Intervention MUST be **Structural** or **Biological** (e.g., Air filtration, Water treatment, Policy change, Implant) and NOT Behavioral.
        
        OUTPUT FORMAT (Markdown):
        
        # Proposal for Future Research: [Title of Study]
        
        ## 1. Rationale
        *   **The Agency Gap:** (Criticize the reliance on "willpower" in previous literature.)
        *   **The Structural Opportunity:** (Why removing choice reveals true causality.)
        
        ## 2. Study Design (The "Gold Standard")
        *   **Type:** (e.g., Cluster-RCT, Natural Experiment, Environmental Intervention).
        *   **Population:** (Inclusion/Exclusion criteria).
        *   **Intervention/Exposure:** (MUST BE PASSIVE. No "advice" or "education". Example: "HEPA filtration in schools" vs "Tell kids to breathe better").
        *   **Control:** (Active control or placebo?).
        
        ## 3. Methodology (The "Fix")
        *   **Data Collection:** (e.g., "Replace self-report with environmental sensors / continuous biomarkers").
        *   **Outcome Measures:** (Primary and Secondary endpoints).
        
        ## 4. Expected Impact
        *   (If this study works, how does it change public health policy?)
        
        """
        
        return self.llm.generate(prompt, system_message="You are Dr. Genesis. You reject behavioral interventions. You build structural solutions.", temperature=0.7)

    def _review_protocol(self, draft_protocol):
        """
        System 2: The "Grant Reviewer" that attacks the proposal.
        """
        prompt = f"""
        You are the CHAIR of the RESEARCH REVIEW BOARD.
        
        PROPOSED PROTOCOL:
        {draft_protocol}
        
        ---
        
        TASK:
        Review the protocol for critical flaws.
        
        CRITERIA:
        1. **Feasibility**: Is the sample size realistic? Is the method impossible?
        2. **Specificity**: Are "Biomarkers" named? Is the "Intervention" vague?
        3. **Logic**: Does the design actually solve the "Gap" identified?
        
        OUTPUT:
        - If excellent: "PASS".
        - If flawed: "REJECT: [Brief explanation of what is vague or impossible]".
        """
        return self.llm.generate(prompt, temperature=0.0)

    def _finalize_protocol(self, draft_protocol, review_comments):
        prompt = f"""
        You are DR. GENESIS. The Review Board has sent back comments.
        
        ORIGINAL DRAFT:
        {draft_protocol}
        
        REVIEWER COMMENTS:
        {review_comments}
        
        TASK:
        Rewrite the protocol to address the reviewer's concerns. 
        Make it more specific, more rigorous, or more feasible.
        Return the full Markdown protocol.
        """
        return self.llm.generate(prompt, temperature=0.7)
