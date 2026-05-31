"""
STEP 4 — Análise Estatística (orientada por classes de tamanho)
=============================================================
Todas as análises e gráficos são organizados pela classificação
Hattori & Lanza (2008) — pequeno / médio / grande — usando
limiares bidimensionais (arquivos × LOC). Nada é feito sobre LOC
"bruto" sem antes mapear para uma das três classes.

O que este script faz:
  1. Classifica cada commit em pequeno / médio / grande (Hattori & Lanza 2008).
  2. Calcula taxa de bug-introducing por classe + IC 95% Wilson.
  3. Teste de tendência de Cochran-Armitage (classe ordinal → taxa).
  4. Distribuição de classes dentro do Grupo A (BIC) vs Grupo B (não-BIC),
     com chi-square e Cramer's V como tamanho de efeito.
  5. Por repositório: % de commits pequenos/médios/grandes e taxa BIC,
     com Spearman entre "% de grandes" e "taxa BIC".
  6. Gera os gráficos correspondentes e CSVs.

PRÉ-REQUISITOS:
  pip install pandas scipy matplotlib numpy

COMO USAR:
  python step4_analise_estatistica.py
"""

import os
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# CAMINHOS
# ─────────────────────────────────────────────
INPUT_CSV  = "./szz_data/commits_classificados.csv"
RESUMO_CSV = "./szz_data/resumo_por_repo.csv"
OUTPUT_DIR = "./szz_data/resultados"

ORDEM_CLASSES = ["pequeno", "medio", "grande"]
CORES_CLASSES = {"pequeno": "#3498db", "medio": "#f39c12", "grande": "#e74c3c"}
ROTULOS_CLASSES = {
    "pequeno": "Pequeno\n(≤5 arq E ≤25 LOC)",
    "medio":   "Médio\n(intermediário)",
    "grande":  "Grande\n(>5 arq E >125 LOC)",
}

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─────────────────────────────────────────────
# CLASSIFICAÇÃO E ESTATÍSTICAS DE BASE
# ─────────────────────────────────────────────

def classify_size(loc: float, files: float) -> str:
    """
    Classifica um commit em pequeno / medio / grande usando os limiares
    bidimensionais de Hattori & Lanza (2008) — "On the Nature of Commits":

      pequeno : arquivos <= 5  E  LOC <= 25
      grande  : arquivos >  5  E  LOC >  125
      medio   : qualquer outro
    """
    if files <= 5 and loc <= 25:
        return "pequeno"
    if files > 5 and loc > 125:
        return "grande"
    return "medio"


