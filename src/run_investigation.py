import os
import sys
import datetime
from dotenv import load_dotenv
from database.connection import Database
from agents.llm import LLM
from agents.investigator import InvestigatorAgent

# Load environment variables
load_dotenv()

def main():
    print("Starting Post-Hoc Investigation...")

    # 1. Setup
    db = Database()
    llm = LLM()
    investigator = InvestigatorAgent(db, llm)

    # 2. Run Investigation
    # We look at the last 10 insights from Dr. Analysis
    print("\n--- Investigating Dr. Analysis ---")
    reports = investigator.run_investigation(target_agent="Dr. Analysis", limit=5)
    
    if reports:
        # Save to file with timestamp to prevent overwriting
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"investigation_report_{timestamp}.md"
        
        full_report = f"# Investigator Report\nGenerated: {timestamp}\n\n" + "\n".join(reports)
        
        with open(filename, "w") as f:
            f.write(full_report)
            
        print(f"\n--- REPORT SAVED: {filename} ---")
        print(full_report)
        print("------------------------------------------------")

    # Optional: Investigate Dr. Vision too
    # investigator.run_investigation(target_agent="Dr. Vision", limit=5)

    db.close()

if __name__ == "__main__":
    main()

