import json
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def build_skill_set(entities, vacancy_reqs):
    """
    Gather all relevant skills from vacancy (required + nice-to-have), lowercased for consistency
    """
    return set([s.lower().strip() for s in vacancy_reqs.get('required_skills', []) + vacancy_reqs.get('nice_to_have_skills', [])])


def vectorize_candidate(candidate, skill_set):
    """
    Convert a single candidate dict into a feature vector dict.
    """
    # Skills vector: presence of each skill in skill_set
    skills = [s.lower().strip() for s in candidate.get('skills', [])]
    skill_vector = {skill: (1 if skill in skills else 0) for skill in skill_set}

    # Experience vector: total years
    exp = candidate.get('experience_years', candidate.get('total_experience_years', 0.0))

    # Education level
    edu = candidate.get('education_level', 0)
    edu_field = candidate.get('education_field', '')

    vec = {
        'file': candidate.get('file'),
        'name': candidate.get('name'),
        'experience_years': exp,
        'education_level': edu,
        'education_field': edu_field,
        'skill_vector': skill_vector
    }
    return vec


def vectorize_vacancy(vacancy_reqs, skill_set):
    """
    Convert vacancy requirements into a vector dict.
    """
    # Skills required / nice-to-have: treat required as 1, nice-to-have as 0.5
    required = vacancy_reqs.get('required_skills', [])
    nice = vacancy_reqs.get('nice_to_have_skills', [])
    skill_vector = {skill: (1 if skill in required else (0.5 if skill in nice else 0)) for skill in skill_set}

    exp = vacancy_reqs.get('minimum_years_experience', 0)
    edu = vacancy_reqs.get('required_education_level', 0)
    edu_field = vacancy_reqs.get('required_education_field', '')

    return {
        'minimum_years_experience': exp,
        'required_education_level': edu,
        'required_education_field': edu_field,
        'skill_vector': skill_vector
    }


def main(entities_json: Path, vacancy_json: Path, output: Path):
    entities = load_json(entities_json)
    vacancy_reqs = load_json(vacancy_json)

    skill_set = build_skill_set(entities, vacancy_reqs)
    # Vectorize candidates
    cand_vecs = [vectorize_candidate(c, skill_set) for c in entities]
    # Vectorize vacancy
    vac_vec = vectorize_vacancy(vacancy_reqs, skill_set)

    data = {
        'candidates': cand_vecs,
        'vacancy': vac_vec,
        'skill_set': list(skill_set)
    }
    output.write_text(json.dumps(data, indent=2))
    print(f"Vectorization complete -> {output}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Vectorize candidates and vacancy')
    parser.add_argument('--entities-json', type=Path, required=True)
    parser.add_argument('--vacancy-json', type=Path, required=True)
    parser.add_argument('--output-json', type=Path, required=True)
    args = parser.parse_args()
    main(args.entities_json, args.vacancy_json, args.output_json)
