import re
import json
from pathlib import Path

def extract_vacancy_requirements(text: str) -> dict:
    """
    Extracts required skills, nice-to-have skills, minimum years of experience,
    and required education level from a vacancy text.
    Returns a dict with these fields.
    """
    # Lowercase for consistent matching
    text_lower = text.lower()

    # Regex patterns
    years_pattern = r"(\d+)\+?\s*(?:years|yrs)[^a-z]"
    edu_keywords = {
        "high school": 0,
        "associate": 0.5,
        "bachelor": 1,
        "master": 2,
        "doctor": 3
    }

    # Extract min years experience (first match)
    years_match = re.search(years_pattern, text_lower)
    min_years = int(years_match.group(1)) if years_match else 0

    # Extract education
    edu_level = 0
    for key, val in edu_keywords.items():
        if key in text_lower:
            edu_level = max(edu_level, val)

    # Skills extraction via simple list-based matching
    # Assume vacancy skills are listed under headings like 'Required Skills:'
    skills = []
    nice_to_have = []
    # Split into lines and search sections
    lines = text.splitlines()
    section = None
    for line in lines:
        low = line.lower().strip()
        if 'required skills' in low:
            section = 'required'
            continue
        if 'nice to have' in low or 'preferred skills' in low:
            section = 'nice'
            continue
        if section == 'required' and low:
            skills.extend([s.strip() for s in re.split(r',|;', low) if s.strip()])
        if section == 'nice' and low:
            nice_to_have.extend([s.strip() for s in re.split(r',|;', low) if s.strip()])

    return {
        'minimum_years_experience': min_years,
        'required_education_level': edu_level,
        'required_education_field': '',  # Placeholder, can be improved with NLP
        'required_skills': skills,
        'nice_to_have_skills': nice_to_have
    }


def parse_vacancy_file(vacancy_path: Path, output_json: Path):
    """
    Reads a vacancy text file, extracts requirements, and writes to JSON.
    """
    text = vacancy_path.read_text(encoding='utf-8')
    reqs = extract_vacancy_requirements(text)
    output_json.write_text(json.dumps(reqs, indent=2))
    print(f"Parsed vacancy -> {output_json}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Parse vacancy text')
    parser.add_argument('--vacancy-file', type=Path, required=True, help='Path to vacancy .txt file')
    parser.add_argument('--output-json', type=Path, required=True, help='Path for output requirements.json')
    args = parser.parse_args()
    parse_vacancy_file(args.vacancy_file, args.output_json)
