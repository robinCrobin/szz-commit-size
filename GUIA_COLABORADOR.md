# Guia do colaborador — rodar os lotes restantes

Este guia é para quem vai processar **lotes de repositórios** em paralelo, numa
máquina diferente. O fluxo de lote é **autocontido**: cada lote clona seus
próprios repos, extrai LOC/bug-fixes direto do `git log`, roda o SZZ e mescla os
resultados. **Você NÃO precisa** dos arquivos grandes de dados
(`commits_clean.csv`, `all_commits_loc.json`, `repos/`); eles são gerados
localmente conforme você roda.

## Status dos lotes

- **Lotes 01–06: JÁ PROCESSADOS** (não refazer).
- **Lotes 07–41: PENDENTES.** São esses que você vai rodar.

Combine com o restante do grupo quem pega qual faixa (ex.: você faz 07–20, outra
pessoa 21–41) para ninguém repetir lote.

## Setup (uma vez)

```powershell
git clone https://github.com/robinCrobin/szz-commit-size.git
cd szz-commit-size

python -m venv venv_szz
.\venv_szz\Scripts\Activate.ps1

pip install -r requirements.txt
pip install -r pyszz\requirements.txt

# Token do GitHub para não bater rate-limit ao clonar (recomendado).
# Gere em https://github.com/settings/tokens (escopo public_repo basta).
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"
$env:PYTHONIOENCODING = "utf-8"
```

Requer `git` no PATH e Python 3.10+.

## Rodar um lote

```powershell
python processar_lote.py lotes\lote_07.txt
```

O script faz tudo de ponta a ponta para os 10 repos do lote:

1. Clona cada repo em `repos/<owner>/<repo>`.
2. Extrai commits dos últimos 5 anos (LOC, arquivos, bug-fix por keyword).
3. Aplica cap de 100 fixes/repo (seed=42, mesmo critério dos 58 originais).
4. Roda o SZZ (MA-SZZ, ver `CLAUDE.md`/`METODOLOGIA.md`).
5. **Mescla** sem duplicar em:
   - `szz_data/all_commits_loc.json`
   - `szz_data/bugfix_commits.json`
   - `pyszz/output_raszz.json`
6. Apaga só os clones que **este** lote criou (libera disco).

Rode um lote por vez, em sequência:

```powershell
python processar_lote.py lotes\lote_08.txt
python processar_lote.py lotes\lote_09.txt
# ... e assim por diante
```

Cada lote leva de minutos a algumas horas dependendo do tamanho dos repos.

## Se um lote falhar no meio

- Se falhar **antes** do merge, os clones são **mantidos** para depuração — veja
  a mensagem de erro. Pode rodar o mesmo lote de novo (repos já clonados são
  reaproveitados).
- O SZZ salva um `.partial.json` a cada 10 fixes em `pyszz/out/`, então uma
  queda no meio do SZZ não perde todo o trabalho.
- `finalizar_lote_05.py` é um exemplo de script de recuperação usado num
  incidente específico — sirva-se dele como referência se precisar finalizar um
  lote a partir de um partial.

## Limpeza de disco (opcional)

Para remover clones cujos dados já foram extraídos:

```powershell
python limpar_clones_processados.py          # dry-run, só lista
python limpar_clones_processados.py --apply  # apaga de fato
```

## Devolver os resultados

Quando terminar sua faixa de lotes, mande de volta (Drive/OneDrive, **não pelo
git** — são gitignored e grandes):

- `szz_data/all_commits_loc.json`
- `szz_data/bugfix_commits.json`
- `pyszz/output_raszz.json`

Esses três contêm **apenas os seus lotes** e serão mesclados no conjunto
principal. O merge é por chave `(repo_name, hash)` / `(repo_name,
fix_commit_hash)`, então mesclar é seguro mesmo se houver sobreposição.

> Dica: os arquivos por lote `szz_data/bugfix_commits_lote_NN.json` registram
> exatamente o subset enviado ao SZZ em cada lote — úteis para auditar o que foi
> processado.
