# Erros registrados — execução dos lotes restantes (rodar_restantes.sh)

## 2026-06-15 — Lote 38 travou em NVIDIA/TensorRT-LLM

- **Repositório:** `NVIDIA/TensorRT-LLM` (lote 38)
- **Fix:** `ad4226d946575546ecf429e3f6cb8abdcc02f69f` (fix 66 de 867 do lote)
- **Sintoma:** `FIX TIMEOUT` disparou às 01:27:34 (SZZ_FIX_TIMEOUT=1200s), mas o
  processo `main.py` (PID 84798) ficou pendurado em seguida — estado `SN`
  (sleeping), 0% CPU, sem nenhum subprocesso git filho, por ~5h30 até ser morto.
- **Causa raiz:** após o timeout, o `del szz_inst` (pyszz/main.py:173) aciona o
  teardown do GitPython/PyDriller sobre um processo de blame que foi interrompido
  no meio pelo SIGALRM → deadlock no cleanup. O timeout *registra* o aviso mas o
  fix seguinte nunca começa. É determinístico para fixes patológicos desse repo
  (arquivos enormes / blame explosivo em `tensorrt_llm/llmapi/mpi_session.py`).
- **Ação:** `NVIDIA/TensorRT-LLM` EXCLUÍDO do universo (mesmo precedente de
  `pytorch/pytorch` e `Significant-Gravitas/AutoGPT`, CLAUDE.md §"Repositories
  excluded"). Lote 38 reprocessado sem ele (`lotes/lote_38b.txt`).
- **Impacto nos resultados:** universo final perde 1 repo (TensorRT-LLM). Os
  outros 9 repos do lote 38 entram normalmente.

## 2026-06-15 — Lote 42 (pendencias): timeout de extracao em 2 repos

- **`ccxt/ccxt`** (lote 42)
  - **Sintoma:** `git log --numstat --all` estourou o timeout de extracao
    (600s, processar_lote.py:127) por causa do historico gigante → 0 commits,
    0 bug-fixes extraidos.
  - **Acao:** EXCLUIDO do universo (decisao do usuario em 2026-06-15: nao vale o
    custo de reprocessar 1 repo de 460). Codigo real, mas extracao inviavel no
    timeout padrao.
- **`SimplifyJobs/Summer2026-Internships`** (lote 42)
  - **Sintoma:** mesmo timeout de `git log`. Na pratica e repo NAO-CODIGO
    (listagem de vagas em markdown, commits automaticos), pertence ao mesmo
    grupo dos 38 repos filtrados por PADROES_SKIP em gerar_lotes.py.
  - **Acao:** EXCLUIDO (nao-codigo).

## Resumo do universo final (2026-06-15)

- CSV de populares: 500 repos
- Nos resultados (pyszz/output_raszz.json): **460 repos**
- Filtrados como nao-codigo (PADROES_SKIP) + hard-excludes: 38
- Excluidos por incidente de execucao: 2 (NVIDIA/TensorRT-LLM, ccxt/ccxt)
  - obs.: SimplifyJobs/Summer2026-Internships conta como nao-codigo, nao incidente
- 500 = 460 + 38 + 2 ✓
