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
- **Sementes aleatórias** fixas (e.g., `np.random.default_rng(42)` no Cliff's Delta com amostragem).
- **Versões de dependências** em [`pyszz/requirements.txt`](pyszz/requirements.txt).
- **Universo de commits** distribuído junto ao código (via `commits_clean.csv` + `all_commits_loc.json`, fora do git por tamanho — ver README §1.4).

---

## 7. Referências

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
