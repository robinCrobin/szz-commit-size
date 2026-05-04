"""
STEP 4 — Análise Estatística
=============================================================
O que este script faz:
  1. Lê o commits_classificados.csv (Grupo A vs Grupo B)
  2. Aplica Mann-Whitney U para comparar LOC dos dois grupos
  3. Calcula Cliff's Delta como tamanho de efeito
  4. Gera gráficos para o artigo (boxplot, violin, distribuição CDF)
  5. Exporta tabela de resultados em CSV

PRÉ-REQUISITOS:
  pip install pandas scipy matplotlib seaborn numpy

COMO USAR:
  python step4_analise_estatistica.py
"""

import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns
import warnings
import os

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# CAMINHOS
# ─────────────────────────────────────────────
INPUT_CSV     = "./szz_data/commits_classificados.csv"
RESUMO_CSV    = "./szz_data/resumo_por_repo.csv"
OUTPUT_DIR    = "./szz_data/resultados"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# FUNÇÕES ESTATÍSTICAS
# ─────────────────────────────────────────────

def cliffs_delta(group_a: np.ndarray, group_b: np.ndarray) -> tuple[float, str]:
    """
    Calcula o Cliff's Delta entre dois grupos.

    Cliff's Delta = P(A > B) - P(B > A)
    Mede o tamanho do efeito de forma não-paramétrica.

    Interpretação (Romano et al., 2006):
      |d| < 0.147  → negligível
      |d| < 0.330  → pequeno
      |d| < 0.474  → médio
      |d| >= 0.474 → grande
    """
    n_a = len(group_a)
    n_b = len(group_b)

    # Conta pares onde A > B e B > A
    # Para eficiência, usa broadcasting NumPy
    # (pode ser lento para amostras muito grandes — use amostragem se necessário)
    if n_a * n_b > 10_000_000:
        # Amostragem para datasets muito grandes
        rng = np.random.default_rng(42)
        sample_a = rng.choice(group_a, size=min(n_a, 5000), replace=False)
        sample_b = rng.choice(group_b, size=min(n_b, 5000), replace=False)
        print("  (Cliff's Delta calculado com amostragem de 5000 por grupo)")
    else:
        sample_a, sample_b = group_a, group_b

    matrix = (sample_a[:, None] > sample_b[None, :]).astype(float) - \
             (sample_a[:, None] < sample_b[None, :]).astype(float)
    delta = matrix.mean()

    # Classificação do tamanho de efeito
    abs_d = abs(delta)
    if abs_d < 0.147:
        magnitude = "negligível"
    elif abs_d < 0.330:
        magnitude = "pequeno"
    elif abs_d < 0.474:
        magnitude = "médio"
    else:
        magnitude = "grande"

    return round(delta, 4), magnitude


def mann_whitney_test(group_a: np.ndarray, group_b: np.ndarray) -> dict:
    """
    Executa o teste Mann-Whitney U unilateral (H1: A > B).
    Retorna estatística U, p-valor e interpretação.
    """
    stat, p_value = stats.mannwhitneyu(group_a, group_b, alternative="greater")

    return {
        "statistic_U": round(stat, 2),
        "p_value":     p_value,
        "p_value_fmt": f"{p_value:.4e}",
        "significant": p_value < 0.05,
        "conclusion":  "Bug-introducing commits são significativamente maiores" if p_value < 0.05
                       else "Sem diferença estatisticamente significativa"
    }


def descriptive_stats(series: pd.Series, name: str) -> dict:
    """Estatísticas descritivas para um grupo."""
    return {
        "grupo":   name,
        "n":       len(series),
        "mean":    round(series.mean(), 2),
        "median":  round(series.median(), 2),
        "std":     round(series.std(), 2),
        "q25":     round(series.quantile(0.25), 2),
        "q75":     round(series.quantile(0.75), 2),
        "q90":     round(series.quantile(0.90), 2),
        "max":     int(series.max()),
    }


# ─────────────────────────────────────────────
# FUNÇÕES DE VISUALIZAÇÃO
# ─────────────────────────────────────────────

def plot_boxplot(grupo_a: pd.Series, grupo_b: pd.Series):
    """
    Boxplot comparativo com escala log (necessário pela distribuição assimétrica de LOC).
    Salvo como PNG de alta resolução para o artigo.
    """
    fig, ax = plt.subplots(figsize=(8, 5))

    data = pd.DataFrame({
        "LOC": pd.concat([grupo_a, grupo_b], ignore_index=True),
        "Grupo": (["Bug-Introducing (A)"] * len(grupo_a) +
                  ["Não Bug-Introducing (B)"] * len(grupo_b))
    })

    sns.boxplot(
        data=data, x="Grupo", y="LOC",
        palette=["#e74c3c", "#3498db"],
        showfliers=False,  # oculta outliers extremos para legibilidade
        ax=ax
    )

    ax.set_yscale("log")
    ax.set_ylabel("LOC por Commit (escala log)", fontsize=11)
    ax.set_xlabel("")
    ax.set_title("Distribuição de LOC: Bug-Introducing vs Não Bug-Introducing", fontsize=12)
    ax.yaxis.set_major_formatter(ticker.ScalarFormatter())

    # Adiciona tamanho de amostra no eixo X
    xticks = ax.get_xticklabels()
    labels = [
        f"Bug-Introducing (A)\nn={len(grupo_a):,}",
        f"Não Bug-Introducing (B)\nn={len(grupo_b):,}"
    ]
    ax.set_xticklabels(labels)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "boxplot_grupos.png")
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Gráfico salvo: {path}")


