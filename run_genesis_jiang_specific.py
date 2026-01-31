import os
import glob
import datetime
import sys
from src.agents.genesis import DrGenesis

def main():
    target_file = "special_issue_advancing_precision_in_hypertension__from_pathophysiology_to_personalized_management_and_outcomes_20260122_1858.md"
    
    print(f"📄 Reading targeted critique: {target_file}")
    with open(target_file, "r") as f:
        content = f.read()

    # 2. Unleash Dr. Genesis with a SPECIFIC FOCUS
    genesis = DrGenesis()
    
    # We modify the call to inject a specific requirement
    print("🧬 Dr. Genesis: Targeting the Jiang et al. (2025) selection bias...")
    
    # Temporary hack: wrap the content with a specific instruction
    focused_content = f"FOCUS ON FIXING THE SELECTION BIAS IN JIANG ET AL (2025) REGARDING ECHOCARDIOGRAPHY.\n\n{content}"
    
    protocol = genesis.design_study(focused_content)
    
    # 3. Save the Protocol
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    output_filename = f"protocol_jiang_fix_{timestamp}.md"
    
    with open(output_filename, "w") as f:
        f.write(protocol)
    
    print(f"\n✅ Dr. Genesis has designed the study: {output_filename}")
    print("-------------------------------------------------------")
    print(protocol[:500] + "...\n(See file for full protocol)")

if __name__ == "__main__":
    main()

