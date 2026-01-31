import os
import sys
from dotenv import load_dotenv
from src.agents.logic import DrLogic
from src.agents.llm import LLM

# Load environment variables
load_dotenv(override=True)

def main():
    print("Initializing Dr. Logic...")
    
    # Initialize LLM (can specify model via env vars if needed)
    llm = LLM() 
    
    # Initialize Dr. Logic
    dr_logic = DrLogic(llm=llm)
    
    # Run Analysis
    dr_logic.run_analysis()

if __name__ == "__main__":
    main()
