"""
merge_lotes.py — Consolida os parciais de szz_data/parcial/ nos arquivos canonicos.

Use isto APENAS depois de rodar varios lotes com `processar_lote.py ... --no-merge`.
Cada lote, no modo --no-merge, grava 3 arquivos isolados (sem corrida):

  szz_data/parcial/<lote>_all.json     -> merge em szz_data/all_commits_loc.json
  szz_data/parcial/<lote>_bugfix.json  -> merge em szz_data/bugfix_commits.json
  szz_data/parcial/<lote>_bic.json     -> merge em pyszz/output_raszz.json

Este script roda UMA vez, sequencialmente, entao nao ha condicao de corrida.
O merge e idempotente (dedup por chave) — rodar duas vezes nao duplica nada,
e os arquivos parciais NAO sao apagados (rode com --limpar para remove-los).

USO:
  python merge_lotes.py            # consolida; preserva os parciais
  python merge_lotes.py --limpar   # consolida e apaga szz_data/parcial/*
"""

import json
import sys
from pathlib import Path

SZZ_DATA    = Path("./szz_data")
PYSZZ_DIR   = Path("./pyszz")
PARCIAL_DIR = SZZ_DATA / "parcial"


def load_json(p: Path, default):
    return json.load(open(p, encoding="utf-8")) if p.exists() else default


def save_json(p: Path, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)


def merge_into(canonical: Path, parciais: list[Path], key_fn):
    """Le o canonico, anexa itens novos (por key_fn) de cada parcial, salva."""
    existing = load_json(canonical, [])
    seen = {key_fn(x) for x in existing}
    added = 0
    for pp in parciais:
        for item in load_json(pp, []):
            k = key_fn(item)
            if k not in seen:
                existing.append(item)
                seen.add(k)
                added += 1
    save_json(canonical, existing)
    print(f"[merge] {canonical}: +{added} (total {len(existing):,})  <- {len(parciais)} parcial(is)")
    return added


def main():
    limpar = "--limpar" in sys.argv[1:]

    if not PARCIAL_DIR.is_dir():
        print(f"Nada para consolidar: {PARCIAL_DIR} nao existe.")
        sys.exit(1)

    all_files = sorted(PARCIAL_DIR.glob("*_all.json"))
    bf_files  = sorted(PARCIAL_DIR.glob("*_bugfix.json"))
    bic_files = sorted(PARCIAL_DIR.glob("*_bic.json"))

    lotes = sorted({p.name.rsplit("_", 1)[0] for p in PARCIAL_DIR.glob("*_*.json")})
    print(f"=== merge_lotes: {len(lotes)} lote(s) em {PARCIAL_DIR} ===")
    for l in lotes:
        print(f"  - {l}")
    print()

    if not (all_files or bf_files or bic_files):
        print("Nenhum parcial encontrado. Abortando.")
        sys.exit(2)

    merge_into(
        SZZ_DATA / "all_commits_loc.json", all_files,
        key_fn=lambda x: (x["repo_name"], x["hash"]),
    )
    merge_into(
        SZZ_DATA / "bugfix_commits.json", bf_files,
        key_fn=lambda x: (x["repo_name"], x["fix_commit_hash"]),
    )
    merge_into(
        PYSZZ_DIR / "output_raszz.json", bic_files,
        key_fn=lambda x: (x["repo_name"], x["fix_commit_hash"]),
    )

    if limpar:
        n = 0
        for p in list(all_files) + list(bf_files) + list(bic_files):
            try:
                p.unlink()
                n += 1
            except Exception as e:
                print(f"  FALHA remover {p}: {e}")
        print(f"\n[limpar] {n} parcial(is) removido(s).")
    else:
        print(f"\nParciais preservados em {PARCIAL_DIR} (use --limpar para apagar).")

    print("\n=== merge concluido ===")


if __name__ == "__main__":
    main()
