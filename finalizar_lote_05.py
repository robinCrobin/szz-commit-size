"""
Finaliza o lote 05 aproveitando o partial salvo antes do kill.

  * Re-extrai LOC/bug-fixes dos 9 repos ainda clonados (pulando o que falhou
    no clone: ccxt).
  * Mescla nos canonicos (all_commits_loc, bugfix_commits).
  * Filtra do partial apenas os fixes que ja foram processados pelo SZZ
    (criterio: campo `inducing_commit_hash` presente).
  * Mescla no output_raszz.json.
  * Limpa os 9 clones do lote.

Uso:  python finalizar_lote_05.py
"""
import json, os, shutil, stat
from pathlib import Path

import sys; sys.path.insert(0, '.')
from processar_lote import extract, rmtree_force, load_json, save_json

LOTE_TXT     = Path("lotes/lote_05.txt")
PARTIAL_PATH = Path("pyszz/out/bic_raszz_1780313166.partial.json")
ALL_LOC      = Path("szz_data/all_commits_loc.json")
BF_PATH      = Path("szz_data/bugfix_commits.json")
OUT_RASZZ    = Path("pyszz/output_raszz.json")
REPOS_DIR    = Path("repos")

def main():
    repos = [r.strip() for r in LOTE_TXT.read_text().splitlines() if r.strip() and not r.startswith("#")]
    print(f"Lote: {len(repos)} repos")

    # 1. re-extract dos que estao no disco
    novos_bf, novos_ac = [], []
    encontrados = []
    for r in repos:
        owner, name = r.split("/")
        p = REPOS_DIR / owner / name
        if not p.is_dir():
            print(f"  [skip extract] nao clonado: {r}")
            continue
        print(f"  [extract] {r}")
        bf, ac = extract(r, p)
        print(f"    -> {len(ac)} commits, {len(bf)} bug-fixes")
        novos_bf.extend(bf)
        novos_ac.extend(ac)
        encontrados.append((r, p))

    # 2. merge canonicos
    print("\n[merge] all_commits_loc.json...")
    existing = load_json(ALL_LOC, [])
    seen = {(x["repo_name"], x["hash"]) for x in existing}
    added = 0
    for c in novos_ac:
        k = (c["repo_name"], c["hash"])
        if k not in seen:
            existing.append(c)
            seen.add(k)
            added += 1
    save_json(ALL_LOC, existing)
    print(f"  +{added} (total {len(existing):,})")

    print("[merge] bugfix_commits.json...")
    existing = load_json(BF_PATH, [])
    seen = {(x["repo_name"], x["fix_commit_hash"]) for x in existing}
    added = 0
    for b in novos_bf:
        k = (b["repo_name"], b["fix_commit_hash"])
        if k not in seen:
            existing.append(b)
            seen.add(k)
            added += 1
    save_json(BF_PATH, existing)
    print(f"  +{added} (total {len(existing):,})")

    # 3. merge partial -> output_raszz (so processados)
    print(f"\n[merge] {OUT_RASZZ.name} <- {PARTIAL_PATH.name}...")
    partial = load_json(PARTIAL_PATH, [])
    processados = [x for x in partial if "inducing_commit_hash" in x]
    nao_proc    = len(partial) - len(processados)
    print(f"  partial total: {len(partial)} | processados: {len(processados)} | pendentes (descartados): {nao_proc}")

    existing = load_json(OUT_RASZZ, [])
    seen = {(x["repo_name"], x["fix_commit_hash"]) for x in existing}
    added = 0
    for x in processados:
        k = (x["repo_name"], x["fix_commit_hash"])
        if k not in seen:
            existing.append(x)
            seen.add(k)
            added += 1
    save_json(OUT_RASZZ, existing)
    print(f"  +{added} (total {len(existing):,})")

    # 4. cleanup clones
    print(f"\n[cleanup] removendo {len(encontrados)} clones...")
    for r, p in encontrados:
        try:
            rmtree_force(p)
            print(f"  removido: {p}")
            if p.parent.is_dir() and not any(p.parent.iterdir()):
                p.parent.rmdir()
        except Exception as e:
            print(f"  FALHA {p}: {e}")

    print("\n=== finalizacao do lote_05 ok ===")

if __name__ == "__main__":
    main()
