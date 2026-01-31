import os
import glob
import datetime
from src.agents.genesis import DrGenesis

def main():
    import sys
    # 1. Target selection
    if len(sys.argv) > 1:
        target_file = sys.argv[1]
    else:
        files = glob.glob("special_issue_*.md")
        if not files:
            print("No Special Issues found. Run the simulation first.")
            return
        files.sort(key=os.path.getmtime, reverse=True)
        target_file = files[0]
    
    if not os.path.exists(target_file):
        print(f"Error: File {target_file} not found.")
        return
    
    print(f"📄 Reading latest critique: {target_file}")
    with open(target_file, "r") as f:
        content = f.read()

    # 2. Unleash Dr. Genesis
    genesis = DrGenesis()
    protocol = genesis.design_study(content)
    
    # 3. Save the Protocol
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    output_filename = f"protocol_genesis_{timestamp}.md"
    
    with open(output_filename, "w") as f:
        f.write(protocol)
    
    print(f"\n✅ Dr. Genesis has designed the study: {output_filename}")
    print("-------------------------------------------------------")
    print(protocol[:500] + "...\n(See file for full protocol)")

if __name__ == "__main__":
    main()

