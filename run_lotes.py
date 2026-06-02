#!/usr/bin/env python3
"""
run_lotes.py — Orquestrador "deixa rodar" para varios lotes.

Roda N lotes em paralelo (default 3). Assim que um termina, o proximo da fila
entra automaticamente (worker pool / encadeamento). Cada lote roda com --no-merge,
gravando parciais isolados em szz_data/parcial/ — sem corrida de escrita.

Robustez para rodar SEM ninguem monitorando:
  - Cada lote ja pula sozinho repos que falham/expiram no clone (30 min) e no
    extract (10 min) — vide processar_lote.py.
  - O SZZ pula fixes que TRAVAM via SZZ_FIX_TIMEOUT (default 20 min/fix) — um
    commit gigante com blame patologico nao prende mais o lote inteiro.
  - Um lote que falhar (rc != 0) NAO derruba os outros; o orquestrador segue.
  - Lotes que ja tem parcial gravado sao pulados (permite retomar de onde parou).

USO:
  python run_lotes.py 1 2 3 4 5              # roda lotes 1..5, 3 em paralelo
  python run_lotes.py 1-10                   # intervalo (lotes 1 a 10)
  python run_lotes.py -j 4 10 11 12 13       # 4 em paralelo
  python run_lotes.py --timeout 1800 7 8 9   # 30 min/fix
  python run_lotes.py --merge 1 2 3          # roda merge_lotes.py no fim
  python run_lotes.py --force 5              # reprocessa mesmo se ja tem parcial

No fim, se NAO usar --merge, rode voce mesmo (uma vez):
  python merge_lotes.py
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT      = Path(__file__).resolve().parent
LOTES_DIR = ROOT / "lotes"
PARCIAL   = ROOT / "szz_data" / "parcial"
LOGS      = ROOT / "logs"
RUN_LOTE  = ROOT / "run_lote.sh"

STATUS_EVERY = 30  # segundos entre as linhas de status no console


def expandir_specs(specs):
    """Converte ['1','3-5','lotes/lote_09.txt'] em [Path, ...] de arquivos de lote."""
    arquivos = []
    for s in specs:
        if "-" in s and all(p.isdigit() for p in s.split("-", 1)):
            a, b = s.split("-", 1)
            for n in range(int(a), int(b) + 1):
                arquivos.append(LOTES_DIR / f"lote_{n:02d}.txt")
        elif s.isdigit():
            arquivos.append(LOTES_DIR / f"lote_{int(s):02d}.txt")
        else:
            arquivos.append(Path(s))
    return arquivos


def ja_concluido(lote_file: Path) -> bool:
    """True se os 3 parciais do lote ja existem (lote ja rodou com --no-merge)."""
    stem = lote_file.stem
    return all((PARCIAL / f"{stem}_{x}.json").exists() for x in ("all", "bugfix", "bic"))


def progresso_szz(lote_file: Path) -> str:
    """Le a ultima linha de progresso 'N of M: repo' do log do lote."""
    log = LOGS / f"{lote_file.stem}.log"
    if not log.exists():
        return "iniciando"
    ultima = ""
    try:
        with open(log, "r", encoding="utf-8", errors="ignore") as f:
            for ln in f:
                seg = ln.split("::")[-1].strip()  # ex.: "593 of 762: usestrix/strix"
                parts = seg.split()
                if len(parts) >= 3 and parts[0].isdigit() and parts[1] == "of":
                    ultima = seg
    except Exception:
        return "?"
    return ultima[:48] if ultima else "clone/extract"


def main():
    ap = argparse.ArgumentParser(description="Orquestrador de lotes (pool paralelo).")
    ap.add_argument("specs", nargs="+", help="numeros, intervalos (1-5) ou caminhos de lote")
    ap.add_argument("-j", "--jobs", type=int, default=3, help="lotes em paralelo (default 3)")
    ap.add_argument("--timeout", type=int, default=1200, help="SZZ_FIX_TIMEOUT em segundos (default 1200 = 20 min)")
    ap.add_argument("--merge", action="store_true", help="roda merge_lotes.py ao final")
    ap.add_argument("--force", action="store_true", help="reprocessa lotes que ja tem parcial")
    args = ap.parse_args()

    LOGS.mkdir(exist_ok=True)
    PARCIAL.mkdir(parents=True, exist_ok=True)

    # ── monta a fila ──
    fila, pulados, faltando = [], [], []
    for f in expandir_specs(args.specs):
        if not f.exists():
            faltando.append(f)
            continue
        if not args.force and ja_concluido(f):
            pulados.append(f)
            continue
        fila.append(f)

    print(f"=== run_lotes | {args.jobs} em paralelo | timeout {args.timeout}s/fix ===")
    if faltando:
        print(f"  AUSENTES (ignorados): {', '.join(p.name for p in faltando)}")
    if pulados:
        print(f"  JA CONCLUIDOS (pulados, use --force p/ refazer): {', '.join(p.name for p in pulados)}")
    if not fila:
        print("  Nada a rodar.")
        if args.merge:
            _merge()
        return
    print(f"  A RODAR ({len(fila)}): {', '.join(p.name for p in fila)}\n")

    env = dict(os.environ, SZZ_FIX_TIMEOUT=str(args.timeout))
    fila = list(fila)
    rodando = {}   # Popen -> lote_file
    resultados = {}  # lote_file -> rc
    ultimo_status = 0.0

    def lancar(lote_file):
        # run_lote.sh ja faz: token do .env, caffeinate, log em logs/<lote>.log
        p = subprocess.Popen(
            ["bash", str(RUN_LOTE), str(lote_file.relative_to(ROOT)), "--no-merge"],
            cwd=str(ROOT), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        rodando[p] = lote_file
        print(f"[lancado] {lote_file.name}  (rodando: {len(rodando)})")

    # preenche o pool inicial
    while fila and len(rodando) < args.jobs:
        lancar(fila.pop(0))

    while rodando:
        # checa quem terminou
        for p in list(rodando):
            rc = p.poll()
            if rc is None:
                continue
            lote = rodando.pop(p)
            resultados[lote] = rc
            ok = "OK" if rc == 0 else f"FALHOU(rc={rc})"
            print(f"[fim] {lote.name}: {ok}  | restam na fila: {len(fila)}")
            if fila:
                lancar(fila.pop(0))

        # status periodico
        agora = time.time()
        if rodando and agora - ultimo_status >= STATUS_EVERY:
            ultimo_status = agora
            hora = time.strftime("%H:%M:%S")
            partes = [f"{l.name.replace('lote_','').replace('.txt','')}:{progresso_szz(l)}"
                      for l in rodando.values()]
            print(f"  [{hora}] rodando {len(rodando)} | fila {len(fila)} | " + " || ".join(partes))

        time.sleep(2)

    # ── resumo ──
    print("\n=== RESUMO ===")
    oks = [l.name for l, rc in resultados.items() if rc == 0]
    fail = [l.name for l, rc in resultados.items() if rc != 0]
    print(f"  concluidos OK: {len(oks)} -> {', '.join(oks) if oks else '-'}")
    if fail:
        print(f"  FALHARAM: {', '.join(fail)}  (cheque logs/<lote>.log)")

    if args.merge:
        _merge()
    else:
        print("\n  Para consolidar nos arquivos canonicos, rode UMA vez:")
        print("    python merge_lotes.py")


def _merge():
    print("\n=== merge_lotes.py ===")
    subprocess.run([sys.executable, str(ROOT / "merge_lotes.py")], cwd=str(ROOT))


if __name__ == "__main__":
    main()
