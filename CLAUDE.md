# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

Empirical study testing whether **larger commits are more likely to be bug-introducing**, using the SZZ algorithm over 58 popular Python repositories on GitHub. Output is a TCC/paper artifact (Q1 with three triangulating statistical tests). See `README.md`, `METODOLOGIA.md`, and `RESULTADOS.md` for the academic write-up.

## Environment

- Windows + PowerShell. Always activate the venv first: `.\venv_szz\Scripts\Activate.ps1`
- Python 3.10+. Install: `pip install -r requirements.txt` and `pip install -r pyszz\requirements.txt`
- For scripts that print Unicode (steps 3 and 4), set `$env:PYTHONIOENCODING="utf-8"` before running, otherwise Windows cp1252 raises `UnicodeEncodeError` when stdout is redirected.

## Pipeline (canonical run)

The pipeline is a strict 4-stage chain. Each stage consumes the previous stage's output; never run a later stage without producing the input.

```
commits_clean.csv
  └── step1_adaptar_csv.py
        ├── szz_data/bugfix_commits.json   (SZZ input — list of {repo_name, fix_commit_hash})
        ├── szz_data/all_commits_loc.json  (universe of commits with LOC — denominator for step3)
        └── repos/<owner>/<repo>/          (local clones, required by git blame in SZZ)

szz_data/bugfix_commits.json + repos/
  └── pyszz/main.py <input.json> conf/raszz.yml ..\repos
        └── pyszz/out/bic_raszz_<ts>.json
              (final list of fixes; each entry has inducing_commit_hash: [...])
              partial saved every 10 fixes as bic_raszz_<ts>.partial.json

(rename) pyszz/out/bic_raszz_<ts>.json -> pyszz/output_raszz.json
  └── step3_enriquecer_com_loc.py
        ├── szz_data/commits_classificados.csv  (one row per commit, grupo ∈ {bug_introducing, not_bug_inducing})
        └── szz_data/resumo_por_repo.csv        (aggregated per repo)

szz_data/commits_classificados.csv + resumo_por_repo.csv
  └── step4_analise_estatistica.py
        └── szz_data/resultados/   (CSVs + 3 PNGs)
```

Run a single SZZ subset (e.g. divided between collaborators):
```powershell
cd pyszz
python main.py ..\szz_data\bugfix_commits_meus.json conf\raszz.yml ..\repos
cd ..
copy pyszz\out\bic_raszz_<timestamp>.json pyszz\output_raszz.json
python step3_enriquecer_com_loc.py
$env:PYTHONIOENCODING="utf-8"
python step4_analise_estatistica.py
```

Quick smoke-test sample for sanity checks: `python gerar_amostra.py` produces `szz_data/bugfix_commits_teste.json` from 5 small repos.

## Architecture: things that span multiple files

### 1. `pyszz/` is a modified fork of `grosa1/pyszz_v2` (GPL-3.0)
Modifications relevant to all SZZ runs:
- **`pyszz/main.py`** sorts bugfixes by `repo_name` and reuses one SZZ instance per repository (the upstream re-clones the repo per fix — ~80% time saving on large repos). It writes a `.partial.json` every `SAVE_EVERY = 10` fixes so a crash mid-run does not lose work.
- **`pyszz/szz/ag_szz.py`** memoizes `_exclude_commits_by_change_size` to avoid re-instantiating PyDriller `RepositoryMining` on every blame entry.
- **`pyszz/analyze_bic_size.py`** is a *new* script (not in upstream) for a simple binary risk-ratio analysis. Complementary, not the primary evidence.

When resuming after a crash: read the `.partial.json`, identify completed repos, filter `bugfix_commits.json` to the remaining repos, and rerun. SZZ does not have built-in resume.

### 2. The configured SZZ variant and why parameters look unusual
`pyszz/conf/raszz.yml` is **intentionally** named `raszz.yml` but configures **MA-SZZ** (`szz_name: "ma"`). Do not rename it or assume RA-SZZ semantics.

