# Q1 — Conteúdo atualizado dos slides (páginas 12–19)

> **O que mudou na metodologia:** saímos da comparação de LOC bruto (Mann-Whitney U +
> Cliff's Delta, "BICs são maiores que commits normais") para uma análise por **classes
> de tamanho** (Hattori & Lanza 2008: pequeno / médio / grande) com três testes:
> **Cochran-Armitage** (tendência), **χ² + Cramer's V** (composição) e **Spearman** (por repo).
>
> **REMOVER de todos os slides da Q1:** Mann-Whitney U, Cliff's Delta, boxplot de LOC,
> gráfico CDF, "mediana 143 vs 23 LOC / 6,2×".
>
> **Base nova:** 460 repositórios · 1.850.512 commits · 45.031 BICs (2,4%).
> (antes: 58 repos · 98.517 commits · 5.223 BICs 5,3%)
>
> **Gráficos novos** (já em `slides/`):
> - `q1_bug_rate_por_classe.png`            → slide 15 (figura principal)
> - `q1_distribuicao_classes_por_grupo.png` → slide 17
> - `q1_pct_grande_vs_taxa_bic.png`         → slide 18

---

## Slide 12 — GQM: métricas e hipótese  *(ajustar)*

**Título (mantém):** Q1: QUAL A RELAÇÃO ENTRE O TAMANHO DO COMMIT E A OCORRÊNCIA DE BUGS?

**Métricas:**
- **M1.1:** LOC modificadas por commit (linhas adicionadas + removidas)
- **M1.2:** Classificação do commit como bug-introducing (BIC), identificado pelo algoritmo
  MA-SZZ a partir dos bug-fix commits via git blame
- **M1.3:** Classificação do commit em **classes de tamanho** (Hattori & Lanza, 2008):
  pequeno / médio / grande *(substitui a antiga M1.4 de Cliff's Delta)*
- **M1.4:** Taxa de BIC por classe e por repositório (n_BIC / total_commits)

> ❌ **REMOVER** a M1.4 antiga: "Tamanho de efeito (Cliff's Delta) entre LOC dos BICs vs
> commits não bug-introducing".

**Hipótese (reformulada para o enfoque de classe):**
Quanto **maior** o commit, **maior a probabilidade** de ele ser bug-introducing. Mudanças
volumosas envolvem mais código e mais arquivos de uma só vez, mais carga cognitiva para
quem escreve e revisa, abrindo espaço para efeitos colaterais que passam despercebidos.

---

## Slide 13 — Contexto da amostra + análise  *(substituir números e testes)*

**Texto:**
Analisamos **1.850.512 commits** Python em **460 repositórios** do GitHub para verificar se
o **tamanho do commit** (classes de Hattori & Lanza) está associado à introdução de bugs.

**Caixas de destaque:**
- **45.031 BICs (2,4%)**
- **1.805.481 commits não bug-introducing**

**Classes de tamanho (Hattori & Lanza, 2008):**
- **Pequeno:** ≤ 5 arquivos **E** ≤ 25 LOC
- **Grande:** > 5 arquivos **E** > 125 LOC
- **Médio:** os demais

**Análise** *(substitui Mann-Whitney / Cliff's Delta / Spearman antigos):*
- **Cochran-Armitage** — tendência da taxa de BIC ao longo das classes ordinais (evidência principal)
- **χ² + Cramer's V** — associação/composição entre classe de tamanho e grupo (BIC vs não-BIC)
- **Spearman ρ** por repositório — correlação entre % de commits grandes e taxa de BIC

---

## Slide 14 — Exclusões + amostragem  *(atualizar)*

**Repositórios excluídos** (incompatibilidade ou inviabilidade de execução/extração):
`pytorch/pytorch` (NTFS case-insensitive), `Significant-Gravitas/AutoGPT`,
`NVIDIA/TensorRT-LLM` (deadlock no teardown após timeout), `ccxt/ccxt` (histórico
grande estourou o timeout de extração). Além desses, **38 candidatos foram filtrados a
priori por não serem código Python** (listas, livros, cheatsheets, skill packs — vide METODOLOGIA §7.5.3).

**Amostragem:** cap de **100 fixes por repositório** (seed = 42) para equilibrar o peso dos
projetos. *(Observação honesta: 5 repositórios históricos — django, scikit-learn, hermes-agent,
MemPalace, EbookFoundation — ficaram sem cap, e o hermes-agent concentra ~4,4k fixes;
limitação a declarar.)*

**Impacto marginal:** cada repositório representa ~100 fixes sobre ~45 mil BICs totais.

---

## Slide 15 — FIGURA PRINCIPAL: taxa de BIC por classe  *(substituir gráfico e números)*

**Subtítulo:** A taxa de BIC cresce de forma monotônica com o tamanho do commit

**Caixas de destaque (substituem 143 LOC / 23 LOC / 6,2×):**
- **0,9%** — taxa de BIC nos commits **pequenos**
- **3,1%** — taxa de BIC nos commits **médios**
- **7,5%** — taxa de BIC nos commits **grandes**
- **≈ 8,7×** — diferença entre grande e pequeno

**Tabela:** `q1_bug_rate_por_classe.png` *(taxa de BIC + IC 95% Wilson, n e BICs por classe)*

**Resultado do teste (rodapé):**
**Cochran-Armitage: Z = 179,5 · p ≈ 0 → tendência crescente significativa** (Q1₀)

| Classe | n | Taxa BIC | IC 95% (Wilson) | LOC mediana |
|---|---:|---:|---|---:|
| Pequeno | 955.481 | 0,86% | 0,84–0,88 | 6 |
| Médio   | 684.903 | 3,07% | 3,03–3,12 | 72 |
| Grande  | 210.128 | 7,51% | 7,40–7,63 | 481 |

---

## Slide 16 — O que são os testes  *(substituir explicações)*

> ❌ **REMOVER** "O que é Mann-Whitney?" e "O que é Cliff's Delta?".

**O que é o teste de Cochran-Armitage?**
Verifica se existe uma **tendência** (crescente ou decrescente) em uma proporção ao longo de
categorias ordenadas — aqui, a taxa de BIC do pequeno → médio → grande. O p-valor ínfimo
indica que o crescimento não é obra do acaso.

**O que é χ² + Cramer's V?**
O χ² testa se a **composição** de classes difere entre BICs e não-BICs. O Cramer's V mede a
**força** dessa associação (0 = nenhuma, 1 = total). V = 0,14 → associação real, de magnitude
pequena, mas com direção clara: BICs se concentram em médio/grande.

**O que é Spearman ρ?**
Mede se duas variáveis crescem juntas (positivo) ou em sentidos opostos (negativo). Aqui:
% de commits grandes de um repositório × taxa de BIC desse repositório.

---

## Slide 17 — Composição por grupo (χ²)  *(substituir gráfico e números)*

**Subtítulo:** BICs se concentram em commits médios e grandes

> ❌ **REMOVER** "Mann-Whitney U → p < 10⁻⁵⁰", "Cliff's Delta = 0,48" e o gráfico CDF.

**Destaques:**
- **χ² = 34.021 · gl = 2 · p ≈ 0 · Cramer's V = 0,14** (Q1a)

**Composição de cada grupo:**
- **Grupo A (BIC):** 18,2% pequeno · 46,8% médio · **35,1% grande**
- **Grupo B (não-BIC):** 52,5% pequeno · 36,8% médio · **10,8% grande**

**Gráfico:** `q1_distribuicao_classes_por_grupo.png` *(barras: composição % dentro de cada grupo)*

**Leitura:** entre os BICs, ~1 em cada 3 é grande; entre os não-BICs, ~1 em cada 9.

---

## Slide 18 — Spearman por repositório  *(substituir números)*

**Destaques (substituem ρ=0,36 / p=0,006):**
- **ρ = 0,135** — correlação de Spearman
- **p = 0,0038** — significativo, porém **fraco** (n = 460 repositórios)

**Gráfico:** `q1_pct_grande_vs_taxa_bic.png` *(substitui o scatter antigo)*

**Leitura (ser honesto sobre a magnitude):**
A nível de repositório existe uma correlação positiva e **estatisticamente significativa**
(p = 0,0038), mas de magnitude **fraca** (ρ ≈ 0,13): repositórios com maior proporção de
commits grandes tendem a ter taxa de BIC um pouco maior. O efeito por projeto é muito mais
sutil que o efeito por commit.

---

## Slide 19 — Conclusão  *(reescrever)*

> ❌ **REMOVER** a conclusão antiga ("6,2× maior… Cliff's Delta 0,48… ρ=0,36").

**Hipótese comprovada (forte por commit, fraca por projeto):**

- ✅ **A nível de commit/agregado:** a taxa de BIC cresce de 0,9% (pequeno) para 7,5%
  (grande) — razão ≈ 8,7× — com tendência significativa (Cochran-Armitage Z = 179,5, p ≈ 0)
  e associação confirmada entre classe e grupo (χ², p ≈ 0; Cramer's V = 0,14).

- ➖ **A nível de projeto:** a correlação entre % de commits grandes e taxa de BIC por
  repositório é significativa, mas **fraca** (Spearman ρ = 0,13, p = 0,0038, n = 460).

**Conclusão:** commits maiores têm, individualmente, probabilidade substancialmente maior de
introduzir bugs (efeito forte e claro). Esse padrão também aparece entre projetos, porém de
forma bem mais tênue — o sinal é predominantemente do **commit**, não do **projeto**.
