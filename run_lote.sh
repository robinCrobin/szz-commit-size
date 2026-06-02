#!/usr/bin/env bash
# run_lote.sh <lote_NN.txt> [args extras...] — roda um lote sob caffeinate,
# carregando o token do .env. Args extras sao repassados ao processar_lote.py
# (ex.: --no-merge para rodar lotes em paralelo).
# Loga em logs/<lote>.log. Uso: bash run_lote.sh lotes/lote_10.txt [--no-merge]
set -uo pipefail
cd "$(dirname "$0")"

LOTE="${1:?uso: run_lote.sh lotes/lote_NN.txt [--no-merge]}"
shift  # remove o lote dos argumentos; o resto ($@) vai pro processar_lote.py
NAME="$(basename "$LOTE" .txt)"
LOG="logs/${NAME}.log"

# carrega GITHUB_TOKEN do .env sem vazar no log
if [ -f .env ]; then
  export GITHUB_TOKEN="$(grep -E '^GITHUB_TOKEN=' .env | head -1 | cut -d= -f2- | tr -d '"'"'"' \r')"
fi
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1
# Pula fixes que travam (ex.: blame patologico em commit gigante). Default 20 min
# por fix; respeita o valor herdado se o orquestrador ja tiver exportado.
export SZZ_FIX_TIMEOUT="${SZZ_FIX_TIMEOUT:-1200}"

{
  echo "===== INICIO $NAME @ $(date '+%Y-%m-%d %H:%M:%S') ====="
  echo "token: $([ -n "${GITHUB_TOKEN:-}" ] && echo presente || echo AUSENTE)"
} >> "$LOG"

# caffeinate -i (idle) -m (disco) -s (system, vale no AC) envolve o processo todo
caffeinate -i -m -s .venv/bin/python processar_lote.py "$LOTE" "$@" >> "$LOG" 2>&1
RC=$?

echo "===== FIM $NAME rc=$RC @ $(date '+%Y-%m-%d %H:%M:%S') =====" >> "$LOG"
exit $RC
