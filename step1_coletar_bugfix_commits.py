"""
STEP 1 — Coletar commits de correção de bug e preparar input para o pySZZ
=========================================================================
O que este script faz:
  1. Lê uma lista de repositórios Python do GitHub (via API GraphQL)
  2. Para cada repositório, clona localmente (necessário para o pySZZ)
  3. Usa o PyDriller para iterar todos os commits
  4. Identifica commits de correção por palavras-chave na mensagem
  5. Salva dois arquivos:
       - bugfix_commits.json  → entrada para o pySZZ (RA-SZZ)
       - all_commits_loc.json → LOC de TODOS os commits (usado no Step 3)

PRÉ-REQUISITOS:
  pip install pydriller gitpython requests tqdm
  git deve estar instalado no sistema

COMO USAR:
  1. Defina seu GITHUB_TOKEN abaixo
  2. Defina REPOS_DIR (onde os repos serão clonados)
  3. Defina REPOS_LIST_FILE (csv com coluna "repo_name" no formato "owner/repo")
     OU deixe o script buscar os 1000 repositórios automaticamente
  4. python step1_coletar_bugfix_commits.py
"""

import json
import os
import subprocess
import time
import requests
from tqdm import tqdm
from pydriller import Repository
from datetime import datetime, timezone

# ─────────────────────────────────────────────
# CONFIGURAÇÃO — edite aqui antes de rodar
# ─────────────────────────────────────────────
GITHUB_TOKEN    = "SEU_TOKEN_AQUI"          # token pessoal do GitHub
REPOS_DIR       = "./repos"                 # pasta onde os repos serão clonados
OUTPUT_DIR      = "./szz_data"              # pasta para os JSONs de saída
REPOS_LIST_FILE = None                      # None = busca automática | "repos.csv" = usa arquivo local
MAX_REPOS       = 100                       # quantos repositórios processar (comece com 100 para testar)
YEARS_BACK      = 5                         # janela temporal em anos

# Palavras-chave para identificar commits de correção
BUG_KEYWORDS = [
    "fix", "bug", "error", "hotfix", "patch",
    "defect", "fault", "issue", "crash", "exception",
    "correction", "repair", "resolve"
]

# ─────────────────────────────────────────────
# NÃO EDITE ABAIXO DESTA LINHA
# ─────────────────────────────────────────────

os.makedirs(REPOS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Content-Type":  "application/json"
}


