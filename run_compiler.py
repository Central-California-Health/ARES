import os
import sys

# Add 'src' to python path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
from database.connection import Database
from agents.llm import LLM
from agents.compiler import CompilerAgent
from evaluate_quality import evaluate_report

load_dotenv(override=True)

def main():
    print("Manually triggering Compiler Agent...")
    db = Database()
    llm = LLM()
    
    # Try to load a "Smart" LLM (e.g., a larger local model) for complex tasks
    smart_llm = None
    smart_model = os.getenv("SMART_LLM_MODEL")
    if smart_model:
        print(f"Initializing Smart LLM ({smart_model})...")
        smart_llm = LLM(model=smart_model)
        # For the compiler specifically, we use the smart model for everything if requested
        # llm = smart_llm 
    
    compiler = CompilerAgent(db, llm, smart_llm=smart_llm)
    compiler.generate_thematic_review()
    db.close()

    # Trigger Evaluation
    print("🔄 triggering Automatic Quality Evaluation for Living Meta-Analysis...")
    if os.path.exists("living_meta_analysis.md"):
        evaluate_report("living_meta_analysis.md")
    else:
        print("❌ living_meta_analysis.md not found.")

if __name__ == "__main__":
    main()
