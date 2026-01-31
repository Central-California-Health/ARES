import datetime
import os
import json
import threading
import yaml
import re
from .memory import MemoryStream
from .llm import LLM
from .matrix import DrMatrix
from .genesis import DrGenesis
from .reasoner import ReasonerAgent

class Researcher:
    _bib_lock = threading.Lock()
    _matrix_lock = threading.Lock()
    _genesis_lock = threading.Lock()

    def __init__(self, name: str, persona: str, llm: LLM, db=None, enable_kg_updates=True, reasoner: ReasonerAgent = None):
        self.name = name
        self.persona = persona
        self.llm = llm
        self.db = db
        self.enable_kg_updates = enable_kg_updates
        self.reasoner = reasoner
        self.memory = MemoryStream(llm, db, name)
        
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

        # Initialize Sub-Agents
        self.matrix = DrMatrix()
        self.genesis = DrGenesis()

    def _get_taxonomy_path(self):
        return self.taxonomy_path

    def _load_taxonomy(self) -> str:
        """
        Loads the persistent taxonomy to help guide tagging.
        """
        path = self._get_taxonomy_path()
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    taxonomy = yaml.safe_load(f)
                
                # Flatten the taxonomy for the prompt context
                def flatten(d, parent=""):
                    items = []
                    for k, v in d.items():
                        path = f"{parent} > {k}" if parent else k
                        if isinstance(v, dict):
                            items.extend(flatten(v, path))
                        elif isinstance(v, list):
                            for leaf in v:
                                items.append(f"{path} > {leaf}")
                    return items
                
                flattened = flatten(taxonomy)
                return "\n".join([f"- {item}" for item in flattened])
            except:
                return ""
        return ""

    def _load_and_format_prompt(self, filename: str, **kwargs) -> str:
        try:
            with open(f"prompts/{filename}", "r") as f:
                template = f.read()
            
            # Default values
            format_args = {
                "name": self.name,
                "persona": self.persona,
                "topic": self.research_topic
            }
            # Update with kwargs (overriding defaults if present)
            format_args.update(kwargs)
            
            return template.format(**format_args)
        except Exception as e:
            print(f"Error loading prompt {filename}: {e}")
            return ""

    def _format_citation(self, paper: dict) -> str:
        """
        Constructs a standard citation string (Author et al., Year).
        Robustly handles various author formats (list of dicts, strings, etc.)
        """
        try:
            # 1. Extract Authors
            raw_authors = paper.get('authors')
            author_str = "Unknown Authors"
            
            if isinstance(raw_authors, dict) and 'list' in raw_authors:
                raw_authors = raw_authors['list']
                
            if isinstance(raw_authors, list):
                # Format first 3 authors + et al.
                names = []
                for a in raw_authors:
                    if isinstance(a, dict):
                            # Try to construct "Surname Firstname"
                            surname = a.get('family', '')
                            given = a.get('given', '')
                            if surname or given:
                                names.append(f"{surname}".strip()) # Just surname for citation
                            else:
                                names.append(a.get('full_name', a.get('name', 'Unknown')))
                    elif isinstance(a, str):
                        names.append(a)
                
                # Filter out empty names
                names = [n for n in names if n]

                if not names:
                    author_str = "Unknown"
                elif len(names) == 1:
                    author_str = names[0]
                elif len(names) == 2:
                    author_str = f"{names[0]} & {names[1]}"
                else:
                    author_str = f"{names[0]} et al."
            elif isinstance(raw_authors, str):
                # Heuristic for string authors
                author_str = raw_authors.split(',')[0].strip()
                if "et al" not in author_str and "," in raw_authors:
                    author_str += " et al."

            # 2. Extract Year
            pub_date = paper.get('published_at')
            year = "n.d."
            if isinstance(pub_date, datetime.date):
                year = str(pub_date.year)
            elif isinstance(pub_date, str):
                match = re.search(r'\d{4}', pub_date)
                if match:
                    year = match.group(0)
            
            return f"{author_str} ({year})"
        except Exception as e:
            print(f"Error formatting citation: {e}")
            return "Unknown (n.d.)"

    def _update_bibliography(self, key: str, paper: dict):
        """
        Updates the shared bibliography.json file with the new paper.
        Thread-safe using a class-level lock.
        Format is a List of Objects: [{"number": 1, "citation": "(Key)", "reference": "Full String"}]
        """
        bib_file = "bibliography.json"
        
        with Researcher._bib_lock:
            try:
                bibliography = []
                if os.path.exists(bib_file):
                    try:
                        with open(bib_file, "r") as f:
                            data = json.load(f)
                            if isinstance(data, dict):
                                # Migrate legacy dict to list
                                bibliography = [{"citation": k, "reference": v} for k, v in data.items()]
                            elif isinstance(data, list):
                                bibliography = data
                    except:
                        bibliography = []

                # --- Re-extract full author list for the detailed entry ---
                raw_authors = paper.get('authors')
                full_author_str = "Unknown Authors"
                if isinstance(raw_authors, dict) and 'list' in raw_authors:
                    raw_authors = raw_authors['list']
                
                if isinstance(raw_authors, list):
                    names = []
                    for a in raw_authors:
                        if isinstance(a, dict):
                             surname = a.get('family', '')
                             given = a.get('given', '')
                             if surname or given:
                                 names.append(f"{surname} {given}".strip())
                             else:
                                 names.append(a.get('full_name', a.get('name', 'Unknown')))
                        elif isinstance(a, str):
                            names.append(a)
                    if len(names) > 3:
                        full_author_str = ", ".join(names[:3]) + ", et al."
                    else:
                        full_author_str = ", ".join(names)
                elif isinstance(raw_authors, str):
                    full_author_str = raw_authors

                # Year
                pub_date = paper.get('published_at')
                year = "n.d."
                if isinstance(pub_date, datetime.date):
                    year = str(pub_date.year)
                elif isinstance(pub_date, str):
                    match = re.search(r'\d{4}', pub_date)
                    if match:
                        year = match.group(0)

                # Construct Entry
                title = paper.get('title', 'Untitled')
                
                raw_journal = paper.get('journal')
                if isinstance(raw_journal, dict):
                    journal = raw_journal.get('title', 'Unknown Journal')
                elif isinstance(raw_journal, str) and raw_journal:
                    journal = raw_journal
                else:
                    journal = "Unknown Journal"

                doi = paper.get('doi')
                if not doi: 
                    doi = 'No DOI'
                
                # Formatted Value
                entry = f"{full_author_str} ({year}). {title}. *{journal}*. DOI: {doi}"
                
                # Update Key (ensure parentheses)
                if not key.startswith("("):
                    key = f"({key})"
                
                # Update or Append
                found = False
                for item in bibliography:
                    if item.get("citation") == key:
                        item["reference"] = entry
                        found = True
                        break
                
                if not found:
                    new_number = len(bibliography) + 1
                    bibliography.append({
                        "number": new_number,
                        "citation": key, 
                        "reference": entry
                    })
                
                # Re-assign numbers to ensure consistency if any migration happened
                for i, item in enumerate(bibliography):
                    item["number"] = i + 1

                with open(bib_file, "w") as f:
                    json.dump(bibliography, f, indent=2)
                    
            except Exception as e:
                print(f"Error updating bibliography: {e}")

    def perceive_paper(self, paper: dict, time: datetime.datetime):
        """
        Reads a paper, adds a summary to memory, and tags it with themes.
        """
        # 0. Validity Check
        if not paper.get('title') or not str(paper['title']).strip():
            print(f"[{self.name}] Skipped malformed paper (missing title): {paper.get('id', 'Unknown')}")
            return

        # 1. Relevance Check (Gatekeeper)
        relevance_prompt = self._load_and_format_prompt(
            "check_relevance.txt",
            title=paper['title'],
            abstract=paper.get('abstract', 'No abstract available')
        )
        is_relevant = self.llm.generate(relevance_prompt, system_message="You are a relevance filter.").strip().upper()
        
        if "NO" in is_relevant and "YES" not in is_relevant:
            print(f"[{self.name}] Skipped irrelevant paper: '{paper['title']}'")
            return

        # 2. Load prompt from file
        taxonomy_context = self._load_taxonomy()
        prompt = self._load_and_format_prompt(
            "summarize_paper.txt", 
            title=paper['title'], 
            abstract=paper.get('abstract', 'No abstract available'),
            taxonomy_context=taxonomy_context,
            keywords=", ".join(self.keywords)
        )
        
        response = self.llm.generate(prompt, system_message=f"You are {self.name}.")
        
        # Parse Response (Simple parsing based on "Summary:", "Quotes:", and "Themes:")
        summary = response
        quotes = []
        themes = []
        
        # Helper to extract sections
        try:
            # 1. Extract Themes (usually at the end)
            if "Themes:" in response:
                parts = response.split("Themes:")
                theme_str = parts[1].strip()
                remaining = parts[0]
                
                # Robust Parsing for Themes
                # Remove brackets/quotes used as list wrappers
                theme_str = theme_str.replace("[", "").replace("]", "").replace("'", "").replace('"', "")
                
                # Split by comma OR newline to handle list formats
                raw_themes = re.split(r'[,\n]', theme_str)
                
                themes = []
                for t in raw_themes:
                    # Clean each item: remove bullets (*, -) and whitespace
                    clean_t = t.strip()
                    clean_t = re.sub(r'^[\*\-]\s*', '', clean_t) 
                    
                    # Filter empty/tiny noise and conversational artifacts
                    if clean_t and len(clean_t) > 2 and "not directly related" not in clean_t.lower():
                        themes.append(clean_t)

            else:
                remaining = response

            # 2. Extract Quotes (middle)
            if "Quotes:" in remaining:
                parts = remaining.split("Quotes:")
                quote_str = parts[1].strip()
                summary = parts[0].replace("Summary:", "").strip()
                # Simple quote parsing: split by comma if list, or just take lines
                # Assuming the model follows ["Q1", "Q2"] or similar
                # We'll just clean up brackets/quotes
                quote_matches = re.findall(r'"([^"]*)"', quote_str)
                if quote_matches:
                    quotes = quote_matches
                else:
                    # Fallback if not quoted strings
                    quotes = [quote_str]
            else:
                summary = remaining.replace("Summary:", "").strip()

        except Exception as e:
            print(f"Error parsing response: {e}")

        # Parse Author/Year for Memory Citation
        citation_key = self._format_citation(paper)
        
        try:
            # === UPDATE BIBLIOGRAPHY ===
            # We use the raw key here, _update_bibliography handles the dict details
            self._update_bibliography(citation_key, paper)
            
        except Exception as e:
            print(f"Error parsing citation: {e}")

        memory_text = f"[{citation_key}] Read paper '{paper['title']}': {summary}"
        print(f"[{self.name}] {memory_text}")
        if quotes:
            print(f"[{self.name}] > Quotes: {quotes}")
        if themes:
            print(f"[{self.name}] > Themes: {themes}")

        self.memory.add_memory(memory_text, time)


        # Save to DB if available
        if self.db and 'id' in paper:
            # print(f"DEBUG: Saving insight for {paper['title']}...")
            try:
                # We assume paper['id'] is a UUID string now
                self.db.save_insight(self.name, str(paper['id']), summary, themes, quotes)
                # print(f"DEBUG: Saved insight for {paper['title']}.")
            except Exception as e:
                print(f"DEBUG: Error saving insight: {e}")
            
        # === ARES ADVANCED PIPELINE ===
        # Trigger Dr. Matrix (Epistemic Audit) and Dr. Genesis (Protocol Design)
        # print(f"DEBUG: Calling _run_advanced_analysis for '{paper.get('title')}'...")
        self._run_advanced_analysis(paper, summary)

    def _run_advanced_analysis(self, paper, summary):
        # print(f"DEBUG: Entering _run_advanced_analysis...")
        """
        Runs the advanced 'ARES' sub-agents:
        1. Dr. Matrix: Extracts structured claims and title-bait gaps.
        2. Dr. Genesis: Designs a future study protocol based on this paper's flaws.
        """
        # --- DR. MATRIX ---
        if self.enable_kg_updates:
            try:
                # Construct text for analysis
                authors = paper.get('authors', 'Unknown')
                if isinstance(authors, list):
                    # meaningful string representation
                    authors = ", ".join([str(a.get('family', a)) for a in authors if isinstance(a, dict)]) or str(authors)
                elif isinstance(authors, dict) and 'list' in authors:
                    # Handle dict format {'list': [...]}
                    authors_list = authors['list']
                    authors = ", ".join([str(a.get('family', a.get('name', 'Unknown'))) for a in authors_list if isinstance(a, dict)]) or str(authors)
                    
                pub_date = paper.get('published_at', 'n.d.')
                
                # Generate the reliable citation key in Python
                citation_key = self._format_citation(paper)
                
                # Sanitize Title and Abstract to prevent prompt breakage
                clean_title = str(paper.get('title', '')).replace('\n', ' ').replace('\r', '').strip()
                clean_abstract = str(paper.get('abstract', '')).replace('\n', ' ').replace('\r', '').strip()
                
                # Extract and Format Sections
                sections_raw = paper.get('sections')
                sections_text = ""
                
                if sections_raw:
                    if isinstance(sections_raw, dict):
                        for k, v in sections_raw.items():
                            sections_text += f"\n\n### {k.upper()}\n{v}"
                    elif isinstance(sections_raw, list):
                        for item in sections_raw:
                            if isinstance(item, dict):
                                head = item.get('header', item.get('title', 'Section'))
                                body = item.get('content', item.get('text', str(item)))
                                sections_text += f"\n\n### {head}\n{body}"
                            else:
                                sections_text += f"\n\n{item}"
                    elif isinstance(sections_raw, str):
                        sections_text = f"\n\n### FULL TEXT SECTIONS\n{sections_raw}"

                analysis_text = f"""
### STUDY IDENTIFICATION ###
Title: {clean_title}
Citation: {citation_key}
Authors: {authors}
Date: {pub_date}
###########################

Abstract: {clean_abstract}
Summary: {summary}
{sections_text}
"""

                claims_json = self.matrix.extract_claims(analysis_text)
                
                # Parse and Append to living_knowledge_graph.json
                try:
                    claims_data = json.loads(claims_json)
                    
                    # === FORCE OVERWRITE CITATION ===
                    # We trust our Python logic more than the LLM's extraction
                    for claim in claims_data:
                        claim['study_citation'] = citation_key
                        claim['study_title'] = paper.get('title') # Also enforce title accuracy

                    with Researcher._matrix_lock:
                        kg_file = "living_knowledge_graph.json"
                        existing_kg = []
                        if os.path.exists(kg_file):
                            with open(kg_file, "r") as f:
                                try:
                                    existing_kg = json.load(f)
                                except:
                                    existing_kg = []
                        
                        # Deduplicate: Case-insensitive check on title
                        existing_titles = {str(item.get('study_title', '')).strip().lower() for item in existing_kg}
                        
                        for claim in claims_data:
                            title = claim.get('study_title')
                            if title:
                                clean_title = str(title).strip().lower()
                                if clean_title not in existing_titles:
                                    existing_kg.append(claim)
                                    existing_titles.add(clean_title)
                        
                        with open(kg_file, "w") as f:
                            json.dump(existing_kg, f, indent=2)
                    print(f"[{self.name}] Dr. Matrix updated knowledge graph.")
                except Exception as e:
                    print(f"[{self.name}] Dr. Matrix JSON Parse Failed: {e}")
                    print(f"[{self.name}] Raw Output: {claims_json[:500]}...") # Print snippet
            except Exception as e:
                print(f"[{self.name}] Dr. Matrix failed: {e}")

        # --- DR. GENESIS ---
        # DISABLED per user request to focus on Knowledge Graph and Bibliography
        # try:
        #     # Ask Genesis to design a study fixing this specific paper's limitations
        #     # We pass the paper title and abstract/summary
        #     genesis_prompt = f"Target Study: {paper.get('title')}\nContext: {summary}\n\nTask: Design a study that overcomes the limitations of this specific work."
        #     protocol = self.genesis.design_study(genesis_prompt)
            
        #     # Append to living_protocols.json (as a list of objects)
        #     with Researcher._genesis_lock:
        #         proto_file = "living_protocols.json"
        #         existing_protos = []
        #         if os.path.exists(proto_file):
        #             with open(proto_file, "r") as f:
        #                 try:
        #                     existing_protos = json.load(f)
        #                 except:
        #                     existing_protos = []
                
        #         new_entry = {
        #             "target_paper": paper.get("title"),
        #             "date": datetime.datetime.now().isoformat(),
        #             "protocol": protocol
        #         }
        #         existing_protos.append(new_entry)
                
        #         with open(proto_file, "w") as f:
        #             json.dump(existing_protos, f, indent=2)
        #     print(f"[{self.name}] Dr. Genesis designed a new protocol.")
        # except Exception as e:
        #     print(f"[{self.name}] Dr. Genesis failed: {e}")

    def reflect(self, time: datetime.datetime) -> str:
        """
        Generates high-level thoughts based on recent memories.
        Returns the insight text.
        """
        # 1. Retrieve STRICTLY RECENT memories (Current Batch)
        recent_memories = self.memory.get_recent(n=5)
        
        if not recent_memories:
            return ""

        # 2. Retrieve Relevant Historical Memories (Contextual)
        # We construct a query from the recent memories to find what's relevant in the past.
        query_context = " ".join([m.description for m in recent_memories])
        # Retrieve more than we need to allow for filtering
        potential_context = self.memory.retrieve(query_context, time, top_k=10)
        
        # Filter out memories that are already in the "recent" batch
        recent_descriptions = {m.description for m in recent_memories}
        historical_memories = [m for m in potential_context if m.description not in recent_descriptions][:3]

        context_list = [f"- {m.description}" for m in recent_memories]
        anchor_list = [f"- {m.description}" for m in historical_memories]
        
        recent_str = "\n".join(context_list) if context_list else "No recent observations."
        history_str = "\n".join(anchor_list) if anchor_list else "No specific historical context."
        
        prompt = self._load_and_format_prompt("reflect.txt", 
                                              recent_observations=recent_str,
                                              historical_context=history_str)
        insight = self.llm.generate(prompt, system_message=f"You are {self.name}.")
        
        print(f"[{self.name} REFLECTION] {insight}")
        self.memory.add_memory(f"Reflection: {insight}", time)
        
        if self.db:
             self.db.save_report(self.name, "reflection", insight)
        
        return insight

    def discuss_with(self, other_agent, time: datetime.datetime, my_reflection: str = "", other_reflection: str = ""):
        """
        Engages in a multi-turn debate with another agent.
        1. Agent A (Self) proposes a reflection.
        2. Agent B (Other) critiques it (Skeptic Mode).
        3. Agent A synthesizes a Joint Statement.
        """
        # Retrieve context for both agents (STRICTLY RECENT)
        my_memories = self.memory.get_recent(n=5)
        other_memories = other_agent.memory.get_recent(n=5)
        
        if not my_memories and not other_memories:
            print(f"[{self.name} & {other_agent.name}] Discussion skipped (No recent memories).")
            return

        # Retrieve Relevant Historical Context (Dynamic instead of Static Anchor)
        my_query = " ".join([m.description for m in my_memories])
        other_query = " ".join([m.description for m in other_memories])
        
        my_potential = self.memory.retrieve(my_query, time, top_k=5)
        other_potential = other_agent.memory.retrieve(other_query, time, top_k=5)
        
        # Filter duplicates
        my_recent_descs = {m.description for m in my_memories}
        other_recent_descs = {m.description for m in other_memories}
        
        my_history = [m for m in my_potential if m.description not in my_recent_descs][:3]
        other_history = [m for m in other_potential if m.description not in other_recent_descs][:3]
        
        # Format strings for prompt
        my_recent_str = "\n".join([f"- {m.description}" for m in my_memories])
        my_history_str = "\n".join([f"- {m.description}" for m in my_history])
        
        other_recent_str = "\n".join([f"- {m.description}" for m in other_memories])
        other_history_str = "\n".join([f"- {m.description}" for m in other_history])

        # Reconstruct combined evidence for downstream tasks (Resolution & Fact Check)
        combined_evidence = f"""
        === NEW FINDINGS (CURRENT BATCH) ===
        {my_recent_str}
        {other_recent_str}
        
        === HISTORICAL CONTEXT (PREVIOUS BATCHES) ===
        {my_history_str}
        {other_history_str}
        """

        # --- STEP 1: CRITIQUE (The Other Agent speaks) ---
        print(f"\n[{other_agent.name}] Critiquing {self.name}'s findings...")
        critique_prompt = self._load_and_format_prompt(
            "critique.txt",
            name=other_agent.name,           # The Critic's Name
            persona=other_agent.persona,     # The Critic's Persona
            other_name=self.name,            # The Proponent (Self)
            other_reflection=my_reflection if my_reflection else "No specific reflection provided.",
            # Pass granular context
            my_recent=my_recent_str,
            my_history=my_history_str,
            other_recent=other_recent_str,
            other_history=other_history_str
        )
        
        # We use self.llm but with other_agent's persona in system message
        critique_response = self.llm.generate(
            critique_prompt, 
            system_message=f"You are {other_agent.name}. You are a critical reviewer."
        )
        print(f"[{other_agent.name} CRITIQUE]\n{critique_response}\n")

        # --- STEP 2: JOINT RESOLUTION (Self speaks, incorporating critique) ---
        resolution_prompt = f"""
        You are {self.name}. {self.persona}
        
        You recently proposed this reflection:
        "{my_reflection}"
        
        Your colleague, {other_agent.name}, critiqued it:
        "{critique_response}"
        
        **Evidence Board:**
        
        **A. NEW FINDINGS (Primary Focus):**
        {my_recent_str}
        {other_recent_str}
        
        **B. HISTORICAL CONTEXT (Secondary):**
        {my_history_str}
        {other_history_str}
        
        **Task:**
        Respond to the critique and formulate a FINAL JOINT STATEMENT.
        
        **CRITICAL INSTRUCTION:**
        1. **PRIORITIZE SECTION A (NEW FINDINGS):** Your synthesis MUST focus on the new papers read in this batch.
        2. **Use History Only to Frame:** Use Section B only to support or contrast the new findings. Do NOT let history dominate.
        3. **Do Not Defend Overreach:** If the critique is valid, concede.

        **Output Structure:**
        "Response: [Your response]"
        "Joint Statement: [The final agreed research proposal. MUST be split into two clear sections:
        1. **Evidence-Based Consensus**: Synthesize the *NEW* findings with the *HISTORICAL* context. Explicitly cite the new papers.
        2. **Speculative Implications & Future Directions**: Clearly labeled as hypotheses.]"
        """
        
        if self.reasoner:
            print(f"[{self.name}] Engaging Dr. Logic (DeepSeek) for recursive synthesis...")
            discussion_result = self.reasoner.reason(resolution_prompt)
        else:
            discussion_result = self.llm.generate(
                resolution_prompt, 
                system_message=f"You are {self.name}. You aim for scientific rigor and consensus."
            )
        print(f"[{self.name} RESPONSE & RESOLUTION]\n{discussion_result}\n")

        # --- FACT CHECKER SAFEGUARD ---
        # Only check the "Joint Statement" part to avoid checking conversational "Response" text
        statement_to_check = discussion_result
        if "Joint Statement:" in discussion_result:
            statement_to_check = discussion_result.split("Joint Statement:", 1)[1].strip()

        check_prompt = self._load_and_format_prompt(
            "fact_check.txt",
            evidence=combined_evidence,
            conclusion=statement_to_check
        )
        verification_response = self.llm.generate(check_prompt, system_message="You are a strict fact checker.")
        
        # Parse Fact Check
        status = "UNKNOWN"
        evidence_lines = []
        parsing_evidence = False

        for line in verification_response.split('\n'):
            clean_line = line.strip()
            if clean_line.startswith("Status:"):
                status_part = clean_line.split(":", 1)[1].strip().upper()
                # Remove brackets and punctuation
                status = status_part.replace('[', '').replace(']', '').replace('.', '')
                parsing_evidence = False
            elif clean_line.startswith("Evidence:"):
                parsing_evidence = True
                content = clean_line.split(":", 1)[1].strip()
                if content:
                    evidence_lines.append(content)
            elif parsing_evidence:
                evidence_lines.append(clean_line)
        
        evidence_text = "\n".join(evidence_lines).strip()
        
        # Fallback if parsing failed but keyword exists
        if status == "UNKNOWN":
            if "VERIFIED_SYNTHESIS" in verification_response:
                status = "VERIFIED_SYNTHESIS"
            elif "VERIFIED" in verification_response:
                status = "VERIFIED"
            elif "UNSUPPORTED" in verification_response:
                status = "UNSUPPORTED"
            elif "HYPOTHESIS" in verification_response:
                status = "HYPOTHESIS"

        # Detect if LLM just repeated the prompt options
        if "|" in status: 
            print(f"[Fact Check Warning] Malformed status: {status}. Defaulting to HYPOTHESIS.")
            status = "HYPOTHESIS"
            
        # Safeguard against "lazy" verification
        if status.startswith("VERIFIED"):
            # If evidence is empty, too short, or looks like a placeholder
            clean_evidence = evidence_text.lower().strip()
            if not evidence_text or len(evidence_text) < 10 or clean_evidence.endswith("quotes:"):
                print(f"[Fact Check Warning] Status is VERIFIED but evidence length ({len(evidence_text)}) is insufficient. Marking as UNSUPPORTED.")
                status = "UNSUPPORTED"
            # If evidence quotes the agent's reflection instead of the paper
            elif clean_evidence.startswith("reflection:") or clean_evidence.startswith("discussion:") or "based on the provided observations" in clean_evidence:
                print(f"[Fact Check Warning] Invalid proof (quoting reflection, not paper). Marking as UNSUPPORTED.")
                status = "UNSUPPORTED"

        print(f"[Fact Check] Status: {status}")
        if evidence_text:
            print(f"[Fact Check] Proof: {evidence_text}")
        
        if status == "UNSUPPORTED":
            print(">>> Discussion discarded due to lack of evidence.")
            return
        
        # Save Result
        prefix = "[HYPOTHESIS] " if "HYPOTHESIS" in status else ""
        memory_text = f"{prefix}Discussion ({self.name} vs {other_agent.name}): {discussion_result}"
        
        self.memory.add_memory(memory_text, time)
        other_agent.memory.add_memory(memory_text, time)
        
        # Save to DB
        if self.db:
            self.db.save_report(f"{self.name} & {other_agent.name}", "discussion", discussion_result)
            
        # Extract Joint Statement for JSON
        joint_statement_text = discussion_result
        if "Joint Statement:" in discussion_result:
            joint_statement_text = discussion_result.split("Joint Statement:", 1)[1].strip()
            
        # Save to JSON File
        try:
            discussion_entry = {
                "date": time.isoformat(),
                "participants": [self.name, other_agent.name],
                "full_transcript": discussion_result,
                "joint_statement": joint_statement_text,
                "fact_check_status": status
            }
            
            json_file = "living_discussions.json"
            existing_data = []
            
            if os.path.exists(json_file):
                with open(json_file, "r") as f:
                    try:
                        existing_data = json.load(f)
                    except:
                        existing_data = []
            
            existing_data.append(discussion_entry)
            
            with open(json_file, "w") as f:
                json.dump(existing_data, f, indent=2)
                
            print(f"[{self.name}] Saved joint statement to {json_file}")
        except Exception as e:
            print(f"Error saving discussion JSON: {e}")

    def gap_analysis(self, time: datetime.datetime) -> str:
        """
        Produces a gap analysis based on all retrieved relevant memories.
        Uses Map-Reduce if context is too large.
        """
        # Increase retrieval for final analysis
        memories = self.memory.retrieve("limitations gaps missing research hypertension", time, top_k=50)
        
        if not memories:
            return "No memories found for gap analysis."

        all_descriptions = [m.description for m in memories]
        
        # Simple Map-Reduce Strategy
        CHUNK_SIZE = 10 
        if len(all_descriptions) > CHUNK_SIZE:
            print(f"[{self.name}] Large context detected ({len(all_descriptions)} items). Performing Map-Reduce...")
            chunks = [all_descriptions[i:i + CHUNK_SIZE] for i in range(0, len(all_descriptions), CHUNK_SIZE)]
            
            partial_summaries = []
            for i, chunk in enumerate(chunks):
                chunk_context = "\n".join([f"- {d}" for d in chunk])
                prompt = self._load_and_format_prompt("gap_analysis.txt", context=chunk_context)
                # Modify prompt slightly for intermediate step? For now, using same prompt is okay, 
                # but we'll prepend "Intermediate Analysis Part X"
                partial_analysis = self.llm.generate(prompt, system_message=f"You are {self.name}. Analyze this subset of data.")
                partial_summaries.append(partial_analysis)
            
            # Reduce
            context = "\n".join([f"Part {i+1}: {s}" for i, s in enumerate(partial_summaries)])
        else:
            context = "\n".join([f"- {d}" for d in all_descriptions])
        
        # Final Generation
        prompt = self._load_and_format_prompt("gap_analysis.txt", context=context)
        analysis = self.llm.generate(prompt, system_message=f"You are {self.name}.")
        
        if self.db:
            self.db.save_report(self.name, "gap_analysis", analysis)
        
        return analysis
