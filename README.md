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

## 1. Estrutura do projeto

```
szz/
├── commits_clean.csv                # Fonte original: todos os commits + flag is_bug_fix
├── gerar_amostra.py                 # Gera input pequeno do pySZZ (5 repos)
├── step1_adaptar_csv.py             # Converte commits_clean.csv → bugfix + all_commits
├── step1_coletar_bugfix_commits.py  # (Alternativo) coleta direto do GitHub
├── step3_enriquecer_com_loc.py      # Cruza output do SZZ com all_commits → CSVs
├── step4_analise_estatistica.py     # Mann-Whitney U + Cliff's Delta + gráficos
│
├── pyszz/                           # SZZ engine (fork do pyszz_v2)
│   ├── main.py                      # Entry-point do SZZ
│   ├── conf/raszz.yml               # Configuração ATIVA (max_change_size: 999999)
│   ├── analyze_bic_size.py          # Análise complementar (taxa por classe)
│   ├── output_raszz.json            # Output consolidado p/ step3
│   └── out/                         # Outputs intermediários (bic_raszz_<ts>.json)
│
├── szz_data/
│   ├── bugfix_commits.json          # Input completo do SZZ (gerado por step1)
│   ├── all_commits_loc.json         # Universo de commits (gerado por step1)
│   ├── bugfix_commits_teste.json    # Subset 5 repos pequenos (gerado por gerar_amostra)
│   ├── commits_classificados.csv    # Saída step3 (Grupo A vs B)
│   ├── resumo_por_repo.csv          # Saída step3 (agregação por repo)
│   └── resultados/                  # Saída step4 (CSVs + PNGs)
│
├── repos/                           # Repositórios clonados pelo step1
└── venv_szz/                        # Virtualenv ativo (Python 3.11)
```

---

## 2. Pré-requisitos

```powershell
# 1. Python 3.11 e Git instalados
# 2. Ativar o virtualenv:
.\venv_szz\Scripts\Activate.ps1

# 3. Instalar dependências (uma única vez):
pip install pandas tqdm scipy matplotlib seaborn pydriller gitpython requests pyyaml
pip install -r pyszz\requirements.txt

# 4. Configurar token do GitHub (apenas para step1, se for re-coletar repos):
$env:GITHUB_TOKEN = "ghp_seu_token_aqui"
```

> ⚠️ **Segurança**: o `step1_adaptar_csv.py` lê o token de `$env:GITHUB_TOKEN`. **Nunca cole tokens no código.** Se você commitou um token alguma vez, **revogue-o em https://github.com/settings/tokens** e gere outro.

---

## 3. Pipeline completo (do zero)

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

### Passo a passo

**1) Preparar inputs (uma única vez):**

```powershell
python step1_adaptar_csv.py
# Gera szz_data/bugfix_commits.json + all_commits_loc.json e clona ./repos
```

**2) Rodar o SZZ:**

```powershell
cd pyszz
python main.py ..\szz_data\bugfix_commits.json conf\raszz.yml ..\repos
# Saída: pyszz/out/bic_raszz_<timestamp>.json
# Salva parcial a cada 10 fixes em out/bic_raszz_<ts>.partial.json
```

> Se rodar sub-conjuntos, basta passar um JSON menor. Veja `gerar_amostra.py` como exemplo.

**3) Renomear o JSON do SZZ para o nome esperado pelo step3:**

```powershell
copy pyszz\out\bic_raszz_<timestamp>.json pyszz\output_raszz.json
```

**4) Cruzar com `all_commits_loc.json`:**

```powershell
cd ..
python step3_enriquecer_com_loc.py
# Gera szz_data/commits_classificados.csv + resumo_por_repo.csv
```

> ⚠️ **Importante**: se você rodou o SZZ em **menos repos** que os existentes em `all_commits_loc.json`, **filtre o CSV** depois para só os repos analisados (evita viés). Trecho rápido em Python:
> ```python
> import pandas as pd, json
> repos_run = sorted({x['repo_name'] for x in json.load(open('pyszz/output_raszz.json'))})
> for csv in ['szz_data/commits_classificados.csv', 'szz_data/resumo_por_repo.csv']:
>     df = pd.read_csv(csv)
>     df[df.repo_name.isin(repos_run)].to_csv(csv, index=False)
> ```

**5) Análise estatística formal:**

```powershell
python step4_analise_estatistica.py
# Gera szz_data/resultados/{boxplot,violin,cdf,scatter}_*.png + resultados_q1.csv
```

**6) (Opcional) Análise complementar por classe de tamanho:**

```powershell
cd pyszz
python analyze_bic_size.py output_raszz.json ..\repos
# Saída no terminal: tabela de risco "grandes vs pequenos"
```

---

## 4. Dividindo o trabalho entre pessoas (60 repos → 30 + 30)

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

## 5. Interpretando as saídas — explicação acadêmica

### 5.1 `analyze_bic_size.py` (análise complementar, **não-formal**)

**O que mede:** classifica BICs em "grande" (>5 arquivos AND >125 linhas) vs "pequeno", e calcula:

- **Análise A (proporção entre BICs)**: % de BICs grandes vs pequenos. Descritiva.
- **Análise B (taxa de bug por classe)**: para cada commit do repo, calcula `P(BIC | grande)` vs `P(BIC | pequeno)` e o **risk ratio** (razão entre as duas taxas).

**Como interpretar o risk ratio:**

> "Risk ratio = 8.46 significa que commits que cruzam o limiar têm ~8× mais chance de serem bug-introducing comparados aos que não cruzam."