def wilson_ci(n_success: int, n_total: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de confianca de Wilson (95% por padrao) para uma proporcao."""
    if n_total == 0:
        return (0.0, 0.0)
    p = n_success / n_total
    denom  = 1 + z**2 / n_total
    center = (p + z**2 / (2 * n_total)) / denom
    margin = (z * np.sqrt((p * (1 - p) + z**2 / (4 * n_total)) / n_total)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def cramers_v_label(v: float) -> str:
    """Magnitude de Cramer's V para tabela 2x3 (Cohen 1988, df*=min(r,c)-1=1)."""
    if v < 0.10:
        return "negligível"
    if v < 0.30:
        return "pequeno"
    if v < 0.50:
        return "médio"
    return "grande"


# ─────────────────────────────────────────────
# ANÁLISES POR CLASSE
# ─────────────────────────────────────────────

def add_classe_tamanho(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["classe_tamanho"] = [
        classify_size(loc, files)
        for loc, files in zip(df["loc"].values, df["files_changed"].values)
    ]
    return df


def bug_rate_by_size_class(df: pd.DataFrame) -> pd.DataFrame:
    """Taxa de bug-introducing por classe + IC 95% Wilson."""
    linhas = []
    for classe in ORDEM_CLASSES:
        sub = df[df["classe_tamanho"] == classe]
        n_total = len(sub)
        n_bic   = int((sub["grupo"] == "bug_introducing").sum())
        taxa    = (n_bic / n_total) if n_total > 0 else 0.0
        lo, hi  = wilson_ci(n_bic, n_total)
        linhas.append({
            "classe":         classe,
            "n_total":        n_total,
            "n_bic":          n_bic,
            "taxa_bic":       round(taxa, 6),
            "taxa_bic_pct":   round(taxa * 100, 2),
            "ic95_lo_pct":    round(lo * 100, 2),
            "ic95_hi_pct":    round(hi * 100, 2),
            "loc_mediana":    round(sub["loc"].median(), 2) if n_total else None,
            "files_mediana":  round(sub["files_changed"].median(), 2) if n_total else None,
        })
    return pd.DataFrame(linhas)


def cochran_armitage_trend(counts_bic, counts_total) -> dict:
    """
    Teste de tendencia de Cochran-Armitage.
    H0: a proporcao de BIC nao depende da classe ordinal de tamanho.
    H1: a proporcao cresce (ou decresce) monotonicamente com a classe.
    """
    scores = np.arange(len(counts_total))  # 0, 1, 2
    n_i = np.asarray(counts_total, dtype=float)
    r_i = np.asarray(counts_bic,   dtype=float)
    N = n_i.sum(); R = r_i.sum()
    if N == 0 or R == 0 or R == N:
        return {"Z": float("nan"), "p_value": float("nan"), "trend": "indefinido"}
    num = (scores * (r_i - n_i * R / N)).sum()
    var = (R * (N - R) / N) * ((n_i * scores**2).sum() - ((n_i * scores).sum())**2 / N) / N
    Z = num / np.sqrt(var) if var > 0 else float("nan")
    p_value = 2 * (1 - stats.norm.cdf(abs(Z)))
    trend = "crescente" if Z > 0 else ("decrescente" if Z < 0 else "ausente")
    return {"Z": round(float(Z), 4), "p_value": float(p_value), "trend": trend}


def dist_classes_por_grupo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Distribuicao percentual das classes dentro de cada grupo (BIC vs nao-BIC).
    Retorna DataFrame: classe | grupo | n | pct_dentro_grupo.
    """
    linhas = []
    for grupo, label in [("bug_introducing", "Bug-Introducing (A)"),
                         ("not_bug_inducing", "Não Bug-Introducing (B)")]:
        sub = df[df["grupo"] == grupo]
        n_grupo = len(sub)
        for classe in ORDEM_CLASSES:
            n_cls = int((sub["classe_tamanho"] == classe).sum())
            pct   = (n_cls / n_grupo * 100) if n_grupo else 0.0
            linhas.append({
                "grupo":            label,
                "grupo_key":        grupo,
                "classe":           classe,
                "n":                n_cls,
                "pct_dentro_grupo": round(pct, 2),
            })
    return pd.DataFrame(linhas)


def chi_square_classe_grupo(df: pd.DataFrame) -> dict:
    """
    Teste de associacao entre classe de tamanho (pequeno/medio/grande)
    e grupo (BIC / nao-BIC), com Cramer's V como tamanho de efeito.
    """
    tab = pd.crosstab(df["classe_tamanho"], df["grupo"]).reindex(ORDEM_CLASSES)
    chi2, p_value, dof, expected = stats.chi2_contingency(tab.values)
    n = tab.values.sum()
    v = float(np.sqrt(chi2 / (n * (min(tab.shape) - 1))))
    return {
        "chi2":        round(float(chi2), 2),
        "dof":         int(dof),
        "p_value":     float(p_value),
        "cramers_v":   round(v, 4),
        "magnitude":   cramers_v_label(v),
        "contingency": tab,
    }


def repo_class_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Para cada repositorio, calcula:
      - n_total, n_bic, taxa_bic_pct
      - pct_pequeno, pct_medio, pct_grande
    """
    linhas = []
    for repo, grp in df.groupby("repo_name"):
        n_total = len(grp)
        if n_total == 0:
            continue
        n_bic = int((grp["grupo"] == "bug_introducing").sum())
        counts = grp["classe_tamanho"].value_counts()
        linhas.append({
            "repo_name":     repo,
            "n_total":       n_total,
            "n_bic":         n_bic,
            "taxa_bic_pct":  round(n_bic / n_total * 100, 2),
            "pct_pequeno":   round(counts.get("pequeno", 0) / n_total * 100, 2),
            "pct_medio":     round(counts.get("medio",   0) / n_total * 100, 2),
            "pct_grande":    round(counts.get("grande",  0) / n_total * 100, 2),
        })
    return pd.DataFrame(linhas)


# ─────────────────────────────────────────────
# GRÁFICOS (todos orientados por classe)
# ─────────────────────────────────────────────

def plot_bug_rate_por_classe(df_classes: pd.DataFrame):
    """Bar chart: % de BIC em cada classe, com IC 95% Wilson."""
    fig, ax = plt.subplots(figsize=(8.5, 5.5))

    x       = np.arange(len(df_classes))
    taxas   = df_classes["taxa_bic_pct"].values
    err_lo  = taxas - df_classes["ic95_lo_pct"].values
    err_hi  = df_classes["ic95_hi_pct"].values - taxas
    ns      = df_classes["n_total"].values
    bics    = df_classes["n_bic"].values
    classes = df_classes["classe"].tolist()

    bars = ax.bar(
        x, taxas, yerr=[err_lo, err_hi],
        color=[CORES_CLASSES[c] for c in classes],
        edgecolor="black", linewidth=0.6,
        capsize=8, error_kw=dict(elinewidth=1.2, ecolor="#333"),
    )
    for i, bar in enumerate(bars):
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            h + err_hi[i] + max(taxas) * 0.02,
            f"{taxas[i]:.1f}%\n(n={ns[i]:,}; BIC={bics[i]:,})",
            ha="center", va="bottom", fontsize=9,
        )

    ax.set_xticks(x)
    ax.set_xticklabels([ROTULOS_CLASSES[c] for c in classes], fontsize=10)
    ax.set_ylabel("% de commits bug-introducing (IC 95% Wilson)", fontsize=11)
    ax.set_title(
        "Taxa de bug-introducing por classe de tamanho do commit\n"
        "(Hattori & Lanza, 2008 — limiares bidimensionais arquivos × LOC)",
        fontsize=12,
    )
    ax.set_ylim(0, max(taxas + err_hi) * 1.35)
    ax.grid(True, axis="y", alpha=0.3)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "bug_rate_por_classe.png")
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Grafico salvo: {path}")


