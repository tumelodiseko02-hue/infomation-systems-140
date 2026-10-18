
import io

import matplotlib

matplotlib.use("Agg")  # headless backend, no display needed
import matplotlib.pyplot as plt
import pandas as pd
from scipy import stats

INK = "#1f2933"
MUTED = "#6b7785"
GRID = "#e4e7eb"
SERIES = "#2f6f4e"  # single series -> single hue


def trials_frame(trials, farmers):

    t = pd.DataFrame(trials)
    if t.empty:
        return t
    f = pd.DataFrame(farmers)[["id", "name", "village"]].rename(
        columns={"id": "farmer_id", "name": "farmer", "village": "village"}
    )
    df = t.merge(f, on="farmer_id", how="left")
    df["yield_kg_per_ha"] = pd.to_numeric(df["yield_kg_per_ha"], errors="coerce")
    return df.dropna(subset=["yield_kg_per_ha"])


def mean_ci(values, confidence=0.95):

    s = pd.Series(values, dtype="float64").dropna()
    n = len(s)
    mean = float(s.mean()) if n else float("nan")
    if n < 2:
        return {"n": n, "mean": mean, "sd": float("nan"),
                "lower": float("nan"), "upper": float("nan")}
    sd = float(s.std(ddof=1))
    sem = sd / n ** 0.5
    margin = float(stats.t.ppf((1 + confidence) / 2, df=n - 1)) * sem
    return {"n": n, "mean": mean, "sd": sd,
            "lower": mean - margin, "upper": mean + margin}


def summary_by_crop(df):

    if df.empty:
        return pd.DataFrame(columns=["crop", "n", "mean", "sd", "lower", "upper"])
    rows = []
    for crop, g in df.groupby("crop"):
        r = mean_ci(g["yield_kg_per_ha"])
        r["crop"] = crop
        rows.append(r)
    out = pd.DataFrame(rows)[["crop", "n", "mean", "sd", "lower", "upper"]]
    return out.sort_values("mean", ascending=False).reset_index(drop=True)


def overview(df, farmers):

    return {
        "farmers": len(farmers),
        "trials": 0 if df.empty else len(df),
        "mean_yield": None if df.empty else round(float(df["yield_kg_per_ha"].mean()), 1),
        "crops": 0 if df.empty else int(df["crop"].nunique()),
    }


def ci_chart_png(summary):

    fig, ax = plt.subplots(figsize=(8, 4.4), dpi=130)
    ax.set_facecolor("white")

    plotted = summary.dropna(subset=["lower", "upper"]) if not summary.empty else summary
    if plotted.empty:
        ax.text(0.5, 0.5, "Not enough data yet\n(each crop needs at least 2 trials)",
                ha="center", va="center", color=MUTED, fontsize=11,
                transform=ax.transAxes)
        ax.set_axis_off()
    else:
        x = range(len(plotted))
        means = plotted["mean"].to_numpy()
        err = [means - plotted["lower"].to_numpy(), plotted["upper"].to_numpy() - means]
        ax.errorbar(x, means, yerr=err, fmt="o", color=SERIES, ecolor=SERIES,
                    elinewidth=2, capsize=5, capthick=2, markersize=8,
                    markeredgecolor="white", markeredgewidth=2, zorder=3)
        for i, row in enumerate(plotted.itertuples()):
            ax.annotate(f"{row.mean:,.0f}", (i, row.upper), xytext=(0, 7),
                        textcoords="offset points", ha="center",
                        color=INK, fontsize=9)
        ax.set_xticks(list(x))
        ax.set_xticklabels([f"{c}\n(n={n})" for c, n in zip(plotted["crop"], plotted["n"])],
                           color=INK, fontsize=9)
        ax.set_ylabel("Yield (kg/ha)", color=MUTED, fontsize=9)
        ax.set_xlim(-0.6, len(plotted) - 0.4)
        lo = min(plotted["lower"].min(), 0 if plotted["lower"].min() < 0 else plotted["lower"].min())
        ax.set_ylim(max(0, lo * 0.85), plotted["upper"].max() * 1.12)
        ax.yaxis.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.tick_params(axis="y", colors=MUTED, labelsize=9, length=0)
        ax.tick_params(axis="x", length=0)
        ax.set_title("Mean yield by crop with 95% confidence interval",
                     loc="left", color=INK, fontsize=12, pad=14)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    return buf.getvalue()
