"""
STEP 1 ADAPTADO — Converter CSV existente para formato pySZZ + clonar repositórios
====================================================================================
Você já tem o commits_metodologia.csv com a coluna is_bug_fix.
Este script:
  1. Lê o CSV
  2. Filtra os commits com is_bug_fix == True → esses são o INPUT do pySZZ
  3. Gera o bugfix_commits.json no formato exato que o pySZZ espera
  4. Clona localmente os repositórios necessários (pySZZ precisa do repo local)
  5. Gera o all_commits_loc.json com LOC de todos os commits (para o Step 3)

PRÉ-REQUISITOS:
  pip install pandas tqdm
  git instalado no sistema

COMO USAR:
  1. Defina GITHUB_TOKEN e os caminhos abaixo
  2. python step1_adaptar_csv.py
"""

import json
import os
import subprocess
import pandas as pd
from tqdm import tqdm

# ─────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────
CSV_PATH      = "commits_clean.csv"   # seu CSV existente
REPOS_DIR     = "./repos"                   # onde os repos serão clonados
OUTPUT_DIR    = "./szz_data"
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")  # exporte no ambiente: $env:GITHUB_TOKEN="ghp_..."

os.makedirs(REPOS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def clone_repo(repo_name: str) -> str | None:
    """Clona owner/repo em REPOS_DIR/owner/repo. Retorna o path ou None."""
    owner, repo = repo_name.split("/")
    repo_dir = os.path.join(REPOS_DIR, owner, repo)
    os.makedirs(os.path.join(REPOS_DIR, owner), exist_ok=True)

    if os.path.isdir(repo_dir):
        print(f"  ✓ {repo_name} já clonado, atualizando...")
        subprocess.run(["git", "-C", repo_dir, "pull", "--quiet"],
                       capture_output=True, timeout=120)
        return repo_dir

    print(f"  Clonando {repo_name}...")
    url = f"https://{GITHUB_TOKEN}@github.com/{repo_name}.git"
    result = subprocess.run(
        ["git", "clone", "--quiet", url, repo_dir],
        capture_output=True, timeout=600
    )
    if result.returncode != 0:
        print(f"  ✗ Erro: {result.stderr.decode()[:150]}")
        return None
    return repo_dir


def main():
    print(f"Lendo {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH)

    print(f"  Total de commits   : {len(df):,}")
    print(f"  is_bug_fix = True  : {df['is_bug_fix'].sum():,}")
    print(f"  is_bug_fix = False : {(~df['is_bug_fix']).sum():,}")
    print(f"  Repositórios       : {df['repo_name'].nunique()}")

    # ── 1. Gerar bugfix_commits.json para o pySZZ ──
    # O pySZZ espera uma lista de { "repo_name": "owner/repo", "fix_commit_hash": "abc123" }
    bug_fix_df = df[df["is_bug_fix"] == True].copy()

    # Excluir merges (commits com is_revert também podem ser excluídos opcionalmente)
    bug_fix_df = bug_fix_df[bug_fix_df["is_revert"] == False]

    bugfix_commits = [
        {
            "repo_name":       row["repo_name"],
            "fix_commit_hash": row["commit_sha"]
        }
        for _, row in bug_fix_df.iterrows()
    ]

    bugfix_path = os.path.join(OUTPUT_DIR, "bugfix_commits.json")
    with open(bugfix_path, "w") as f:
        json.dump(bugfix_commits, f, indent=2)
    print(f"\n✅ bugfix_commits.json gerado: {len(bugfix_commits):,} commits")

    # ── 2. Gerar all_commits_loc.json com TODOS os commits do CSV ──
    # Remove commits com LOC=0 e merges (is_revert pode ser mantido — são commits reais)
    df_clean = df[df["total_loc_modified"] > 0].copy()

    all_commits = [
        {
            "repo_name":     row["repo_name"],
            "hash":          row["commit_sha"],
            "authored_date": row["date"],
            "loc":           int(row["total_loc_modified"]),
            "files_changed": int(row["files_changed"]) if pd.notna(row["files_changed"]) else 0,
            "is_bug_fix":    bool(row["is_bug_fix"]),
            "is_revert":     bool(row["is_revert"]),
            "message":       str(row["message"])[:200] if pd.notna(row["message"]) else ""
        }
        for _, row in df_clean.iterrows()
    ]

    all_commits_path = os.path.join(OUTPUT_DIR, "all_commits_loc.json")
    with open(all_commits_path, "w") as f:
        json.dump(all_commits, f, indent=2)
    print(f"✅ all_commits_loc.json gerado: {len(all_commits):,} commits")

    # ── 3. Clonar repositórios necessários para o pySZZ ──
    repos = df["repo_name"].unique().tolist()
    print(f"\nClonando {len(repos)} repositórios (necessário para o pySZZ)...")

    repos_clonados = []
    repos_falhos   = []

    for repo_name in tqdm(repos, desc="Clonando repos"):
        path = clone_repo(repo_name)
        if path:
            repos_clonados.append(repo_name)
        else:
            repos_falhos.append(repo_name)

    print(f"\n  Clonados com sucesso : {len(repos_clonados)}")
    print(f"  Falhos               : {len(repos_falhos)}")
    if repos_falhos:
        print(f"  Repos com erro: {repos_falhos}")

    # ── Resumo e próximos passos ──
    print("\n" + "="*60)
    print("PRÓXIMO PASSO — Rodar o pySZZ com RA-SZZ:")
    print("="*60)
    print()
    print("  # Clonar e instalar pySZZ (uma vez só):")
    print("  git clone https://github.com/grosa1/pyszz_v2.git pyszz")
    print("  cd pyszz && pip install -r requirements.txt")
    print()
    print("  # Copiar o arquivo de configuração:")
    print("  cp ../raszz.yml conf/raszz.yml")
    print()
    print("  # Executar (pode demorar horas dependendo do volume):")
    print(f"  python main.py ../szz_data/bugfix_commits.json conf/raszz.yml ../{REPOS_DIR}")
    print()
    print("  # O output será salvo como output_raszz.json na pasta pyszz/")
    print()
    print("  Depois execute: python step3_enriquecer_com_loc.py")


if __name__ == "__main__":
    main()