def plot_distribuicao_classes_por_grupo(df_dist: pd.DataFrame):
    """
    Barras agrupadas: dentro do Grupo A (BIC) e Grupo B (nao-BIC),
    qual a porcentagem de pequeno/medio/grande.
    Deixa visivel que commits BIC concentram em medio/grande.
    """
    fig, ax = plt.subplots(figsize=(9, 5.5))

    grupos     = df_dist["grupo"].unique().tolist()
    x          = np.arange(len(grupos))
    largura    = 0.26

    for i, classe in enumerate(ORDEM_CLASSES):
        valores = [
            float(df_dist[(df_dist["grupo"] == g) & (df_dist["classe"] == classe)]["pct_dentro_grupo"].iloc[0])
            for g in grupos
        ]
        offsets = x + (i - 1) * largura
        bars = ax.bar(
            offsets, valores, width=largura,
            color=CORES_CLASSES[classe],
            edgecolor="black", linewidth=0.5,
            label=ROTULOS_CLASSES[classe].replace("\n", " "),
        )
        for bar, val in zip(bars, valores):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                f"{val:.1f}%", ha="center", va="bottom", fontsize=9,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(grupos, fontsize=10)
    ax.set_ylabel("% de commits dentro do grupo", fontsize=11)
    ax.set_title(
        "Distribuição das classes de tamanho dentro de cada grupo\n"
        "(Bug-Introducing vs Não Bug-Introducing)",
        fontsize=12,
    )
    ax.set_ylim(0, 100)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, axis="y", alpha=0.3)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "distribuicao_classes_por_grupo.png")
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Grafico salvo: {path}")


