"""
processar_lote.py — Pipeline completo para um lote de repositorios.

Para cada repo do lote:
  1. Clona em repos/<owner>/<repo>
  2. Extrai via PyDriller: bug-fixes (por keyword) + LOC de todos os commits
     (janela = ultimos 5 anos)

Depois do batch:
  3. Aplica cap aleatorio de 100 fixes/repo (seed=42) — mesmo cap usado nos 58 originais
  4. Roda SZZ no subset
  5. Mescla resultados nos arquivos canonicos (sem duplicar):
       - szz_data/all_commits_loc.json
       - szz_data/bugfix_commits.json
       - pyszz/output_raszz.json
  6. Deleta APENAS os clones que ESTE script criou (preserva os pre-existentes)

USO:
  $env:GITHUB_TOKEN = "ghp_..."   # opcional, evita rate-limit
  python processar_lote.py lotes/lote_01.txt
  python processar_lote.py lotes/lote_01.txt --no-merge   # p/ rodar lotes em paralelo

Com --no-merge o script NAO toca nos arquivos canonicos compartilhados
(all_commits_loc.json, bugfix_commits.json, output_raszz.json). Em vez disso
grava o resultado do lote isolado em szz_data/parcial/<lote>_{all,bugfix,bic}.json.
Isso elimina a corrida de escrita quando varios lotes rodam ao mesmo tempo.
Depois que todos terminarem, rode `python merge_lotes.py` UMA vez para
consolidar tudo nos canonicos (passo sequencial, sem corrida).

Se algo falhar antes do merge, os clones NAO sao deletados (para depuracao).
"""

import json
import os
import random
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
REPOS_DIR     = Path("./repos")
SZZ_DATA      = Path("./szz_data")
PYSZZ_DIR     = Path("./pyszz")
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")

BUG_KEYWORDS = [
    "fix", "bug", "error", "hotfix", "patch",
    "defect", "fault", "issue", "crash", "exception",
    "correction", "repair", "resolve",
]
YEARS_BACK   = 5
CAP_PER_REPO = 100
SEED         = 42


# ─────────────────────────────────────────────
# UTILS
# ─────────────────────────────────────────────

def is_bug_fix(msg: str) -> bool:
    m = msg.lower()
    return any(k in m for k in BUG_KEYWORDS)


def clone(repo_name: str) -> tuple[Path | None, bool]:
    """Retorna (path, criado_agora). criado_agora=False se ja existia."""
    owner, repo = repo_name.split("/")
    target = REPOS_DIR / owner / repo
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_dir():
        return target, False
    cred = f"{GITHUB_TOKEN}@" if GITHUB_TOKEN else ""
    url = f"https://{cred}github.com/{repo_name}.git"
    try:
        r = subprocess.run(
            ["git", "clone", "--quiet", "--no-tags", url, str(target)],
            capture_output=True, timeout=1800,  # 30 min para repos grandes
        )
    except subprocess.TimeoutExpired:
        print(f"  [clone] TIMEOUT {repo_name} (>30min); pulando")
        # estado parcial pode ter sido criado — limpar
        if target.exists():
            try:
                shutil.rmtree(target, ignore_errors=True)
            except Exception:
                pass
        return None, False
    if r.returncode != 0:
        print(f"  [clone] ERRO {repo_name}: {r.stderr.decode(errors='ignore')[:140]}")
        return None, False
    return target, True


