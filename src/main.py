import os
import sys
import re
import datetime
import glob
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from database.connection import Database
from agents.llm import LLM
from agents.researcher import Researcher
from agents.reasoner import ReasonerAgent

import sys
from simulation.state_manager import StateManager

from agents.compiler import CompilerAgent
from agents.meta_reviewer import MetaReviewerAgent
from agents.investigator import InvestigatorAgent

# Import Judge
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add root to path
try:
    from evaluate_quality import evaluate_report
except ImportError:
    print("Warning: Could not import evaluate_quality.py. Quality checks will be skipped.")
    def evaluate_report(f): pass

# Load environment variables
load_dotenv(override=True)

def get_latest_special_issue():
    files = glob.glob("special_issue_*.md")
    if not files: return None
    return max(files, key=os.path.getmtime)

def process_paper_task(paper, agents, time):
    """
    Worker function to process a single paper with all agents.
    Designed for ThreadPoolExecutor.
    """
    try:
        print(f"Processing Paper: {paper.get('title', 'Unknown')}")
        # Each agent reads the paper
        for agent in agents:
            agent.perceive_paper(paper, time)
    except Exception as e:
        print(f"Error processing paper {paper.get('title', 'Unknown')}: {e}")

def main():
    print("Initializing Hypertension Research Simulation...")

    # 0. State Management
    state_manager = StateManager()
    state = state_manager.load_state()
    
    # Check for --new flag to force restart
    if "--new" in sys.argv:
        print("Starting NEW simulation (ignoring previous state)...")
        state = None
        state_manager.clear_state()
        
        # Reset Database Tables
        print("Resetting database tables...")
        try:
            temp_db = Database()
            temp_db.reset_tables()
            temp_db.close()
        except Exception as e:
            print(f"Warning: Failed to reset database tables: {e}")

    # 1. Setup
    db = Database()
    llm = LLM()

    # Try to load a "Smart" LLM for the compiler
    smart_llm = None
    smart_model = os.getenv("SMART_LLM_MODEL")
    compiler_llm = llm
    if smart_model:
        print(f"Initializing Smart LLM for Compiler ({smart_model})...")
        smart_llm = LLM(model=smart_model)
        compiler_llm = smart_llm

    # Try to load a specialized LLM for Dr. Vision
    vision_llm = llm
    vision_model = os.getenv("VISION_LLM_MODEL")
    if vision_model:
        print(f"Initializing Vision LLM for Dr. Vision ({vision_model})...")
        vision_llm = LLM(model=vision_model)

    # Initialize Dr. Logic (DeepSeek R1 Integration)
    reasoner = None
    reasoning_model = os.getenv("REASONING_LLM_MODEL") # e.g. "deepseek/deepseek-r1"
    reasoning_url = os.getenv("REASONING_LLM_BASE_URL")
    
    if reasoning_model:
        print(f"Initializing Reasoning LLM for Dr. Logic ({reasoning_model})...")
        reasoning_llm = LLM(model=reasoning_model, base_url=reasoning_url)
        reasoner = ReasonerAgent(reasoning_llm)
        print("recursive thinking enabled via Dr. Logic.")

    compiler = CompilerAgent(db, compiler_llm, smart_llm=smart_llm)
    meta_reviewer = MetaReviewerAgent(compiler_llm)
    investigator = InvestigatorAgent(db, llm)
    
    # Refine Taxonomy on new runs (to ensure structure matches topic)
    if state is None:
        try:
            from taxonomy_manager import refine_taxonomy
            # Prefer smart_llm, then standard llm
            refining_llm = smart_llm if smart_llm else llm
            refine_taxonomy(refining_llm)
        except Exception as e:
            print(f"Warning: Taxonomy refinement failed: {e}")

    # Extract keywords from RESEARCH_TOPIC for SQL filtering
    # Try to load from taxonomy.yml first
    research_topic = os.getenv("RESEARCH_TOPIC", "Hypertension")
    if os.path.exists("taxonomy.yml"):
        import yaml
        try:
            with open("taxonomy.yml", 'r') as f:
                data = yaml.safe_load(f)
                if data and 'research_topic' in data:
                    research_topic = data['research_topic']
                    print(f"Loaded Research Topic from taxonomy.yml: {research_topic}")
        except Exception as e:
            print(f"Warning: Failed to load topic from taxonomy.yml: {e}")

    topic_str = research_topic
    # Simple split by common delimiters
    raw_keywords = re.split(r',|\sand\s|\sor\s', topic_str)
    keywords = [k.strip() for k in raw_keywords if k.strip()]
    print(f"Filtering papers by keywords: {keywords}")

    # 2. Create Agents
    # You can add more agents with different personas
    agents = [
        Researcher("Dr. Analysis", "You are a strict meta-analyst. Your goal is to synthesize ONLY what is explicitly supported by evidence. You summarize findings and identify patterns directly cited in the studies. You DO NOT speculate.", llm, db, enable_kg_updates=True, reasoner=reasoner),
        Researcher("Dr. Vision", "You are a hypothesis generator. Your goal is to explore implications and future research gaps. You MUST distinguish between 'proven facts' and 'speculative opportunities'. Do not present speculation as a conclusion.", vision_llm, db, enable_kg_updates=False, reasoner=reasoner)
    ]

    # 3. Simulation Loop
    if state:
        print(f"Resuming simulation from offset {state['offset']} (Time: {state['current_time']})")
        offset = state['offset']
        current_time = state['current_time']
    else:
        print("Starting simulation from beginning...")
        offset = 0
        current_time = datetime.datetime.now()
    
    # Load configuration from environment or use defaults
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5"))
    COMPILATION_INTERVAL = int(os.getenv("COMPILATION_INTERVAL", "200"))
    # Default meta-review to run every 2 compilations if not set
    META_REVIEW_INTERVAL = int(os.getenv("META_REVIEW_INTERVAL", str(COMPILATION_INTERVAL * 2)))
    # Investigator runs every 2 batches (approx) to audit recent findings
    INVESTIGATION_INTERVAL = int(os.getenv("INVESTIGATION_INTERVAL", str(BATCH_SIZE * 2)))

    print(f"Configuration: Batch Size={BATCH_SIZE}, Compile Every={COMPILATION_INTERVAL}, Audit Every={INVESTIGATION_INTERVAL}")
    
    while True:
        print(f"\n--- Fetching Batch (Offset: {offset}) ---")
        papers = db.fetch_papers(limit=BATCH_SIZE, offset=offset, keywords=keywords)
        
        if not papers:
            print("No more papers found. Simulation complete.")
            break
            
        # Parallel Execution
        # We process all papers in the batch simultaneously using threads.
        print(f"Processing {len(papers)} papers in parallel...")
        with ThreadPoolExecutor(max_workers=BATCH_SIZE) as executor:
            futures = [executor.submit(process_paper_task, paper, agents, current_time) for paper in papers]
            for future in futures:
                future.result() # Wait for completion to catch exceptions if any

        # Advance time by 1 hour per paper (simulating effort, even if parallelized)
        current_time += datetime.timedelta(hours=len(papers))

        # End of Batch: Reflection & Discussion
        print("\n--- Batch Complete: Reflecting & Discussing ---")
        reflections = {}
        for agent in agents:
            insight = agent.reflect(current_time)
            reflections[agent.name] = insight
        
        # Have agents discuss with each other
        if len(agents) >= 2:
            # Simple pair discussion: Agent 0 talks to Agent 1
            # Pass their reflections as the seed for discussion
            ref_0 = reflections.get(agents[0].name, "")
            ref_1 = reflections.get(agents[1].name, "")
            agents[0].discuss_with(agents[1], current_time, my_reflection=ref_0, other_reflection=ref_1)
            
        offset += BATCH_SIZE
        
        # Save State Checkpoint
        state_manager.save_state(offset, current_time, [a.name for a in agents])

        # Periodic Investigation (The Audit)
        if offset > 0 and offset % INVESTIGATION_INTERVAL == 0:
            print(f"\n[Investigator] Audit Triggered at offset {offset}...")
            # Audit the last batch of items (approx INVESTIGATION_INTERVAL items)
            # We target Dr. Analysis for rigorous checking
            reports = investigator.run_investigation(target_agent="Dr. Analysis", limit=INVESTIGATION_INTERVAL)
            
            if reports:
                # 1. Save Timestamped Report
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"investigation_report_offset_{offset}_{timestamp}.md"
                full_report = f"# Investigator Audit Report\nOffset: {offset}\nGenerated: {timestamp}\n\n" + "\n".join(reports)
                
                with open(filename, "w") as f:
                    f.write(full_report)
                print(f"[Investigator] Report saved: {filename}")

                # 2. Update Living Log
                log_file = "living_investigation_log.md"
                try:
                    with open(log_file, "a") as f:
                        f.write(f"\n\n# Audit at Offset {offset} ({timestamp})\n\n")
                        f.write("\n".join(reports))
                        f.write("\n\n---\n")
                    print(f"[Investigator] Appended to {log_file}")
                except Exception as e:
                    print(f"[Investigator] Error updating log: {e}")

            # Optional: Audit Dr. Vision
            # investigator.run_investigation(target_agent="Dr. Vision", limit=INVESTIGATION_INTERVAL)

        # Periodic Compilation
        if offset > 0 and offset % COMPILATION_INTERVAL == 0:
            print(f"\n[Compiling] Reached {offset} papers. Updating Living Meta-Analysis...")
            compiler.generate_thematic_review()
            evaluate_report("living_meta_analysis.md")
            
        # Meta-Review (Editor-in-Chief)
        if offset > 0 and offset % META_REVIEW_INTERVAL == 0:
            print(f"\n[Editor-in-Chief] Reached {offset} papers. Commissioning Special Issues...")
            meta_reviewer.run_review()
            latest_issue = get_latest_special_issue()
            if latest_issue:
                evaluate_report(latest_issue)

    # 5. Final Output
    print("\n\n=== FINAL GAP ANALYSIS ===")
    for agent in agents:
        print(f"\n--- {agent.name}'s Report ---")
        analysis = agent.gap_analysis(current_time)
        print(analysis)

    # 6. Compilation
    compiler.generate_thematic_review()
    evaluate_report("living_meta_analysis.md")

    db.close()

if __name__ == "__main__":
    main()
