# Guia do Projeto — SZZ + Análise de tamanho de commit

Pipeline completo para identificar **bug-introducing commits (BIC)** em repositórios Python e testar a hipótese de que **commits maiores têm maior probabilidade de introduzir bugs**.

> **Créditos:** o diretório [`pyszz/`](pyszz/) é um *fork modificado* do projeto [`grosa1/pyszz_v2`](https://github.com/grosa1/pyszz_v2), licenciado sob **GPL-3.0**. A licença original está preservada em [`pyszz/LICENSE`](pyszz/LICENSE). Modificações principais feitas neste fork:
> - `pyszz/main.py` — agrupamento de fixes por repositório com reuso de clone, salvamento parcial e factory para criar instâncias do SZZ.
> - `pyszz/szz/ag_szz.py` — memoização de `_exclude_commits_by_change_size`.
> - `pyszz/conf/raszz.yml` — configuração calibrada para o estudo (`max_change_size: 999999`, `filter_revert_commits: true`).
> - `pyszz/analyze_bic_size.py` — script novo de análise complementar (taxa de BIC por classe de tamanho).
>
> Por ser derivado de código GPL-3.0, qualquer redistribuição deste projeto em forma binária ou modificada deve manter os termos da GPL-3.0 para a parte derivada.

---

## Índice

1. [Setup do zero (numa máquina nova)](#1-setup-do-zero-numa-máquina-nova)
2. [O que cada script faz (visão rápida)](#2-o-que-cada-script-faz-visão-rápida)
3. [Estrutura do projeto](#3-estrutura-do-projeto)
4. [Pipeline completo (passo-a-passo com verificações)](#4-pipeline-completo-passo-a-passo-com-verificações)
5. [Dividindo o trabalho entre pessoas](#5-dividindo-o-trabalho-entre-pessoas-60-repos--30--30)
6. [Interpretando as saídas — explicação acadêmica](#6-interpretando-as-saídas--explicação-acadêmica)
7. [Limitações metodológicas](#7-limitações-metodológicas-declarar-no-artigo)
8. [Referências centrais](#8-referências-centrais)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Setup do zero (numa máquina nova)

### 1.1 Pré-requisitos do sistema

| Requisito | Versão | Para quê |
|---|---|---|
| Python | **3.11** (3.10+ funciona) | rodar todos os scripts |
| Git | qualquer | clonar repositórios |
| Java | 8+ (opcional) | só se for usar RA-SZZ (não usamos) |
| Espaço em disco | ~10 GB livres | repos clonados ocupam 4-5 GB |

### 1.2 Clonar este projeto

```powershell
git clone https://github.com/robinCrobin/szz-commit-size.git
cd szz-commit-size
```

### 1.3 Criar o virtualenv e instalar dependências

```powershell
# Criar venv (uma única vez):
python -m venv venv_szz

# Ativar (toda vez que abrir um terminal):
.\venv_szz\Scripts\Activate.ps1

# Instalar dependências (uma única vez):
pip install pandas tqdm scipy matplotlib seaborn pydriller gitpython requests pyyaml
pip install -r pyszz\requirements.txt
```

> Se o PowerShell bloquear o `Activate.ps1`, rode antes (uma vez):
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

### 1.4 Obter os arquivos de dados

Os dados (~75 MB) **não estão no repositório** (foram gitignored para manter o repo leve). Você precisa de:

| Arquivo | Como obter |
|---|---|
| `commits_clean.csv` (~28 MB) | Receba do colaborador via Drive/OneDrive/transferência. É a fonte original. |
| `szz_data/all_commits_loc.json` (~44 MB) | Idem. **Use o mesmo de quem dividiu o trabalho** para evitar viés. |
| `szz_data/bugfix_commits.json` (~6 MB) | Idem. |
| `repos/` (~4.5 GB) | Idem (compactar e enviar) **ou** gerar localmente rodando `python step1_adaptar_csv.py` (clona via GitHub, requer token). |

> 💡 **Atalho mais rápido**: peça à pessoa que dividiu os repos para enviar `commits_clean.csv` + `szz_data/` (zipado) + `repos/` (zipado, ~2 GB compactado). Coloque em `C:\Users\<seu_user>\...\szz-commit-size\` mantendo a estrutura.

### 1.5 (Opcional) Token do GitHub

Só é necessário se você for **re-coletar dados** (rodar `step1_*` para clonar repos novos):

```powershell
$env:GITHUB_TOKEN = "ghp_seu_token_aqui"
```

> ⚠️ **NUNCA cole tokens dentro de arquivos do projeto**. O `step1_adaptar_csv.py` lê de `$env:GITHUB_TOKEN`. Se você acidentalmente commitar um token, [revogue imediatamente](https://github.com/settings/tokens).

---

## 2. O que cada script faz (visão rápida)

| Script | Entrada | Saída | Tempo* |
|---|---|---|---|
| [`step1_adaptar_csv.py`](step1_adaptar_csv.py) | `commits_clean.csv` | `szz_data/bugfix_commits.json`, `szz_data/all_commits_loc.json`, `repos/` clonados | 30min–2h |
| [`step1_coletar_bugfix_commits.py`](step1_coletar_bugfix_commits.py) | API GitHub (1000 repos) | mesmo do anterior | 2-4h |
| [`gerar_amostra.py`](gerar_amostra.py) | `commits_clean.csv` | `szz_data/bugfix_commits_teste.json` (subset de teste) | 1s |
| [`pyszz/main.py`](pyszz/main.py) | `bugfix_commits*.json` + `repos/` | `pyszz/out/bic_raszz_<ts>.json` | 30min–dias** |
| [`pyszz/analyze_bic_size.py`](pyszz/analyze_bic_size.py) | output do SZZ + `repos/` | tabela de "risco grande × pequeno" no terminal | 5–30 min |
| [`step3_enriquecer_com_loc.py`](step3_enriquecer_com_loc.py) | `pyszz/output_raszz.json` + `all_commits_loc.json` | `commits_classificados.csv`, `resumo_por_repo.csv` | <1 min |
| [`step4_analise_estatistica.py`](step4_analise_estatistica.py) | os 2 CSVs do step3 | `szz_data/resultados/*.png` + `resultados_q1.csv` | <1 min |

\* tempos para rodada completa de 60 repos / ~10k fixes.
\*\* MA-SZZ é o configurado (rápido). RA-SZZ ficaria 5-20× mais lento.

---

## 3. Estrutura do projeto

```
szz-commit-size/
├── commits_clean.csv                # [não-versionado] Fonte original: todos os commits + flag is_bug_fix
├── gerar_amostra.py                 # Gera input pequeno do pySZZ (5 repos)
├── step1_adaptar_csv.py             # Converte commits_clean.csv → bugfix + all_commits
├── step1_coletar_bugfix_commits.py  # (Alternativo) coleta direto do GitHub
├── step3_enriquecer_com_loc.py      # Cruza output do SZZ com all_commits → CSVs
├── step4_analise_estatistica.py     # Mann-Whitney U + Cliff's Delta + gráficos
├── README.md                        # Este arquivo
├── .gitignore
│
├── pyszz/                           # SZZ engine (fork do pyszz_v2)
│   ├── main.py                      # Entry-point do SZZ
│   ├── conf/raszz.yml               # Configuração ATIVA (max_change_size: 999999)
│   ├── analyze_bic_size.py          # Análise complementar (taxa por classe)
│   ├── output_raszz.json            # [não-versionado] Output consolidado p/ step3
│   └── out/                         # [não-versionado] bic_raszz_<ts>.json
│
├── szz_data/                        # [não-versionado] todos os dados gerados
│   ├── bugfix_commits.json          # Input completo do SZZ (gerado por step1)
│   ├── all_commits_loc.json         # Universo de commits (gerado por step1)
│   ├── bugfix_commits_teste.json    # Subset 5 repos pequenos (gerado por gerar_amostra)
│   ├── commits_classificados.csv    # Saída step3 (Grupo A vs B)
│   ├── resumo_por_repo.csv          # Saída step3 (agregação por repo)
│   └── resultados/                  # Saída step4 (CSVs + PNGs)
│
├── repos/                           # [não-versionado] Repositórios clonados pelo step1
└── venv_szz/                        # [não-versionado] Virtualenv (Python 3.11)
```

---

## 4. Pipeline completo (passo-a-passo com verificações)

```
[ commits_clean.csv ]
        │
        ▼   step1_adaptar_csv.py
[ bugfix_commits.json ]    [ all_commits_loc.json ]    [ repos/ clonados ]
        │                            │
        ▼   pyszz/main.py            │
[ pyszz/out/bic_raszz_<ts>.json ]    │
        │                            │
        ▼ (renomear/mover)           │
[ pyszz/output_raszz.json ] ─────────┤
                                     ▼   step3_enriquecer_com_loc.py
                            [ commits_classificados.csv ]
                            [ resumo_por_repo.csv ]
                                     │
                                     ▼   step4_analise_estatistica.py
                            [ szz_data/resultados/*.png + .csv ]
```

### Passo 0 — Confirmar que o setup terminou

Antes de qualquer rodada, confirme que você tem:

```powershell
# venv ativo
.\venv_szz\Scripts\Activate.ps1
python --version    # deve ser 3.10+

# Arquivos de dados (vindos do colaborador, ver §1.4):
Test-Path commits_clean.csv               # True
Test-Path szz_data\bugfix_commits.json    # True
Test-Path szz_data\all_commits_loc.json   # True
(Get-ChildItem repos -Directory).Count    # > 0
```

Se algo falhar, volte para a seção 1.

---

### Passo 1 — (apenas se você for fazer a coleta) Gerar inputs do zero

> **Pule este passo** se você já recebeu os arquivos de dados prontos do colaborador.

```powershell
python step1_adaptar_csv.py
```

**Saídas esperadas:**
- `szz_data/bugfix_commits.json` — lista de fixes
- `szz_data/all_commits_loc.json` — universo de commits com LOC
- `repos/` — repositórios clonados

**Tempo:** 30 min a 2 h (depende da quantidade de repos a clonar).

---

### Passo 2 — (opcional) Filtrar para um subset menor

Se você vai rodar só **alguns repos** (divisão de trabalho, ou teste rápido), monte um JSON com só os fixes que te interessam:

```python
import json
data = json.load(open('szz_data/bugfix_commits.json'))
meus_repos = {'pytorch/pytorch', 'odoo/odoo', '...'}   # lista que te coube
sub = [x for x in data if x['repo_name'] in meus_repos]
json.dump(sub, open('szz_data/bugfix_commits_meus.json', 'w'))
print(f'subset: {len(sub)} fixes')
```

Veja [`gerar_amostra.py`](gerar_amostra.py) como exemplo.

**Verificação:** o JSON gerado deve ter sua quantidade esperada de fixes.

---

### Passo 3 — Rodar o SZZ (descobrir os bug-introducing commits)

```powershell
cd pyszz
python main.py ..\szz_data\bugfix_commits_meus.json conf\raszz.yml ..\repos
```

**Saídas esperadas:**
- Durante a execução: `pyszz/out/bic_raszz_<ts>.partial.json` (atualizado a cada 10 fixes — **resiliente** a quedas).
- No final: `pyszz/out/bic_raszz_<ts>.json` (versão final consolidada).
- Mensagem final no log: `+++ DONE +++`.

**Tempo:** depende — ~10 segundos por fix em média; varia muito por repo. Monitore o log:

```powershell
Get-Content pyszz\_run.log -Wait -Tail 20
```

**Verificações:**
- `Test-Path pyszz\out\bic_raszz_*.json` = `True`
- O JSON final deve ser uma lista cujos itens têm `inducing_commit_hash` (lista, possivelmente vazia).

---

### Passo 4 — Consolidar o output do SZZ

Renomeie o JSON do SZZ para o nome que o step3 espera:

```powershell
copy pyszz\out\bic_raszz_<timestamp>.json pyszz\output_raszz.json
```

> Se vocês são **várias pessoas** e cada uma rodou um pedaço, [veja seção 5 sobre como mesclar](#5-dividindo-o-trabalho-entre-pessoas-60-repos--30--30) antes de seguir.

---

### Passo 5 — Cruzar com o universo de commits (gera os grupos A e B)

```powershell
cd ..
python step3_enriquecer_com_loc.py
```

**Saídas esperadas:**
- `szz_data/commits_classificados.csv` — uma linha por commit, coluna `grupo` ∈ {`bug_introducing`, `not_bug_inducing`}
- `szz_data/resumo_por_repo.csv` — uma linha por repositório com taxa de bugs

**Verificações:**
```powershell
Get-Content szz_data\commits_classificados.csv | Select-Object -First 3
Get-Content szz_data\resumo_por_repo.csv | Select-Object -First 5
```

> ⚠️ **Importante**: se você rodou o SZZ em **menos repos** que os existentes em `all_commits_loc.json`, **filtre os CSVs** para só os repos analisados (evita viés no Spearman):
> ```python
> import pandas as pd, json
> repos_run = sorted({x['repo_name'] for x in json.load(open('pyszz/output_raszz.json'))})
> for csv in ['szz_data/commits_classificados.csv', 'szz_data/resumo_por_repo.csv']:
>     df = pd.read_csv(csv)
>     df[df.repo_name.isin(repos_run)].to_csv(csv, index=False)
> ```

---

### Passo 6 — Análise estatística formal (Mann-Whitney + Cliff's Delta + Spearman)

```powershell
$env:PYTHONIOENCODING="utf-8"   # evita erro de encoding no Windows
python step4_analise_estatistica.py
```

**Saídas esperadas:**
- `szz_data/resultados/resultados_q1.csv` — tabela resumo dos testes
- `szz_data/resultados/boxplot_grupos.png`
- `szz_data/resultados/violin_grupos.png`
- `szz_data/resultados/cdf_grupos.png`
- `szz_data/resultados/scatter_repos.png`

**No terminal**, você vê o resumo final:
```
RESUMO FINAL — Q1
  Bug-introducing commits são maiores? : SIM
  Tamanho do efeito (Cliff's Delta)    : 0.62 (grande)
  Mediana Grupo A / Grupo B            : 168.5 / 18.0 LOC
  Correlação por repositório (ρ)       : ...
```

Para entender o que cada número significa, vá para a [§6 Interpretando as saídas](#6-interpretando-as-saídas--explicação-acadêmica).

---

### Passo 7 — (opcional) Análise complementar por classe de tamanho

```powershell
cd pyszz
python analyze_bic_size.py output_raszz.json ..\repos
```

**Saída:** tabela no terminal mostrando proporção de BICs grandes vs pequenos e o **risk ratio** (razão de chances). Útil como descritiva — não substitui os testes formais do passo 6.

---

## 5. Dividindo o trabalho entre pessoas (60 repos → 30 + 30)

A divisão é **embaraçosamente paralela**: cada pessoa roda o SZZ em sua fatia de repositórios e os resultados são concatenados no final. O `all_commits_loc.json` (passo 1) é repo-agnóstico — pode ser gerado uma vez por uma pessoa e compartilhado.

### Setup (feito por uma pessoa, uma única vez)

1. Roda `step1_adaptar_csv.py` para gerar:
   - `szz_data/bugfix_commits.json` (todos os fixes de todos os repos)
   - `szz_data/all_commits_loc.json` (universo total de commits)
   - `repos/` clonados
2. Compartilha esses três artefatos com as outras pessoas.

### Cada pessoa pega um subset

Cada pessoa cria seu input filtrado:

```python
# Pessoa A: roda nos primeiros 30 repos (alfabético)
import json
data = json.load(open('szz_data/bugfix_commits.json'))
repos = sorted({x['repo_name'] for x in data})
meus = set(repos[:30])  # ou repos[30:] para Pessoa B
sub = [x for x in data if x['repo_name'] in meus]
json.dump(sub, open('szz_data/bugfix_commits_pessoaA.json', 'w'))
```

E roda o SZZ no seu subset:

```powershell
cd pyszz
python main.py ..\szz_data\bugfix_commits_pessoaA.json conf\raszz.yml ..\repos
# Salva pyszz/out/bic_raszz_<ts>.json (renomeie para bic_pessoaA.json)
```

### Juntar no final (uma pessoa)

```python
import json
files = ['bic_pessoaA.json', 'bic_pessoaB.json']  # adicione todos
merged = []
for f in files:
    merged.extend(json.load(open(f)))

# Sanity check: cada fix deve aparecer no máximo 1×
seen = set()
for x in merged:
    key = (x['repo_name'], x['fix_commit_hash'])
    assert key not in seen, f'duplicado: {key}'
    seen.add(key)

json.dump(merged, open('pyszz/output_raszz.json', 'w'))
```

A partir daí, **uma pessoa só** roda step3 + step4 normalmente — eles trabalham com o JSON consolidado.

> 💡 **Dica**: usem o mesmo `all_commits_loc.json` para que step3 cruze contra um universo consistente. Se cada pessoa gerar o seu, datas de coleta diferentes podem incluir/excluir commits diferentes.

---

## 6. Interpretando as saídas — explicação acadêmica

### 6.1 `analyze_bic_size.py` (análise complementar, **não-formal**)

**O que mede:** classifica BICs em "grande" (>5 arquivos AND >125 linhas) vs "pequeno", e calcula:

- **Análise A (proporção entre BICs)**: % de BICs grandes vs pequenos. Descritiva.
- **Análise B (taxa de bug por classe)**: para cada commit do repo, calcula `P(BIC | grande)` vs `P(BIC | pequeno)` e o **risk ratio** (razão entre as duas taxas).

**Como interpretar o risk ratio:**

> "Risk ratio = 8.46 significa que commits que cruzam o limiar têm ~8× mais chance de serem bug-introducing comparados aos que não cruzam."

**Fraqueza acadêmica:** o limiar (5 arquivos, 125 linhas) é arbitrário. Em revisão por pares, alguém vai perguntar *"por que esses números?"*. Useável como análise prática/exploratória, não como evidência principal.

### 6.2 `step4_analise_estatistica.py` (análise formal)

Aplica **três testes não-paramétricos** consagrados na literatura de Engenharia de Software empírica.

#### 6.2.1 Mann-Whitney U (`mannwhitneyu`)

**Pergunta**: "A distribuição de LOC do Grupo A (BICs) é estocasticamente maior que a do Grupo B (não-BICs)?"

**Por que não-paramétrico**: distribuições de LOC são fortemente assimétricas (long-tail). Testes paramétricos (t-test) assumem normalidade — falsificada na prática.

**Saída e interpretação:**
- `U`: estatística do teste (varia com tamanho amostral, sozinha não significa muito).
- `p-valor`: probabilidade de observar essa diferença sob H0 ("os grupos vêm da mesma distribuição"). Convencionalmente: **p < 0.05** → rejeita H0.
- **Atenção**: p-valor diz *se* há diferença, não *quanto*. Daí Cliff's Delta.

**Referências fundadoras:**
- Mann, H. B. & Whitney, D. R. (1947). *On a Test of Whether one of Two Random Variables is Stochastically Larger than the Other.* Annals of Mathematical Statistics.
- Em ES: Kim, S. et al. (2008). *Classifying Software Changes: Clean or Buggy?* IEEE TSE.

#### 6.2.2 Cliff's Delta (δ)

**Pergunta**: "Qual o **tamanho do efeito**? Em quantos pares o Grupo A excede o Grupo B?"

**Fórmula**: `δ = P(A > B) − P(B > A)`. Varia em `[-1, 1]`.

**Thresholds de interpretação (Romano et al., 2006):**

| `|δ|`         | Magnitude |
|--------------:|-----------|
| < 0.147       | negligível |
| < 0.330       | pequeno    |
| < 0.474       | médio      |
| ≥ 0.474       | **grande** |

**Por que importa**: com amostras grandes, qualquer diferença minúscula vira "significativa" (p < 0.05). Cliff's Delta diz se a diferença é **grande o suficiente para ser relevante** — separa "estatisticamente significativo" de "praticamente importante".

**Referência:**
- Romano, J. et al. (2006). *Appropriate statistics for ordinal level data: Should we really be using t-test and Cohen's d for evaluating group differences on the NSSE and other surveys?* Annual Meeting of the Florida Association of Institutional Research.

#### 6.2.3 Spearman ρ (correlação por repositório)

**Pergunta**: "**Por projeto**, repositórios com LOC médio maior têm proporção maior de bugs?"

**Por que Spearman e não Pearson**: Spearman testa correlação **monotônica** (não exige relação linear). Robusto a outliers — alguns repos podem ter padrões muito diferentes.

**Saída**:
- `ρ` ∈ `[-1, 1]`. Próximo de 0 = sem correlação.
- `p-valor`: similar ao M-W.

**Atenção crítica**: Spearman exige **muitos repositórios** (n ≥ 20-30 idealmente) para ter poder estatístico. Com só 5 repos analisados, o teste é fraco — esperado dar não-significativo. **É exatamente por isso que vocês querem dividir o trabalho entre pessoas e analisar 60 repos: para que esse teste vire conclusivo.**

**Referência:**
- Spearman, C. (1904). *The proof and measurement of association between two things.* American Journal of Psychology.

### 6.3 Gráficos (`szz_data/resultados/*.png`)

| Gráfico | O que mostra | Quando citar no artigo |
|---|---|---|
| **Boxplot** (escala log) | Mediana, quartis, dispersão dos dois grupos | Visualização principal — primeiro contato do leitor com a diferença |
| **Violin** | Forma completa da distribuição (densidade) | Quando quiser destacar bimodalidade/cauda |
| **CDF** | Proporção acumulada de commits ≤ X LOC | Útil para "que % dos BICs estão acima de Y LOC" |
| **Scatter** | Cada ponto = um repo: LOC médio × taxa de bugs | Junto da Spearman; ilustra a correlação por projeto |

### 6.4 Resumo das três perguntas (mapa mental)

| Pergunta | Teste | Significância? | Tamanho de efeito |
|---|---|---|---|
| BICs são maiores que não-BICs? | Mann-Whitney U | p-valor | Cliff's Delta |
| **Quanto maiores?** | — | — | Cliff's Delta + medianas |
| Em repos com commits maiores, mais bugs? | Spearman ρ | p-valor | ρ |
| Acima de um limiar prático, qual o risco? | (analyze_bic_size.py) | — | Risk ratio |

---

## 7. Limitações metodológicas (declarar no artigo)

1. **MA-SZZ ainda apresenta falsos positivos**: o algoritmo confunde commits "tocados pelo blame" com commits "que introduziram o bug". Estudos empíricos reportam ~17% de "ghost commits" mesmo em variantes melhoradas. Cite Rezk et al. (2022).
2. **`is_bug_fix` por keyword**: o `commits_clean.csv` infere bug-fix por palavras-chave na mensagem (`fix`, `bug`, `error`, ...). Falso-positivos esperados — refatorações chamadas "fix typo" não são bugs reais. Cite Herzig et al. (2013).
3. **LOC como proxy de tamanho**: não captura complexidade ciclomática, profundidade de aninhamento, ou impacto semântico. Reconheça e considere métricas adicionais em trabalho futuro.
4. **Apenas Python**: o filtro `file_ext_to_parse: ['py']` no `raszz.yml` restringe blame a arquivos Python. Não generalize para outras linguagens sem rerodar.
5. **Universo limitado**: se rodaram em N repos, conclusões valem apenas para esse universo. Se quiser generalização, justifique a amostragem.

---

## 8. Referências centrais

| Autor / Ano | Contribuição |
|---|---|
| Śliwerski, J., Zimmermann, T., Zeller, A. (2005) | SZZ original |
| Kim, S., Zimmermann, T., Pan, K. & Whitehead, E.J. (2006) | AG-SZZ (annotation-graph) |
| Da Costa, D.A. et al. (2017) | Avaliação empírica das variantes SZZ |
| Neto, E.C., da Costa, D.A. & Kulesza, U. (2018) | RA-SZZ (refactoring-aware) |
| Rezk, V., Kamei, Y., McIntosh, S. (2022) | "Ghost commits" e calibração de SZZ |
| Mann & Whitney (1947) | Teste U |
| Romano et al. (2006) | Thresholds de Cliff's Delta |
| Herzig, K. et al. (2013) | Inacurácia de classificação por keyword |

---

## 9. Troubleshooting

**`Activate.ps1 cannot be loaded because running scripts is disabled`**
→ Rode no PowerShell (uma vez por usuário): `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`.

**`ModuleNotFoundError: No module named 'pandas'` (ou outro)**
→ Você esqueceu de ativar o venv. Rode `.\venv_szz\Scripts\Activate.ps1`. Confirme com `where.exe python` apontando para `venv_szz`.

**`UnicodeEncodeError: 'charmap' codec can't encode character ...`**
→ No Windows, redirecionar stdout pra arquivo usa cp1252 por padrão. Solução:
```powershell
$env:PYTHONIOENCODING="utf-8"
python step3_enriquecer_com_loc.py
```
Ou no PowerShell: `python script.py | Out-File -Encoding utf8 saida.txt`.

**SZZ muito lento (cada fix demora minutos)**
→ Confira que está usando MA-SZZ (`szz_name: ma` em `pyszz/conf/raszz.yml`). RA-SZZ é 5-20× mais lento por chamar Java/RefactoringMiner. Para a hipótese tamanho×bug, MA-SZZ é suficiente.

**SZZ travou no meio**
→ O parcial em `pyszz/out/bic_raszz_<ts>.partial.json` tem o que foi feito até a última centena. Para retomar:
1. Olhe quais repos já apareceram nele.
2. Filtre seu `bugfix_commits_meus.json` excluindo os repos já processados.
3. Rode novamente — vai começar do zero **dos restantes**.

**Spearman ρ próximo de 0 (não-significativo)**
→ Verifique quantos repositórios estão no `resumo_por_repo.csv`. Se for < 20, o teste é **fraco por construção** (poder estatístico baixo). Junte mais repos antes de concluir.

**`output_raszz.json: file not found` no step3**
→ O step3 espera o JSON em `pyszz/output_raszz.json`. Você precisa renomear/copiar o output do SZZ:
```powershell
copy pyszz\out\bic_raszz_<timestamp>.json pyszz\output_raszz.json
```

**`commits_metodologia.csv: file not found`**
→ Você está executando uma versão antiga adaptada do step3 que não existe mais nesse projeto. Use `step3_enriquecer_com_loc.py` (sem `_adaptado`).

**Resultados zerados ou com `n_bug_inducing = 0` em quase todos os repos**
→ O `all_commits_loc.json` cobre repos que você não rodou no SZZ. Aplique o filtro de viés do passo 5 (filtrar CSVs para repos efetivamente rodados).

**Erro de permissão ao apagar `_szztemp/`**
→ Arquivos `.git/pack` no Windows têm flag de read-only. Feche qualquer processo Python pendente e tente:
```powershell
Get-ChildItem _szztemp -Recurse | ForEach-Object { $_.Attributes = 'Normal' }
Remove-Item -Recurse -Force _szztemp
```

**`Exception ignored in: <function Popen.__del__>` no log do SZZ**
→ Benigno. É o garbage collector do Python tentando fechar handles do GitPython no Windows. O próprio Python descarta a exceção e o processamento continua. Pode ignorar.
