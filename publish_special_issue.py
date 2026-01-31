import os
import sys

# Add 'src' to python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
from agents.llm import LLM
from agents.meta_reviewer import MetaReviewerAgent
# Import the evaluator function
from evaluate_quality import evaluate_report

load_dotenv(override=True)

def main():
    print("Manually triggering Editor-in-Chief (Special Issue Commission)...")
    
    # Use Qwen3 32B for the Meta-Reviewer as requested
    target_model = "qwen3:32b-q8_0" 
    print(f"Initializing Meta-Reviewer with {target_model}...")
    llm = LLM(model=target_model)

    reviewer = MetaReviewerAgent(llm)
    
    # Run Review and Capture Filename
    generated_file = reviewer.run_review("living_meta_analysis.md")
    
    if generated_file:
        print(f"\n✅ Special Issue Published: {generated_file}")
        print("🔄 triggering Automatic Quality Evaluation...")
        evaluate_report(generated_file)
    else:
        print("\n❌ No special issue was generated.")

if __name__ == "__main__":
    main()
