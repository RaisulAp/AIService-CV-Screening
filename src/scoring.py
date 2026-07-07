import json
import csv
from pathlib import Path
import difflib
import math

def compute_score(candidate_vec, vacancy_vec, weights=None):
    """
    Compute weighted match score between a candidate and the vacancy.
    Uses cosine similarity for skills, level + field education scoring,
    and clamped experience scoring.
    """
    if weights is None:
        weights = {'skills': 0.5, 'experience': 0.3, 'education': 0.2}

    # Skill vectors
    cand_skills = set([k for k, v in candidate_vec.get("skill_vector", {}).items() if v])
    vac_skills = set([k for k, v in vacancy_vec.get("skill_vector", {}).items() if v])
    all_skills = set(candidate_vec.get("skill_vector", {}).keys()) | set(vacancy_vec.get("skill_vector", {}).keys())
    # Cosine similarity for skill vectors
    cand_vec = [candidate_vec.get("skill_vector", {}).get(skill, 0) for skill in all_skills]
    vac_vec = [vacancy_vec.get("skill_vector", {}).get(skill, 0) for skill in all_skills]
    dot = sum(a*b for a, b in zip(cand_vec, vac_vec))
    norm_cand = math.sqrt(sum(a*a for a in cand_vec))
    norm_vac = math.sqrt(sum(b*b for b in vac_vec))
    skills_score = dot / (norm_cand * norm_vac) if norm_cand and norm_vac else 0
    # Skill match count (intersection)
    matched_skills = list(vac_skills & cand_skills)

    # Experience score (clamped)
    cand_exp = max(candidate_vec.get('experience_years', 0), 0)
    vac_exp = vacancy_vec.get('minimum_years_experience', 0)
    if vac_exp > 0:
        experience_score = min(cand_exp / vac_exp, 1.0)
    else:
        experience_score = 1.0
    # Education level + field score
    cand_level = candidate_vec.get('education_level', 0)
    vac_level = vacancy_vec.get('required_education_level', 0)
    cand_field = candidate_vec.get('education_field', '').lower()
    vac_field = vacancy_vec.get('required_education_field', '').lower()
    level_score = 0.5 if cand_level >= vac_level else 0
    field_score = 0.5 if vac_field and vac_field in cand_field else 0
    education_score = level_score + field_score

    # Final weighted score
    final_score = (
        weights["skills"] * skills_score +
        weights["experience"] * experience_score +
        weights["education"] * education_score
    )

    return round(final_score, 4), {
        'Skill Matches': len(matched_skills),
        'Years of Experiences': candidate_vec.get('experience_years', 0),
        'Education Field': candidate_vec.get('education_field', '')
    }

def rank_candidates(vector_json: Path, output_csv: Path):
    data = json.loads(vector_json.read_text(encoding='utf-8'))
    cand_vecs = data['candidates']
    vac_vec = data['vacancy']

    rankings = []
    for c in cand_vecs:
        score, breakdown = compute_score(c, vac_vec)
        rankings.append({
            'file': c['file'],
            'name': c['name'],
            'Score': score,
            'Skill Matches': breakdown['Skill Matches'],
            'Years of Experiences': c.get('experience_years', 0),
            'Education Field': c.get('education_field', '')
        })

    rankings.sort(key=lambda x: x['Score'], reverse=True)

    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['file', 'name', 'Score', 'Skill Matches', 'Years of Experiences', 'Education Field']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rankings:
            writer.writerow(row)

    print(f"✅ Ranking complete -> {output_csv}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Rank candidates against vacancy')
    parser.add_argument('--vector-json', type=Path, required=True, help='Path to vectorized data JSON')
    parser.add_argument('--output-csv', type=Path, required=True, help='Path for output ranking CSV')
    args = parser.parse_args()
    rank_candidates(args.vector_json, args.output_csv)
