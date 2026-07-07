from openai import OpenAI
from dotenv import load_dotenv
import json
from pathlib import Path
import os

# Load variables from .env
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_vacancy_structure(vacancy_text: str) -> dict:
    response = client.chat.completions.create(
        model="gpt-4",  # or "gpt-4.1" if supported
        messages=[
            {
                "role": "system",
                "content": (
                    "You extract structured hiring requirements from raw job postings. "
                    "Your response must be a valid JSON dictionary with only the following fields:\n\n"
                    "- required_skills: list of must-have skills\n"
                    "- nice_to_have_skills: list of optional skills\n"
                    "- required_education_level: number [0=high school, 0.5=associate, 1=bachelor, 2=master, 3=doctor]\n"
                    "- required_education_field: short string, e.g. 'architecture', 'informatics'\n"
                    "- minimum_years_experience: float\n"
                )
            },
            {
                "role": "user",
                "content": f"Extract job requirements from this posting:\n\n'''{vacancy_text}'''"
            }
        ],
        temperature=0.2
    )

    content = response.choices[0].message.content
    return json.loads(content)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract structured fields from a vacancy using GPT")
    parser.add_argument("--input", type=Path, required=True, help="Path to vacancy .txt file")
    parser.add_argument("--output", type=Path, required=True, help="Path to save structured JSON")
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8")
    structured = extract_vacancy_structure(text)

    args.output.write_text(json.dumps(structured, indent=2))
    print(f"✅ Vacancy structure saved to {args.output}")
