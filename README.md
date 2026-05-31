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

> 📑 **Para o artigo / TCC:**
> - [`METODOLOGIA.md`](METODOLOGIA.md) — descrição estruturada da metodologia (perguntas de pesquisa, justificativa de cada escolha, ameaças à validade, referências, e §7 com a trajetória empírica completa incluindo incidentes).
> - [`RESULTADOS.md`](RESULTADOS.md) — discussão dos achados finais (n=58 repositórios), análise por repositório, sensibilidade do efeito e implicações práticas.

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
├── step4_analise_estatistica.py     # Análise por classes (Hattori & Lanza) + gráficos
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

### Passo 6 — Análise estatística formal (por classes de tamanho)

Todas as análises e gráficos são orientados pela classificação Hattori & Lanza 2008 (pequeno / médio / grande) — não há mais análises diretas sobre LOC bruto.

```powershell
$env:PYTHONIOENCODING="utf-8"   # evita erro de encoding no Windows
python step4_analise_estatistica.py
```

**Saídas esperadas:**
**Tabelas (CSV):**
- `szz_data/resultados/resultados_q1.csv` — consolidado das análises (taxas por classe, Cochran-Armitage, distribuição A/B, χ² + Cramer's V, Spearman por repo)
- `szz_data/resultados/taxa_bug_por_classe.csv` — n_total, n_bic, taxa% e IC 95% Wilson por classe (pequeno/médio/grande)
- `szz_data/resultados/distribuicao_classes_por_grupo.csv` — % de pequeno/médio/grande dentro de cada grupo (BIC vs não-BIC)
- `szz_data/resultados/resumo_por_repo_classes.csv` — para cada repositório: total, n_bic, taxa_bic_pct, pct_pequeno, pct_medio, pct_grande

**Gráficos (PNG):**
- `szz_data/resultados/bug_rate_por_classe.png` — **principal**: % de BIC em cada classe com IC 95% Wilson e n anotado. Responde *"qual a relação entre tamanho do commit e ocorrência de bugs?"*
- `szz_data/resultados/distribuicao_classes_por_grupo.png` — barras agrupadas: composição de pequeno/médio/grande dentro do Grupo A (BIC) e Grupo B (não-BIC)
- `szz_data/resultados/pct_grande_vs_taxa_bic.png` — scatter por repositório: % de commits grandes × taxa de BIC do repo, com linha de tendência e ρ de Spearman no título

**No terminal**, você vê o resumo final (todas as métricas em termos de classes):
```
RESUMO FINAL — Q1 (orientado por classes de tamanho)
  Taxa BIC | pequeno : 1.77%   medio : 7.68%   grande: 11.94%
  Tendencia (Cochran-Armitage): Z=51.43  p=0.0000e+00  (crescente)
  Grupo A (BIC):     16.3% peq / 56.7% med / 27.0% gra
  Grupo B (nao-BIC): 50.7% peq / 38.1% med / 11.2% gra
  Associacao classe x grupo  : chi2=2671.7, p=0.0000e+00, Cramer's V=0.165 (pequeno)
  Spearman por repo (% gra x taxa BIC): rho=0.334, p=1.04e-02 (sig.)
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

### 6.0 Taxa de bug-introducing por classe de tamanho (análise principal)

> **Esta é a análise que responde diretamente à pergunta principal: "qual a relação entre o tamanho do commit e a ocorrência de bugs?"** Foi adicionada ao `step4_analise_estatistica.py` em resposta à crítica de que comparar a distribuição de LOC de BICs vs não-BICs não tornava explícito *o que é* um commit pequeno/grande e *quanto mais provável* cada classe é de introduzir bugs.

**Classes (Hattori & Lanza, 2008 — limiares bidimensionais `arquivos × LOC`):**

| Classe   | Regra                                                                 |
|----------|-----------------------------------------------------------------------|
| pequeno  | arquivos ≤ 5 **E** LOC ≤ 25                                           |
| grande   | arquivos > 5 **E** LOC > 125                                          |
| medio    | qualquer outro (muitos arq. com volume controlado, **ou** poucos arq. com volume maior) |

**O que é computado** (`taxa_bug_por_classe.csv`):

| coluna           | significado                                                       |
|------------------|-------------------------------------------------------------------|
| `n_total`        | total de commits da classe (no universo `commits_classificados.csv`) |
| `n_bic`          | quantos foram apontados como BIC pelo SZZ                         |
| `taxa_bic_pct`   | `n_bic / n_total × 100` — probabilidade empírica de um commit dessa classe ser BIC |
| `ic95_lo/hi_pct` | intervalo de confiança de 95% (Wilson) para `taxa_bic_pct`        |
| `loc_mediana`    | LOC mediano da classe (sanity-check de que a categorização faz sentido) |

**Por que IC de Wilson e não normal**: para proporções pequenas ou tamanhos amostrais não-uniformes entre classes (a classe `grande` tende a ter `n` bem menor), o IC normal subestima incerteza. Wilson tem cobertura correta inclusive em extremos.

**Teste formal de tendência — Cochran-Armitage:**

- **Pergunta**: a taxa de BIC cresce monotonicamente conforme a classe de tamanho aumenta (pequeno → médio → grande)?
- **Por que esse teste e não χ²**: o χ² genérico testa independência entre as duas variáveis sem usar a *ordem* das classes. Cochran-Armitage atribui scores ordinais (0/1/2) e testa especificamente uma tendência linear na proporção — mais sensível e diretamente alinhado à hipótese.
- **Saída**: `Z` (sinal indica direção, módulo indica intensidade) e `p-valor`. `Z > 0` ∧ `p < 0.05` ⇒ tendência crescente significativa.
- **Referência**: Armitage, P. (1955). *Tests for Linear Trends in Proportions and Frequencies.* Biometrics 11(3).

**Gráfico `bug_rate_por_classe.png`**: barras com a taxa em %, barras de erro com IC 95%, `n` e `n_bic` anotados em cada barra, limiares de cada classe na legenda do eixo X. **É o gráfico para colocar como Figura 1 do artigo / TCC.**

**Como reportar no artigo (exemplo)**:

> "Aplicando os limiares bidimensionais de Hattori & Lanza (2008), commits pequenos (≤5 arquivos e ≤25 LOC) apresentaram taxa de bug-introducing de X% (IC 95% [a, b]), commits médios Y% [c, d] e commits grandes Z% [e, f]. O teste de Cochran-Armitage indicou tendência crescente significativa (Z=…, p<0.001), evidenciando uma relação monotônica positiva entre tamanho do commit e probabilidade de introduzir bugs."

### 6.1 `analyze_bic_size.py` (análise complementar, **não-formal**)

**O que mede:** classifica BICs em "grande" (>5 arquivos AND >125 linhas) vs "pequeno", e calcula:

- **Análise A (proporção entre BICs)**: % de BICs grandes vs pequenos. Descritiva.
- **Análise B (taxa de bug por classe)**: para cada commit do repo, calcula `P(BIC | grande)` vs `P(BIC | pequeno)` e o **risk ratio** (razão entre as duas taxas).

**Como interpretar o risk ratio:**

> "Risk ratio = 8.46 significa que commits que cruzam o limiar têm ~8× mais chance de serem bug-introducing comparados aos que não cruzam."

**Fraqueza acadêmica:** o limiar (5 arquivos, 125 linhas) é arbitrário. Em revisão por pares, alguém vai perguntar *"por que esses números?"*. Useável como análise prática/exploratória, não como evidência principal.

### 6.2 `step4_analise_estatistica.py` (análise formal, toda por classes)

Todos os testes são organizados pela classificação Hattori & Lanza (pequeno/médio/grande). Nenhuma análise compara LOC bruto entre grupos.

#### 6.2.1 Cochran-Armitage (tendência classe ordinal → taxa de BIC)

**Pergunta**: "A taxa `P(BIC | classe)` cresce monotonicamente conforme a classe vai de pequeno para grande?"

**Por que esse teste**: o teste atribui scores ordinais (0/1/2) às classes e testa especificamente uma tendência linear na proporção. χ² genérico ignora a *ordem* das classes — perde poder para detectar o gradiente que nos interessa.

**Saída**:
- `Z`: sinal indica direção (positivo = crescente), módulo indica intensidade.
- `p-valor`: bilateral, `p < 0.05` ⇒ tendência significativa.

**Referência:** Armitage, P. (1955). *Tests for Linear Trends in Proportions and Frequencies.* Biometrics 11(3).

#### 6.2.2 χ² + Cramer's V (associação classe × grupo)

**Pergunta**: "A distribuição das classes (pequeno/médio/grande) dentro do Grupo A (BIC) é diferente da do Grupo B (não-BIC)?"

**Por que esse teste**: complementa o Cochran-Armitage olhando para o problema na outra direção. Cochran-Armitage testa `P(BIC | classe)`; χ² testa se `P(classe | grupo)` difere. Os dois conjuntamente cercam o fenômeno (taxa condicional vs composição).

**Saída**:
- `χ²` e `gl`: estatística e graus de liberdade da tabela 2×3.
- `p-valor`: `p < 0.05` ⇒ associação significativa.
- **Cramer's V**: tamanho de efeito normalizado em [0, 1]. Thresholds (Cohen 1988, `df*=1`): < 0,10 negligível; < 0,30 pequeno; < 0,50 médio; ≥ 0,50 grande.

**Por que Cramer's V e não risk ratio**: V é a métrica padrão para tabela de contingência categórica, comparável com outros estudos. O risk ratio é informativo mas dicotomiza.

**Referências:**
- Pearson, K. (1900). *On the Criterion that a Given System of Deviations…*
- Cramér, H. (1946). *Mathematical Methods of Statistics*.
- Cohen, J. (1988). *Statistical Power Analysis for the Behavioral Sciences*.

#### 6.2.3 Spearman ρ por repositório (% de grandes × taxa de BIC)

**Pergunta**: "Repositórios em que commits grandes são proporcionalmente mais frequentes apresentam taxa de bug-introducing mais alta?"

A correlação é calculada entre dois números *por repositório*:
- `pct_grande` — % de commits do repo classificados como grandes (Hattori & Lanza).
- `taxa_bic_pct` — % de commits do repo marcados como BIC pelo SZZ.

**Por que `pct_grande` e não LOC médio**: alinha a Q1c com as outras análises (todas pela classificação) e evita que outliers de LOC distorçam a média do repositório.

**Por que Spearman e não Pearson**: testa correlação **monotônica** (não exige linearidade). Robusto a outliers.

**Atenção crítica**: Spearman exige n ≥ 20–30 repositórios para poder estatístico aceitável. O estudo atual usa 58 repos — suficiente.

**Referência:** Spearman, C. (1904). *The proof and measurement of association between two things.*

### 6.3 Gráficos (`szz_data/resultados/*.png`)

| Gráfico | O que mostra | Quando citar no artigo |
|---|---|---|
| **`bug_rate_por_classe.png`** | Taxa de BIC em cada classe (Hattori & Lanza 2D) com IC 95% Wilson e n anotado | **Figura principal** — responde diretamente à pergunta de pesquisa |
| **`distribuicao_classes_por_grupo.png`** | Barras agrupadas: % de pequeno/médio/grande dentro do Grupo A (BIC) e Grupo B (não-BIC) | Acompanha o χ² + Cramer's V — mostra que BICs concentram em médio/grande |
| **`pct_grande_vs_taxa_bic.png`** | Cada ponto = um repositório. X: % de commits grandes no repo; Y: taxa BIC do repo. Linha de tendência + ρ no título | Acompanha o Spearman — ilustra a correlação por projeto |

### 6.4 Resumo das perguntas (mapa mental)

| Pergunta | Teste | Significância? | Tamanho de efeito |
|---|---|---|---|
| **Qual a relação entre tamanho e ocorrência de bugs?** | **Taxas por classe + Cochran-Armitage** | p-valor | Diferença absoluta de taxas + IC 95% Wilson |
| BICs e não-BICs têm composição de classes diferente? | χ² (classe × grupo) | p-valor | Cramer's V |
| Em repos com mais commits grandes, mais bugs? | Spearman ρ (pct_grande × taxa BIC) | p-valor | ρ |
| Acima de um limiar prático, qual o risco? | (`analyze_bic_size.py`) | — | Risk ratio |

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
| Hattori, L. & Lanza, M. (2008) | Limiares de classe de tamanho (pequeno/médio/grande) |
| Armitage, P. (1955) | Teste de tendência em proporções |
| Pearson, K. (1900) / Cramér, H. (1946) / Cohen, J. (1988) | χ² + Cramer's V (associação categórica) |
| Wilson, E. B. (1927) / Brown, Cai & DasGupta (2001) | IC para proporção binomial |
| Spearman, C. (1904) | Correlação por postos |
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
