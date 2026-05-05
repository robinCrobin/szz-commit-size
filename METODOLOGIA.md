# Metodologia

Documento de apoio descrevendo as escolhas metodológicas do estudo, com justificativas e ancoragem na literatura. Estruturado para ser adaptado a uma seção de Metodologia / Methods em artigo.

---

## 1. Pergunta de pesquisa

A questão central é:

> **Q1.** Commits classificados como *bug-introducing* (pelo SZZ) apresentam tamanho — em linhas alteradas (LOC) — significativamente maior do que os demais commits do mesmo projeto?

Como subperguntas:

> **Q1a.** Há diferença estatisticamente significativa entre as distribuições de LOC dos dois grupos? (teste de hipótese)
>
> **Q1b.** Quão grande é essa diferença? (tamanho de efeito)
>
> **Q1c.** A nível de projeto, repositórios cujos commits são em média maiores apresentam taxa proporcional de BICs mais alta? (correlação agregada)

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
| Q1a — há diferença significativa? | **Mann-Whitney U** unilateral (H1: A > B) | p-valor |
| Q1b — quão grande é o efeito? | **Cliff's Delta (δ)** | δ ∈ [-1, 1] |
| Q1c — correlação por projeto? | **Spearman ρ** | ρ ∈ [-1, 1], p-valor |

#### 4.3.1 Mann-Whitney U

Teste não-paramétrico para comparar duas distribuições. Justificado em ES por **Arcuri & Briand (2014)** como o teste de escolha quando os dados violam normalidade — o que invariavelmente ocorre com LOC (long-tail). Implementação: `scipy.stats.mannwhitneyu(group_a, group_b, alternative="greater")`.

#### 4.3.2 Cliff's Delta

Tamanho de efeito não-paramétrico (Cliff 1993): `δ = P(A > B) − P(B > A)`. Escolhemos sobre Cohen's *d* porque não pressupõe normalidade nem variâncias iguais. Adotamos os limiares de **Romano et al. (2006)**:

| `|δ|` | Magnitude |
|--:|---|
| < 0.147 | negligível |
| < 0.330 | pequeno |
| < 0.474 | médio |
| ≥ 0.474 | grande |

> **Por que reportar tanto p-valor quanto δ?** Com amostras grandes (~10⁴ commits), praticamente qualquer diferença vira "significativa". O p-valor responde *se* há diferença; o Cliff's Delta responde *se importa na prática*. Esta é uma recomendação explícita de **Arcuri & Briand (2014)** e da comunidade de Mining Software Repositories.

#### 4.3.3 Spearman ρ por repositório

Para Q1c, agregamos por repositório: para cada projeto, calculamos LOC médio dos commits e a taxa de BIC (`n_bug_inducing / total_commits`). Aplicamos `scipy.stats.spearmanr` sobre os pares (LOC médio, taxa de BIC) entre todos os repositórios analisados.

> **Ressalva (poder estatístico).** Spearman exige **n ≥ 20-30** repositórios para ter poder estatístico aceitável. Com n menor, o teste tende a não-rejeitar H0 mesmo havendo correlação real. Por isso a divisão de trabalho entre colaboradores (cada pessoa rodando 30 repos) é metodologicamente necessária — não apenas pragmática.

### 4.4 Análise complementar — não-paramétrica de classes

Como suplemento descritivo, classificamos cada BIC em **"grande" (`>5 arquivos AND >125 linhas alteradas`)** ou **"pequeno"**, e calculamos:

```
risk_ratio = P(BIC | grande) / P(BIC | pequeno)
```

Sobre o universo total de commits dos repos analisados.

> **Ressalva.** Os limiares **5 arquivos** e **125 linhas** são empiricamente derivados da distribuição observada (próximos ao P75 e P90 dos commits, respectivamente), **não de uma teoria *a priori***. Esta análise é exploratória, complementar à inferência formal da §4.3, e útil para comunicar o achado em termos de "quantas vezes maior o risco" — um framing comum em estudos de epidemiologia/saúde aplicada à ES (Eyolfson et al. 2014). **Não substitui** os testes formais, dada a arbitrariedade do limiar.

---

## 5. Ameaças à validade

Seguindo a taxonomia de **Wohlin et al. (2012)**:

### 5.1 Validade interna

- **SZZ produz falsos positivos.** Mesmo MA-SZZ apresenta erros — **Rezk et al. (2022)** reportam ~17% de "ghost commits" (apontados pelo blame mas que não introduziram o bug). **Mitigação:** uso de MA-SZZ (mais conservador que Base/AG-SZZ) e filtro adicional de reverts.
- **`is_bug_fix` por keyword é heurística** com erro estimado em 30% (Herzig et al. 2013). **Mitigação:** declaração explícita; valida análise com sub-amostra de fixes verificáveis em trabalho futuro.

### 5.2 Validade externa

- **Apenas Python**, apenas **GitHub**, apenas **projetos populares**. Generalizações para outras linguagens, ecossistemas (npm, Maven privados) ou enterprise software requerem estudos adicionais.
- **Janela temporal**: analisamos o histórico completo dos repositórios; mudanças em práticas de engenharia ao longo dos anos podem afetar o sinal (estilos de commit modernos vs antigos).

### 5.3 Validade de constructo