def plot_pct_grande_vs_taxa_bic(df_repos: pd.DataFrame, rho: float, p_value: float):
    """
    Scatter por repositorio:
      X = % de commits grandes no repo
      Y = taxa BIC do repo (%)
    Visualiza a correlacao monotonica (Spearman) entre frequencia
    de commits grandes e taxa de bugs por projeto.
    """
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(
        df_repos["pct_grande"], df_repos["taxa_bic_pct"],
        alpha=0.7, s=55, color=CORES_CLASSES["grande"], edgecolors="black", linewidths=0.6,
    )

    if len(df_repos) >= 2:
        z = np.polyfit(df_repos["pct_grande"], df_repos["taxa_bic_pct"], 1)
        p = np.poly1d(z)
        xs = np.linspace(df_repos["pct_grande"].min(), df_repos["pct_grande"].max(), 100)
        ax.plot(xs, p(xs), "--", color="#444", linewidth=1.4, label="Tendência linear (visual)")

    ax.set_xlabel("% de commits grandes no repositório (>5 arq E >125 LOC)", fontsize=11)
    ax.set_ylabel("Taxa de bug-introducing no repositório (%)", fontsize=11)
    ax.set_title(
        f"Por repositório: frequência de commits grandes × taxa de BIC\n"
        f"Spearman ρ = {rho:.3f}  (p = {p_value:.2e}, n={len(df_repos)})",
        fontsize=12,
    )
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", fontsize=9)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "pct_grande_vs_taxa_bic.png")
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  Grafico salvo: {path}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("Carregando dados...")
    df = pd.read_csv(INPUT_CSV)
    df = add_classe_tamanho(df)

    total = len(df)
    n_bic = int((df["grupo"] == "bug_introducing").sum())
    print(f"  Commits totais          : {total:,}")
    print(f"  Bug-introducing (Grupo A): {n_bic:,}")
    print(f"  Nao bug-inducing (Grupo B): {total - n_bic:,}")

    # ── 1. Taxa de BIC por classe ──
    print("\n[1/4] Taxa de bug-introducing por classe (Hattori & Lanza 2D)...")
    df_classes = bug_rate_by_size_class(df)
    print(df_classes.to_string(index=False))
    df_classes.to_csv(os.path.join(OUTPUT_DIR, "taxa_bug_por_classe.csv"), index=False, encoding="utf-8")

    # ── 2. Cochran-Armitage ──
    print("\n[2/4] Tendencia de Cochran-Armitage (classe ordinal -> taxa de BIC)...")
    ca = cochran_armitage_trend(df_classes["n_bic"].tolist(), df_classes["n_total"].tolist())
    ca_p_fmt = f"{ca['p_value']:.4e}" if ca["p_value"] == ca["p_value"] else "nan"
    print(f"  Z = {ca['Z']}  |  p = {ca_p_fmt}  |  tendencia = {ca['trend']}")
    ca_sig = (ca["p_value"] == ca["p_value"]) and ca["p_value"] < 0.05

    # ── 3. Distribuição das classes dentro de cada grupo + chi² ──
    print("\n[3/4] Distribuicao das classes dentro de cada grupo (BIC vs nao-BIC)...")
    df_dist = dist_classes_por_grupo(df)
    print(df_dist.pivot(index="classe", columns="grupo", values="pct_dentro_grupo")
                 .reindex(ORDEM_CLASSES).to_string())
    df_dist.to_csv(os.path.join(OUTPUT_DIR, "distribuicao_classes_por_grupo.csv"),
                   index=False, encoding="utf-8")

    print("\n  Teste de associacao chi-square (classe x grupo) + Cramer's V...")
    chi = chi_square_classe_grupo(df)
    chi_p_fmt = f"{chi['p_value']:.4e}"
    print(f"  chi2 = {chi['chi2']}  |  gl = {chi['dof']}  |  p = {chi_p_fmt}")
    print(f"  Cramer's V = {chi['cramers_v']} ({chi['magnitude']})")
    chi_sig = chi["p_value"] < 0.05

    # ── 4. Por repositorio: % de grandes vs taxa BIC ──
    print("\n[4/4] Por repositorio: % de commits grandes vs taxa BIC (Spearman)...")
    df_repos = repo_class_summary(df)
    df_repos.to_csv(os.path.join(OUTPUT_DIR, "resumo_por_repo_classes.csv"),
                    index=False, encoding="utf-8")
    rho, p_spr = stats.spearmanr(df_repos["pct_grande"], df_repos["taxa_bic_pct"])
    print(f"  n_repos = {len(df_repos)}")
    print(f"  Spearman ρ = {rho:.4f}  |  p = {p_spr:.4e}  |  significativo = {'sim' if p_spr < 0.05 else 'nao'}")

    # ── Gráficos ──
    print("\nGerando graficos (todos orientados por classe)...")
    plot_bug_rate_por_classe(df_classes)
    plot_distribuicao_classes_por_grupo(df_dist)
    plot_pct_grande_vs_taxa_bic(df_repos, rho, p_spr)

    # ── CSV consolidado de resultados ──
    cls_row = {c: df_classes.set_index("classe").loc[c] for c in ORDEM_CLASSES}
    pct_grupo_a = {c: df_dist[(df_dist["grupo_key"] == "bug_introducing")
                              & (df_dist["classe"] == c)]["pct_dentro_grupo"].iloc[0]
                   for c in ORDEM_CLASSES}
    pct_grupo_b = {c: df_dist[(df_dist["grupo_key"] == "not_bug_inducing")
                              & (df_dist["classe"] == c)]["pct_dentro_grupo"].iloc[0]
                   for c in ORDEM_CLASSES}
    results = {
        "analise": [
            "Taxa BIC — Pequeno (≤5 arq E ≤25 LOC)",
            "Taxa BIC — Médio (intermediário)",
            "Taxa BIC — Grande (>5 arq E >125 LOC)",
            "Cochran-Armitage (tendência classe → taxa BIC)",
            "Distribuição classes dentro do Grupo A (BIC)",
            "Distribuição classes dentro do Grupo B (não-BIC)",
            "Chi-square (classe × grupo)",
            "Cramer's V (tamanho de efeito)",
            "Spearman por repo (% grandes × taxa BIC)",
        ],
        "valor_principal": [
            f"{cls_row['pequeno']['taxa_bic_pct']:.2f}% (IC95 {cls_row['pequeno']['ic95_lo_pct']:.2f}–{cls_row['pequeno']['ic95_hi_pct']:.2f}; n={int(cls_row['pequeno']['n_total']):,})",
            f"{cls_row['medio']['taxa_bic_pct']:.2f}% (IC95 {cls_row['medio']['ic95_lo_pct']:.2f}–{cls_row['medio']['ic95_hi_pct']:.2f}; n={int(cls_row['medio']['n_total']):,})",
            f"{cls_row['grande']['taxa_bic_pct']:.2f}% (IC95 {cls_row['grande']['ic95_lo_pct']:.2f}–{cls_row['grande']['ic95_hi_pct']:.2f}; n={int(cls_row['grande']['n_total']):,})",
            f"Z={ca['Z']}, p={ca_p_fmt}, tendência={ca['trend']}",
            f"peq={pct_grupo_a['pequeno']:.1f}% / med={pct_grupo_a['medio']:.1f}% / gra={pct_grupo_a['grande']:.1f}%",
            f"peq={pct_grupo_b['pequeno']:.1f}% / med={pct_grupo_b['medio']:.1f}% / gra={pct_grupo_b['grande']:.1f}%",
            f"chi²={chi['chi2']}, gl={chi['dof']}, p={chi_p_fmt}",
            f"V={chi['cramers_v']} ({chi['magnitude']})",
            f"ρ={rho:.4f}, p={p_spr:.4e} (n_repos={len(df_repos)})",
        ],
        "significativo": [
            "—", "—", "—",
            "Sim" if ca_sig else "Não",
            "—", "—",
            "Sim" if chi_sig else "Não",
            "—",
            "Sim" if p_spr < 0.05 else "Não",
        ],
    }
    pd.DataFrame(results).to_csv(
        os.path.join(OUTPUT_DIR, "resultados_q1.csv"),
        index=False, encoding="utf-8",
    )

    # ── Resumo final ──
    print("\n" + "=" * 64)
    print("RESUMO FINAL — Q1 (orientado por classes de tamanho)")
    print("=" * 64)
    print(f"  Taxa BIC | pequeno : {cls_row['pequeno']['taxa_bic_pct']:.2f}%   "
          f"medio : {cls_row['medio']['taxa_bic_pct']:.2f}%   "
          f"grande: {cls_row['grande']['taxa_bic_pct']:.2f}%")
    print(f"  Tendencia (Cochran-Armitage): Z={ca['Z']}  p={ca_p_fmt}  ({ca['trend']})")
    print(f"  Grupo A (BIC):     {pct_grupo_a['pequeno']:.1f}% peq / "
          f"{pct_grupo_a['medio']:.1f}% med / {pct_grupo_a['grande']:.1f}% gra")
    print(f"  Grupo B (nao-BIC): {pct_grupo_b['pequeno']:.1f}% peq / "
          f"{pct_grupo_b['medio']:.1f}% med / {pct_grupo_b['grande']:.1f}% gra")
    print(f"  Associacao classe x grupo  : chi2={chi['chi2']}, p={chi_p_fmt}, "
          f"Cramer's V={chi['cramers_v']} ({chi['magnitude']})")
    print(f"  Spearman por repo (% gra x taxa BIC): rho={rho:.4f}, p={p_spr:.4e} "
          f"({'sig.' if p_spr < 0.05 else 'nao sig.'})")
    print("=" * 64)
    print(f"\nResultados salvos em: {OUTPUT_DIR}/")
    print(f"   - resultados_q1.csv                       (consolidado)")
    print(f"   - taxa_bug_por_classe.csv                 (taxas + IC95 por classe)")
    print(f"   - distribuicao_classes_por_grupo.csv      (distribuicao A vs B)")
    print(f"   - resumo_por_repo_classes.csv             (% classes + taxa BIC por repo)")
    print(f"   - bug_rate_por_classe.png                 (grafico principal)")
    print(f"   - distribuicao_classes_por_grupo.png      (composicao de cada grupo)")
    print(f"   - pct_grande_vs_taxa_bic.png              (correlacao por repositorio)")

    # Limitação metodológica para incluir no artigo
    print("\nLEMBRETE — Declare estas limitacoes no artigo:")
    print("   1. SZZ ainda pode apontar commits erroneos em ~17% dos casos (ghost commits).")
    print("   2. Identificacao de bug-fix por keywords e heuristica (Herzig 2013).")
    print("   3. Limiares de classe (Hattori & Lanza 2008) sao convencao da literatura.")


if __name__ == "__main__":
    main()
