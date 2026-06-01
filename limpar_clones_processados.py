"""
limpar_clones_processados.py — Remove os clones em repos/ cujos dados ja foram
extraidos e estao em pyszz/output_raszz.json. Operacao one-shot.

Preserva:
  - Quaisquer clones que NAO estao no output_raszz.json (futuros lotes em transito)
  - Owner dirs que ainda tem outros sub-repos

USO:
  python limpar_clones_processados.py            # dry-run (apenas lista)
  python limpar_clones_processados.py --apply    # deleta de fato
"""

import json
import os
import shutil
import stat
import sys
from pathlib import Path

REPOS_DIR = Path("./repos")
SZZ_OUT   = Path("./pyszz/output_raszz.json")


def rmtree_force(p: Path):
    def on_rm_error(func, path, exc_info):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass
    if p.is_dir():
        shutil.rmtree(p, onerror=on_rm_error)


def main():
    apply = "--apply" in sys.argv

    if not SZZ_OUT.exists():
        print(f"ERRO: {SZZ_OUT} nao encontrado.")
        sys.exit(1)

    processados = {x["repo_name"] for x in json.load(open(SZZ_OUT))}
    print(f"Repos com dados em output_raszz.json: {len(processados)}")

    # tambem inclui pytorch e AutoGPT (excluidos por incidente; clones nao servem)
    excluidos = {"pytorch/pytorch", "Significant-Gravitas/AutoGPT"}
    alvos = processados | excluidos

    a_deletar = []
    nao_no_disco = []
    preservados  = []

    for repo_name in sorted(alvos):
        owner, repo = repo_name.split("/")
        target = REPOS_DIR / owner / repo
        if target.is_dir():
            a_deletar.append(target)
        else:
            nao_no_disco.append(repo_name)

    # tambem detecta clones em disco que NAO estao na lista (preservar)
    if REPOS_DIR.is_dir():
        for owner_dir in REPOS_DIR.iterdir():
            if not owner_dir.is_dir():
                continue
            for repo_dir in owner_dir.iterdir():
                if not repo_dir.is_dir():
                    continue
                rn = f"{owner_dir.name}/{repo_dir.name}"
                if rn not in alvos:
                    preservados.append(rn)

    print(f"\nAlvos no disco a deletar: {len(a_deletar)}")
    print(f"Alvos nao-presentes no disco (ok, ja limpos): {len(nao_no_disco)}")
    print(f"Outros clones preservados (nao processados): {len(preservados)}")
    for p in preservados:
        print(f"  PRESERVADO: {p}")

    if not apply:
        print(f"\n[DRY-RUN] Use --apply para deletar de fato.")
        return

    print(f"\nDeletando {len(a_deletar)} clones...")
    for p in a_deletar:
        try:
            rmtree_force(p)
            print(f"  removido: {p}")
            # remove owner dir se ficou vazio
            if p.parent.is_dir() and not any(p.parent.iterdir()):
                p.parent.rmdir()
        except Exception as e:
            print(f"  FALHA {p}: {e}")

    print("\nLimpeza concluida.")


if __name__ == "__main__":
    main()
