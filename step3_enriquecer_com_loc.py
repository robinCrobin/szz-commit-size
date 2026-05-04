"""
STEP 3 — Enriquecer output do pySZZ com LOC e montar os dois grupos
====================================================================
O que este script faz:
  1. Lê o output do pySZZ (output_raszz.json) que contém os bug-introducing
     commits identificados pelo RA-SZZ
  2. Lê o all_commits_loc.json gerado no Step 1 (LOC de todos os commits)
  3. Classifica cada commit em:
       Grupo A → bug-introducing (identificado pelo RA-SZZ)
       Grupo B → todos os outros commits (não bug-introducing)
  4. Exporta dois arquivos:
       - commits_classificados.csv  → tabela completa com grupo de cada commit
       - resumo_por_repo.csv        → médias agregadas por repositório (para Q1 agregada)

PRÉ-REQUISITOS:
  pip install pandas tqdm

COMO USAR:
  Ajuste os caminhos abaixo e execute:
  python step3_enriquecer_com_loc.py
"""

import json
import pandas as pd
from tqdm import tqdm

# ─────────────────────────────────────────────
# CAMINHOS — ajuste conforme sua estrutura
# ─────────────────────────────────────────────
PYSZZ_OUTPUT    = "./pyszz/output_raszz.json"   # output gerado pelo pySZZ
ALL_COMMITS_LOC = "./szz_data/all_commits_loc.json"  # gerado no step 1
OUTPUT_CSV      = "./szz_data/commits_classificados.csv"
RESUMO_CSV      = "./szz_data/resumo_por_repo.csv"


def load_pyszz_output(path: str) -> dict[str, list]:
    """
    Lê o JSON do pySZZ e retorna um dicionário:
      { fix_commit_hash → [bug_introducing_commit_hash, ...] }

    O formato do output do pySZZ é uma lista de objetos assim:
    [
      {
        "repo_name": "owner/repo",
        "fix_commit_hash": "abc123",
        "inducing_commit_hash": ["def456", "ghi789"]
      },
      ...
    ]
    """
    with open(path) as f:
        raw = json.load(f)

    # Coleta todos os hashes de bug-introducing commits em um set para lookup O(1)
    inducing_hashes = set()
    fix_to_inducing = {}

    for entry in raw:
        fix_hash = entry.get("fix_commit_hash", "")
        inducing = entry.get("inducing_commit_hash", [])

        if inducing is None:
            inducing = []

        fix_to_inducing[fix_hash] = inducing
        for h in inducing:
            if h:
                inducing_hashes.add(h)

    print(f"  Bug-fix commits no output pySZZ : {len(fix_to_inducing)}")
    print(f"  Bug-introducing commits únicos  : {len(inducing_hashes)}")
    return inducing_hashes, fix_to_inducing


def load_all_commits(path: str) -> list[dict]:
    """Carrega o JSON de todos os commits gerado no Step 1."""
    with open(path) as f:
        return json.load(f)


def classify_commits(all_commits: list[dict], inducing_hashes: set) -> pd.DataFrame:
    """
    Classifica cada commit como:
      - 'bug_introducing'   → identificado pelo RA-SZZ
      - 'not_bug_inducing'  → todos os outros
    Exclui merge commits e commits sem modificações (LOC == 0).
    """
    rows = []

    for c in tqdm(all_commits, desc="Classificando commits"):
        # Excluir merges e commits vazios
        if c.get("is_merge", False):
            continue
        if c.get("loc", 0) == 0:
            continue

        grupo = "bug_introducing" if c["hash"] in inducing_hashes else "not_bug_inducing"

        rows.append({
            "repo_name":     c["repo_name"],
            "commit_hash":   c["hash"],
            "authored_date": c.get("authored_date", ""),
            "loc":           c["loc"],
            "files_changed": c.get("files_changed", 0),
            "message":       c.get("message", "")[:100],
            "grupo":         grupo
        })

    return pd.DataFrame(rows)


