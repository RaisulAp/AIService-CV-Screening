import streamlit as st
import pandas as pd
import json
import os
import shutil
from pathlib import Path
import openai
from dotenv import load_dotenv

st.set_page_config(page_title="CV Analyzer Dashboard", layout="wide")
st.title("CV Analyzer Dashboard")

# Paths
data_dir = "outputs"
plots_dir = os.path.join(data_dir, "plots")
text_dir = os.path.join(data_dir, "text")
entities_path = os.path.join(data_dir, "entities.json")
ranking_path = os.path.join(data_dir, "ranking.csv")

# Sidebar for file upload and pipeline run
st.sidebar.header("Upload Documents")
cvs_uploaded = st.sidebar.file_uploader("Upload CVs (PDF/DOCX/TXT, multiple)", type=["pdf", "docx", "txt"], accept_multiple_files=True)
vacancy_uploaded = st.sidebar.file_uploader("Upload Vacancy (PDF/DOCX/TXT)", type=["pdf", "docx", "txt"], accept_multiple_files=False)

run_pipeline = st.sidebar.button("Run Analysis")

# Save uploaded files to data dirs if provided
cvs_dir = Path("data/cvs")
vacancy_dir = Path("data/job")
cvs_dir.mkdir(parents=True, exist_ok=True)
vacancy_dir.mkdir(parents=True, exist_ok=True)

if cvs_uploaded:
    for file in cvs_uploaded:
        with open(cvs_dir / file.name, "wb") as f:
            f.write(file.getbuffer())
if vacancy_uploaded:
    with open(vacancy_dir / vacancy_uploaded.name, "wb") as f:
        f.write(vacancy_uploaded.getbuffer())

if run_pipeline:
    # Run the full pipeline using main.py for production robustness
    os.system("python main.py")
    st.success("Analysis complete! See results below.")

# Tabs for dashboard sections
ranking_tab, vacancy_tab, detail_tab = st.tabs(["Ranked Shortlist", "Vacancy Details", "Detail"])

with ranking_tab:
    st.header("Ranked Shortlist")
    if os.path.exists(ranking_path):
        df = pd.read_csv(ranking_path)
        display_columns = ["name", "Score", "Skill Matches", "Education Field"]  # Removed 'Years of Experiences'
        # Only show columns that exist
        display_columns = [col for col in display_columns if col in df.columns]
        st.dataframe(df[display_columns].head(10), use_container_width=True)
    else:
        st.warning("ranking not found.")

with vacancy_tab:
    st.header("Vacancy Details")
    try:
        with open("outputs/vacancy.json", "r", encoding="utf-8") as f:
            vacancy_data = json.load(f)
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Required Skills")
            req_skills = vacancy_data.get("required_skills", [])
            if req_skills:
                st.markdown("\n".join([f"- {skill.title()}" for skill in req_skills]))
            else:
                st.write("None listed.")
            st.subheader("Nice-to-have Skills")
            nice_skills = vacancy_data.get("nice_to_have_skills", [])
            if nice_skills:
                st.markdown("\n".join([f"- {skill.title()}" for skill in nice_skills]))
            else:
                st.write("None listed.")
        with col2:
            st.metric("Required Education Level", vacancy_data.get("required_education_level", "N/A"))
            st.metric("Required Education Field", vacancy_data.get("required_education_field", "N/A"))
            min_years = vacancy_data.get("minimum_years_experience", "N/A")
            if isinstance(min_years, float) and min_years.is_integer():
                min_years = int(min_years)
            st.metric("Minimum Years Experience", min_years)
        st.markdown("---")
    except Exception as e:
        st.error(f"Could not load vacancy.json: {e}")

# Load OpenAI API key
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

def gpt_deep_analysis(cv_text, vacancy_text):
    if not openai_api_key:
        return "[OpenAI API key not set. Cannot run GPT analysis.]"
    client = openai.OpenAI(api_key=openai_api_key)
    prompt = (
        "You are an expert HR assistant. Analyze the following candidate CV in relation to the job vacancy."
        "Extract and summarize. Your response must be a valid JSON dictionary with only the following fields: (leave blank if not found):\n"
        "Name:\nPhone:\nEmail:\nDegree:\nExperiences:\nAchievements:\nStrength:\nWeakness:\nSuitability:\n"
        "Be specific about skill matches, experience, and any gaps.\n\n"
        f"Job Vacancy:\n{vacancy_text}\n\nCV:\n{cv_text}"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "You are an expert HR assistant."}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[GPT analysis failed: {e}]"

