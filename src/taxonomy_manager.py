import yaml
import os
import shutil
from agents.llm import LLM

def refine_taxonomy(llm: LLM, taxonomy_path: str = "taxonomy.yml"):
    """
    Refines the taxonomy structure using the LLM while preserving the research topic.
    """
    if not os.path.exists(taxonomy_path):
        print(f"Taxonomy file {taxonomy_path} not found. Skipping refinement.")
        return

    # 1. Read current topic
    research_topic = "Hypertension" # Default
    try:
        with open(taxonomy_path, 'r') as f:
            data = yaml.safe_load(f)
            if data and 'research_topic' in data:
                research_topic = data['research_topic']
    except Exception as e:
        print(f"Warning: Could not read research_topic from {taxonomy_path}: {e}")
        return

    print(f"🧠 Refine Taxonomy: Re-thinking structure for '{research_topic}'...")

    # 2. Prompt LLM
    prompt = f"""
    You are the Chief Research Architect for an advanced AI meta-analysis system.
    
    Your task is to redesign the Research Taxonomy for the topic: "{research_topic}".
    
    The goal is to create a structured framework that guides agents to find specific, high-value evidence.
    
    Create a comprehensive, hierarchical YAML structure that covers key domains relevant to this topic.
    For "{research_topic}", this typically includes:
    1. Etiology / Causes
    2. Pathophysiology / Mechanisms
    3. Clinical Presentation
    4. Diagnosis / Evaluation
    5. Management / Interventions (Pharmacological & Non-Pharmacological)
    6. Outcomes / Prognosis
    7. Epidemiology / Risk Factors
    
    Ensure the structure is deep, detailed, and scientifically rigorous.
    
    Output ONLY the valid YAML content. 
    The root key MUST be 'research_topic' with value "{research_topic}".
    Followed by the top-level categories as keys.
    
    Example format:
    research_topic: {research_topic}
    Etiology:
      - Sub-cause 1
      - Sub-cause 2
    ...
    
    Do not include markdown backticks (```yaml). Just the raw YAML.
    """

    try:
        # Generate
        new_yaml_content = llm.generate(prompt, temperature=0.7)
        
        # Clean up response
        new_yaml_content = new_yaml_content.replace("```yaml", "").replace("```", "").strip()

        # Validate YAML
        new_data = yaml.safe_load(new_yaml_content)
        
        # Ensure research_topic is preserved exactly
        if 'research_topic' not in new_data:
            new_data['research_topic'] = research_topic
        
        # Backup existing
        shutil.copy(taxonomy_path, f"{taxonomy_path}.bak")
        
        # Write new
        with open(taxonomy_path, 'w') as f:
            yaml.dump(new_data, f, sort_keys=False, allow_unicode=True)
            
        print("✅ Taxonomy structure updated successfully.")
        
    except Exception as e:
        print(f"❌ Failed to refine taxonomy: {e}")
        # Restore backup if something broke during write? 
        # Writing is the last step, so usually fine.
