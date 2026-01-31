import os
import re
import json
import yaml
from typing import List, Dict
from .llm import LLM
from .feedback_manager import FeedbackManager

class MetaReviewerAgent:
    def __init__(self, llm: LLM):
        self.llm = llm
        self.feedback_manager = FeedbackManager()
        
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
        
        self.history_path = "special_issue_history.json"

    def _load_history(self) -> List[Dict]:
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

    def _save_history(self, entry: Dict):
        history = self._load_history()
        history.append(entry)
        try:
            with open(self.history_path, 'w') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save special issue history: {e}")

    def _get_taxonomy_path(self):
        return self.taxonomy_path

    def _load_taxonomy(self) -> str:
        path = self._get_taxonomy_path()
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    return yaml.dump(yaml.safe_load(f))
            except:
                return ""
        return ""

    def run_review(self, source_file: str = "living_meta_analysis.md"):
        print("\n=== STARTING EDITOR-IN-CHIEF (Meta-Reviewer) ===")
        
        # Get Feedback Instructions
        feedback_instructions = self.feedback_manager.generate_improvement_prompt()
        if feedback_instructions:
            print(f"[Meta-Reviewer] Loaded improvement directives based on past feedback.")
        
        if not os.path.exists(source_file):
            print(f"Source file {source_file} not found. Skipping meta-review.")
            return

        with open(source_file, "r") as f:
            content = f.read()

        # 1. Parse the Living Review into Sections
        sections = self._parse_sections(content)
        if not sections:
            print("No sections found in living review to synthesize.")
            return

        # 2. Select ONE Feature Topic (Smart Selection)
        theme_names = list(sections.keys())
        feature_topic, sub_themes = self._select_feature_topic(theme_names, sections)
        
        if not feature_topic:
            print("Editor-in-Chief decided no topic is ready for a special issue yet.")
            return

        print(f"Commissioning Special Issue: '{feature_topic}' (Focusing on: {sub_themes})...")
        return self._write_special_issue(feature_topic, sub_themes, sections)

    def _parse_sections(self, content: str) -> Dict[str, str]:
        """
        Parses the markdown content to extract sections based on ### headers.
        Returns a dictionary mapping section titles to their content.
        """
        sections = {}
        # Find all sections starting with ###
        # We assume these are the theme sections under Executive Summary
        # We stop capturing when we hit the next ### or a top level ## (like References)
        pattern = r"### (.*?)\n(.*?)(?=\n#{2,3} |\Z)"
        matches = re.findall(pattern, content, re.DOTALL)
        
        for title, text in matches:
            sections[title.strip()] = text.strip()
            
        return sections

    def _select_feature_topic(self, theme_names: List[str], sections: Dict[str, str]) -> (str, List[str]):
        """
        Asks LLM to pick the single most "issue-worthy" topic group.
        Uses the Parent Taxonomy and Section Content (Length/Density) to ensure high-impact alignment.
        """
        taxonomy = self._load_taxonomy()
        
        # Load History to avoid repetition
        history = self._load_history()
        # Get themes from the last 5 issues
        recent_themes = []
        for entry in history[-5:]:
            if 'themes' in entry:
                recent_themes.extend(entry['themes'])
            if 'main_theme' in entry:
                recent_themes.append(entry['main_theme'])
        
        recent_themes_str = ", ".join(list(set(recent_themes)))
        
        # Calculate "Evidence Density" proxies
        # We can't easily count papers without parsing, but character count is a decent proxy for "meatiness"
        theme_stats = []
        for t in theme_names:
            content_len = len(sections.get(t, ""))
            # Rough estimate of citation count: count "(Author," patterns
            citation_count = len(re.findall(r'\([A-Za-z]+, \d{4}', sections.get(t, "")))
            theme_stats.append(f"- {t} (Length: {content_len} chars, Approx. Citations: {citation_count})")
        
        stats_block = "\n".join(theme_stats)

        prompt = f"""
        I have a persistent RESEARCH TAXONOMY for {self.research_topic}:
        {taxonomy}

        CORE KEYWORDS: {", ".join(self.keywords)}

        I have a list of themes currently present in our Living Meta-Analysis, with evidence metrics:
        {stats_block}

        **RECENTLY COVERED TOPICS (DO NOT REPEAT THESE):**
        {recent_themes_str}

        Act as an Editor-in-Chief. Select ONE high-impact "Feature Topic" for a Special Issue.
        
        CRITERIA FOR SELECTION:
        1.  **NO REPETITION:** You MUST choose a topic significantly different from the "RECENTLY COVERED TOPICS" list above.
        2.  **Evidence Density:** Prefer themes with higher citation counts and content length. Do NOT pick empty themes.
        3.  **Conflict & Controversy:** Look for themes that likely contain debate (e.g., "Management" often has conflicting drug protocols).
        4.  **Specificity:** Avoid generic titles like "Hypertension Overview". Go for "Resistant Hypertension Management" or "Novel Biomarkers".
        
        GOAL:
        Choose a major branch or a specific cluster that warrants a dedicated "Special Issue".
        - Combine related themes into a cohesive editorial vision.
        - The Title should be academic, specific, and professional.
        
        Output valid JSON only:
        {{
            "rationale": "I chose X because it is distinct from recent topics and has high density...",
            "title": "The Special Issue Title",
            "themes": ["Theme A", "Theme B"]
        }}
        """
        
        try:
            response = self.llm.generate(prompt, system_message="You are a decisive editor who prioritizes data density.")
            
            # Robust Parsing Strategy
            # 1. Strip <think> blocks
            clean_response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
            
            # 2. Look for markdown code blocks
            match = re.search(r"```(?:json)?\s*(.*?)```", clean_response, re.DOTALL)
            if match:
                clean_json = match.group(1).strip()
            else:
                # 3. Fallback: Find the outermost curly braces
                match = re.search(r"\{.*\}", clean_response, re.DOTALL)
                clean_json = match.group(0) if match else clean_response.strip()

            data = json.loads(clean_json)
            print(f"    > Editor Selection Rationale: {data.get('rationale', 'None provided.')}")
            return data["title"], data["themes"]
        except Exception as e:
            print(f"Selection failed: {e}. Raw response: {response[:200]}...")
            if theme_names:
                return theme_names[0], [theme_names[0]]
            return None, []

    def _write_special_issue(self, super_theme: str, sub_themes: List[str], sections: Dict[str, str]):
        # Get Feedback Instructions (Freshly generated)
        feedback_instructions = self.feedback_manager.generate_improvement_prompt()

        # Aggregate content with limits
        combined_content = ""
        MAX_CONTENT_CHARS = 45000 # Increased limit (approx 11k tokens) for modern LLMs
        
        for st in sub_themes:
            if st in sections:
                section_text = sections[st]
                if len(combined_content) + len(section_text) > MAX_CONTENT_CHARS:
                    print(f"    > Warning: Truncating content for theme '{st}' to fit context limit.")
                    remaining = MAX_CONTENT_CHARS - len(combined_content)
                    combined_content += f"\n\n#### Findings on {st}\n{section_text[:remaining]}...\n(Truncated)"
                    break
                combined_content += f"\n\n#### Findings on {st}\n{section_text}"
        
        if not combined_content:
            return

        # --- Extract Valid Citations for Context ---
        citation_pattern = r'\([^\)]+, \d{4}[a-z]?\)'
        valid_keys = sorted(list(set(re.findall(citation_pattern, combined_content))))
        
        # --- Load Bibliography to Enhance Context ---
        paper_context = []
        bibliography = {}
        try:
            if os.path.exists("bibliography.json"):
                with open("bibliography.json", "r") as f:
                    data = json.load(f)
                    # Handle List format
                    if isinstance(data, list):
                        bibliography = {item['citation']: item['reference'] for item in data if 'citation' in item and 'reference' in item}
                    # Handle Legacy Dict format
                    elif isinstance(data, dict):
                        bibliography = data
                
                # Create normalized map for fuzzy matching context
                # Map "bechetal2025" -> "(Bech et al., 2025)"
                normalized_bib_map = {}
                for bib_key in bibliography.keys():
                    if len(bib_key) > 2:
                        # normalize: remove parens, spaces, non-alphanumeric, to lower
                        norm_bib = re.sub(r'[^a-zA-Z0-9]', '', bib_key).lower()
                        normalized_bib_map[norm_bib] = bib_key

                for key in valid_keys:
                    # Limit paper context too
                    if len(paper_context) > 50:
                        paper_context.append("... (References truncated)")
                        break

                    ref_text = None
                    
                    # 1. Exact Match
                    if key in bibliography:
                        ref_text = bibliography[key]
                    else:
                        # 2. Fuzzy Match
                        # Normalize the citation key found in text
                        norm_key = re.sub(r'[^a-zA-Z0-9]', '', key).lower()
                        
                        # Check if this normalized key exists in our map
                        if norm_key in normalized_bib_map:
                            real_key = normalized_bib_map[norm_key]
                            paper_context.append(f"- {real_key}: {bibliography[real_key]}")
                        else:
                            # Fallback: Check for author matches
                            # Extract author part from key "(Smith et al., 2024)" -> "smith"
                            match = re.match(r'\(([a-zA-Z]+)', key)
                            if match:
                                author_prefix = match.group(1).lower()
                                # Find all bib keys that start with this author
                                potential_matches = [
                                    bk for nk, bk in normalized_bib_map.items() 
                                    if nk.startswith(author_prefix)
                                ]
                                # If we found any matches (unique or multiple), provide them all as context
                                # This allows the LLM to disambiguate or at least use a VALID title
                                for pm in potential_matches:
                                    paper_context.append(f"- {pm}: {bibliography[pm]}")

                    # (Removed single ref_text logic to support multiple potential matches)
        except Exception as e:
            print(f"Warning: Could not load bibliography for context: {e}")

        paper_context_str = "\n".join(paper_context)

        prompt = f"""
        You are writing a "Special Issue" Editorial titled "{super_theme}".
        
        {feedback_instructions}

        ---
        INCLUDED PAPERS (Reference Context):
        {paper_context_str}
        
        ---
        SOURCE FINDINGS (Synthesized from above papers):
        {combined_content}
        
        ---
        
        Task:
        Write a rigorous, high-impact academic editorial.
        
        **CRITICAL INSTRUCTIONS (DO NOT IGNORE):**
        1.  **BANISH FLUFF:** Do not use phrases like "complex interplay," "nuanced relationship," or "far-reaching implications." They are empty. Instead, state the **DIRECTION** (e.g., "X increases Y") and **MAGNITUDE** (e.g., "X is a stronger predictor than Z") of effects.
        2.  **FORCE COMPARISON:** Do not list studies serially. Every thematic section **MUST explicitly compare** at least two studies. (e.g., "While Study A argues for dietary changes, Study B suggests resistance training offers superior compliance...")
        3.  **TAKE A STANCE:** You are an Editor, not a scribe. identifying what is **OVER-HYPE** and what is **NEGLECTED**.
            - Explicitly state: "The field is currently over-investing in [X] and under-investing in [Y]."
        4.  **EVIDENCE CONFIDENCE:** For every major claim, qualitatively assess the evidence: **[Strong]**, **[Moderate]**, or **[Speculative/Emerging]**.
        5.  **DECISION RELEVANCE:** In your implications, do not just say "more research is needed." Say: "Without longitudinal evidence on [X], public health resources are likely being misallocated."
        
        **Citation Rules:**
        - **CORRECTNESS**: The Source Findings may contain typos. You MUST use the **exact keys** provided in the "INCLUDED PAPERS" list.
        - **FORMAT**: Use parenthetical citations, e.g., "...as demonstrated in (Smith et al., 2024)."
        - **STRICT MATCHING**: Never output a citation key that is not in your "INCLUDED PAPERS" list.
        
        Structure:
        1. **Executive Summary**: A hard-hitting abstract. what is the headline finding?
        2. **Scope of Reviewed Evidence**: Populations, Settings, Interventions.
        3. **In This Issue** (REQUIRED): A bulleted list of the papers used.
           - Format: `* **(Citation Key)**: "Exact Title"`
           - Example: `* **(Smith et al., 2024)**: "A study of hypertension and salt intake"`
           - **CRITICAL**: COPY THE TITLE EXACTLY from the reference list.
        4. **Critical Analysis**: Synthesize the findings.
           - **MUST** use comparative language ("In contrast to...", "Corroborating...").
           - **MUST** include an **Equity & Implementation** angle: Are these interventions feasible in low-resource settings? Name inequity as a driver if applicable.
           - Use the **CORRECTED** citation keys in parentheses.
        5. **The Editorial Stance**:
           - **Evidence Verdict:** What is solid? What is smoke?
           - **The Blind Spot:** What is the most dangerous assumption currently held in this field?
        6. **Implications for Policy & Practice**: 
           - Link findings to resource allocation and clinical decision-making.
        
        (DO NOT write a "Cited Works" or "References" section. This will be added automatically.)
        """
        
        report_draft = self.llm.generate(prompt, system_message="You are the Editor-in-Chief. Write with authority and precision.", temperature=0.2)
        
        if not report_draft:
             print("    > Failed to generate report draft. Retrying with simplified context...")
             # Retry with just the top 2000 chars of content
             prompt = prompt.replace(combined_content, combined_content[:2000] + "\n...(Truncated)")
             report_draft = self.llm.generate(prompt, system_message="You are the Editor-in-Chief.", temperature=0.2)
        
        if not report_draft:
            print("    > Failed to generate report draft again. Aborting.")
            return

        # --- REVIEW & REVISE LOOP ---
        print(f"    > Reviewing Special Issue draft...")
        critique_prompt = f"""
        You are a Senior Academic Reviewer. Review this Special Issue Editorial draft.
        
        DRAFT:
        {report_draft}
        
        CRITIQUE TASKS:
        1. **SYNTHESIS:** Does it connect the papers into a narrative, or just list them? 
        2. **CRITICALITY:** Does it identify specific methodological weaknesses or gaps? (e.g. "The observational nature of (X) precludes causal claims.")
        3. **VOICE:** Does it sound like an authoritative Editorial or a student summary?
        4. **CITATIONS:** Does it use the EXACT citation keys in parentheses (e.g., (Smith et al., 2024)) for every paper mentioned?
        
        If the draft is excellent (Grade A), reply with "PASS".
        Otherwise, provide 3 specific instructions for the rewrite.
        """
        critique = self.llm.generate(critique_prompt, system_message="You are a ruthless academic reviewer.")
        
        if "PASS" in critique and len(critique) < 20:
            print("    > Draft accepted.")
            report = report_draft
        else:
            print(f"    > Refining Special Issue based on critique...")
            revision_prompt = f"""
            You are a Senior Editor-in-Chief. Rewrite this editorial based on the reviewer's critique.
            
            ORIGINAL DRAFT:
            {report_draft}
            
            CRITIQUE:
            {critique}
            
            STRICT RULES:
            1. Use authoritative, active voice.
            2. Integrate methodological critique directly into the synthesis.
            3. Keep all required sections (Executive Summary, Scope, In This Issue, etc.).
            4. **MANDATORY**: Use the exact citation keys in parentheses (e.g., (Smith et al., 2024)) provided in the original bibliography context.
            """
            report = self.llm.generate(revision_prompt, system_message="You are a high-impact journal editor.")

        # --- Build Reference List (Robust) ---
        try:
            # 1. Pre-compute normalized keys for fuzzy matching
            # Map "bechetal2025" -> "(Bech et al., 2025)"
            normalized_map = {}
            for key in bibliography.keys():
                # Remove parens from key, then normalize
                if len(key) > 2:
                    key_inner = key[1:-1]
                    norm_key = re.sub(r'[^a-zA-Z0-9]', '', key_inner).lower()
                    normalized_map[norm_key] = key

            # 2. Extract used keys
            used_keys = set()
            
            # Strategy A: Direct Key Search (The safest way)
            for key in bibliography.keys():
                if key in report:
                    used_keys.add(key)
            
            # Strategy B: Narrative/Author search (Fallback for when LLM ignores parens)
            for key in bibliography.keys():
                # Extract "Author et al." or "Author" from "(Author et al., 2025)"
                match = re.search(r'\(([^,]+)( et al\.)?, \d{4}', key)
                if match:
                    author_part = match.group(1)
                    if f"{author_part} et al." in report or f"{author_part} ({re.search(r'\d{4}', key).group(0)})" in report:
                        used_keys.add(key)

            # Strategy C: Regex for any remaining parenthetical citations
            raw_citations = re.findall(r'\([^\)]+\)', report)
            for citation_group in raw_citations:
                inner = citation_group[1:-1]
                parts = [p.strip() for p in inner.split(';')]
                
                for part in parts:
                    if not re.search(r'\d{4}', part):
                        continue
                        
                    # Attempt 1: Exact Match
                    exact_key = f"({part})"
                    if exact_key in bibliography:
                        used_keys.add(exact_key)
                        continue
                        
                    # Attempt 2: Fuzzy/Normalized Match
                    norm_part = re.sub(r'[^a-zA-Z0-9]', '', part).lower()
                    
                    # Check if any bibliography key is represented in this citation
                    for norm_key, original_key in normalized_map.items():
                        if norm_key in norm_part:
                            used_keys.add(original_key)
            
            reference_section = "\n\n## Cited Works\n"
            sorted_refs = []
            for key in sorted(list(used_keys)):
                ref_str = bibliography.get(key, f"**{key}** (Details not found)")
                sorted_refs.append(f"- {ref_str}")
            
            # 2. Clean up LLM output if it ignored the "DO NOT" rule
            # Remove existing "Cited Works" or "References" section generated by LLM
            report = re.sub(r'##\s*(Cited Works|References).*', '', report, flags=re.DOTALL | re.IGNORECASE).strip()
            
            if sorted_refs:
                report += reference_section + "\n".join(sorted_refs)
            else:
                print("    > Warning: No citations extracted for the reference list.")
                report += "\n\n## Cited Works\n(No citations identified in text.)"

        except Exception as e:
            print(f"Warning: Could not process bibliography: {e}")


        # Save with Timestamp
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        safe_name = "".join([c if c.isalnum() else "_" for c in super_theme]).lower()
        filename = f"special_issue_{safe_name}_{timestamp}.md"
        
        with open(filename, "w") as f:
            f.write(f"# Special Issue: {super_theme}\n")
            f.write(f"**Date:** {datetime.datetime.now().strftime('%Y-%m-%d')}\n")
            f.write(f"**Included Themes:** {', '.join(sub_themes)}\n\n")
            f.write(report)
            
        # Save to History
        self._save_history({
            "date": datetime.datetime.now().strftime('%Y-%m-%d'),
            "title": super_theme,
            "main_theme": super_theme,
            "themes": sub_themes,
            "filename": filename
        })
            
        print(f"Published Special Issue: {filename}")
        return filename
