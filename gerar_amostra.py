import json, pandas as pd

df = pd.read_csv("commits_clean.csv")

# Escolha 5 repos menores para o teste ser mais rápido
repos_teste = [
    "scrapy/scrapy",
    "pallets/flask",
    "Textualize/rich",
    "django/django",
    "scikit-learn/scikit-learn"
]

df_teste = df[
    (df["repo_name"].isin(repos_teste)) &
    (df["is_bug_fix"] == True) &
    (df["is_revert"] == False)
]

bugfix = [
    {"repo_name": row["repo_name"], "fix_commit_hash": row["commit_sha"]}
    for _, row in df_teste.iterrows()
]

with open("szz_data/bugfix_commits_teste.json", "w") as f:
    json.dump(bugfix, f, indent=2)

print(f"Gerado: {len(bugfix)} bug-fix commits de {len(repos_teste)} repos")