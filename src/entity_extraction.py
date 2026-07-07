import re
import json
from pathlib import Path
import spacy
from spacy.matcher import PhraseMatcher
from concurrent.futures import ProcessPoolExecutor

# Load spaCy model (ensure you have downloaded 'en_core_web_sm')
nlp = spacy.load("en_core_web_sm")

# Predefined mapping for education levels
EDU_LEVELS = {
    "high school": 0,
    "associate": 0.5,
    "bachelor": 1,
    "master": 2,
    "doctor": 3
}

# Vacancy skills placeholder
VACANCY_SKILLS = []


def clean_and_limit_name(name_str: str) -> str:
    """
    Cleans a raw name string, limits it to max 3 words, and ensures it's plausible.
    - Keeps letters (Unicode), digits (temporarily), spaces, hyphens, apostrophes, periods.
    - Removes other "weird" symbols.
    - Removes all digits.
    - Normalizes whitespace.
    - Limits to the first 3 words.
    - Returns empty string if the result has no alphabetic characters or is empty.
    """
    if not name_str:
        return ""

    # Keep letters, digits, whitespace, and "'-."
    valid_chars = []
    for char_val in name_str:
        if char_val.isalnum() or char_val.isspace() or char_val in "'-.":
            valid_chars.append(char_val)
        # else: implicitly discard other "weird" symbols

    cleaned_name = "".join(valid_chars)

    # Remove all digits
    cleaned_name = re.sub(r"\d+", "", cleaned_name)
    # Normalize whitespace (multiple spaces to one, strip leading/trailing)
    cleaned_name = re.sub(r"\s+", " ", cleaned_name).strip()

    if not cleaned_name: # If only digits and weird symbols were present
        return ""

    words = cleaned_name.split()
    # Filter out empty strings that might result from replacements or original data
    words = [word for word in words if word]
    
    limited_name = " ".join(words[:3])

    # Ensure the final name has at least one letter
    if not any(char_val.isalpha() for char_val in limited_name):
        return ""
        
    return limited_name.strip()


def extract_education(text: str) -> dict:
    text_lower = text.lower()
    level = 0
    field = ""

    # Detect education level
    for key, val in EDU_LEVELS.items():
        if key in text_lower:
            level = max(level, val)

    # Detect major/field
    majors = [
        "architecture", "engineering", "computer science", "informatics",
        "design", "civil engineering", "electrical engineering", "business",
        "psychology", "accounting", "law", "economics", "information systems"
    ]
    for major in majors:
        if major in text_lower:
            field = major
            break

    return {"level": level, "field": field}



def extract_experience(text: str) -> float:
    """
    Extracts total years of professional experience from date ranges in text.
    Subtracts years found in the education section to avoid mixing academic experience.
    """
    def sum_years_from_text(txt):
        years = 0.0
        # Regex for simple year-year ranges
        ranges = re.findall(r"(\d{4})\s*[–-]\s*(\d{4})", txt)
        for start, end in ranges:
            s, e = int(start), int(end)
            if e >= s:
                years += e - s
        # Regex for month year to month year (approximate years)
        ranges2 = re.findall(r"([A-Za-z]{3,9})\s*(\d{4})\s*(?:to|until|-|–)\s*([A-Za-z]{3,9})\s*(\d{4})", txt)
        month_map = {m.lower(): i for i, m in enumerate([
            "January","February","March","April","May","June",
            "July","August","September","October","November","December"
        ], start=1)}
        for m1, y1, m2, y2 in ranges2:
            try:
                start_year = int(y1)
                start_month_val = month_map.get(m1.lower(), 1)
                start_val = start_year + (start_month_val - 1) / 12
                end_year = int(y2)
                end_month_val = month_map.get(m2.lower(), 12)
                end_val = end_year + (end_month_val -1 ) / 12
                if end_val >= start_val:
                    years += (end_val - start_val)
            except (ValueError, TypeError):
                continue
        return years

    # 1. Extract all years from the full text
    total_years = sum_years_from_text(text)
    # 2. Try to find education section and subtract its years
    edu_section = ""
    edu_match = re.search(r"EDUCATION(.+?)(EXPERIENCE|SKILLS|$)", text, re.I | re.S)
    if edu_match:
        edu_section = edu_match.group(1)
    edu_years = sum_years_from_text(edu_section)
    prof_years = max(0.0, total_years - edu_years)
    return round(prof_years, 1)


def extract_skills(text: str, skills_list=None) -> list:
    if not skills_list:
        return []

    doc = nlp(text.lower())
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    patterns = [nlp.make_doc(skill.lower()) for skill in skills_list]
    matcher.add("SKILL", patterns)

    matches = matcher(doc)
    found = set()
    for match_id, start, end in matches:
        span = doc[start:end].text.lower()
        found.add(span)
    return list(found)


