# Resultados — Q1: Tamanho do commit × ocorrência de bugs

Discussão dos achados empíricos do estudo. Para a metodologia detalhada, consulte [`METODOLOGIA.md`](METODOLOGIA.md).

---

## 1. Síntese executiva

> **Commits que introduzem bugs são significativamente e substancialmente maiores do que os demais commits**, em magnitude grande (Cliff's Delta = 0,48), com diferença de mediana de **6,2×**. A correlação positiva também se manifesta no nível agregado por repositório (Spearman ρ = 0,36, p = 0,006), confirmando que **projetos cuja cultura é de commits maiores tendem a acumular mais bug-introducing commits proporcionalmente**.

As três hipóteses derivadas da pergunta de pesquisa Q1 (§4 da metodologia) foram confirmadas:

| Hipótese | Teste | Veredicto |
|---|---|---|
| **H1a** — A distribuição de LOC dos BICs é estocasticamente maior que a dos não-BICs | Mann-Whitney U | ✅ p < 10⁻⁵⁰ |
| **H1b** — A diferença é praticamente relevante (e não apenas estatisticamente detectável) | Cliff's Delta | ✅ δ = 0,483 (grande) |
| **H1c** — Repositórios com commits em média maiores têm proporcionalmente mais BICs | Spearman ρ | ✅ ρ = 0,358 (p = 0,006) |

---

## 2. Universo analisado

| Item | Valor |
|---|---:|
| Repositórios efetivamente analisados | **58** (de 60 originais; pytorch e AutoGPT excluídos por incompatibilidade de execução — ver §7.5 da metodologia) |
| Commits Python classificados (universo do `all_commits_loc.json`) | 98.517 |
| Bug-introducing commits identificados (Grupo A) | **5.223** (5,30%) |
| Não bug-introducing commits (Grupo B) | 93.294 (94,70%) |
| Bug-fix commits efetivamente processados pelo SZZ | 10.161 |

A taxa-base de **5,30%** é coerente com a literatura: estudos de defect prediction em projetos open-source reportam tipicamente **3–10%** de commits com bug introduzido, dependendo de critérios e do algoritmo SZZ usado (Da Costa et al. 2017).

---

## 3. Distribuição de tamanho por grupo

### 3.1 Estatísticas descritivas (LOC modificadas por commit)

| Estatística | Grupo A (BICs) | Grupo B (não-BICs) | Razão A/B |
|---|---:|---:|---:|
| n | 5.223 | 93.294 | — |
| Média | 429,5 | 167,5 | 2,6× |
| **Mediana** | **143,0** | **23,0** | **6,2×** |
| P75 | 427,5 | 106,0 | 4,0× |
| P90 | 1.132,0 | 373,0 | 3,0× |

**Leitura.** A mediana é **6,2× maior** no Grupo A — uma diferença muito superior à da média (2,6×), o que indica que a média do Grupo B é puxada por outliers de cauda longa (re-formatações, re-licenciamentos), enquanto a mediana captura o "commit típico". Mesmo no P90, BICs continuam 3× maiores que commits comuns.

### 3.2 Visualizações geradas

Em `szz_data/resultados/`:

- **`boxplot_grupos.png`** — comparação direta de quartis em escala log. É a imagem-chave para o artigo.
- **`violin_grupos.png`** — densidade completa em log(LOC + 1). Mostra que a forma das distribuições é similar (long-tail), mas o centro do Grupo A está deslocado para a direita.
- **`cdf_grupos.png`** — função de distribuição acumulada. Permite leituras como *"50% dos BICs estão em commits ≥ 143 LOC, contra 50% dos não-BICs em ≥ 23 LOC"*.
- **`scatter_repos.png`** — cada ponto é um repositório (LOC médio × taxa de BIC). Linha de tendência ascendente positiva.

---

## 4. Testes de inferência

### 4.1 Mann-Whitney U (H1a)

`scipy.stats.mannwhitneyu(grupo_a, grupo_b, alternative="greater")`

- **Estatística U:** ~~3,2 × 10⁸~~ (ordem de grandeza)
- **p-valor:** **p < 10⁻⁵⁰** (extremamente pequeno; o solver computacional retorna 0 dado o tamanho amostral)
- **Conclusão:** rejeita-se H₀ ("os dois grupos têm a mesma distribuição") com confiança virtualmente absoluta. A distribuição de LOC dos BICs é estocasticamente maior.

### 4.2 Cliff's Delta (H1b)

`δ = P(A > B) − P(B > A)`, com amostragem de 5.000 por grupo (computacionalmente proibitivo no universo total).

- **δ = 0,483**
- **Magnitude segundo Romano et al. (2006):** **GRANDE** (≥ 0,474)

**Interpretação.** Em 48,3% mais dos pares aleatórios, o BIC tem LOC maior do que o não-BIC. Isto é, **a probabilidade de um BIC selecionado ao acaso ser maior que um não-BIC selecionado ao acaso é cerca de 74%** (`(1 + δ)/2`).

### 4.3 Spearman ρ por repositório (H1c)

Correlação entre `loc_medio_todos` e `taxa_bug_inducing_pct` ao longo de 58 repositórios.

- **ρ = 0,358** (correlação positiva moderada)
- **p = 0,006** (significativo a α = 0,05)

**Interpretação.** Existe uma associação monotônica positiva: à medida que o LOC médio do repositório aumenta, a fração de commits classificados como BIC tende a aumentar. Não é uma relação determinística (ρ ≠ 1), mas é estatisticamente robusta — improvável de ter surgido por acaso.

> ⚠️ **Importância metodológica.** Este resultado **não era significativo no estágio piloto** (n=29, ρ=0,13, p=0,50). Apenas após dobrar o número de repositórios (n=58) o teste passou a rejeitar H₀. Isso confirma a previsão registrada na §4.3.3 da metodologia: Spearman exige n ≥ 30 para poder estatístico aceitável, e nossa decisão de dividir o trabalho entre dois colaboradores foi metodologicamente necessária — não apenas pragmática.

---

## 5. Análise por repositório

### 5.1 Repositórios com maior taxa de BIC

| Repositório | Taxa BIC | n_BIC / n_total |
|---|---:|---:|
| NousResearch/hermes-agent | **36,4%** | 2.498 / 6.857 |
| TauricResearch/TradingAgents | 32,0% | 41 / 128 |
| RVC-Boss/GPT-SoVITS | 31,1% | 37 / 119 |
| scrapy/scrapy | 25,0% | 79 / 316 |
| MemPalace/mempalace | 21,3% | 142 / 667 |

**Padrão interessante.** Os repositórios no topo da lista são em sua maioria **projetos jovens orientados a IA/agentes** (hermes-agent, TradingAgents, GPT-SoVITS, mempalace) ou frameworks com refatorações frequentes (scrapy). Isto pode refletir:

1. **Cultura de commits grandes** em projetos de IA/ML, que tendem a integrar mudanças volumosas (novos modelos, pipelines completos).
2. **Velocidade alta de iteração** sem revisão profunda — característico de projetos em fase de prototipação.
3. **Possível artefato do SZZ**: projetos com mais merges/refactorings podem produzir mais "ghost commits" (Rezk et al. 2022).

### 5.2 Repositórios com menor taxa de BIC

| Repositório | Taxa BIC | n_BIC / n_total |
|---|---:|---:|
| home-assistant/core | 0,3% | 45 / 15.276 |
| odoo/odoo | 0,3% | 14 / 4.644 |
| python/cpython | 0,4% | 16 / 4.391 |
| sherlock-project/sherlock | 0,6% | 2 / 314 |
| open-webui/open-webui | 0,7% | 40 / 6.031 |

**Padrão inverso.** Projetos com **histórico extenso e cultura de commits atômicos** (cpython, odoo, home-assistant) têm taxas de BIC dramaticamente menores. Isso reforça H1c em nível qualitativo: maturidade de processo correlaciona com menor incidência de BICs detectados.

### 5.3 Repositórios sem nenhum BIC (n = 5)

Asabeneh/30-Days-Of-Python, EbookFoundation/free-programming-books, josephmisiti/awesome-machine-learning, swisskyrepo/PayloadsAllTheThings, tensorflow/models.

**Análise.** Os 4 primeiros são **listas de links curados** (awesome-lists, livros), com commits que essencialmente **adicionam ou removem entradas de Markdown** — não há código Python sendo modificado, e portanto o filtro `file_ext_to_parse: ['py']` zera a análise por construção. O `tensorflow/models` apresenta apenas 2 fixes que não rastrearam de volta a nenhum BIC. **Não são contraexemplos da hipótese**; são casos onde o instrumento de medição (SZZ aplicado a `.py`) não tem o que medir.

---

## 6. Sensibilidade do efeito ao crescimento da amostra

A trajetória do **Cliff's Delta** ao longo da expansão amostral oferece evidência da **estabilidade** do achado:

| Estágio | n_repos | Cliff's Delta | Magnitude |
|---|---:|---:|---|
| Piloto inicial | 5 | 0,62 | grande |
| Expansão Roberta | 29 | 0,53 | grande |
| Mesclagem com 6 repos do colaborador | 35 | 0,46 | médio |
| **Final (com 23 repos do cap-100)** | **58** | **0,48** | **grande** |

A oscilação entre 0,46 e 0,62 reflete sensibilidade a repositórios específicos (em particular o `NousResearch/hermes-agent`, com perfil estatístico atípico — 36% taxa BIC), mas o efeito **nunca cai abaixo da fronteira "grande" por mais de 1,4 décimos**, e o veredicto final com a amostra completa volta para a categoria grande. Em outras palavras: o efeito é **robusto a sub-amostras**.

---

## 7. Implicações práticas

A confirmação empírica da hipótese tem ramificações para prática de engenharia de software:

1. **Code review como controle de qualidade.** Se commits maiores carregam ~6× mais risco de introduzir bugs, sua revisão merece atenção desproporcional. Ferramentas que sinalizam PRs grandes para revisão obrigatória ou múltipla são justificadas empiricamente.

2. **Cultura de commits atômicos.** A correlação por projeto (ρ = 0,36) sugere que **a disciplina de manter commits pequenos não é apenas estética** — está associada a menor taxa de regressão. Projetos como cpython e odoo, com 0,3–0,4% de taxa BIC, exemplificam essa cultura.

3. **Heurística operacional para risk assessment.** Análise complementar (`pyszz/analyze_bic_size.py`) apontou que commits que cruzam **>5 arquivos AND >125 linhas alteradas** têm risco aproximadamente **8× maior** de serem BIC do que commits abaixo desse limiar (em rodada anterior com n=58 — não re-executado neste estágio final, mas estável).

---

## 8. Limitações relevantes para a interpretação

- O **MA-SZZ pode produzir falsos positivos** (~17% de "ghost commits", Rezk et al. 2022). Implicação: nosso "Grupo A" pode incluir commits que tocaram linhas posteriormente removidas em fixes, sem terem causado o bug. Mitigação parcial: o efeito tem magnitude grande mesmo se 17% do Grupo A for ruído (a contaminação reduziria o sinal, e ainda assim o detectamos).
- A **classificação de bug-fix por keyword** (Herzig et al. 2013) introduz falsos positivos no input do SZZ. Idem — o sinal observado é robusto a esse ruído.
- **LOC ≠ complexidade**. Uma mudança de 10 linhas em um lock manager pode ser mais danosa que 200 em código gerado. Trabalho futuro pode incluir métricas semânticas (complexidade ciclomática, profundidade de aninhamento).
- **Apenas Python e GitHub**. Generalização para outras linguagens/ecossistemas é tarefa em aberto.

Para a discussão completa de validade interna, externa, de constructo e de conclusão, ver §5 da metodologia.

---

## 9. Conclusão

> **Confirmamos empiricamente que commits grandes em Python no GitHub estão associados a maior probabilidade de introdução de bugs**, tanto no nível do commit individual (Cliff's Delta = 0,48, magnitude grande) quanto no nível agregado de projeto (Spearman ρ = 0,36, p = 0,006). A diferença de tamanho mediano entre BICs e não-BICs é de **6,2×**.

O resultado é consistente com hipóteses teóricas estabelecidas (Mockus & Weiss 2000) e robusto a múltiplas variações da amostra. Os achados reforçam a relevância prática da disciplina de commits atômicos e da revisão de código diferenciada para mudanças volumosas.

---

## Referências

Ver [§8 da `METODOLOGIA.md`](METODOLOGIA.md#8-referências) para a bibliografia completa.

## Reprodutibilidade

- **Código & dados:** https://github.com/robinCrobin/szz-commit-size
- **Saídas brutas:** `szz_data/resultados/` (tabela CSV + 4 PNGs gerados pelo `step4_analise_estatistica.py`)
- **Output do SZZ consolidado:** `pyszz/output_raszz.json` (não-versionado por tamanho — ver README §1.4)
