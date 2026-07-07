import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

def plot_scores(ranking_csv: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(ranking_csv)

    # Bar chart: Overall scores
    plt.figure(figsize=(10, 6))
    sns.barplot(data=df, x="name", y="Score", palette="Blues_d")
    plt.title("Candidate Overall Scores")
    plt.ylabel("Score")
    plt.xlabel("Candidate")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_dir / "overall_scores.png")
    plt.close()

    # Stacked bar chart: Skill Matches and Years of Experiences
    plt.figure(figsize=(10, 6))
    df_sorted = df.sort_values("Score", ascending=False)
    bottom = df_sorted["Years of Experiences"]
    plt.bar(df_sorted["name"], df_sorted["Years of Experiences"], label="Years of Experiences")
    plt.bar(df_sorted["name"], df_sorted["Skill Matches"], bottom=bottom, label="Skill Matches")
    plt.title("Score Breakdown by Candidate")
    plt.ylabel("Count")
    plt.xlabel("Candidate")
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "score_breakdown.png")
    plt.close()

    # Optionally: annotate education field as text below the x-axis
    # (not as a bar, since it's categorical)

    print(f"Plots saved to: {output_dir}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate plots from ranking results")
    parser.add_argument("--ranking-csv", type=Path, required=True, help="CSV file with candidate scores")
    parser.add_argument("--output-dir", type=Path, required=True, help="Folder to save plots")
    args = parser.parse_args()

    plot_scores(args.ranking_csv, args.output_dir)
