#!/usr/bin/env bash
# rodar_restantes.sh — Processa os 68 repos que faltaram e fecha o pipeline.
#
# Cobre, end-to-end:
#   1) SZZ nos lotes que nunca rodaram + repos avulsos:
#        - lotes inteiros:  34, 36, 37, 38, 39, 40, 41
#        - pendencias:      lote_42 (3 repos avulsos dos lotes 4/5/11)
#   2) merge_lotes.py  -> consolida parciais nos arquivos canonicos
#   3) step3           -> commits_classificados.csv + resumo_por_repo.csv
#   4) filtro de vies  -> mantem nos CSVs so os repos efetivamente rodados no SZZ
#                         (README §5; evita puxar o Spearman pra 0)
#   5) step4           -> testes + PNGs em szz_data/resultados/
#
# run_lotes.py ja pula lotes que tem parcial (idempotente) e o merge dedup por
# chave, entao reexecutar este script e seguro: ele so faz o que falta.
#
# USO:
#   bash rodar_restantes.sh              # roda tudo (2 lotes em paralelo)
#   JOBS=3 bash rodar_restantes.sh       # 3 em paralelo (use se a maquina aguentar)
#   bash rodar_restantes.sh --so-szz     # para apos o merge; nao roda step3/step4
set -uo pipefail
cd "$(dirname "$0")"

JOBS="${JOBS:-2}"            # lotes em paralelo (default 2; SZZ e pesado em I/O+CPU)
TIMEOUT="${TIMEOUT:-1200}"   # SZZ_FIX_TIMEOUT em segundos (20 min/fix)
PY=".venv/bin/python"
SO_SZZ=0
[ "${1:-}" = "--so-szz" ] && SO_SZZ=1

# Lotes que faltaram (inteiros) + lote_42 (pendencias dos 3 repos avulsos).
LOTES_RESTANTES="34 36-41 42"

echo "================================================================"
echo " rodar_restantes.sh | jobs=$JOBS | timeout=${TIMEOUT}s/fix"
echo " lotes: $LOTES_RESTANTES"
echo "================================================================"

# ── 1+2. SZZ nos lotes restantes, depois consolida (--merge) ──
"$PY" run_lotes.py -j "$JOBS" --timeout "$TIMEOUT" --merge $LOTES_RESTANTES
RC=$?
if [ "$RC" -ne 0 ]; then
  echo "!! run_lotes.py terminou com rc=$RC — confira logs/<lote>.log antes de seguir."
  exit "$RC"
fi

if [ "$SO_SZZ" -eq 1 ]; then
  echo ">> --so-szz: parando apos o merge. Rode step3/step4 manualmente quando quiser."
  exit 0
fi

# ── 3. enriquecimento com LOC (gera commits_classificados.csv + resumo_por_repo.csv) ──
export PYTHONIOENCODING=utf-8
echo; echo "=== step3_enriquecer_com_loc.py ==="
"$PY" step3_enriquecer_com_loc.py || { echo "!! step3 falhou"; exit 4; }

# ── 4. filtro de vies: manter so repos efetivamente rodados no SZZ (README §5) ──
echo; echo "=== filtro de vies (repos presentes em pyszz/output_raszz.json) ==="
"$PY" - <<'PYEOF'
import json, pandas as pd
repos_run = sorted({x["repo_name"] for x in json.load(open("pyszz/output_raszz.json"))})
print(f"  repos rodados no SZZ: {len(repos_run)}")
for csv in ["szz_data/commits_classificados.csv", "szz_data/resumo_por_repo.csv"]:
    df = pd.read_csv(csv)
    antes = df["repo_name"].nunique()
    df = df[df["repo_name"].isin(repos_run)]
    df.to_csv(csv, index=False)
    print(f"  {csv}: {antes} -> {df['repo_name'].nunique()} repos")
PYEOF

# ── 5. analise estatistica (Cochran-Armitage, chi2/Cramer, Spearman) + PNGs ──
echo; echo "=== step4_analise_estatistica.py ==="
"$PY" step4_analise_estatistica.py || { echo "!! step4 falhou"; exit 5; }

echo; echo "================================================================"
echo " CONCLUIDO. Resultados em szz_data/resultados/"
echo " Lembre: os slides (slides/Q1_ATUALIZADO.md) precisam do N atualizado."
echo "================================================================"
