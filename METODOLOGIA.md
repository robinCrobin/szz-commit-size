# Metodologia

Documento de apoio descrevendo as escolhas metodológicas do estudo, com justificativas e ancoragem na literatura. Estruturado para ser adaptado a uma seção de Metodologia / Methods em artigo.

---

## 1. Pergunta de pesquisa

A questão central é:

> **Q1.** Qual é a relação entre o tamanho do commit e a probabilidade de o commit ser *bug-introducing* (segundo o SZZ)?

Decompomos Q1 em uma pergunta primária e três subperguntas correlatas:

> **Q1₀ (principal).** Categorizando commits em **pequeno / médio / grande** pelos limiares bidimensionais de **Hattori & Lanza (2008)** (arquivos × LOC), a probabilidade condicional `P(BIC | classe)` cresce monotonicamente do menor para o maior? (taxa por classe com IC 95% Wilson + teste de tendência de Cochran-Armitage)
>
> **Q1a.** A composição de classes (pequeno/médio/grande) dentro do Grupo A (BIC) difere significativamente da do Grupo B (não-BIC)? (χ² de Pearson + Cramer's V)
>
> **Q1b.** A nível de projeto, repositórios com proporção maior de commits **grandes** apresentam taxa proporcional de BICs mais alta? (Spearman ρ por repositório)

Q1₀ é a evidência primária — ela responde diretamente à pergunta de pesquisa em termos *condicionais* nomeados ("commits da classe X têm Y% de probabilidade de introduzir bug"), formato que tanto facilita a leitura do estudo quanto torna explícito *o que* se considera pequeno ou grande. Q1a–b triangulam o mesmo fenômeno por outras perspectivas — composição de classes dentro de cada grupo (χ²) e comportamento agregado por projeto (Spearman).

**Importante**: todas as análises são feitas sobre a classificação Hattori & Lanza (2008). Não comparamos LOC bruto entre grupos. A justificativa foi metodológica: comparar distribuições de LOC entre BIC e não-BIC responde a uma sub-pergunta (*"BICs tendem a ser maiores?"*) mas não torna explícito *o que conta como pequeno/grande* nem *quão mais provável* cada classe é de introduzir um bug. Ao operar exclusivamente sobre as classes nomeadas, todos os resultados podem ser lidos como afirmações condicionais com classes definidas a priori pela literatura.

A intuição teórica vem do trabalho seminal de **Mockus & Weiss (2000)**, que demonstraram que a probabilidade de defeito cresce com o tamanho da mudança em sistemas telecom da AT&T. Estudos posteriores em projetos open-source (Eyolfson et al. 2014; Kamei et al. 2013) reforçam que LOC é um dos preditores mais robustos de defeito em modelos de *just-in-time defect prediction*.

---

## 2. Coleta de dados

### 2.1 Seleção de repositórios

Foram selecionados **60 repositórios Python** populares no GitHub, abrangendo desde frameworks consagrados (django, scikit-learn, pytorch, cpython) até projetos menores e de nicho. Os critérios foram:

- **Linguagem primária Python** — restringe o domínio para análise reprodutível e permite uso direto do parser de comentários nativo do `pyszz`.
- **Diversidade de tamanho** — inclui projetos com histórico denso (django ~25 anos) e projetos jovens, controlando contra viés de seleção em projetos exclusivamente maduros.
- **Atividade recente** — todos os repos têm commits nos últimos 12 meses, garantindo dados de blame válidos.

> **Ressalva (validade externa).** A escolha por projetos populares no GitHub introduz **viés de popularidade** (Bird et al. 2009): projetos amplamente usados tendem a ter melhores práticas de commit, revisão de código e CI. Generalizações para projetos enterprise, closed-source ou em outras linguagens devem ser feitas com cautela.

### 2.2 Identificação de bug-fix commits

Para cada commit do histórico de cada repositório, marcamos como `is_bug_fix = True` se a mensagem contiver alguma das palavras-chave (case-insensitive):

```
fix, bug, error, hotfix, patch, defect, fault, issue, crash, exception, correction, repair, resolve
```

Esta é a abordagem clássica baseada em texto, originada em **Mockus & Votta (2000)** e formalizada em **Antoniol et al. (2008)**.

> **Ressalva (validade de constructo).** **Herzig et al. (2013)** demonstraram que rotular bug-fix por palavras-chave produz uma taxa de classificação errada de até **30-40%** em alguns projetos — incluem mudanças não-bug ("fix typo in docs", "fix indentation") e perdem fixes sem palavras-chave. Esta limitação é declarada e reconhecemos seu efeito potencial sobre o sinal medido. Uma alternativa mais precisa seria *issue-link mining* (cruzar SHA com issue tracker e filtrar por tipo "bug"), porém demanda dados não disponíveis para todos os 60 repos.

### 2.3 Identificação de bug-introducing commits — SZZ

**Algoritmo escolhido: MA-SZZ** (Meta-change Aware SZZ; Da Costa et al. 2017), implementado no [`pyszz_v2`](https://github.com/grosa1/pyszz_v2). Os parâmetros foram:

| Parâmetro | Valor | Justificativa |
|---|---|---|
| `szz_name` | `ma` | MA-SZZ filtra meta-mudanças (formatação, comentários, refatorações triviais) que produzem falsos positivos clássicos. |
| `max_change_size` | `999999` | **Filtro desativado intencionalmente.** Veja seção 2.4. |
| `filter_revert_commits` | `True` | Reverts apontam para o commit revertido pelo blame, mas não introduziram bug — são meta-mudanças. |
| `only_deleted_lines` | `True` | Heurística clássica do SZZ: blame sobre linhas que foram **removidas** pelo bug-fix (Śliwerski et al. 2005). |
| `file_ext_to_parse` | `['py']` | Restringe blame a arquivos Python (relevantes para o código de produção). |
| `detect_move_from_other_files` | `1` (SAME_COMMIT) | Detecta linhas movidas no mesmo commit, reduzindo falsos negativos por refactoring trivial (Kim et al. 2006). |

#### Por que MA-SZZ e não BaseSZZ ou RA-SZZ?

- **BaseSZZ** (Śliwerski et al. 2005): primeiro algoritmo, mas conhecido por incluir muitos falsos positivos de mudanças triviais que apenas "tocam" linhas (espaço em branco, comentários).
- **AG-SZZ** (Kim et al. 2006): adicionou ignorar mudanças cosméticas, mas ainda confunde refactoring com bug introduction.
- **MA-SZZ** (Da Costa et al. 2017): **estado-da-arte amplamente adotado**, exclui explicitamente *meta-changes* (renames, formatting, comment-only changes, reverts). É o ponto de equilíbrio entre precisão e custo computacional.
- **RA-SZZ** (Neto et al. 2018): adiciona detecção de refatoração via RefactoringMiner. Empiricamente, **Rosa et al. (2021)** mostraram melhoria modesta (~3-5% em F-measure) sobre MA-SZZ, ao custo de execução **5-20× mais lenta** (chama JVM/RefactoringMiner por commit candidato). Para a Q1 (efeito de tamanho), MA-SZZ oferece a melhor relação custo-benefício.

### 2.4 Cuidado crítico — desativação do filtro de tamanho

O parâmetro `max_change_size` no MA-SZZ exclui da lista de candidatos a BIC qualquer commit que tenha modificado mais arquivos que o limiar (default: 20). **Este filtro foi desativado intencionalmente** (definido em 999.999) para esta análise, pelo motivo abaixo:

> **A hipótese H1 do estudo é justamente que commits maiores são mais propensos a introduzir bugs.** Se aplicássemos o filtro padrão, commits grandes seriam *a priori* descartados como candidatos, e a análise estaria circularmente respondendo "commits grandes não causam bugs" — porque foram impedidos de aparecer como tal. A desativação é uma decisão deliberada para evitar **viés de seleção contra a hipótese**.

Para ainda assim mitigar falsos positivos, mantivemos os filtros **independentes de tamanho**:
- `select_meta_changes` (interno do MA-SZZ): exclui commits que só mexem em comentário/whitespace/formatação.
- `filter_revert_commits`: exclui reverts.
- `get_merge_commits`: exclui commits de merge.
1
### 2.5 Amostragem do conjunto de bug-fix commits

Para cada repositório com mais de 100 bug-fix commits identificados pela heurística de keyword (§2.2), aplicou-se **amostragem aleatória simples sem reposição** (`random.sample`, semente fixa `seed = 42`) selecionando 100 fixes para serem submetidos ao SZZ. Repositórios com 100 ou menos fixes foram processados integralmente.

A amostragem incide **exclusivamente sobre o conjunto de bug-fix commits** — o *input* do SZZ. O **universo de commits** utilizado na classificação Grupo A (bug-introducing) vs Grupo B (não-bug-introducing) preserva o conjunto completo de commits dos repositórios (registrado em `all_commits_loc.json`). Em outras palavras, o cap reduz o conjunto de *consultas* feitas ao SZZ, não o universo amostral final de commits classificados.

#### Motivação prática

A execução do SZZ em todos os fixes seria inviável: repositórios como `litellm` (19 058 fixes), `airflow` (10 564), `pandas` (5 012) ou `pytorch` (~13 000) implicariam dias de execução por repositório. O cap de 100 fixes por repositório torna o estudo factível mantendo cobertura ampla de projetos.

#### Implicação para o poder de detecção

Cada fix processado pelo SZZ abre uma janela de blame que pode identificar BICs. Reduzir o número de fixes processados de N para 100 reduz a probabilidade de identificar BICs por fator aproximado de `100/N`. Commits que **seriam** apontados como BIC apenas por fixes descartados ficam classificados como Grupo B mesmo se, em uma execução exaustiva, seriam Grupo A. O viés resultante é discutido formalmente na §5.1.

#### Heterogeneidade na coleta (transparência)

Cinco dos 58 repositórios originais foram processados **antes** da decisão do cap (fase piloto §7.2: `django` n=528, `scikit-learn` n=281) ou pelo colaborador sem cap (`hermes-agent` n=4 427, `mempalace` n=407, `EbookFoundation/free-programming-books` n=185). Esses cinco repositórios permanecem com seus tamanhos amostrais originais. Os 53 demais e todos os repositórios adicionados em lotes posteriores seguem o cap de 100. Essa heterogeneidade é reconhecida como limitação metodológica (§5.1) e não foi normalizada retroativamente para preservar os dados já coletados.

---

## 3. Variável dependente — LOC modificado

Para cada commit, computamos:

```
loc(commit) = sum_{m ∈ commit.modifications} (lines_added(m) + lines_deleted(m))
```

via PyDriller (`commit.modifications`). Excluímos:
- Commits de **merge** (`commit.merge == True`).
- Commits com `loc == 0` (e.g., apenas alterações de modo de arquivo).

> **Ressalva (validade de constructo).** **LOC é uma proxy imperfeita do "tamanho" cognitivo de uma mudança.** Não captura complexidade ciclomática, profundidade de aninhamento, ou impacto semântico (uma mudança de 5 linhas em um lock manager pode ser mais impactante que 500 linhas de código gerado). Métricas alternativas — *cyclomatic complexity churn* (Hindle et al. 2008), *McCabe delta*, ou medidas de coupling — poderiam refinar a análise em trabalho futuro. Optamos por LOC pela simplicidade, reprodutibilidade e por ser a métrica dominante na literatura de defect prediction (Kamei et al. 2013).

---

## 4. Análise estatística

### 4.1 Definição dos grupos

- **Grupo A** (`bug_introducing`): commits identificados pelo MA-SZZ como introdutores de bug em pelo menos um fix subsequente.
- **Grupo B** (`not_bug_inducing`): todos os demais commits do repositório (não bug-fix e não bug-introducing).
- **Excluídos da comparação principal**: commits classificados como `bug-fix` mas que o SZZ **não** rastreou de volta a um BIC (chamamos `bug_fix_only`). Razão: incluí-los no Grupo B contaminaria a categoria de "commits limpos"; incluí-los no Grupo A criaria circularidade.

### 4.2 Filtro de viés por repositório

Após o cruzamento, **filtramos os CSVs** para incluir apenas repositórios efetivamente avaliados pelo SZZ. Isso evita que repositórios não rodados (presentes apenas em `all_commits_loc.json`) contribuam com `n_bug_inducing = 0` por construção, distorcendo o Spearman.

### 4.3 Testes

| Pergunta | Teste | Saída |
|---|---|---|
| **Q1₀ — qual a relação entre tamanho e ocorrência de bugs?** | **Taxa de BIC por classe (Hattori & Lanza 2D) + Cochran-Armitage** | taxa por classe com IC 95% Wilson; Z, p-valor |
| Q1a — a composição de classes difere entre BICs e não-BICs? | **χ² de Pearson + Cramer's V** sobre tabela 3×2 (classe × grupo) | χ², gl, p-valor; V ∈ [0, 1] |
| Q1b — correlação por projeto? | **Spearman ρ** entre `pct_grande` e `taxa_bic_pct` por repositório | ρ ∈ [-1, 1], p-valor |

> **Hierarquia das perguntas.** Q1₀ é a pergunta primária da pesquisa — ela é respondida em termos *condicionais* (`P(BIC | classe)`), que é a direção natural para um leitor que quer aplicar o achado. Q1a e Q1b respondem perguntas correlatas (a composição interna de cada grupo difere? por projeto, repos com mais commits grandes têm mais bugs?) e servem como triangulação independente do mesmo fenômeno.

#### 4.3.0 Taxa de bug-introducing por classe de tamanho (análise principal)

**Motivação.** Comparar a distribuição de LOC entre BICs e não-BICs (Q1a–b) responde *"BICs tendem a ser maiores?"*, mas não torna explícito *o que conta como pequeno/grande* nem *quão mais provável* é cada classe introduzir um bug. A análise por classe inverte a condicional para `P(BIC | tamanho)` e usa limiares nomeados e citáveis.

**Classes (Hattori & Lanza, 2008 — *"On the Nature of Commits"*).** Categorização bidimensional usando simultaneamente número de arquivos e LOC alteradas:

| Classe   | Regra                                                                  |
|----------|------------------------------------------------------------------------|
| pequeno  | arquivos ≤ 5 **E** LOC ≤ 25                                            |
| grande   | arquivos > 5 **E** LOC > 125                                           |
| medio   | demais commits (volume controlado em uma das duas dimensões)            |

A escolha por limiares de **Hattori & Lanza (2008)** ao invés de quartis do próprio dataset é deliberada: (i) são valores publicados e replicáveis, permitindo comparação direta com outros estudos; (ii) eliminam a circularidade de derivar o limiar dos próprios dados que estão sendo testados.

**Estatística por classe.** Para cada classe calculamos:

- `n_total` — total de commits da classe no universo analisado.
- `n_bic` — quantos foram marcados como BIC pelo SZZ.
- `taxa_bic = n_bic / n_total` — estimativa pontual de `P(BIC | classe)`.
- **IC 95% de Wilson** sobre `taxa_bic`. Justificativa: para proporções com `n` muito heterogêneos entre classes (a classe `grande` costuma ter `n` uma ordem de grandeza menor que a `pequeno`) e/ou próximas dos extremos, o IC normal (Wald) subestima incerteza e pode até estender abaixo de 0. Wilson (1927) tem cobertura nominal correta nesses regimes e é a recomendação padrão em Brown, Cai & DasGupta (2001) — *"Interval Estimation for a Binomial Proportion"*.

**Teste formal de tendência — Cochran-Armitage (Armitage 1955).** Atribuímos scores ordinais 0/1/2 às classes pequeno/médio/grande e testamos a hipótese:

- **H0**: `P(BIC | pequeno) = P(BIC | medio) = P(BIC | grande)` (taxa independe da classe).
- **H1**: existe tendência linear monotônica em função do score.

A estatística é `Z = numerador / √variância`, distribuída aproximadamente como `N(0,1)` sob H0. **Por que não χ² genérico**: o χ² de independência ignora a *ordem* das categorias — perde poder para detectar exatamente o que nos interessa (uma relação monotônica). Cochran-Armitage usa essa informação ordinal e é o teste canônico para tendência em proporções em estudos epidemiológicos e de engenharia de software empírica (Agresti 2002, *Categorical Data Analysis*, §3.4).

**Saídas geradas** (`step4_analise_estatistica.py`):

- `szz_data/resultados/taxa_bug_por_classe.csv` — tabela com `n_total`, `n_bic`, `taxa_bic_pct`, `ic95_lo_pct`, `ic95_hi_pct` e medianas de LOC/arquivos por classe.
- `szz_data/resultados/bug_rate_por_classe.png` — barras com IC 95% e `n` anotado. **Figura principal do estudo.**
- Linhas correspondentes em `resultados_q1.csv` e no resumo final do terminal.

**Como reportar (template para o artigo):**

> Aplicando os limiares bidimensionais de Hattori & Lanza (2008), commits pequenos (≤5 arquivos e ≤25 LOC) apresentaram taxa de bug-introducing de X% (IC 95% Wilson [a, b]; n=N₁), commits médios Y% [c, d] (n=N₂) e commits grandes Z% [e, f] (n=N₃). O teste de tendência de Cochran-Armitage rejeita a hipótese nula de equivalência das taxas (Z=…, p<0,001) com tendência crescente, evidenciando relação monotônica positiva entre tamanho do commit e probabilidade de introduzir bugs.


#### 4.3.1 χ² de Pearson + Cramer's V (composição classe × grupo) — Q1a

**Pergunta**: a composição interna do Grupo A (BIC) — quanto é pequeno, médio ou grande — difere significativamente da composição do Grupo B (não-BIC)? Operacionalmente, montamos a tabela de contingência 3×2:

|         | Bug-Introducing | Não Bug-Introducing |
|---------|-----------------|---------------------|
| pequeno |       …         |          …          |
| medio   |       …         |          …          |
| grande  |       …         |          …          |

Aplicamos `scipy.stats.chi2_contingency`. **Cramer's V** é calculado como `V = √(χ² / (N · (k−1)))` com `k = min(linhas, colunas) = 2`, fornecendo um tamanho de efeito normalizado em `[0, 1]`.

**Thresholds (Cohen 1988, para `df* = k − 1 = 1`):**

| `V`           | Magnitude   |
|--------------:|-------------|
| < 0,10        | negligível  |
| < 0,30        | pequeno     |
| < 0,50        | médio       |
| ≥ 0,50        | grande      |

**Por que esse teste e não Mann-Whitney sobre LOC**: Mann-Whitney compara distribuições contínuas de LOC entre grupos — mas a Q1a foi reformulada para operar sobre as classes Hattori & Lanza, de modo a manter coerência com o resto da análise. χ² é o teste canônico para associação entre variáveis categóricas, e Cramer's V é seu tamanho de efeito padrão (Cohen 1988).

**Complementaridade com Cochran-Armitage (Q1₀):** Cochran-Armitage olha `P(BIC | classe)` (taxa condicional, fixando a classe). χ² olha `P(classe | grupo)` (composição condicional, fixando o grupo). Os dois cobrem o fenômeno por perspectivas distintas e independentes.

**Referências:**
- Pearson, K. (1900). *On the Criterion that a Given System of Deviations from the Probable in the Case of a Correlated System of Variables…* Philosophical Magazine.
- Cramér, H. (1946). *Mathematical Methods of Statistics*. Princeton University Press.
- Cohen, J. (1988). *Statistical Power Analysis for the Behavioral Sciences* (2ª ed.). Lawrence Erlbaum.

#### 4.3.2 Spearman ρ por repositório — Q1b

**Pergunta**: repositórios em que commits grandes são proporcionalmente mais frequentes apresentam taxa de bug-introducing mais alta?

Para cada repositório calculamos dois números:
- `pct_grande` — % de commits do repo classificados como grandes (Hattori & Lanza).
- `taxa_bic_pct` — % de commits do repo marcados como BIC pelo SZZ.

Aplicamos `scipy.stats.spearmanr` sobre os 58 pares `(pct_grande, taxa_bic_pct)`.

**Por que `pct_grande` e não LOC médio**: alinha Q1b com Q1₀ e Q1a (todas operam sobre classes), e evita que outliers de LOC distorçam a média do repositório. Conceitualmente também faz mais sentido: a métrica `LOC médio` é dominada por poucos commits gigantes; `pct_grande` é uma medida de *frequência* da prática "fazer commits grandes" no projeto.

**Por que Spearman e não Pearson**: testa correlação **monotônica**, não exige linearidade nem normalidade. Robusto a outliers — repositórios atípicos não dominam o resultado.

> **Ressalva (poder estatístico).** Spearman exige **n ≥ 20–30** repositórios para poder estatístico aceitável. Com n menor, tende a não-rejeitar H0 mesmo havendo correlação real. O estudo atual usa 58 repositórios — suficiente.

### 4.4 Análise complementar — risk ratio binário (`analyze_bic_size.py`)

Como leitura adicional, mantemos o script `pyszz/analyze_bic_size.py` que dicotomiza os commits em **"grande" (`>5 arquivos AND >125 linhas alteradas`)** vs **"pequeno"** e calcula:

```
risk_ratio = P(BIC | grande) / P(BIC | pequeno)
```

> **Ressalva.** Esta dicotomização agrega a classe "medio" (na categorização Hattori & Lanza 2D usada em §4.3.0) ao lado "pequeno". É retida como visualização compacta — "commits que cruzam o limiar têm K× mais chance de introduzir bug" — comum em estudos com framing epidemiológico (Eyolfson et al. 2014). **Não substitui** a análise por classe ordinal (§4.3.0), que preserva o gradiente médio e é a evidência principal apresentada no artigo.

---

## 5. Ameaças à validade

Seguindo a taxonomia de **Wohlin et al. (2012)**:

### 5.1 Validade interna

- **SZZ produz falsos positivos.** Mesmo MA-SZZ apresenta erros — **Rezk et al. (2022)** reportam ~17% de "ghost commits" (apontados pelo blame mas que não introduziram o bug). **Mitigação:** uso de MA-SZZ (mais conservador que Base/AG-SZZ) e filtro adicional de reverts.
- **`is_bug_fix` por keyword é heurística** com erro estimado em 30% (Herzig et al. 2013). **Mitigação:** declaração explícita; valida análise com sub-amostra de fixes verificáveis em trabalho futuro.
- **Amostragem do conjunto de bug-fix commits reduz o poder de detecção do SZZ** (§2.5). Commits que seriam identificados como bug-introducing apenas por fixes não amostrados ficam classificados como Grupo B, inflando-o e atenuando o efeito medido. **Direção do viés:** conservador em relação à hipótese principal (subestima a diferença Grupo A vs B). **Impacto desigual por análise:**
  - *Q1₀ (taxa por classe — Cochran-Armitage):* afetado de forma modesta — agregamos por classe através de todos os repositórios; o efeito relativo entre classes é preservado se BICs perdidos têm distribuição uniforme de tamanho. Se BICs grandes vierem desproporcionalmente de repositórios capados (grandes), o efeito é atenuado — viés conservador.
  - *Q1a (χ² + Cramer's V):* afetado de forma modesta pela mesma razão.
  - *Q1b (Spearman por repositório):* afetado de forma mais expressiva — a `taxa_bic_pct` reportada para repositórios grandes está sistematicamente subestimada (numerador reduzido, denominador inalterado), o que pode atenuar a correlação por projeto.
- **Heterogeneidade na amostragem entre repositórios** (§2.5). Cinco repositórios foram processados sem cap por motivos históricos (piloto e fase pré-decisão pelo colaborador), enquanto os demais seguem o cap de 100. O outlier `hermes-agent` (4 427 fixes) sozinho domina aproximadamente 44% dos fixes totais nos 58 repositórios originais, podendo enviesar o agregado em sua direção específica. **Mitigação:** declaração explícita; análise de sensibilidade variando o cap (50, 100, 300) em sub-amostra é apontada como trabalho futuro.

### 5.2 Validade externa

- **Apenas Python**, apenas **GitHub**, apenas **projetos populares**. Generalizações para outras linguagens, ecossistemas (npm, Maven privados) ou enterprise software requerem estudos adicionais.
- **Janela temporal**: analisamos o histórico completo dos repositórios; mudanças em práticas de engenharia ao longo dos anos podem afetar o sinal (estilos de commit modernos vs antigos).
- **Repositórios excluídos por incompatibilidade de execução**: 2 dos 60 repositórios originais ficaram fora da análise final — `pytorch/pytorch` (incompatibilidade NTFS/case-sensitivity em Windows) e `Significant-Gravitas/AutoGPT` (erros recorrentes do SZZ). Detalhes em §7.5. O universo efetivo é portanto **58 repositórios**.

### 5.3 Validade de constructo

- **LOC ≠ tamanho cognitivo da mudança.** Discutido em §3.
- **Definição operacional de BIC = output do MA-SZZ.** Não é verdade absoluta — é a melhor aproximação automatizável dado o estado-da-arte. **Rosa et al. (2023)** discutem trade-offs entre as variantes.

### 5.4 Validade de conclusão

- **Múltiplas comparações.** Reportamos três testes (Cochran-Armitage, χ² + Cramer's V, Spearman) sobre a mesma amostra. Embora cada um responda uma pergunta diferente — tendência ordinal (Q1₀), composição categórica (Q1a), correlação por projeto (Q1b) —, uma correção de Bonferroni poderia ser discutida se quisermos um critério ainda mais conservador. Dada a magnitude dos efeitos observados (Z>50 em Cochran-Armitage; χ² na ordem de 10³), os testes têm robustez suficiente sem correção.

---

## 6. Reprodutibilidade

- **Código aberto** em https://github.com/robinCrobin/szz-commit-size (este repositório).
- **Configuração SZZ** em [`pyszz/conf/raszz.yml`](pyszz/conf/raszz.yml) (parâmetros exatos da execução).
- **Sementes aleatórias** fixas (e.g., `random.seed(42)` no sampling de fixes por repositório).
- **Versões de dependências** em [`pyszz/requirements.txt`](pyszz/requirements.txt).
- **Universo de commits** distribuído junto ao código (via `commits_clean.csv` + `all_commits_loc.json`, fora do git por tamanho — ver README §1.4).

---

## 7. Execução: trajetória empírica, decisões e incidentes

Esta seção documenta a execução **real** do estudo — escolhas pragmáticas, otimizações aplicadas, problemas encontrados e como foram resolvidos. Esse histórico é importante para **rastreabilidade**, **reprodutibilidade**, e para fundamentar honestamente as limitações declaradas na §5.

### 7.1 Origem dos dados (etapa pré-SZZ)

A fonte primária do estudo é o arquivo `commits_clean.csv` (≈ 28 MB), gerado externamente em fase anterior da pesquisa pelo grupo. Cada linha representa um commit com os campos: `repo_name`, `commit_sha`, `date`, `total_loc_modified`, `files_changed`, `is_bug_fix` (heurística por keyword), `is_revert`, `message`. Esse universo cobre 60 repositórios Python populares do GitHub.

A partir desse CSV, o script [`step1_adaptar_csv.py`](step1_adaptar_csv.py) gera dois artefatos:

- `szz_data/bugfix_commits.json` — entrada do SZZ, lista de `{repo_name, fix_commit_hash}` filtrada para `is_bug_fix == True` e `is_revert == False`.
- `szz_data/all_commits_loc.json` — universo completo de commits com LOC, usado pelo step3 como denominador na classificação Grupo A vs Grupo B.

Adicionalmente, o step1 clona localmente os repositórios em `repos/<owner>/<repo>` (≈ 4,5 GB no total). O clone local é necessário porque o algoritmo SZZ depende de `git blame` em todos os arquivos modificados pelos bug-fixes — operação que seria proibitivamente lenta via API remota do GitHub.

### 7.2 Estudo piloto: validação metodológica em 5 repositórios

Antes de comprometer dezenas de horas de execução, validamos toda a pipeline em uma amostra de 5 repositórios escolhidos por **diversidade de tamanho** (não por conveniência):

| Repositório | Fixes | Justificativa |
|---|---:|---|
| Textualize/rich | 51 | repositório pequeno, pipeline rápido |
| pallets/flask | 15 | menor da amostra, sanity-check |
| scrapy/scrapy | 71 | médio, usa estrutura de packages típica |
| django/django | 528 | grande, histórico denso |
| scikit-learn/scikit-learn | 281 | grande, ML/cientifico |

Resultado do piloto (137 + 809 = 946 fixes processados):

- Mann-Whitney U: p ≈ 5,9 × 10⁻⁵⁷
- Cliff's Delta: 0,62 (magnitude **grande**)
- Mediana Grupo A vs B: **168,5 vs 18 LOC** (~9× maior)

O efeito foi **suficientemente claro mesmo com n pequeno** para validar a metodologia. O Spearman foi não-significativo (n=5 é insuficiente), o que motivou a expansão para mais repositórios.

### 7.3 Otimizações de execução aplicadas

A execução nativa do `pyszz_v2` apresentou tempo proibitivo. As seguintes modificações foram aplicadas no fork (ver [README §Créditos](README.md)):

#### 7.3.1 Reuso de clone por repositório

**Problema identificado.** O `pyszz/main.py` original, no upstream, instancia uma nova classe SZZ a cada bug-fix e cada `__init__` clona o repositório em um diretório temporário (`_szztemp/`) via `Repo.clone_from(... '--local')`. Para 946 fixes do piloto e 528 fixes só do `django/django`, isso significa **528 clones idênticos do mesmo repo** num único run.

**Resolução.** Modificamos `main.py` para ordenar bugfixes por `repo_name` e **reutilizar a mesma instância SZZ** entre fixes do mesmo repositório, dispondo dela apenas na transição. Ganho observado: redução de ~80% no tempo de execução em repos grandes.

#### 7.3.2 Salvamento parcial a cada 10 fixes

**Problema identificado.** O upstream salva o JSON apenas no fim. Em runs de muitas horas, qualquer interrupção (crash, energia, kill) implicaria perda total.

**Resolução.** Adicionamos `SAVE_EVERY = 10` em `main.py`, gravando `pyszz/out/bic_raszz_<ts>.partial.json` a cada 10 fixes processados. Esse arquivo é **resiliente a crashes** e foi crítico no incidente descrito em §7.5.

#### 7.3.3 Memoização de `_exclude_commits_by_change_size`

**Problema identificado.** Em `pyszz/szz/ag_szz.py`, a função `_exclude_commits_by_change_size` é chamada repetidamente para o mesmo `commit_hash` ao longo do `find_bic` (uma vez por entrada de blame). Cada chamada inicializa um `RepositoryMining` do PyDriller — operação não-trivial.

**Resolução.** Cache simples por hash em `self.__exclude_size_cache: Dict[Tuple[str, int], Set[str]]`. Custo de memória negligível, ganho marginal mas grátis.

#### 7.3.4 Configuração calibrada

`pyszz/conf/raszz.yml` foi customizada para o estudo:

```yaml
szz_name: "ma"                  # MA-SZZ
file_ext_to_parse: ["py"]       # apenas Python
only_deleted_lines: true        # heuristica classica
issue_date_filter: false        # nao filtramos por data de issue
max_change_size: 999999         # DESATIVADO (ver §2.4)
detect_move_from_other_files: 1 # SAME_COMMIT
filter_revert_commits: true     # exclui reverts
```

### 7.4 Amostragem por cap de fixes

Após o piloto, planejamos analisar os 60 repositórios restantes — alguns deles muito grandes:

| Repositório | Fixes no universo | Tempo estimado |
|---|---:|---:|
| pytorch/pytorch | 13.790 | ~3,5 dias |
| NousResearch/hermes-agent | 4.427 | ~28 h |
| odoo/odoo | 3.885 | ~24 h |

Rodar todos os fixes seria inviável. Optou-se pela **estratégia de cap aleatório**: para cada repositório com mais de 100 bug-fixes, **amostrar 100 fixes aleatoriamente** (semente `random.seed(42)`). Para repositórios com ≤ 100 fixes, usar todos.

**Justificativa metodológica.** A amostragem aleatória dentro de cada repositório **não enviesa a comparação Grupo A vs Grupo B**: ambos os grupos são afetados proporcionalmente. O que se reduz é o tamanho amostral nominal (≈ 2k–3k fixes em vez de dezenas de milhares), o que afeta apenas o poder estatístico — não a validade. Com efeito de magnitude grande (Cliff's Delta ≥ 0,5), o teste M-W permanece massivamente significativo mesmo com amostras de 5.000 commits.

A divisão de trabalho prevista é de **30 repositórios por colaborador** (total ≈ 60 com a outra pessoa). Os arquivos de configuração compartilhados (`bugfix_commits.json`, `all_commits_loc.json`) garantem que ambas as execuções usem o mesmo universo.

### 7.5 Incidentes: repositórios excluídos (pytorch e AutoGPT)

Durante a execução, **dois repositórios** apresentaram problemas e foram excluídos da análise:

#### 7.5.1 pytorch/pytorch (incompatibilidade de filesystem)

**Incidente.** O processo abortou em 2026-05-05 às 07:52:33 ao tentar clonar `pytorch/pytorch` no diretório temporário do SZZ:

```
fatal: unable to checkout working tree
warning: Clone succeeded, but checkout failed.
```

**Diagnóstico.** O repositório `pytorch/pytorch` contém arquivos cuja diferença está **apenas em maiúsculas/minúsculas** (e.g., `aten/src/.../foo.cpp` vs `aten/src/.../FOO.cpp`). O sistema de arquivos NTFS do Windows é **case-insensitive** por padrão, o que causa colisão durante o `git checkout`. O clone original em `repos/pytorch/pytorch` permaneceu intacto; a falha foi exclusivamente no clone interno do SZZ via `Repo.clone_from(... '--local')`, que recria a árvore de trabalho.

#### 7.5.2 Significant-Gravitas/AutoGPT (erros de execução)

**Incidente.** Durante o run do colaborador na fase de coleta paralela, o repositório `Significant-Gravitas/AutoGPT` apresentou erros de execução repetidos no SZZ. O colaborador **removeu o repositório do input** e prosseguiu com os 23 restantes.

#### Decisão

Ambos foram **excluídos da análise** após autorização explícita ("se continuar dando muito erro, apenas anote que esse repositório apresentou problemas e vai ser deixado fora da análise"). Tentativas de contornar problemas de filesystem (habilitar `core.protectNTFS=false`, migrar para WSL) foram avaliadas e rejeitadas pelo custo-benefício, dado que (a) cada repo excluído representa 100 fixes amostrados — perda marginal sobre 10.000+ fixes totais, e (b) a hipótese é robusta o suficiente para que perdas pontuais não comprometam a inferência.

**Limitação declarada.** Os 2 repositórios excluídos representam uma **limitação de validade externa**: em sistemas Linux/macOS (case-sensitive por padrão), pytorch seria processado normalmente. Esta limitação é citada na §5.2. O universo final efetivamente analisado é de **58 repositórios** (de 60 originais).

### 7.6 Recuperação após o crash

Após o aborto, os 1.710 fixes já processados estavam salvos em `pyszz/out/bic_raszz_<ts>.partial.json` graças ao salvamento incremental (§7.3.2). Para retomar:

1. **Diagnóstico do partial.** Script `python` ad-hoc identificou repositórios completos vs pendentes. 1.710 fixes em 20 repositórios completos; 391 fixes pendentes em 6 repositórios.
2. **Filtro do input de retomada.** Construído `bugfix_commits_retomada.json` contendo apenas os 291 fixes pendentes em 5 repositórios (excluindo os 100 do pytorch).
3. **Re-execução.** SZZ disparado novamente em prioridade `BelowNormal` (anti-overheat) sobre o input filtrado. Concluiu em ~40 minutos.
4. **Mesclagem.** Script ad-hoc combinou:
   - 137 fixes do piloto inicial (rich + flask + scrapy)
   - 809 fixes do segundo run do piloto (django + scikit-learn)
   - 1.710 fixes do partial pré-crash (excluindo pytorch)
   - 291 fixes da retomada
   - **Total: 2.947 fixes em 29 repositórios**, sem duplicatas (verificado por `(repo, fix_commit_hash)` único).

### 7.7 Pequenos bugs corrigidos durante a execução

Documentados para rastreabilidade:

- **Encoding cp1252 no Windows.** Os scripts `step3` e `step4`, ao serem executados com stdout redirecionado a arquivo, falharam em emojis (`✅`) e setas Unicode (`→`). Corrigido com `$env:PYTHONIOENCODING="utf-8"` no shell e `sys.stdout.reconfigure(encoding='utf-8')` em `analyze_bic_size.py`.
- **`step3_enriquecer_com_loc_adaptado.py` incompatível.** Uma versão antiga "adaptada" do step3 esperava `commits_metodologia.csv` (arquivo inexistente) e produzia colunas com nomes incompatíveis com o que o `step4_analise_estatistica.py` lê (`total_loc_modified` em vez de `loc`, `not_involved` em vez de `not_bug_inducing`). O arquivo foi **removido do projeto** para evitar uso acidental. A versão canônica é `step3_enriquecer_com_loc.py`.
- **Filtro de viés do `all_commits_loc.json`.** O `all_commits_loc.json` cobre os 60 repositórios do CSV original. Quando o SZZ é rodado em apenas um subset (29 repositórios neste caso), os repositórios não-rodados aparecem em `commits_classificados.csv` com `n_bug_inducing = 0` por construção (não pelo SZZ não tê-los analisado). Isso contaminaria especialmente a Spearman ρ, puxando-a artificialmente para zero. **Mitigação aplicada**: após o step3, filtrar `commits_classificados.csv` e `resumo_por_repo.csv` para conter apenas os repositórios efetivamente rodados pelo SZZ. Versão completa preservada com sufixo `_full.csv` para auditoria.

### 7.8 Resultados finais (n = 58 repositórios)

Após a entrega do segundo lote pelo colaborador (23 repositórios + 6 já completos = 29 do colaborador) e a mesclagem com os 29 repositórios deste autor, totalizamos **58 repositórios efetivos** (60 originais menos pytorch e AutoGPT). O universo classificado contém **98.517 commits**, dos quais **5.223 foram identificados como bug-introducing** pelo MA-SZZ (taxa-base de 5,30%).

| Métrica | Valor | Interpretação |
|---|---:|---|
| Mann-Whitney U (n=10.161 fixes processados) | p < 10⁻⁵⁰ | Diferença extremamente significativa |
| Cliff's Delta | **0,483** | Magnitude **grande** (≥ 0,474) |
| Mediana Grupo A (BICs) | **143,0 LOC** | |
| Mediana Grupo B (não-BICs) | 23,0 LOC | ≈ 6,2× menor |
| Spearman ρ (correlação por repositório) | **0,358** | **p = 0,006 ✓ significativo** |

**Os três testes formais foram confirmados em conjunto** — algo que não era verdade no estágio piloto (n=29), em que apenas Mann-Whitney e Cliff's Delta eram conclusivos. O Spearman tornou-se significativo após dobrar o número de repositórios, confirmando a previsão metodológica da §4.3.3 de que **n ≥ 30 é insuficiente para correlações monotônicas no nível de projeto**.

A discussão detalhada destes resultados está em [`RESULTADOS.md`](RESULTADOS.md).

---

## 8. Referências

### SZZ e variantes

- **Śliwerski, J., Zimmermann, T., Zeller, A.** (2005). *When Do Changes Induce Fixes?* Proceedings of the International Workshop on Mining Software Repositories (MSR). [SZZ original]
- **Kim, S., Zimmermann, T., Pan, K., Whitehead, E. J.** (2006). *Automatic Identification of Bug-Introducing Changes.* IEEE/ACM International Conference on Automated Software Engineering (ASE). [AG-SZZ]
- **Da Costa, D. A., McIntosh, S., Shang, W., Kulesza, U., Coelho, R., Hassan, A. E.** (2017). *A Framework for Evaluating the Results of the SZZ Approach for Identifying Bug-Introducing Changes.* IEEE Transactions on Software Engineering, 43(7). [MA-SZZ]
- **Neto, E. C., da Costa, D. A., Kulesza, U.** (2018). *The Impact of Refactoring Changes on the SZZ Algorithm: An Empirical Study.* SANER. [RA-SZZ]
- **Rosa, G., Pascarella, L., Scalabrino, S., Tufano, R., Bavota, G., Lanza, M., Oliveto, R.** (2021). *Evaluating SZZ Implementations through a Developer-informed Oracle.* IEEE/ACM ICSE.
- **Rezk, V., Kamei, Y., McIntosh, S.** (2022). *The Ghost Commit Problem When Identifying Fix-Inducing Changes.* IEEE Transactions on Software Engineering.

### Bug-fix identification

- **Mockus, A., Votta, L. G.** (2000). *Identifying Reasons for Software Changes Using Historic Databases.* International Conference on Software Maintenance (ICSM).
- **Antoniol, G., Ayari, K., Di Penta, M., Khomh, F., Guéhéneuc, Y.-G.** (2008). *Is It a Bug or an Enhancement? A Text-Based Approach to Classify Change Requests.* CASCON.
- **Herzig, K., Just, S., Zeller, A.** (2013). *It's Not a Bug, It's a Feature: How Misclassification Impacts Bug Prediction.* IEEE/ACM ICSE.
- **Bird, C., Bachmann, A., Aune, E., Duffy, J., Bernstein, A., Filkov, V., Devanbu, P.** (2009). *Fair and Balanced? Bias in Bug-Fix Datasets.* ESEC/FSE.

### Tamanho de commits e defect prediction

- **Mockus, A., Weiss, D. M.** (2000). *Predicting Risk of Software Changes.* Bell Labs Technical Journal, 5(2). [seminal: tamanho × bug]
- **Kamei, Y., Shihab, E., Adams, B., Hassan, A. E., Mockus, A., Sinha, A., Ubayashi, N.** (2013). *A Large-Scale Empirical Study of Just-In-Time Quality Assurance.* IEEE Transactions on Software Engineering, 39(6).
- **Eyolfson, J., Tan, L., Lam, P.** (2014). *Do Time of Day and Developer Experience Affect Commit Bugginess?* MSR.
- **Hindle, A., German, D. M., Holt, R.** (2008). *What Do Large Commits Tell Us? A Taxonomical Study of Large Commits.* MSR.

### Classificação de tamanho de commits

- **Hattori, L., Lanza, M.** (2008). *On the Nature of Commits.* 4th International ERCIM Workshop on Software Evolution and Evolvability (Evol'08). Limiares pequeno/médio/grande adotados nesta metodologia.

### Estatística não-paramétrica e categórica em Engenharia de Software

- **Pearson, K.** (1900). *On the Criterion that a Given System of Deviations from the Probable in the Case of a Correlated System of Variables is Such that it can be Reasonably Supposed to have Arisen from Random Sampling.* Philosophical Magazine, 50(302). Origem do teste χ².
- **Cramér, H.** (1946). *Mathematical Methods of Statistics.* Princeton University Press. Cramer's V.
- **Cohen, J.** (1988). *Statistical Power Analysis for the Behavioral Sciences* (2ª ed.). Lawrence Erlbaum. Thresholds de magnitude para Cramer's V.
- **Armitage, P.** (1955). *Tests for Linear Trends in Proportions and Frequencies.* Biometrics, 11(3). Cochran-Armitage.
- **Agresti, A.** (2002). *Categorical Data Analysis* (2ª ed.). Wiley. Tratamento moderno do Cochran-Armitage e χ².
- **Wilson, E. B.** (1927). *Probable Inference, the Law of Succession, and Statistical Inference.* Journal of the American Statistical Association, 22(158). IC de Wilson.
- **Brown, L. D., Cai, T. T., DasGupta, A.** (2001). *Interval Estimation for a Binomial Proportion.* Statistical Science, 16(2). Recomendação atual para IC de proporção.
- **Spearman, C.** (1904). *The Proof and Measurement of Association Between Two Things.* American Journal of Psychology, 15(1).
- **Arcuri, A., Briand, L.** (2014). *A Hitchhiker's Guide to Statistical Tests for Assessing Randomized Algorithms in Software Engineering.* Software Testing, Verification and Reliability, 24(3).

### Metodologia em ES empírica

- **Wohlin, C., Runeson, P., Höst, M., Ohlsson, M. C., Regnell, B., Wesslén, A.** (2012). *Experimentation in Software Engineering.* Springer.