with detail_tab:
    st.header("Candidate Details (Top 10)")
    try:
        with open("outputs/entities.json", "r", encoding="utf-8") as f:
            entities = json.load(f)
        with open("outputs/vacancy.json", "r", encoding="utf-8") as f:
            vacancy = json.load(f)
        required_skills = set([s.lower() for s in vacancy.get("required_skills", [])])
        # Load top 10 from ranking.csv, sorted by Score descending
        import pandas as pd
        top_df = pd.read_csv("outputs/ranking.csv").sort_values(by="Score", ascending=False).head(10)
        top_names = set(top_df["name"].tolist())
        # Load vacancy text for GPT
        vacancy_text = Path("outputs/text/job/Vacancy.txt").read_text(encoding="utf-8") if Path("outputs/text/job/Vacancy.txt").exists() else ""
        # Sort entities by Score descending (matching top 10)
        name_to_score = dict(zip(top_df["name"], top_df["Score"]))
        top_entities = [cand for cand in entities if cand["name"] in top_names]
        top_entities.sort(key=lambda c: name_to_score.get(c["name"], 0), reverse=True)
        for cand in top_entities:
            st.subheader(cand["name"])
            cand_skills = set([s.lower() for s in cand.get("skills", [])])
            matched_skills = required_skills & cand_skills
            st.markdown(f"**Matched Skills:** {', '.join([s.title() for s in matched_skills]) if matched_skills else 'None'}")
            # Removed Experience Years from display
            cv_txt_path = Path(f"outputs/text/cvs/{cand['file'].replace('.pdf','.txt').replace('.docx','.txt')}")
            cv_text = cv_txt_path.read_text(encoding="utf-8") if cv_txt_path.exists() else "[CV text not found]"
            with st.expander("Deep Analysis (GPT)"):
                key = f"gpt_{cand['name']}"
                if key not in st.session_state:
                    st.session_state[key] = None
                if st.button(f"Run Deep Analysis for {cand['name']}", key=f"btn_{cand['name']}"):
                    if cv_text and vacancy_text:
                        with st.spinner("Running GPT deep analysis..."):
                            st.session_state[key] = gpt_deep_analysis(cv_text, vacancy_text)
                    else:
                        st.session_state[key] = "[CV or vacancy text not found for GPT analysis]"
                if st.session_state[key]:
                    # Try to pretty print JSON if possible, else fallback to raw
                    try:
                        gpt_data = json.loads(st.session_state[key])
                        st.markdown(f"**Name:** {gpt_data.get('Name','')}")
                        st.markdown(f"**Phone:** {gpt_data.get('Phone','')}")
                        st.markdown(f"**Email:** {gpt_data.get('Email','')}")
                        st.markdown(f"**Degree:** {gpt_data.get('Degree','')}")
                        # Experiences
                        exps = gpt_data.get('Experiences','')
                        if isinstance(exps, list):
                            st.markdown("**Experiences:**\n" + "\n".join([f"- {e}" for e in exps]) if exps else "**Experiences:**")
                        elif exps:
                            st.markdown(f"**Experiences:** {exps}")
                        # Achievements
                        achs = gpt_data.get('Achievements','')
                        if isinstance(achs, list):
                            st.markdown("**Achievements:**\n" + "\n".join([f"- {a}" for a in achs]) if achs else "**Achievements:**")
                        elif achs:
                            st.markdown(f"**Achievements:** {achs}")
                        # Strength
                        strengths = gpt_data.get('Strength','')
                        if isinstance(strengths, list):
                            st.markdown("**Strengths:**\n" + "\n".join([f"- {s}" for s in strengths]) if strengths else "**Strengths:**")
                        elif strengths:
                            st.markdown(f"**Strengths:** {strengths}")
                        # Weakness
                        weaknesses = gpt_data.get('Weakness','')
                        if isinstance(weaknesses, list):
                            st.markdown("**Weaknesses:**\n" + "\n".join([f"- {w}" for w in weaknesses]) if weaknesses else "**Weaknesses:**")
                        elif weaknesses:
                            st.markdown(f"**Weaknesses:** {weaknesses}")
                        # Suitability
                        st.markdown(f"**Suitability:** {gpt_data.get('Suitability','')}")
                    except Exception:
                        st.write(st.session_state[key])
            st.markdown("---")
    except Exception as e:
        st.error(f"Could not load candidate details: {e}")

# Remove Output button
col1, col2, col3 = st.columns([6, 1, 1])
with col3:
    remove_clicked = st.button("Remove Output", help="Delete all output files", type="secondary")
if remove_clicked:
    for root, dirs, files in os.walk("outputs", topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            shutil.rmtree(os.path.join(root, name), ignore_errors=True)
    st.warning("All output files have been removed.")