def parse_document(txt_path: Path, skills_list=None) -> dict:
    """
    Parses a text file for education, experience, and skills.
    Returns a dict with extracted fields, using multiple strategies for name detection.
    """
    text = txt_path.read_text(encoding="utf-8")
    edu_info = extract_education(text)
    exp = extract_experience(text)
    skills = extract_skills(text, skills_list)

    name = None
    lines = text.splitlines()

    # 1) Email-based heuristic across all lines
    email_pattern = re.compile(r"^\s*(.+?)\s+[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    for line in lines:
        m = email_pattern.search(line)
        if m:
            raw_candidate = m.group(1).strip()
            if len(raw_candidate) >= 2: # Check if raw candidate is plausible
                processed_candidate = clean_and_limit_name(raw_candidate)
                if processed_candidate:
                    name = processed_candidate
                    break
    
    # 2) If email heuristic failed, fall back to spaCy NER on first few lines
    if not name:
        for line_content in lines[:5]: # Process first few lines
            stripped_line = line_content.strip()
            if not stripped_line: # Skip empty or whitespace-only lines
                continue
            doc = nlp(stripped_line)
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    raw_candidate = ent.text.strip()
                    if len(raw_candidate) >= 2: # Check if raw candidate is plausible
                        processed_candidate = clean_and_limit_name(raw_candidate)
                        if processed_candidate:
                            name = processed_candidate
                            break # Found a PERSON entity, break from entities loop
            if name:
                break # Found a name from this line, break from lines loop

    # 3) Fallback to filename stem
    if not name:
        stem = txt_path.stem
        
        # Attempt 3a: Clean stem aggressively (remove keywords, digits, then clean_and_limit)
        stem_normalized_spaces = re.sub(r"[\s_-]+", " ", stem).strip() # Normalize separators to spaces
        
        keywords_pattern = r"\b(cv|resume|résumé|curriculum vitae|sample)\b"
        temp_name = re.sub(keywords_pattern, "", stem_normalized_spaces, flags=re.IGNORECASE)
        temp_name = re.sub(r"\d+", "", temp_name) # Remove all digits
        temp_name = re.sub(r"\s+", " ", temp_name).strip() # Normalize spaces again
        
        processed_candidate = clean_and_limit_name(temp_name)
        if processed_candidate:
            name = processed_candidate
        
        # Attempt 3b: If 3a failed (e.g., aggressive cleaning removed everything),
        # try clean_and_limit on the original stem.
        if not name:
            processed_candidate_raw_stem = clean_and_limit_name(stem)
            if processed_candidate_raw_stem:
                name = processed_candidate_raw_stem

    # Final fallback if name is still None or empty string
    if not name:
        name = "Unknown"

    return {
        "file": txt_path.name,
        "name": name,
        "education_level": edu_info["level"],
        "education_field": edu_info["field"],
        "total_experience_years": exp,
        "skills": skills
}



def parse_document_helper(args):
    return parse_document(*args)

def batch_parse(input_dir: Path, output_json: Path, skills_list=None):
    """
    Parses all .txt files in input_dir and writes a JSON list to output_json.
    Uses multiprocessing for scalability.
    """
    txt_files = list(input_dir.glob("*.txt"))
    args_list = [(f, skills_list) for f in txt_files]
    results = []
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor() as executor:
        results = list(executor.map(parse_document_helper, args_list))
    output_json.write_text(json.dumps(results, indent=2, ensure_ascii=False)) # ensure_ascii=False for Unicode names
    print(f"Parsed {len(results)} documents -> {output_json}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract entities from CV/text files")
    parser.add_argument("--input-dir", type=Path, required=True, help="Folder with .txt docs")
    parser.add_argument("--output-json", type=Path, required=True, help="Output JSON file path")
    parser.add_argument("--skills-file", type=Path, help="Optional: JSON file with vacancy skills list")
    args = parser.parse_args()

    # Ensure parent directory for output_json exists
    args.output_json.parent.mkdir(parents=True, exist_ok=True)

    if args.skills_file and args.skills_file.exists():
        VACANCY_SKILLS.clear()
        try:
            skills_data = json.loads(args.skills_file.read_text(encoding='utf-8'))
            # Extend with unique skills only, preserving order from file if possible, then sort
            loaded_skills = []
            for skill in skills_data.get('required_skills', []):
                if skill not in loaded_skills:
                    loaded_skills.append(skill)
            for skill in skills_data.get('nice_to_have_skills', []):
                 if skill not in loaded_skills:
                    loaded_skills.append(skill)
            VACANCY_SKILLS.extend(loaded_skills)

        except json.JSONDecodeError:
            print(f"Warning: could not load skills from {args.skills_file}. Invalid JSON.")
        except Exception as e:
            print(f"Warning: error processing skills file {args.skills_file}: {e}")


    batch_parse(args.input_dir, args.output_json, VACANCY_SKILLS)