import subprocess
from pathlib import Path

# Define paths
project_root = Path(__file__).parent

data_dir = project_root / "data"
cvs_dir = data_dir / "cvs"
vacancy_dir = data_dir / "job"

outputs_dir = project_root / "outputs"
text_dir = outputs_dir / "text"
cvs_text_dir = text_dir / "cvs"
job_text_dir = text_dir / "job"

entities_json = outputs_dir / "entities.json"
vacancy_json = outputs_dir / "vacancy.json"
vectors_json = outputs_dir / "vectors.json"
ranking_csv = outputs_dir / "ranking.csv"

# Ensure output directories exist
cvs_text_dir.mkdir(parents=True, exist_ok=True)
job_text_dir.mkdir(parents=True, exist_ok=True)
(outputs_dir / "plots").mkdir(parents=True, exist_ok=True)

# Helper to run shell commands
def run_cmd(cmd: str):
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

if __name__ == "__main__":
    # Step 1: Extract text from CVs and vacancy
    run_cmd(f"python src/text_extraction.py --input-dir {cvs_dir} --output-dir {cvs_text_dir}")
    run_cmd(f"python src/text_extraction.py --input-dir {vacancy_dir} --output-dir {job_text_dir}")

    # Identify vacancy TXT file
    vac_txt_files = list(job_text_dir.glob("*.txt"))
    if not vac_txt_files:
        raise FileNotFoundError(f"No text files found in {job_text_dir}")
    vac_txt = vac_txt_files[0]

    # Step 2: Parse vacancy requirements first
    run_cmd(f"python src/gpt_vacancy_parser.py --input {vac_txt} --output {vacancy_json}")

    # run_cmd(f"python src/vacancy_parsing.py --vacancy-file {vac_txt} --output-json {vacancy_json}")

    # Step 3: Extract entities from CV texts (now pass correct skills file)
    run_cmd(f"python src/entity_extraction.py --input-dir {cvs_text_dir} --output-json {entities_json} --skills-file {vacancy_json}")

    # Step 4: Vectorize candidates and vacancy
    run_cmd(f"python src/vectorize.py --entities-json {entities_json} --vacancy-json {vacancy_json} --output-json {vectors_json}")

    # Step 5: Compute scores and ranking
    run_cmd(f"python src/scoring.py --vector-json {vectors_json} --output-csv {ranking_csv}")

    # Step 6: Plots Results
    run_cmd(f"python src/plot_results.py --ranking-csv {ranking_csv} --output-dir {outputs_dir / 'plots'}")

    # Step Optional: GPT Parser
    
    print("Pipeline complete. Results:")
    print(f"- CV texts: {cvs_text_dir}")
    print(f"- Vacancy text: {vac_txt}")
    print(f"- Parsed entities: {entities_json}")
    print(f"- Vacancy requirements: {vacancy_json}")
    print(f"- Vectors: {vectors_json}")
    print(f"- Ranking CSV: {ranking_csv}")