def compute_repo_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega os dados por repositório para análise em nível de projeto.
    Útil para Q1 na visão agregada (Spearman por repo).

    Para cada repositório calcula:
      - loc_medio_todos      → LOC médio de todos os commits
      - loc_medio_inducing   → LOC médio dos bug-introducing commits
      - loc_medio_normal     → LOC médio dos commits não bug-introducing
      - total_commits        → total de commits analisados
      - n_bug_inducing       → número de bug-introducing commits
      - taxa_bug_inducing    → % de commits que são bug-introducing
    """
    resumos = []

    for repo_name, grp in df.groupby("repo_name"):
        inducing = grp[grp["grupo"] == "bug_introducing"]
        normal   = grp[grp["grupo"] == "not_bug_inducing"]

        resumos.append({
            "repo_name":            repo_name,
            "total_commits":        len(grp),
            "n_bug_inducing":       len(inducing),
            "taxa_bug_inducing_pct": round(len(inducing) / len(grp) * 100, 2) if len(grp) > 0 else 0,
            "loc_medio_todos":      round(grp["loc"].mean(), 2),
            "loc_medio_inducing":   round(inducing["loc"].mean(), 2) if len(inducing) > 0 else None,
            "loc_medio_normal":     round(normal["loc"].mean(), 2)   if len(normal) > 0   else None,
            "loc_mediana_todos":    round(grp["loc"].median(), 2),
            "loc_mediana_inducing": round(inducing["loc"].median(), 2) if len(inducing) > 0 else None,
            "loc_mediana_normal":   round(normal["loc"].median(), 2)   if len(normal) > 0   else None,
            "loc_p75_todos":        round(grp["loc"].quantile(0.75), 2),
        })

    return pd.DataFrame(resumos)


def print_preview(df: pd.DataFrame) -> None:
    """Imprime estatísticas descritivas dos dois grupos."""
    grupo_a = df[df["grupo"] == "bug_introducing"]["loc"]
    grupo_b = df[df["grupo"] == "not_bug_inducing"]["loc"]

    print("\n" + "="*60)
    print("ESTATÍSTICAS DESCRITIVAS")
    print("="*60)

    print(f"\nGrupo A — Bug-Introducing (n={len(grupo_a):,})")
    print(f"  Média   : {grupo_a.mean():.1f} LOC")
    print(f"  Mediana : {grupo_a.median():.1f} LOC")
    print(f"  P75     : {grupo_a.quantile(0.75):.1f} LOC")
    print(f"  P90     : {grupo_a.quantile(0.90):.1f} LOC")
    print(f"  Máximo  : {grupo_a.max():.1f} LOC")

    print(f"\nGrupo B — Não Bug-Introducing (n={len(grupo_b):,})")
    print(f"  Média   : {grupo_b.mean():.1f} LOC")
    print(f"  Mediana : {grupo_b.median():.1f} LOC")
    print(f"  P75     : {grupo_b.quantile(0.75):.1f} LOC")
    print(f"  P90     : {grupo_b.quantile(0.90):.1f} LOC")
    print(f"  Máximo  : {grupo_b.max():.1f} LOC")

    print(f"\nTotal de commits classificados: {len(df):,}")
    print(f"  Bug-introducing   : {len(grupo_a):,} ({len(grupo_a)/len(df)*100:.1f}%)")
    print(f"  Não bug-inducing  : {len(grupo_b):,} ({len(grupo_b)/len(df)*100:.1f}%)")
    print("="*60)


def main():
    print("Carregando output do pySZZ...")
    inducing_hashes, _ = load_pyszz_output(PYSZZ_OUTPUT)

    print("Carregando todos os commits...")
    all_commits = load_all_commits(ALL_COMMITS_LOC)
    print(f"  Total de commits no arquivo: {len(all_commits):,}")

    print("Classificando commits nos dois grupos...")
    df = classify_commits(all_commits, inducing_hashes)

    print_preview(df)

    print("\nComputando resumo por repositório...")
    df_resumo = compute_repo_summary(df)

    # Salvar CSVs
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    df_resumo.to_csv(RESUMO_CSV, index=False, encoding="utf-8")

    print(f"\n✅ Arquivos salvos:")
    print(f"   {OUTPUT_CSV}  ({len(df):,} linhas)")
    print(f"   {RESUMO_CSV} ({len(df_resumo):,} repositórios)")
    print()
    print("PRÓXIMO PASSO:")
    print("   python step4_analise_estatistica.py")


if __name__ == "__main__":
    main()
