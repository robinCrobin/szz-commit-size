"""
gerar_lotes.py — Gera arquivos lotes/lote_NN.txt com 10 repos cada,
em ordem de popularidade (stars), excluindo:
  - repos ja processados (presentes em pyszz/output_raszz.json)
  - repos excluidos por incidente (pytorch, AutoGPT)
  - repos que nao sao codigo (awesome-lists, cheatsheets, skill packs, livros)

USO:
  python gerar_lotes.py
"""

import csv
import json
import os
import re
from pathlib import Path

CSV_POP    = Path("repos_python_populares.csv")
SZZ_OUT    = Path("pyszz/output_raszz.json")
LOTES_DIR  = Path("lotes")
TAM_LOTE   = 10

# Repos manualmente excluidos (vide METODOLOGIA.md §7.5)
EXCLUIDOS_HARD = {"pytorch/pytorch", "Significant-Gravitas/AutoGPT"}

# Padroes (substring case-insensitive) que indicam repo nao-codigo:
# listas curadas, cheatsheets, skill packs, livros, hosts files, etc.
PADROES_SKIP = [
    "public-apis",
    "awesome",
    "cheatsheet",
    "-skill",          # *-skills, *-skill-*, etc
    "skills-",
    "/skills",
    "exercises",
    "howto",
    "free-programming",
    "free-llm-api",
    "professional-programming",
    "developer-portfolios",
    "hellogithub",
    "linux-insides",
    "ml-engineering",
    "cookbook",
    "wtfpython",
    "supertinyicons",
    "ungoogled-chromium",  # patches, nao codigo Python
    "chinese-independent-blogs",
    "linkedin-skill",
    "free-claude-code",
    "claude-code-templates",
    "claude-howto",
    "/claude-skills",
    "/agentskills",
    "/agent-skills-for",
    "stevenblack/hosts",
    "cs249r_book",
    "/ddia",
    "rossant/awesome-math",
    "python-cheatsheet",
    "/hosts",
    "chinese-llama-alpaca",  # mais peso, mas e modelo+docs
]

def eh_nao_codigo(repo_name: str) -> bool:
    rn = repo_name.lower()
    return any(p in rn for p in PADROES_SKIP)

def main():
    # 1. ja processados
    done = set()
    if SZZ_OUT.exists():
        data = json.load(open(SZZ_OUT))
        done = {x["repo_name"] for x in data}
    print(f"Ja processados: {len(done)}")

    # 2. ler CSV (ordem = popularidade)
    candidatos = []
    pulados_nao_codigo = []
    with open(CSV_POP, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rn = f"{row['owner']}/{row['name']}"
            if rn in done or rn in EXCLUIDOS_HARD:
                continue
            if eh_nao_codigo(rn):
                pulados_nao_codigo.append(rn)
                continue
            candidatos.append(rn)

    print(f"Excluidos por filtro 'nao-codigo': {len(pulados_nao_codigo)}")
    print(f"  Exemplos: {pulados_nao_codigo[:6]}")
    print(f"Candidatos finais: {len(candidatos)}")

    # 3. gerar arquivos de lote
    LOTES_DIR.mkdir(exist_ok=True)
    n_lotes = (len(candidatos) + TAM_LOTE - 1) // TAM_LOTE
    for i in range(n_lotes):
        lote = candidatos[i * TAM_LOTE : (i + 1) * TAM_LOTE]
        path = LOTES_DIR / f"lote_{i + 1:02d}.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Lote {i+1}/{n_lotes} — {len(lote)} repos\n")
            for r in lote:
                f.write(r + "\n")
    print(f"\n{n_lotes} lotes gerados em {LOTES_DIR}/")
    print(f"\nPrimeiro lote (lote_01.txt):")
    for r in candidatos[:TAM_LOTE]:
        print(f"  - {r}")

if __name__ == "__main__":
    main()