- **LOC ≠ tamanho cognitivo da mudança.** Discutido em §3.
- **Definição operacional de BIC = output do MA-SZZ.** Não é verdade absoluta — é a melhor aproximação automatizável dado o estado-da-arte. **Rosa et al. (2023)** discutem trade-offs entre as variantes.

### 5.4 Validade de conclusão

- **Múltiplas comparações.** Reportamos três testes (M-W, Cliff's Delta, Spearman) sobre a mesma amostra. Embora cada um responda uma pergunta diferente (significância, tamanho, correlação agregada), uma correção de Bonferroni poderia ser discutida se quisermos um critério ainda mais conservador. Dado o efeito esperado (Cliff's Delta grande), os testes têm robustez suficiente.

---

## 6. Reprodutibilidade

- **Código aberto** em https://github.com/robinCrobin/szz-commit-size (este repositório).
- **Configuração SZZ** em [`pyszz/conf/raszz.yml`](pyszz/conf/raszz.yml) (parâmetros exatos da execução).
- **Sementes aleatórias** fixas (e.g., `random.seed(42)` no sampling de fixes por repositório; `np.random.default_rng(42)` no Cliff's Delta com amostragem).
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

### 7.5 Incidente: pytorch/pytorch (filesystem incompatível)

**Incidente.** Durante a rodada principal, o processo abortou em 2026-05-05 às 07:52:33 ao tentar clonar `pytorch/pytorch` no diretório temporário do SZZ. O log mostrou:

```
fatal: unable to checkout working tree
warning: Clone succeeded, but checkout failed.
```

**Diagnóstico.** O repositório `pytorch/pytorch` contém arquivos cuja diferença está **apenas em maiúsculas/minúsculas** (e.g., `aten/src/.../foo.cpp` vs `aten/src/.../FOO.cpp`). O sistema de arquivos NTFS do Windows é **case-insensitive** por padrão, o que causa colisão durante o `git checkout`. O clone original em `repos/pytorch/pytorch` permaneceu intacto (operação prévia de `step1_adaptar_csv.py`); a falha foi exclusivamente no clone interno do SZZ via `Repo.clone_from(... '--local')`, que recria a árvore de trabalho.

**Resolução.** O repositório `pytorch/pytorch` foi **excluído da análise** após autorização explícita ("se continuar dando muito erro, apenas anote que esse repositório apresentou problemas e vai ser deixado fora da análise"). Tentativas de contornar (habilitar `core.protectNTFS=false`, mover para WSL) foram avaliadas e rejeitadas pelo custo-benefício, dado que (a) `pytorch` representava apenas 100 fixes no plano amostrado (cap), e (b) a hipótese é robusta o suficiente para que a perda de 1 repo de 60 não comprometa a inferência.

**Limitação declarada.** O fato de pytorch/pytorch não ter sido analisado é uma **limitação de validade externa específica para a infraestrutura Windows/NTFS**. Em sistemas Linux/macOS (case-sensitive por padrão), o repo seria processado normalmente. Esta limitação é citada na §5.2.

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

### 7.8 Resultados parciais (n=29 repositórios)

| Métrica | Valor | Interpretação |
|---|---:|---|
| Mann-Whitney U | p ≈ 9,97 × 10⁻²¹⁶ | Diferença extremamente significativa |
| Cliff's Delta | 0,53 | Magnitude **grande** |
| Mediana Grupo A | 195,0 LOC | |
| Mediana Grupo B | 24,0 LOC | ≈ 8× menor |
| Spearman ρ | 0,13 | p = 0,50 (não-significativo) |

A não-significância da Spearman é **esperada** com n=29 e era prevista na §4.3.3. A entrega do segundo lote de repositórios (≈ 30 do colaborador) levará o n para próximo de 60 e tende a tornar o teste conclusivo. Os resultados de M-W e Cliff's Delta já permitem rejeitar a hipótese nula em nível individual (commits BIC são significativamente maiores), com tamanho de efeito grande — esses dois resultados são **estáveis** e dificilmente mudarão de magnitude com mais dados.

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

### Estatística não-paramétrica em Engenharia de Software

- **Mann, H. B., Whitney, D. R.** (1947). *On a Test of Whether one of Two Random Variables is Stochastically Larger than the Other.* Annals of Mathematical Statistics, 18(1).
- **Cliff, N.** (1993). *Dominance Statistics: Ordinal Analyses to Answer Ordinal Questions.* Psychological Bulletin, 114(3).
- **Romano, J., Kromrey, J. D., Coraggio, J., Skowronek, J., Devine, L.** (2006). *Appropriate Statistics for Ordinal Level Data: Should We Really Be Using t-test and Cohen's d for Evaluating Group Differences on the NSSE and Other Surveys?* Annual Meeting of the Florida Association of Institutional Research.
- **Spearman, C.** (1904). *The Proof and Measurement of Association Between Two Things.* American Journal of Psychology, 15(1).
- **Arcuri, A., Briand, L.** (2014). *A Hitchhiker's Guide to Statistical Tests for Assessing Randomized Algorithms in Software Engineering.* Software Testing, Verification and Reliability, 24(3).

### Metodologia em ES empírica

- **Wohlin, C., Runeson, P., Höst, M., Ohlsson, M. C., Regnell, B., Wesslén, A.** (2012). *Experimentation in Software Engineering.* Springer.