Critical: `max_change_size: 999999` is **deliberately disabled**. The MA-SZZ default (20) would *a priori* exclude large commits from being candidate BICs — which would circularly answer the study's hypothesis ("large commits don't cause bugs because they were filtered out"). Do not "restore the default" — see METODOLOGIA.md §2.4.

`file_ext_to_parse: ["py"]` restricts blame to Python files; the study does not generalize to other languages.

### 3. The two SZZ outputs (final vs partial)
- `pyszz/out/bic_raszz_<ts>.json` — final consolidated output written at end of run.
- `pyszz/out/bic_raszz_<ts>.partial.json` — incremental, rewritten every 10 fixes; sole source of truth if the run dies. After a clean run, both exist and contain the same data.
- `pyszz/output_raszz.json` — the file step3 reads. You must copy/rename the chosen `bic_raszz_*.json` to this name before running step3.

### 4. Bias filter that step3 does not apply automatically
`all_commits_loc.json` covers all 60 original repos. If SZZ ran on only a subset (e.g. one collaborator did 30 repos), the un-run repos appear in `commits_classificados.csv` with `n_bug_inducing = 0` *by construction* — not because the SZZ rejected them. This **artificially pulls Spearman ρ toward 0**.

Always filter both CSVs to repositories actually present in `pyszz/output_raszz.json` before running step4. The README §5 has the snippet; do not skip this step or report results from unfiltered data.

### 5. Hattori & Lanza 2D thresholds drive every analysis in step4
Every test and plot operates over three classes (not raw LOC):
```
pequeno : files ≤ 5  AND  LOC ≤ 25
grande  : files >  5  AND  LOC > 125
medio   : everything else
```
The classifier is `classify_size` in `step4_analise_estatistica.py`. If you change these thresholds, every downstream result and the academic justification (Hattori & Lanza 2008) becomes invalid. The thresholds are external/published precisely to avoid deriving thresholds from the data being tested.

The three formal tests:
- **Cochran-Armitage** (Q1₀): trend across the ordinal classes — primary evidence.
- **χ² + Cramer's V** (Q1a): composition of classes within each group.
- **Spearman ρ** (Q1b): per-repository `pct_grande` × `taxa_bic_pct`. Needs n ≥ ~30 repos; with 58 it just barely reaches significance.

`pyszz/analyze_bic_size.py` uses the same (5 files / 125 LOC) cutoff but reports a binary risk ratio. It is descriptive only — do not present it as the formal evidence.

## Repositories excluded from the universe

Two of the original 60 repos were dropped during execution:
- `pytorch/pytorch` — NTFS case-insensitivity breaks `git checkout` inside SZZ's internal `_szztemp/` clone (the *initial* clone in `repos/` is fine; SZZ does a second internal clone that fails).
- `Significant-Gravitas/AutoGPT` — recurring SZZ execution errors during the parallel run.

Final universe is **58 repositories**. If you reprocess data, expect these two to be missing and do not flag it as a bug.

## Data files are not in the repo

`commits_clean.csv` (~28 MB), `szz_data/*.json` (~50 MB), and `repos/` (~4.5 GB) are gitignored. A new contributor must receive them from a collaborator or regenerate via `step1_adaptar_csv.py` (needs `$env:GITHUB_TOKEN`). Do not assume they exist — check `Test-Path` first when scripting.

## Conventions

- Documentation language is Portuguese (TCC artifact). Keep new docs in Portuguese unless asked otherwise.
- The pipeline scripts (`step1_*`, `step3_*`, `step4_*`) use hardcoded paths at the top of each file relative to the project root — run them from the project root, not from subdirectories. The exception is `pyszz/main.py`, which is run from `pyszz/`.
- An older `step3_enriquecer_com_loc_adaptado.py` was deleted because it expected a non-existent `commits_metodologia.csv` and produced column names incompatible with step4. Do not recreate it; the canonical step3 is `step3_enriquecer_com_loc.py`.
- The fork's GPL-3.0 license is preserved in `pyszz/LICENSE`. Any redistribution of derived parts must keep GPL-3.0.