def is_bug_fix_commit(message: str) -> bool:
    """Retorna True se a mensagem do commit contiver palavras-chave de bug."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in BUG_KEYWORDS)


def fetch_top_python_repos(limit: int = 1000) -> list[dict]:
    """
    Busca os repositórios Python mais ativos no GitHub via GraphQL API.
    Critérios: Python, >100 commits, >4 contribuidores, atividade recente.
    """
    print(f"Buscando top {limit} repositórios Python no GitHub...")
    repos = []
    cursor = None
    per_page = 25  # GraphQL tem limites por query

    # Data limite: últimos YEARS_BACK anos
    since_year = datetime.now().year - YEARS_BACK

    while len(repos) < limit:
        after_clause = f', after: "{cursor}"' if cursor else ""
        query = f"""
        {{
          search(
            query: "language:Python stars:>100 pushed:>{since_year}-01-01"
            type: REPOSITORY
            first: {per_page}
            {after_clause}
          ) {{
            pageInfo {{
              hasNextPage
              endCursor
            }}
            nodes {{
              ... on Repository {{
                nameWithOwner
                stargazerCount
                pushedAt
                defaultBranchRef {{
                  target {{
                    ... on Commit {{
                      history(first: 1) {{
                        totalCount
                      }}
                    }}
                  }}
                }}
                mentionableUsers {{
                  totalCount
                }}
              }}
            }}
          }}
        }}
        """
        resp = requests.post(
            "https://api.github.com/graphql",
            json={"query": query},
            headers=HEADERS,
            timeout=30
        )
        data = resp.json()

        if "errors" in data:
            print(f"  Erro na API: {data['errors']}")
            break

        search = data["data"]["search"]
        for node in search["nodes"]:
            if node is None:
                continue
            total_commits = 0
            try:
                total_commits = node["defaultBranchRef"]["target"]["history"]["totalCount"]
            except (TypeError, KeyError):
                pass

            contributors = node.get("mentionableUsers", {}).get("totalCount", 0)

            # Aplicar critérios de seleção
            if total_commits >= 100 and contributors > 4:
                repos.append({
                    "repo_name": node["nameWithOwner"],
                    "stars":     node["stargazerCount"],
                    "pushed_at": node["pushedAt"],
                    "commits":   total_commits
                })

        if not search["pageInfo"]["hasNextPage"]:
            break
        cursor = search["pageInfo"]["endCursor"]

        # Respeitar rate limit
        time.sleep(0.5)

        if len(repos) >= limit:
            break

    print(f"  {len(repos)} repositórios encontrados após filtragem.")
    return repos[:limit]


def clone_or_update_repo(repo_name: str) -> str | None:
    """
    Clona o repositório em REPOS_DIR/owner/repo.
    Se já existir, faz git pull para atualizar.
    Retorna o caminho local ou None em caso de erro.
    """
    owner, repo = repo_name.split("/")
    owner_dir = os.path.join(REPOS_DIR, owner)
    repo_dir  = os.path.join(owner_dir, repo)

    os.makedirs(owner_dir, exist_ok=True)

    if os.path.isdir(repo_dir):
        # Já existe — atualiza
        result = subprocess.run(
            ["git", "-C", repo_dir, "pull", "--quiet"],
            capture_output=True, timeout=120
        )
        if result.returncode != 0:
            return None
    else:
        # Clona pela primeira vez
        url = f"https://{GITHUB_TOKEN}@github.com/{repo_name}.git"
        result = subprocess.run(
            ["git", "clone", "--quiet", url, repo_dir],
            capture_output=True, timeout=300
        )
        if result.returncode != 0:
            print(f"    Erro ao clonar {repo_name}: {result.stderr.decode()[:100]}")
            return None

    return repo_dir


def collect_commits_from_repo(repo_name: str, repo_path: str) -> tuple[list, list]:
    """
    Itera todos os commits do repositório usando PyDriller.

    Retorna:
      bugfix_commits → lista de dicts no formato esperado pelo pySZZ
      all_commits    → lista de dicts com hash + LOC de TODOS os commits
    """
    bugfix_commits = []
    all_commits    = []

    since_dt = datetime(datetime.now().year - YEARS_BACK, 1, 1, tzinfo=timezone.utc)

    try:
        for commit in Repository(repo_path, since=since_dt).traverse_commits():
            loc = commit.insertions + commit.deletions
            files_changed = commit.files

            commit_info = {
                "repo_name":     repo_name,
                "hash":          commit.hash,
                "authored_date": commit.author_date.isoformat(),
                "loc":           loc,
                "files_changed": files_changed,
                "is_merge":      commit.merge,
                "message":       commit.msg[:200]  # trunca msg longa
            }
            all_commits.append(commit_info)

            # Verifica se é commit de correção
            if is_bug_fix_commit(commit.msg) and not commit.merge:
                bugfix_commits.append({
                    "repo_name":       repo_name,
                    "fix_commit_hash": commit.hash,
                    # earliest_issue_date pode ser adicionado depois se houver issue linkada
                })

    except Exception as e:
        print(f"    Erro ao processar {repo_name}: {e}")

    return bugfix_commits, all_commits


def main():
    # 1. Carregar lista de repositórios
    if REPOS_LIST_FILE and os.path.isfile(REPOS_LIST_FILE):
        import csv
        with open(REPOS_LIST_FILE) as f:
            reader = csv.DictReader(f)
            repos = [{"repo_name": row["repo_name"]} for row in reader]
        print(f"Carregados {len(repos)} repositórios de {REPOS_LIST_FILE}")
    else:
        repos = fetch_top_python_repos(limit=MAX_REPOS)

    # Salvar lista de repos para referência
    with open(os.path.join(OUTPUT_DIR, "repos_selecionados.json"), "w") as f:
        json.dump(repos, f, indent=2, ensure_ascii=False)

    all_bugfix_commits = []
    all_commits_global = []

    # 2. Para cada repositório: clonar + coletar commits
    for repo_info in tqdm(repos[:MAX_REPOS], desc="Processando repositórios"):
        repo_name = repo_info["repo_name"]

        # Clonar
        repo_path = clone_or_update_repo(repo_name)
        if not repo_path:
            continue

        # Coletar commits
        bugfix, all_commits = collect_commits_from_repo(repo_name, repo_path)
        all_bugfix_commits.extend(bugfix)
        all_commits_global.extend(all_commits)

        tqdm.write(
            f"  {repo_name}: {len(all_commits)} commits, "
            f"{len(bugfix)} bug-fix commits"
        )

    # 3. Salvar arquivos de saída
    bugfix_path     = os.path.join(OUTPUT_DIR, "bugfix_commits.json")
    all_commits_path = os.path.join(OUTPUT_DIR, "all_commits_loc.json")

    with open(bugfix_path, "w") as f:
        json.dump(all_bugfix_commits, f, indent=2, ensure_ascii=False)

    with open(all_commits_path, "w") as f:
        json.dump(all_commits_global, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Concluído!")
    print(f"   Bug-fix commits encontrados : {len(all_bugfix_commits)}")
    print(f"   Total de commits coletados  : {len(all_commits_global)}")
    print(f"   Arquivo para o pySZZ        : {bugfix_path}")
    print(f"   LOC de todos os commits     : {all_commits_path}")
    print()
    print("PRÓXIMO PASSO — rode o pySZZ com RA-SZZ:")
    print(f"  git clone https://github.com/grosa1/pyszz_v2.git pyszz")
    print(f"  cd pyszz")
    print(f"  pip install -r requirements.txt")
    print(f"  python main.py ../{bugfix_path} conf/raszz.yml ../{REPOS_DIR}")
    print(f"  # O output será salvo como 'output_raszz.json' na pasta do pySZZ")


if __name__ == "__main__":
    main()