def plot_violin(grupo_a: pd.Series, grupo_b: pd.Series):
    """Violin plot para mostrar a forma completa das distribuições."""
    fig, ax = plt.subplots(figsize=(8, 5))

    data = pd.DataFrame({
        "LOC": pd.concat([
            np.log1p(grupo_a),
            np.log1p(grupo_b)
        ], ignore_index=True),
        "Grupo": (["Bug-Introducing (A)"] * len(grupo_a) +
                  ["Não Bug-Introducing (B)"] * len(grupo_b))
    })

    sns.violinplot(
        data=data, x="Grupo", y="LOC",
        palette=["#e74c3c", "#3498db"],
        inner="quartile",
        ax=ax
    )

    ax.set_ylabel("log(LOC + 1)", fontsize=11)
    ax.set_xlabel("")
    ax.set_title("Forma da Distribuição de LOC por Grupo", fontsize=12)
    plt.tight_layout()

    path = os.path.join(OUTPUT_DIR, "violin_grupos.png")
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Gráfico salvo: {path}")


def plot_cdf(grupo_a: pd.Series, grupo_b: pd.Series):
    """
    CDF (Cumulative Distribution Function) — permite ver em que LOC
    uma proporção dos commits está concentrada.
    """
    fig, ax = plt.subplots(figsize=(9, 5))

    for serie, label, color in [
        (grupo_a, "Bug-Introducing (A)", "#e74c3c"),
        (grupo_b, "Não Bug-Introducing (B)", "#3498db")
    ]:
        sorted_vals = np.sort(serie)
        cdf = np.arange(1, len(sorted_vals) + 1) / len(sorted_vals)
        ax.plot(sorted_vals, cdf, label=label, color=color, linewidth=2)

    ax.set_xscale("log")
    ax.set_xlabel("LOC por Commit (escala log)", fontsize=11)
    ax.set_ylabel("Proporção Acumulada", fontsize=11)
    ax.set_title("CDF — LOC por Commit: Bug-Introducing vs Não Bug-Introducing", fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(left=1)
    plt.tight_layout()

    path = os.path.join(OUTPUT_DIR, "cdf_grupos.png")
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Gráfico salvo: {path}")


def plot_scatter_repo(df_resumo: pd.DataFrame):
    """
    Scatter plot por repositório:
    Eixo X = LOC médio de todos os commits do repo
    Eixo Y = % de commits bug-introducing no repo
    Permite visualizar a tendência agregada (Q1 por projeto).
    """
    df_plot = df_resumo.dropna(subset=["loc_medio_inducing"])

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(
        df_plot["loc_medio_todos"],
        df_plot["taxa_bug_inducing_pct"],
        alpha=0.6, s=40, color="#2ecc71", edgecolors="#27ae60"
    )

    # Linha de tendência
    z = np.polyfit(df_plot["loc_medio_todos"], df_plot["taxa_bug_inducing_pct"], 1)
    p = np.poly1d(z)
    x_line = np.linspace(df_plot["loc_medio_todos"].min(), df_plot["loc_medio_todos"].max(), 100)
    ax.plot(x_line, p(x_line), "r--", linewidth=1.5, label="Tendência linear")

    ax.set_xlabel("LOC Médio por Commit no Repositório", fontsize=11)
    ax.set_ylabel("% de Commits Bug-Introducing", fontsize=11)
    ax.set_title("Relação entre LOC Médio e Taxa de Bugs por Repositório", fontsize=12)
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    path = os.path.join(OUTPUT_DIR, "scatter_repos.png")
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Gráfico salvo: {path}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("Carregando dados...")
    df = pd.read_csv(INPUT_CSV)
    df_resumo = pd.read_csv(RESUMO_CSV)

    grupo_a = df[df["grupo"] == "bug_introducing"]["loc"].values
    grupo_b = df[df["grupo"] == "not_bug_inducing"]["loc"].values

    print(f"  Grupo A (bug-introducing)   : {len(grupo_a):,} commits")
    print(f"  Grupo B (não bug-inducing)  : {len(grupo_b):,} commits")

    # ── 1. Estatísticas descritivas ──
    print("\n[1/4] Calculando estatísticas descritivas...")
    desc_a = descriptive_stats(pd.Series(grupo_a), "Bug-Introducing (A)")
    desc_b = descriptive_stats(pd.Series(grupo_b), "Não Bug-Inducing (B)")

    df_desc = pd.DataFrame([desc_a, desc_b])
    print(df_desc.to_string(index=False))

    # ── 2. Mann-Whitney U ──
    print("\n[2/4] Executando Mann-Whitney U (H1: LOC do Grupo A > Grupo B)...")
    mw = mann_whitney_test(grupo_a, grupo_b)
    print(f"  Estatística U : {mw['statistic_U']:.2f}")
    print(f"  p-valor       : {mw['p_value_fmt']}")
    print(f"  Significativo : {'✅ Sim (p < 0.05)' if mw['significant'] else '❌ Não (p >= 0.05)'}")
    print(f"  Conclusão     : {mw['conclusion']}")

    # ── 3. Cliff's Delta ──
    print("\n[3/4] Calculando Cliff's Delta (tamanho de efeito)...")
    delta, magnitude = cliffs_delta(grupo_a, grupo_b)
    print(f"  Cliff's Delta : {delta}")
    print(f"  Magnitude     : {magnitude}")
    print(f"  Interpretação : {'Grupo A tende a ter LOC maior que Grupo B' if delta > 0 else 'Grupo B tende a ter LOC maior'}")

    # ── 4. Spearman por repositório (análise agregada) ──
    print("\n[4/4] Correlação de Spearman entre LOC médio e taxa de bugs (por repositório)...")
    df_spr = df_resumo.dropna(subset=["loc_medio_todos", "taxa_bug_inducing_pct"])
    rho, p_spr = stats.spearmanr(df_spr["loc_medio_todos"], df_spr["taxa_bug_inducing_pct"])
    print(f"  Rho de Spearman : {rho:.4f}")
    print(f"  p-valor         : {p_spr:.4e}")
    print(f"  Significativo   : {'✅ Sim (p < 0.05)' if p_spr < 0.05 else '❌ Não'}")

    # ── Salvar tabela de resultados ──
    results = {
        "analise": [
            "Estatísticas Descritivas — Grupo A",
            "Estatísticas Descritivas — Grupo B",
            "Mann-Whitney U",
            "Cliff's Delta",
            "Spearman (por repositório)"
        ],
        "valor_principal": [
            f"Mediana={desc_a['median']} LOC, Média={desc_a['mean']} LOC",
            f"Mediana={desc_b['median']} LOC, Média={desc_b['mean']} LOC",
            f"U={mw['statistic_U']}, p={mw['p_value_fmt']}",
            f"δ={delta} ({magnitude})",
            f"ρ={rho:.4f}, p={p_spr:.4e}"
        ],
        "significativo": [
            "—",
            "—",
            "Sim" if mw["significant"] else "Não",
            "—",
            "Sim" if p_spr < 0.05 else "Não"
        ]
    }
    df_results = pd.DataFrame(results)
    results_path = os.path.join(OUTPUT_DIR, "resultados_q1.csv")
    df_results.to_csv(results_path, index=False, encoding="utf-8")

    # ── Gráficos ──
    print("\nGerando gráficos...")
    plot_boxplot(pd.Series(grupo_a), pd.Series(grupo_b))
    plot_violin(pd.Series(grupo_a), pd.Series(grupo_b))
    plot_cdf(pd.Series(grupo_a), pd.Series(grupo_b))
    plot_scatter_repo(df_resumo)

    # ── Resumo final ──
    print("\n" + "="*60)
    print("RESUMO FINAL — Q1")
    print("="*60)
    print(f"  Bug-introducing commits são maiores? : {'SIM' if mw['significant'] and delta > 0 else 'NÃO CONFIRMADO'}")
    print(f"  Tamanho do efeito (Cliff's Delta)   : {delta} ({magnitude})")
    print(f"  Mediana Grupo A / Grupo B            : {desc_a['median']} / {desc_b['median']} LOC")
    print(f"  Correlação por repositório (ρ)       : {rho:.4f} ({'sig.' if p_spr < 0.05 else 'não sig.'})")
    print("="*60)
    print(f"\n✅ Resultados salvos em: {OUTPUT_DIR}/")
    print(f"   - resultados_q1.csv")
    print(f"   - boxplot_grupos.png")
    print(f"   - violin_grupos.png")
    print(f"   - cdf_grupos.png")
    print(f"   - scatter_repos.png")

    # Limitação metodológica para incluir no artigo
    print("\n⚠️  LEMBRETE — Declare estas limitações no artigo:")
    print("   1. RA-SZZ ainda pode apontar commits errôneos em ~17% dos casos (ghost commits).")
    print("   2. Identificação de bug-fix commits via keywords é heurística (pode incluir falsos positivos).")
    print("   3. LOC como proxy de tamanho não captura complexidade semântica da mudança.")


if __name__ == "__main__":
    main()
