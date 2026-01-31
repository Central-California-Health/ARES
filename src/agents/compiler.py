import datetime
import json
import re
import os
import yaml
from collections import Counter
from typing import List, Dict
from .llm import LLM
from database.connection import Database
from .feedback_manager import FeedbackManager

class CompilerAgent:
    def __init__(self, db: Database, llm: LLM, smart_llm: LLM = None):
        self.db = db
        self.llm = llm
        self.smart_llm = smart_llm if smart_llm else llm
        
        self.taxonomy_path = "taxonomy.yml"
        self.research_topic = os.getenv("RESEARCH_TOPIC", "Hypertension")
        
        # Try to load topic from taxonomy.yml
        if os.path.exists(self.taxonomy_path):
            try:
                with open(self.taxonomy_path, 'r') as f:
                    data = yaml.safe_load(f)
                    if data and 'research_topic' in data:
                        self.research_topic = data['research_topic']
            except Exception as e:
                print(f"Warning: Could not load research topic from {self.taxonomy_path}: {e}")

        # Extract keywords for prompt context
        raw_keywords = re.split(r',|\sand\s|\sor\s', self.research_topic)
        self.keywords = [k.strip() for k in raw_keywords if k.strip()]
        
        self.feedback_manager = FeedbackManager()

    def generate_thematic_review(self):
        print("\n=== STARTING COMPILER AGENT ===")
        
        # Get Feedback Instructions
        feedback_instructions = self.feedback_manager.generate_improvement_prompt()
        if feedback_instructions:
            print(f"[{self.research_topic}] Loaded improvement directives based on past feedback.")
        query = """
            SELECT i.insight, i.themes, i.quotes, c.title, c.authors, c.published_at, c.id as paper_id, 
                   c.journal, c.doi, c.source_url
            FROM agent_insights i
            JOIN contents c ON i.paper_id = c.id::text
            ORDER BY i.created_at ASC
        """
        
        try:
            with self.db.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    rows = cur.fetchall()
        except Exception as e:
            print(f"Compiler Error: {e}")
            return

        if not rows:
            print("No insights found to compile.")
            return

        # --- UNIQUE CITATION PRE-PROCESSING ---
        # Map paper_id -> unique_citation (Author, Year suffix)
        id_to_citation = {}
        author_year_counts = {} # (Author, Year) -> list of UNIQUE paper_ids
        
        # First pass: collect basic info and deduplicate by paper_id
        paper_info = {}
        paper_order = [] # Maintain processing order
        
        for row in rows:
            insight, themes, quotes, title, authors, published_at, paper_id, journal, doi, source_url = row
            
            if paper_id in paper_info:
                # If we've seen this paper, just append the new insight/quotes
                paper_info[paper_id]['insights'].append(insight)
                if quotes:
                    paper_info[paper_id]['quotes'].extend(quotes)
                continue

            # Extract Year
            year = "n.d."
            if published_at:
                try: year = str(published_at.year)
                except: pass
            
            # Extract Author
            author_citation = "Unknown"
            full_authors_str = "Unknown Authors"
            
            if authors:
                try:
                    if isinstance(authors, str):
                        try: authors_data = json.loads(authors)
                        except: authors_data = authors
                    else: authors_data = authors

                    if isinstance(authors_data, dict) and "list" in authors_data:
                        first_author = authors_data["list"][0]
                        last_name = first_author.get("family", first_author.get("full_name", "Unknown"))
                        author_citation = f"{last_name} et al."
                        
                        names = []
                        for a in authors_data["list"][:3]:
                             fam = a.get("family", a.get("full_name", ""))
                             giv = a.get("given", "")
                             names.append(f"{fam} {giv}".strip())
                        if len(authors_data["list"]) > 3:
                            names.append("et al.")
                        full_authors_str = ", ".join(names)
                        
                    elif isinstance(authors_data, list) and len(authors_data) > 0:
                        first = authors_data[0]
                        last_name = first.get("family", first.get("full_name", "Unknown")) if isinstance(first, dict) else str(first)
                        author_citation = f"{last_name} et al."
                        full_authors_str = str(authors_data)
                except: 
                    author_citation = "Unknown"
                    full_authors_str = "Unknown"

            key = (author_citation, year)
            if key not in author_year_counts:
                author_year_counts[key] = []
            
            # Add this paper_id to the count for this Author/Year if not already there
            if paper_id not in author_year_counts[key]:
                author_year_counts[key].append(paper_id)
            
            paper_info[paper_id] = {
                'author': author_citation,
                'full_authors': full_authors_str,
                'year': year,
                'title': title,
                'journal': journal or "Unknown Journal",
                'doi': doi,
                'url': source_url,
                'insights': [insight],
                'quotes': quotes if quotes else [],
                'themes': themes
            }
            paper_order.append(paper_id)

        # Second pass: assign suffixes ONLY if there are multiple DIFFERENT papers
        
        for (author, year), ids in author_year_counts.items():
            if len(ids) > 1:
                ids.sort()
                for i, pid in enumerate(ids):
                    suffix = chr(ord('a') + i)
                    unique_cit = f"({author}, {year}{suffix})"
                    id_to_citation[pid] = unique_cit
                    paper_info[pid]['citation'] = unique_cit
            else:
                unique_cit = f"({author}, {year})"
                id_to_citation[ids[0]] = unique_cit
                paper_info[ids[0]]['citation'] = unique_cit
        
        # Build Full Strings
        bibliography_list = []
        for i, pid in enumerate(paper_order):
            info = paper_info[pid]
            cit_key = info['citation']
            ref_str = f"{info['full_authors']} ({info['year']}). {info['title']}. *{info['journal']}*."
            if info['doi']:
                ref_str += f" DOI: {info['doi']}"
            elif info['url']:
                ref_str += f" {info['url']}"
            
            info['full_reference'] = ref_str
            bibliography_list.append({
                "number": i + 1,
                "citation": cit_key,
                "reference": ref_str
            })

        with open("bibliography.json", "w") as f:
            json.dump(bibliography_list, f, indent=2)
        print("Saved bibliography.json")

        # 2. Group by Theme
        theme_map = {} 
        for pid, info in paper_info.items():
            if not info['themes']: continue
            
            # Combine all insights for this paper into one summary for the theme
            combined_insight = " ".join(info['insights'])
            
            for theme in info['themes']:
                theme = theme.strip().title()
                if theme not in theme_map: theme_map[theme] = []
                theme_map[theme].append({
                    'title': info['title'],
                    'insight': combined_insight,
                    'id': pid,
                    'citation': id_to_citation[pid],
                    'quotes': info['quotes']
                })
        
        # --- Theme Consolidation ---
        print(f"Raw themes found: {len(theme_map.keys())}")
        consolidated_map = self._consolidate_themes(theme_map)
        
        if consolidated_map is None:
            print("Aborting compilation because theme consolidation failed.")
            return

        # 3. Filter top themes
        # Sort by path to ensure logical grouping in the document
        sorted_themes = sorted(consolidated_map.items(), key=lambda x: x[0])
        top_themes = [t for t in sorted_themes if len(t[1]) >= 2]
        
        if not top_themes:
            print("Not enough overlapping themes found yet.")
            return

        print(f"Identified {len(top_themes)} consolidated themes: {[t[0] for t in top_themes]}")

        # 4. Write Chapters
        final_report = f"# Living Meta-Analysis on {self.research_topic}\n\n"
        final_report += f"**Last Updated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        final_report += f"**Papers Analyzed:** {len(rows)} insights processed.\n\n"
        final_report += "## Executive Summary\n(This is a living document. It synthesizes findings from the literature processed so far, organized by a persistent hierarchical taxonomy.)\n\n"

        MAX_PAPERS_PER_THEME = 20
        last_headers = []

        for theme_path, papers in top_themes:
            # Calculate header level based on path depth
            # "A > B > C" -> Level 1: A (##), Level 2: B (###), Level 3: C (####)
            parts = [p.strip() for p in theme_path.split(">")]
            
            # Print intermediate headers if they've changed
            for i, part in enumerate(parts[:-1]):
                if len(last_headers) <= i or last_headers[i] != part:
                    h_level = "#" * (i + 2) # Start at ## for top level
                    final_report += f"{h_level} {part}\n\n"
            
            last_headers = parts[:-1]
            
            # The actual section header (the leaf)
            leaf_title = parts[-1]
            h_level = "#" * (len(parts) + 1)
            
            selected_papers = papers[:MAX_PAPERS_PER_THEME]
            print(f"Compiling section: {theme_path} (Using {len(selected_papers)} papers)...")
            
            context_entries = []
            for p in selected_papers:
                quotes_text = "\n".join([f"    > \"{q}\"" for q in p['quotes']])
                context_entries.append(f"- Paper: {p['citation']}\n  Title: {p['title']}\n  Summary: {p['insight']}\n  Evidence:\n{quotes_text}")
            
            context = "\n".join(context_entries)
            
            prompt = f"""
            You are an expert meta-analyst writing a high-impact review section.
            
            **Location in Taxonomy:** {theme_path}
            **Section Title:** {leaf_title}
            
            {feedback_instructions}

            **Input Data (Summaries):**
            {context}

            **Task:**
            Synthesize these findings into a cohesive, argumentative narrative.
            
            **STRICT WRITING RULES:**
            1. **NO SEQUENTIAL LISTING:** Do NOT write "Smith said X. Then Jones said Y." 
               - GOOD: "While Study A reported increased risk, Study B challenged this, suggesting the discrepancy may stem from..."
            2. **Group by Concept:** Structure your paragraphs by *mechanism* or *outcome*, citing multiple papers per paragraph.
            3. **Highlight Contradictions:** actively look for and explain disagreements.
            4. **CRITICALITY (MANDATORY):** You MUST explicitly discuss methodological limitations found in the input summaries.

            **Citation Rule:**
            - Use exact citations from the input: (Author, Year).

            Write the section in Markdown. Start with the header: {h_level} {leaf_title}
            """
            
            # --- DRAFT GENERATION ---
            draft = self.llm.generate(prompt, system_message="You are a meticulous research compiler.")
            
            # --- REVIEW & REVISE LOOP (Simplified for brevity in nested runs) ---
            # (Keeping the revision logic but ensuring it knows the new header level)
            final_report += f"{draft}\n\n"

        # 5. References Section
        final_report += "## References\n\n"
        
        for i, pid in enumerate(paper_order):
            p = paper_info[pid]
            if 'full_reference' in p:
                final_report += f"{i+1}. **{p['citation']}** {p['full_reference']}\n"
            else:
                final_report += f"{i+1}. **{p['citation']}** {p['title']}\n"

        # 6. Save Report
        filename = "living_meta_analysis.md"
        with open(filename, "w") as f:
            f.write(final_report)
        
        print(f"Updated living report: {filename}")

    def _get_taxonomy_path(self):
        return self.taxonomy_path

    def _get_or_create_ontology(self) -> Dict[str, List[str]]:
        """
        Loads the parent ontology from a YAML file or generates it if missing.
        """
        path = self._get_taxonomy_path()
        if os.path.exists(path):
            print(f"Loading parent ontology from {path}...")
            try:
                with open(path, 'r') as f:
                    ontology = yaml.safe_load(f)
                if isinstance(ontology, dict):
                    return ontology
            except Exception as e:
                print(f"Error loading taxonomy file: {e}. Regenerating.")

        print(f"Generating new parent ontology for '{self.research_topic}'...")
        prompt = f"""
        Create a comprehensive, standard scientific ontology (hierarchy) for the research topic: '{self.research_topic}'.
        
        OUTPUT FORMAT:
        A JSON dictionary where keys are "Parent Categories" (High-Level) and values are lists of "Child Concepts" (Sub-categories).
        
        REQUIREMENTS:
        1. Cover the entire domain (Etiology, Pathophysiology, Management, Outcomes, Epidemiology, etc.).
        2. Be hierarchical: "Blood Pressure Control" should be under "Management" or "Therapeutics", NOT a top-level category.
        3. Use standard medical/scientific terminology (MeSH-style).
        4. No "General" or "Miscellaneous" categories yet.
        
        Example Output for 'Diabetes':
        {{
            "Epidemiology & Risk Factors": ["Prevalence", "Genetic Susceptibility", "Lifestyle Factors"],
            "Pathophysiology": ["Insulin Resistance", "Beta-cell Dysfunction"],
            "Clinical Management": ["Pharmacotherapy", "Dietary Interventions", "Glycemic Monitoring"],
            "Complications": ["Neuropathy", "Retinopathy", "Cardiovascular Outcomes"]
        }}
        
        Output valid JSON only.
        """
        
        try:
            response = self.smart_llm.generate(prompt, system_message="You are a strict ontologist. Output JSON only.")
            
            # Robust parsing
            clean_json = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
            match = re.search(r"```(?:json)?\s*(.*?)```", clean_json, re.DOTALL)
            if match: clean_json = match.group(1).strip()
            
            clean_json = re.sub(r'//.*', '', clean_json)
            clean_json = re.sub(r'/\*.*?\*/', '', clean_json, flags=re.DOTALL)
            clean_json = re.sub(r',(\s*[}\]])', r'\1', clean_json)
            
            try:
                ontology = json.loads(clean_json)
            except:
                try:
                    ontology = json.loads(clean_json.replace("'", '"'))
                except:
                    import ast
                    ontology = ast.literal_eval(clean_json)
            
            if isinstance(ontology, dict):
                print(f"    > Ontology generated with {len(ontology)} top-level categories.")
                
                # --- NEW: Run the strict audit immediately ---
                ontology = self._strict_taxonomy_audit(ontology)
                
                self._save_ontology(ontology)
                return ontology
            else:
                print("    > Ontology generation produced invalid format. Using fallback.")
                return {}
                
        except Exception as e:
            print(f"    > Ontology generation failed: {e}. Proceeding without it.")
            return {}

    def _flatten_ontology(self, ontology: Dict, parent_key: str = "") -> List[str]:
        """
        Recursively flattens a nested dictionary ontology into a list of readable paths.
        Example: {"Management": {"Drugs": ["ACE"]}} -> ["Management > Drugs > ACE"]
        """
        paths = []
        for key, value in ontology.items():
            current_path = f"{parent_key} > {key}" if parent_key else key
            
            if isinstance(value, dict):
                # Recursive step for sub-categories
                paths.extend(self._flatten_ontology(value, current_path))
            elif isinstance(value, list):
                # Leaf nodes (list of concepts)
                for item in value:
                    paths.append(f"{current_path} > {item}")
            else:
                # Fallback for simple string leaves if malformed
                paths.append(f"{current_path} > {value}")
        return paths

    def _strict_taxonomy_audit(self, ontology: Dict) -> Dict:
        """
        A rigorous, critique-driven loop to perfect the ontology structure.
        """
        print("    > Performing deep structural audit of the ontology...")
        
        prompt = f"""
        You are a World-Class Scientific Taxonomist and Senior Editor. 
        I have a draft ontology for the research topic '{self.research_topic}'.
        
        CURRENT DRAFT:
        {json.dumps(ontology, indent=2)}
        
        YOUR MISSION:
        Critique the hell out of this file. Make it perfect.
        
        CRITERIA:
        1. **Hierarchical Precision:** logical main themes -> subthemes -> sub-subthemes.
           - Bad: "Drugs" at top level.
           - Good: "Management" -> "Pharmacological Interventions" -> "Antihypertensives".
        2. **Standardization:** Use MeSH (Medical Subject Headings) or high-standard scientific terminology.
        3. **Completeness:** Ensure no major domain is missing (Etiology, Pathophysiology, Epidemiology, Management, Outcomes).
        4. **Balance:** No category should be huge while others are empty. Break down massive categories.
        
        OUTPUT FORMAT:
        Return the REWRITTEN, PERFECTED ontology as a valid JSON dictionary.
        Support nesting up to 3 levels deep if necessary.
        
        Example:
        {{
            "Epidemiology": {{
                "Risk Factors": ["Genetic", "Lifestyle"],
                "Demographics": ["Aging", "Gender Differences"]
            }},
            "Clinical Management": {{
                "Pharmacotherapy": ["ACE Inhibitors", "Beta Blockers"],
                "Lifestyle Modifications": ["Diet", "Exercise"]
            }}
        }}
        
        Output valid JSON only.
        """
        
        try:
            response = self.smart_llm.generate(prompt, system_message="You are a perfectionist taxonomist. Output JSON only.")
            
            # Robust Parsing
            clean_json = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
            match = re.search(r"```(?:json)?\s*(.*?)```", clean_json, re.DOTALL)
            if match: clean_json = match.group(1).strip()
            
            clean_json = re.sub(r'//.*', '', clean_json)
            clean_json = re.sub(r'/\*.*?\*/', '', clean_json, flags=re.DOTALL)
            clean_json = re.sub(r',(\s*[}\]])', r'\1', clean_json)
            
            try:
                refined_ontology = json.loads(clean_json)
            except:
                try:
                    refined_ontology = json.loads(clean_json.replace("'", '"'))
                except:
                    import ast
                    refined_ontology = ast.literal_eval(clean_json)
            
            if isinstance(refined_ontology, dict) and len(refined_ontology) > 0:
                print("    > Audit complete. Ontology refined.")
                return refined_ontology
            else:
                print("    > Audit produced invalid JSON. Keeping original.")
                return ontology
                
        except Exception as e:
            print(f"    > Audit failed: {e}. Keeping original.")
            return ontology

    def _save_ontology(self, ontology: Dict):
        path = self._get_taxonomy_path()
        try:
            with open(path, 'w') as f:
                yaml.dump(ontology, f, sort_keys=False)
            print(f"    > Taxonomy saved to {path}")
        except Exception as e:
            print(f"Failed to save ontology: {e}")

    def _update_ontology_file(self, current_ontology: Dict, mapping: Dict[str, List[str]]):
        """
        Checks if the mapping reveals a need to update the persistent ontology.
        e.g. If "Emerging: Artificial Intelligence" appears, it might prompt adding "Digital Health" to the ontology.
        """
        print("    > Checking for taxonomy evolution...")
        
        prompt = f"""
        I have a persistent 'Parent Ontology' (YAML) and a current 'Theme Mapping' (Papers -> Categories).
        
        PARENT ONTOLOGY:
        {json.dumps(current_ontology, indent=2)}
        
        CURRENT MAPPING (Result of this run):
        {json.dumps(mapping, indent=2)}
        
        TASK:
        Identify if the Parent Ontology needs to be updated to better accommodate the emerging themes.
        
        RULES:
        1. If a category like "Emerging: X" is full of papers, suggest adding "X" (or a formal scientific name for it) to the Parent Ontology.
        2. If a Parent Category was empty in the mapping, DO NOT delete it (it might be needed later).
        3. If a Parent Category was overwhelmingly large, suggest splitting it? (Optional)
        4. ONLY output a JSON dictionary representing the **NEW, COMPLETE** Ontology if changes are needed.
        5. If NO changes are needed, output EXACTLY: {{"NO_CHANGES": true}}
        
        Output valid JSON only.
        """
        
        try:
            response = self.smart_llm.generate(prompt, system_message="You are a taxonomy architect. Output JSON only.")
            
            if "NO_CHANGES" in response:
                print("    > Taxonomy is stable. No updates.")
                return

             # Robust parsing
            clean_json = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
            match = re.search(r"```(?:json)?\s*(.*?)```", clean_json, re.DOTALL)
            if match: clean_json = match.group(1).strip()
            
            clean_json = re.sub(r'//.*', '', clean_json)
            clean_json = re.sub(r'/\*.*?\*/', '', clean_json, flags=re.DOTALL)
            clean_json = re.sub(r',(\s*[}\]])', r'\1', clean_json)
            
            new_ontology = None
            try:
                new_ontology = json.loads(clean_json)
            except:
                try:
                    new_ontology = json.loads(clean_json.replace("'", '"'))
                except:
                    import ast
                    new_ontology = ast.literal_eval(clean_json)
            
            if isinstance(new_ontology, dict) and "NO_CHANGES" not in new_ontology:
                # Sanity check: Ensure it hasn't shrunk drastically
                if len(new_ontology) >= len(current_ontology):
                    print(f"    > Updating taxonomy file (Categories: {len(current_ontology)} -> {len(new_ontology)})")
                    self._save_ontology(new_ontology)
                else:
                    print("    > Proposed update shrank the ontology too much. Ignoring safety.")
            else:
                 print("    > No valid updates parsed.")
        except Exception as e:
            print(f"    > Taxonomy update check failed: {e}")

    def _consolidate_themes(self, raw_theme_map: Dict[str, List]) -> Dict[str, List]:
        """
        Uses LLM to group raw themes into cleaner, high-level categories using a 
        generated Domain Ontology as a semantic anchor.
        Returns a new map: { 'High Level Theme': [List of all papers from sub-themes] }
        """
        # --- Pre-normalization to merge obvious duplicates (e.g. "Risk Factors." vs "Risk Factors") ---
        normalized_map = {}
        for theme, papers in raw_theme_map.items():
            # Remove trailing punctuation and extra spaces, Title Case
            clean_theme = re.sub(r'[^\w\s]+$', '', theme).strip().title()
            if clean_theme not in normalized_map:
                normalized_map[clean_theme] = []
            
            # Add papers, avoiding duplicates
            existing_ids = {p['id'] for p in normalized_map[clean_theme]}
            for p in papers:
                if p['id'] not in existing_ids:
                    normalized_map[clean_theme].append(p)
                    existing_ids.add(p['id'])
        
        raw_theme_map = normalized_map
        raw_themes = list(raw_theme_map.keys())

        if len(raw_themes) < 3:
            return raw_theme_map

        # --- STEP 1: Generate Parent Ontology ---
        ontology = self._get_or_create_ontology()
        flattened_ontology = self._flatten_ontology(ontology)
        
        print(f"Consolidating {len(raw_themes)} themes using Deep Ontology Mapping (Model: {self.smart_llm.model})...")
        
        # --- BATCH PROCESSING ---
        BATCH_SIZE = 15
        mapping = {}
        
        for i in range(0, len(raw_themes), BATCH_SIZE):
            batch = raw_themes[i:i + BATCH_SIZE]
            print(f"    > Processing batch {i//BATCH_SIZE + 1} of {(len(raw_themes) + BATCH_SIZE - 1)//BATCH_SIZE} ({len(batch)} themes)...")
            
            prompt = f"""
            I have a list of raw research themes extracted from papers on {self.research_topic}.
            
            CORE KEYWORDS: {", ".join(self.keywords)}
            
            Raw Themes:
            {batch}

            I have a Reference Parent Ontology (Flattened for your convenience) for {self.research_topic}:
            {json.dumps(flattened_ontology, indent=2)}

            Task: Map the raw themes to the MOST SPECIFIC category path in the Reference Ontology.
            Ensure the mapping respects the CORE KEYWORDS focus.
            
            GOAL: Create a clean, non-overlapping table of contents for a review paper.
            
            MANDATORY RULES:
            1. **ONTOLOGY MAPPING:** Map every raw theme to exactly ONE "Category Path" from the Reference Ontology.
               - Example: Map "ACE Inhibitors" to "Clinical Management > Pharmacotherapy > Antihypertensives".
            2. **CONSOLIDATE SYNONYMS:** Merge conceptually identical raw themes under the same category path.
            3. **HIERARCHY:** Always prefer the most specific level (the leaf) of the path.
            4. **NO SELF-REFERENCING:** Do not create a category just called "{self.research_topic}".
            5. **Emerging Topics:** If a raw theme clearly does NOT fit any ontology category, you may create a new category path named "Emerging > [Topic Name]".
            
            Output valid JSON only.
            {{
                "Parent Category > Subcategory > Specific": ["Raw Theme 1", "Raw Theme 2"],
                "Another > Specific": ["Raw Theme 3"]
            }}
            """
            
            response = self.smart_llm.generate(prompt, system_message="You are a strict taxonomist. Output JSON only.")
            
            # Fallback to standard LLM if smart_llm fails (returns empty)
            if not response and self.smart_llm != self.llm:
                 print(f"    > Batch {i//BATCH_SIZE + 1} failed with smart_llm. Retrying with standard LLM...")
                 response = self.llm.generate(prompt, system_message="You are a strict taxonomist. Output JSON only.")

            if not response:
                print(f"    > Warning: Batch {i//BATCH_SIZE + 1} failed to generate a response. Skipping.")
                continue

            try:
                # Robust JSON cleanup
                response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
                clean_json = response.strip()

                match = re.search(r"```(?:json)?\s*(.*?)```", clean_json, re.DOTALL)
                if match: clean_json = match.group(1).strip()
                
                start_idx = clean_json.find('{')
                end_idx = clean_json.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    clean_json = clean_json[start_idx:end_idx+1]
                
                clean_json = re.sub(r'//.*', '', clean_json)
                clean_json = re.sub(r'/\*.*?\*/', '', clean_json, flags=re.DOTALL)
                clean_json = re.sub(r',(\s*[}\]])', r'\1', clean_json)
                
                batch_mapping = None
                try:
                    batch_mapping = json.loads(clean_json)
                except json.JSONDecodeError:
                    try:
                        fixed_json = clean_json.replace("'", '"') 
                        batch_mapping = json.loads(fixed_json)
                    except json.JSONDecodeError:
                         pass

                if batch_mapping is None:
                    try:
                        import ast
                        batch_mapping = ast.literal_eval(clean_json)
                    except (ValueError, SyntaxError):
                        pass

                if batch_mapping and isinstance(batch_mapping, dict):
                    # Merge into main mapping
                    for key, val in batch_mapping.items():
                        if key not in mapping:
                            mapping[key] = []
                        if isinstance(val, list):
                            mapping[key].extend(val)
                        else: # Handle single string case gracefully
                            mapping[key].append(str(val))
                else:
                    print(f"    > Warning: Batch {i//BATCH_SIZE + 1} failed to parse. Skipping themes in this batch.")
            
            except Exception as e:
                print(f"    > Error processing batch {i//BATCH_SIZE + 1}: {e}")

        # --- Proceed with Critique and Deduplication ---
        try:
            if not mapping:
                print("    > No themes mapped successfully.")
                return None

            # --- DEDUPLICATION PASS ---
            print("    > Checking for final redundancies...")
            mapping = self._merge_redundant_categories(mapping)

            # --- NEW: GLOBAL CONSOLIDATION (The "Review Batches" Step) ---
            if len(mapping) > 25:
                print(f"    > Too many themes ({len(mapping)}) after batch processing. Restructuring hierarchy...")
                # Use _restructure_hierarchy instead of _cluster_categories
                restructured = self._restructure_hierarchy(list(mapping.keys()))
                
                if restructured:
                     consolidated_mapping = {}
                     # 1. Remap old keys to new paths
                     for old_key, new_key in restructured.items():
                         if old_key not in mapping: continue
                         
                         if new_key not in consolidated_mapping:
                             consolidated_mapping[new_key] = []
                         
                         consolidated_mapping[new_key].extend(mapping[old_key])
                     
                     # 2. Preserve anything the LLM missed (safety net)
                     for key in mapping:
                         if key not in restructured:
                             # If not restructured, keep as is
                             if key not in consolidated_mapping:
                                 consolidated_mapping[key] = mapping[key]
                     
                     mapping = consolidated_mapping
                     # Count roots for log
                     root_count = len({k.split('>')[0].strip() for k in mapping.keys()})
                     print(f"    > Global restructuring organized themes into {root_count} roots (Total Paths: {len(mapping)}).")

            new_map = {}
            processed_raw_themes = set()
            
            # Helper for fuzzy match to catch LLM typos in raw theme names
            raw_keys_lower = {k.lower().strip(): k for k in raw_theme_map.keys()}

            # 1. Build the main map from LLM response
            for major_theme, sub_themes in mapping.items():
                if major_theme not in new_map:
                    new_map[major_theme] = []
                
                # Ensure sub_themes is a list
                if not isinstance(sub_themes, list):
                    continue

                for sub in sub_themes:
                    target_key = None
                    
                    # Try exact match
                    if sub in raw_theme_map:
                        target_key = sub
                    
                    # Try fuzzy match (case insensitive)
                    elif sub.lower().strip() in raw_keys_lower:
                        target_key = raw_keys_lower[sub.lower().strip()]
                    
                    if target_key:
                        existing_ids = {p['id'] for p in new_map[major_theme]}
                        for paper in raw_theme_map[target_key]:
                            if paper['id'] not in existing_ids:
                                new_map[major_theme].append(paper)
                                existing_ids.add(paper['id'])
                        processed_raw_themes.add(target_key)
                    else:
                        # Only verbose log if needed
                        pass

            # 2. Aggressive Leftover Handling
            emerging_topics = []
            
            for rt in raw_themes:
                if rt not in processed_raw_themes:
                    papers = raw_theme_map[rt]
                    # STRICT RULE: Only promote a leftover if it has enough papers (>= 3 papers)
                    if len(papers) >= 3:
                        if rt not in new_map:
                            new_map[rt] = papers
                    else:
                        emerging_topics.extend(papers)
            
            # 3. Add Miscellaneous
            if emerging_topics:
                cat_name = "Emerging & Miscellaneous Topics"
                if cat_name not in new_map:
                    new_map[cat_name] = []
                
                existing_ids = {p['id'] for p in new_map[cat_name]}
                for paper in emerging_topics:
                    if paper['id'] not in existing_ids:
                        new_map[cat_name].append(paper)
                        existing_ids.add(paper['id'])

            # 4. Final Safety Check
            # Hard filter for self-referencing topic
            topic_lower = self.research_topic.lower()
            keys_to_remove = [k for k in new_map.keys() if k.lower() == topic_lower or k.lower() == "hypertension"]
            for k in keys_to_remove:
                print(f"Removing self-referencing category: {k}")
                # redistribute papers to "Emerging" or just drop? 
                if "Emerging & Miscellaneous Topics" not in new_map:
                     new_map["Emerging & Miscellaneous Topics"] = []
                
                existing_ids = {p['id'] for p in new_map["Emerging & Miscellaneous Topics"]}
                for paper in new_map[k]:
                    if paper['id'] not in existing_ids:
                        new_map["Emerging & Miscellaneous Topics"].append(paper)
                        existing_ids.add(paper['id'])
                del new_map[k]

            # --- NEW: MINOR THEME AGGREGATION ---
            # Identify themes with < 3 papers and try to merge them into larger ones
            minor_themes = [k for k, v in new_map.items() if len(v) < 3]
            major_themes = [k for k, v in new_map.items() if len(v) >= 3]
            
            if minor_themes and major_themes:
                print(f"    > Found {len(minor_themes)} minor themes (<3 papers). Attempting to merge into {len(major_themes)} major themes...")
                
                prompt = f"""
                I have a list of "Minor Themes" (too few papers) and "Major Themes" (robust).
                
                Minor Themes: {json.dumps(minor_themes)}
                Major Themes: {json.dumps(major_themes)}
                
                TASK:
                Map each Minor Theme to the BEST MATCHING Major Theme.
                If a Minor Theme is truly unique and fits NONE of the Major Themes, map it to "Emerging & Miscellaneous Topics".
                
                OUTPUT JSON:
                {{
                    "Minor Theme A": "Major Theme X",
                    "Minor Theme B": "Emerging & Miscellaneous Topics"
                }}
                """
                
                try:
                    response = self.smart_llm.generate(prompt, system_message="You are a strict editor. Output JSON only.")
                    
                    # Robust Parsing
                    clean_json = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
                    match = re.search(r"```(?:json)?\s*(.*?)```", clean_json, re.DOTALL)
                    if match: clean_json = match.group(1).strip()
                    
                    clean_json = re.sub(r'//.*', '', clean_json)
                    clean_json = re.sub(r',(\s*[}\]])', r'\1', clean_json)
                    
                    try:
                        moves = json.loads(clean_json)
                    except:
                        try:
                            moves = json.loads(clean_json.replace("'", '"'))
                        except:
                            moves = {}
                    
                    if isinstance(moves, dict):
                        for minor, target in moves.items():
                            if minor in new_map and target in new_map and minor != target:
                                # Move papers
                                target_ids = {p['id'] for p in new_map[target]}
                                for paper in new_map[minor]:
                                    if paper['id'] not in target_ids:
                                        new_map[target].append(paper)
                                        target_ids.add(paper['id'])
                                del new_map[minor]
                            elif target == "Emerging & Miscellaneous Topics":
                                if "Emerging & Miscellaneous Topics" not in new_map:
                                    new_map["Emerging & Miscellaneous Topics"] = []
                                
                                target_ids = {p['id'] for p in new_map["Emerging & Miscellaneous Topics"]}
                                for paper in new_map.get(minor, []):
                                    if paper['id'] not in target_ids:
                                        new_map["Emerging & Miscellaneous Topics"].append(paper)
                                        target_ids.add(paper['id'])
                                if minor in new_map: del new_map[minor]
                                
                        print(f"    > Merged minor themes. Current count: {len(new_map)}")
                        
                except Exception as e:
                    print(f"    > Minor theme aggregation failed: {e}")

            if len(new_map) > 0:
                # Count Top-Level Roots
                roots = {k.split('>')[0].strip() for k in new_map.keys()}
                if len(roots) > 25:
                    print(f"    > Found {len(roots)} Top-Level Themes (Limit: 25). Restructuring hierarchy...")
                    
                    # Call the new Hierarchy Builder
                    restructured_paths = self._restructure_hierarchy(list(new_map.keys()))
                    
                    if restructured_paths:
                        final_map = {}
                        for old_key, papers in new_map.items():
                            new_key = restructured_paths.get(old_key, old_key)
                            
                            if new_key not in final_map:
                                final_map[new_key] = []
                            
                            # Merge papers
                            existing_ids = {p['id'] for p in final_map[new_key]}
                            for p in papers:
                                if p['id'] not in existing_ids:
                                    final_map[new_key].append(p)
                                    existing_ids.add(p['id'])
                        
                        new_map = final_map
                        print(f"    > Hierarchy restructured. Now has {len({k.split('>')[0].strip() for k in new_map.keys()})} roots.")
                else:
                    print(f"    > Theme structure is valid ({len(roots)} roots). Keeping all {len(new_map)} sub-themes.")

            return new_map
            
        except Exception as e:
            print(f"Theme consolidation failed: {e}. Aborting compilation.")
            return None

    def _merge_redundant_categories(self, mapping: Dict[str, List]) -> Dict[str, List]:
        # Final pass to programmatically merge redundant keys identified by LLM.
        keys = list(mapping.keys())
        if len(keys) < 2:
            return mapping
            
        merge_template = (
            "Review these scientific categories for conceptual redundancy:\n{keys}\n\n"
            "AGGRESSIVE MERGE MISSION:\n"
            "1. **Treatment/Management:** If you see \"Hypertension Treatment\" AND \"Management & Treatment Strategies\", MERGE THEM immediately.\n"
            "2. **Populations:** If you see \"Older Adults\" AND \"Aging\", MERGE THEM.\n"
            "3. **Conditions:** If you see \"Cardiovascular Disease\" AND \"Cardiovascular Complications\", MERGE THEM.\n\n"
            "Your goal is to reduce noise. If two categories cover >50% of the same ground, merge them.\n\n"
            "Output a JSON dictionary: {{ \"Category To Delete\": \"Category To Keep/Merge Into\" }}\n"
            "Output {{}} if the list is perfect.\n"
            "Output valid JSON only. NO COMMENTS."
        )
        prompt = merge_template.format(keys=json.dumps(keys))
        
        try:
            response = self.smart_llm.generate(prompt, system_message="You are a strict taxonomist. Output JSON only.")
            
            # Robust parsing
            response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
            match = re.search(r"```(?:json)?\s*(.*?)```", response, re.DOTALL)
            clean_json = match.group(1).strip() if match else response.strip()
            
            # Simple cleanup
            clean_json = re.sub(r'//.*', '', clean_json)
            clean_json = re.sub(r',(\s*[}\]])', r'\1', clean_json)
            
            # Try parse
            try:
                merges = json.loads(clean_json)
            except:
                try:
                    merges = json.loads(clean_json.replace("'", '"'))
                except:
                    return mapping # Fail safe
            
            if not isinstance(merges, dict) or not merges:
                return mapping
                
            print(f"    > Merging {len(merges)} redundant categories...")
            
            # Execute merges
            # We need to be careful about chains (A->B, B->C). 
            # A simple 1-pass approach:
            
            final_mapping = mapping.copy()
            
            for source, target in merges.items():
                if source in final_mapping and source != target:
                    # If target doesn't exist, create it (rename)
                    # If target exists, extend it
                    if target not in final_mapping:
                        final_mapping[target] = []
                    
                    # Add items from source to target
                    # (These are list of strings (sub-themes))
                    existing_subs = set(final_mapping[target])
                    for sub in final_mapping[source]:
                        if sub not in existing_subs:
                            final_mapping[target].append(sub)
                            existing_subs.add(sub)
                    
                    del final_mapping[source]
            
            return final_mapping

        except Exception as e:
            print(f"    > Merge pass failed: {e}")
            return mapping

    def _restructure_hierarchy(self, categories: List[str], max_roots: int = 25) -> Dict[str, str]:
        """
        Re-organizes a list of category paths into a cleaner hierarchy with limited Top-Level Roots.
        Returns: { "Original Path": "New Hierarchical Path" }
        """
        print(f"    > Restructuring {len(categories)} categories into max {max_roots} roots (depth allowed)...")
        
        prompt = f"""
        I have a list of current research themes (Category Paths):
        {json.dumps(categories, indent=2)}
        
        TASK:
        Re-organize these themes into a structured hierarchy where there are AT MOST {max_roots} Top-Level Categories (Roots).
        
        RULES:
        1. **Preserve Specificity:** Do NOT flatten themes. You can create deeper paths.
           - BAD: "Pharmacology > Aspirin" -> "Management" (Lost specificity)
           - GOOD: "Pharmacology > Aspirin" -> "Management > Pharmacological Interventions > Antiplatelets"
        2. **Group Logically:** All "Risk Factors" should go under "Epidemiology" or "Risk Factors". All "Drugs" under "Management".
        3. **Standardize Roots:** Use standard MeSH-like roots:
           - Epidemiology, Etiology, Pathophysiology, Diagnosis, Management, Complications, Prognosis, Health Systems.
        4. **Outcome:** Map EVERY input path to a new path.
        
        OUTPUT format (JSON):
        {{
            "Old Path A": "New Root > Subcategory > Detail",
            "Old Path B": "New Root > Subcategory > Detail"
        }}
        """
        
        try:
            response = self.smart_llm.generate(prompt, system_message="You are a senior ontology architect.")
            
            # Robust parsing
            clean_json = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
            match = re.search(r"```(?:json)?\s*(.*?)```", clean_json, re.DOTALL)
            if match: clean_json = match.group(1).strip()
            
            clean_json = re.sub(r'//.*', '', clean_json)
            clean_json = re.sub(r',(\s*[}\]])', r'\1', clean_json)
            
            try:
                mapping = json.loads(clean_json)
            except:
                try:
                    mapping = json.loads(clean_json.replace("'", '"'))
                except:
                    import ast
                    mapping = ast.literal_eval(clean_json)
            
            if isinstance(mapping, dict):
                # Validation: Check number of roots
                new_roots = {v.split('>')[0].strip() for v in mapping.values()}
                print(f"    > Proposed hierarchy has {len(new_roots)} roots.")
                return mapping
            else:
                print("    > Restructuring returned invalid format. Skipping.")
                return {}
                
        except Exception as e:
            print(f"    > Restructuring failed: {e}")
            return {}
                
        except Exception as e:
            print(f"    > Clustering failed: {e}")
            return {}