**Fraqueza acadêmica:** o limiar (5 arquivos, 125 linhas) é arbitrário. Em revisão por pares, alguém vai perguntar *"por que esses números?"*. Useável como análise prática/exploratória, não como evidência principal.

### 5.2 `step4_analise_estatistica.py` (análise formal)

Aplica **três testes não-paramétricos** consagrados na literatura de Engenharia de Software empírica.

#### 5.2.1 Mann-Whitney U (`mannwhitneyu`)

**Pergunta**: "A distribuição de LOC do Grupo A (BICs) é estocasticamente maior que a do Grupo B (não-BICs)?"

**Por que não-paramétrico**: distribuições de LOC são fortemente assimétricas (long-tail). Testes paramétricos (t-test) assumem normalidade — falsificada na prática.

**Saída e interpretação:**
- `U`: estatística do teste (varia com tamanho amostral, sozinha não significa muito).
- `p-valor`: probabilidade de observar essa diferença sob H0 ("os grupos vêm da mesma distribuição"). Convencionalmente: **p < 0.05** → rejeita H0.
- **Atenção**: p-valor diz *se* há diferença, não *quanto*. Daí Cliff's Delta.

**Referências fundadoras:**
- Mann, H. B. & Whitney, D. R. (1947). *On a Test of Whether one of Two Random Variables is Stochastically Larger than the Other.* Annals of Mathematical Statistics.
- Em ES: Kim, S. et al. (2008). *Classifying Software Changes: Clean or Buggy?* IEEE TSE.

#### 5.2.2 Cliff's Delta (δ)

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

#### 5.2.3 Spearman ρ (correlação por repositório)

**Pergunta**: "**Por projeto**, repositórios com LOC médio maior têm proporção maior de bugs?"

**Por que Spearman e não Pearson**: Spearman testa correlação **monotônica** (não exige relação linear). Robusto a outliers — alguns repos podem ter padrões muito diferentes.

**Saída**:
- `ρ` ∈ `[-1, 1]`. Próximo de 0 = sem correlação.
- `p-valor`: similar ao M-W.

**Atenção crítica**: Spearman exige **muitos repositórios** (n ≥ 20-30 idealmente) para ter poder estatístico. Com só 5 repos analisados, o teste é fraco — esperado dar não-significativo. **É exatamente por isso que vocês querem dividir o trabalho entre pessoas e analisar 60 repos: para que esse teste vire conclusivo.**

**Referência:**
- Spearman, C. (1904). *The proof and measurement of association between two things.* American Journal of Psychology.

### 5.3 Gráficos (`szz_data/resultados/*.png`)

| Gráfico | O que mostra | Quando citar no artigo |
|---|---|---|
| **Boxplot** (escala log) | Mediana, quartis, dispersão dos dois grupos | Visualização principal — primeiro contato do leitor com a diferença |
| **Violin** | Forma completa da distribuição (densidade) | Quando quiser destacar bimodalidade/cauda |
| **CDF** | Proporção acumulada de commits ≤ X LOC | Útil para "que % dos BICs estão acima de Y LOC" |
| **Scatter** | Cada ponto = um repo: LOC médio × taxa de bugs | Junto da Spearman; ilustra a correlação por projeto |

### 5.4 Resumo das três perguntas (mapa mental)

| Pergunta | Teste | Significância? | Tamanho de efeito |
|---|---|---|---|
| BICs são maiores que não-BICs? | Mann-Whitney U | p-valor | Cliff's Delta |
| **Quanto maiores?** | — | — | Cliff's Delta + medianas |
| Em repos com commits maiores, mais bugs? | Spearman ρ | p-valor | ρ |
| Acima de um limiar prático, qual o risco? | (analyze_bic_size.py) | — | Risk ratio |

---

## 6. Limitações metodológicas (declarar no artigo)

1. **MA-SZZ ainda apresenta falsos positivos**: o algoritmo confunde commits "tocados pelo blame" com commits "que introduziram o bug". Estudos empíricos reportam ~17% de "ghost commits" mesmo em variantes melhoradas. Cite Rezk et al. (2022).
2. **`is_bug_fix` por keyword**: o `commits_clean.csv` infere bug-fix por palavras-chave na mensagem (`fix`, `bug`, `error`, ...). Falso-positivos esperados — refatorações chamadas "fix typo" não são bugs reais. Cite Herzig et al. (2013).
3. **LOC como proxy de tamanho**: não captura complexidade ciclomática, profundidade de aninhamento, ou impacto semântico. Reconheça e considere métricas adicionais em trabalho futuro.
4. **Apenas Python**: o filtro `file_ext_to_parse: ['py']` no `raszz.yml` restringe blame a arquivos Python. Não generalize para outras linguagens sem rerodar.
5. **Universo limitado**: se rodaram em N repos, conclusões valem apenas para esse universo. Se quiser generalização, justifique a amostragem.

---

## 7. Referências centrais

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

## 8. Troubleshooting

**SZZ muito lento**
→ Confira que está usando MA-SZZ (`szz_name: ma` em `pyszz/conf/raszz.yml`). RA-SZZ é 5-20× mais lento por chamar Java/RefactoringMiner. Para sua pergunta sobre tamanho×bug, MA-SZZ é suficiente.

**Spearman ρ próximo de 0**
→ Verifique quantos repositórios estão no `resumo_por_repo.csv`. Se for < 20, o teste é fraco por construção. Junte mais repos antes de concluir.