def extract(repo_name: str, repo_path: Path) -> tuple[list, list]:
    """
    Extrai commits via `git log --numstat`. Para cada commit no historico dos
    ultimos YEARS_BACK anos, calcula:
      loc           = soma de linhas adicionadas + removidas (numstat)
      files_changed = numero de arquivos modificados (numstat)
      is_merge      = >= 2 parents
      is_bug_fix    = mensagem contem alguma BUG_KEYWORDS

    Muito mais rapido que pydriller.modifications, que reabre o diff de cada arquivo.
    """
    since = f"{datetime.now().year - YEARS_BACK}-01-01"
    sep   = "\x1e"   # ASCII Record Separator — improvavel em mensagens de commit
    # %H hash | %P parents | %aI author iso | %s subject (1 linha)
    fmt = f"%H{sep}%P{sep}%aI{sep}%s"
    cmd = [
        "git", "-C", str(repo_path), "log", f"--since={since}",
        "--all", "--no-merges", "--numstat",
        f"--pretty=format:COMMIT{sep}{fmt}",
    ]
    # nota: --no-merges exclui merges do log, simplificando o parse.
    # commits de merge nao entram em all_commits nem em bugfix (consistente com
    # step1_adaptar_csv.py: bugfix_df = bugfix_df[bugfix_df['is_revert'] == False]
    # e step3_enriquecer_com_loc.py: skip if c.get('is_merge', False))

    try:
        out = subprocess.run(
            cmd, capture_output=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        print(f"  [extract] TIMEOUT git log {repo_name}")
        return [], []
    if out.returncode != 0:
        print(f"  [extract] ERRO git log {repo_name}: {out.stderr.decode(errors='ignore')[:140]}")
        return [], []

    text = out.stdout.decode("utf-8", errors="replace")
    bugfix, allc = [], []

    # Divide o stream em commits. Cada bloco comeca com "COMMIT<sep>".
    for block in text.split("COMMIT" + sep):
        block = block.strip()
        if not block:
            continue
        # primeira linha: hash<sep>parents<sep>iso<sep>subject
        # depois: linhas de numstat (added\tremoved\tfile)
        first_nl = block.find("\n")
        if first_nl == -1:
            header, rest = block, ""
        else:
            header, rest = block[:first_nl], block[first_nl + 1 :]
        parts = header.split(sep)
        if len(parts) < 4:
            continue
        h, parents, iso, subject = parts[0], parts[1], parts[2], sep.join(parts[3:])

        added_total = 0
        removed_total = 0
        files_n = 0
        for ln in rest.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            # numstat: "<added>\t<removed>\t<path>"; "-\t-\t<path>" para binarios
            cols = ln.split("\t", 2)
            if len(cols) < 3:
                continue
            a, r = cols[0], cols[1]
            if a == "-" or r == "-":
                files_n += 1
                continue
            try:
                added_total += int(a)
                removed_total += int(r)
                files_n += 1
            except ValueError:
                continue

        loc = added_total + removed_total
        is_merge_commit = len(parents.split()) >= 2  # com --no-merges sempre False
        bug = is_bug_fix(subject)

        allc.append({
            "repo_name":     repo_name,
            "hash":          h,
            "authored_date": iso,
            "loc":           loc,
            "files_changed": files_n,
            "is_merge":      is_merge_commit,
            "is_bug_fix":    bug,
            "message":       subject[:200],
        })
        if bug and not is_merge_commit:
            bugfix.append({"repo_name": repo_name, "fix_commit_hash": h})

    return bugfix, allc


def rmtree_force(p: Path):
    """rmtree resiliente a arquivos read-only do .git/pack (problema do Windows)."""
    def on_rm_error(func, path, exc_info):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass
    if p.is_dir():
        shutil.rmtree(p, onerror=on_rm_error)


def load_json(p: Path, default):
    return json.load(open(p, encoding="utf-8")) if p.exists() else default


def save_json(p: Path, data):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    argv = sys.argv[1:]
    no_merge = "--no-merge" in argv
    posicional = [a for a in argv if not a.startswith("--")]
    if not posicional:
        print("Uso: python processar_lote.py <lote_NN.txt> [--no-merge]")
        sys.exit(1)

    lote_path = Path(posicional[0])
    if not lote_path.exists():
        print(f"Arquivo nao encontrado: {lote_path}")
        sys.exit(1)

    repos = [
        r.strip() for r in lote_path.read_text(encoding="utf-8").splitlines()
        if r.strip() and not r.startswith("#")
    ]
    print(f"=== {lote_path.name} | {len(repos)} repos ===")
    for r in repos:
        print(f"  - {r}")

    # ── 1. clone + extract ──
    novos_bugfix: list = []
    novos_all:    list = []
    a_limpar: list[Path] = []  # todos os clones do lote sao removidos no final

    for r in repos:
        print(f"\n[clone] {r}")
        p, criado_agora = clone(r)
        if not p:
            continue
        a_limpar.append(p)
        if criado_agora:
            print(f"  novo clone: {p}")
        else:
            print(f"  reaproveitando: {p}")

        print(f"[extract] {r}")
        bf, ac = extract(r, p)
        print(f"  -> {len(ac)} commits, {len(bf)} bug-fixes")
        novos_bugfix.extend(bf)
        novos_all.extend(ac)

    if not novos_all:
        print("\nNada extraido. Abortando.")
        sys.exit(2)

    # ── 2. subset com cap 100/repo (seed=42) ──
    random.seed(SEED)
    by_repo: dict[str, list] = {}
    for bf in novos_bugfix:
        by_repo.setdefault(bf["repo_name"], []).append(bf)
    subset = []
    for repo_name, items in by_repo.items():
        if len(items) > CAP_PER_REPO:
            items = random.sample(items, CAP_PER_REPO)
        subset.extend(items)

    lote_name = lote_path.stem
    sub_path  = SZZ_DATA / f"bugfix_commits_{lote_name}.json"
    save_json(sub_path, subset)
    print(f"\n[szz input] {sub_path}: {len(subset)} fixes (cap {CAP_PER_REPO}/repo, seed={SEED})")

    # ── 3. roda SZZ ──
    print(f"\n[szz] iniciando...")
    out_dir = PYSZZ_DIR / "out"
    out_dir.mkdir(exist_ok=True)
    before = {p.name for p in out_dir.glob("bic_raszz_*.json") if not p.name.endswith(".partial.json")}
    r = subprocess.run(
        [sys.executable, "main.py", f"../{sub_path}", "conf/raszz.yml", "../repos"],
        cwd=str(PYSZZ_DIR),
    )
    if r.returncode != 0:
        print(f"[szz] FALHOU (rc={r.returncode}). Clones MANTIDOS para depuracao.")
        sys.exit(3)

    # ── 4. encontra output novo do SZZ ──
    after = sorted(
        [p for p in out_dir.glob("bic_raszz_*.json") if not p.name.endswith(".partial.json")],
        key=lambda x: x.stat().st_mtime,
    )
    novos = [p for p in after if p.name not in before]
    if not novos:
        print("[szz] nenhum output final novo encontrado. Abortando merge.")
        sys.exit(4)
    latest = novos[-1]
    print(f"[szz] output: {latest}")

    # ── 5a. modo paralelo: grava parciais isolados, NAO mexe nos canonicos ──
    if no_merge:
        parcial_dir = SZZ_DATA / "parcial"
        parcial_dir.mkdir(parents=True, exist_ok=True)
        p_all = parcial_dir / f"{lote_name}_all.json"
        p_bf  = parcial_dir / f"{lote_name}_bugfix.json"
        p_bic = parcial_dir / f"{lote_name}_bic.json"
        save_json(p_all, novos_all)
        save_json(p_bf, novos_bugfix)
        save_json(p_bic, load_json(latest, []))
        print(f"\n[no-merge] parciais gravados (sem tocar nos canonicos):")
        print(f"  {p_all}  ({len(novos_all):,} commits)")
        print(f"  {p_bf}   ({len(novos_bugfix):,} bug-fixes)")
        print(f"  {p_bic}  (output SZZ)")
        print(f"  -> rode `python merge_lotes.py` no fim para consolidar.")

        # cleanup dos clones deste lote (repos sao distintos entre lotes)
        print(f"\n[cleanup] removendo {len(a_limpar)} clones do lote...")
        for p in a_limpar:
            try:
                rmtree_force(p)
                print(f"  removido: {p}")
            except Exception as e:
                print(f"  FALHA remover {p}: {e}")
            try:
                if p.parent.is_dir() and not any(p.parent.iterdir()):
                    p.parent.rmdir()
            except Exception:
                pass
        print(f"\n=== {lote_path.name} CONCLUIDO (no-merge) ===")
        return

    # ── 5. merge ──
    # all_commits_loc.json
    all_loc_path = SZZ_DATA / "all_commits_loc.json"
    existing_all = load_json(all_loc_path, [])
    seen = {(x["repo_name"], x["hash"]) for x in existing_all}
    added = 0
    for c in novos_all:
        k = (c["repo_name"], c["hash"])
        if k not in seen:
            existing_all.append(c)
            seen.add(k)
            added += 1
    save_json(all_loc_path, existing_all)
    print(f"[merge] all_commits_loc.json: +{added} (total {len(existing_all):,})")

    # bugfix_commits.json
    bf_path = SZZ_DATA / "bugfix_commits.json"
    existing_bf = load_json(bf_path, [])
    seen_bf = {(x["repo_name"], x["fix_commit_hash"]) for x in existing_bf}
    added_bf = 0
    for b in novos_bugfix:
        k = (b["repo_name"], b["fix_commit_hash"])
        if k not in seen_bf:
            existing_bf.append(b)
            seen_bf.add(k)
            added_bf += 1
    save_json(bf_path, existing_bf)
    print(f"[merge] bugfix_commits.json: +{added_bf} (total {len(existing_bf):,})")

    # pyszz/output_raszz.json
    out_path = PYSZZ_DIR / "output_raszz.json"
    existing_out = load_json(out_path, [])
    seen_out = {(x["repo_name"], x["fix_commit_hash"]) for x in existing_out}
    novos_out = load_json(latest, [])
    added_out = 0
    for x in novos_out:
        k = (x["repo_name"], x["fix_commit_hash"])
        if k not in seen_out:
            existing_out.append(x)
            seen_out.add(k)
            added_out += 1
    save_json(out_path, existing_out)
    print(f"[merge] output_raszz.json:    +{added_out} (total {len(existing_out):,})")

    # ── 6. cleanup ──
    print(f"\n[cleanup] removendo {len(a_limpar)} clones do lote...")
    for p in a_limpar:
        try:
            rmtree_force(p)
            print(f"  removido: {p}")
        except Exception as e:
            print(f"  FALHA remover {p}: {e}")
        # tenta remover owner dir se ficou vazio
        try:
            if p.parent.is_dir() and not any(p.parent.iterdir()):
                p.parent.rmdir()
        except Exception:
            pass

    print(f"\n=== {lote_path.name} CONCLUIDO ===")


if __name__ == "__main__":
    main()
