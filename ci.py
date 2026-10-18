
import argparse
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from dashboard import GRID, INK, MUTED, SERIES, mean_ci


def group_stats(df, value_col, group_col, groups=None, confidence=0.95):

    work = df[[group_col, value_col]].copy()
    work[value_col] = pd.to_numeric(work[value_col], errors="coerce")
    work = work.dropna(subset=[value_col, group_col])
    work[group_col] = work[group_col].astype(str).str.strip()
    names = list(groups) if groups else sorted(work[group_col].unique())
    rows = []
    for name in names:
        r = mean_ci(work.loc[work[group_col] == name, value_col], confidence)
        rows.append({"group": name, **{k: (None if v != v else v) for k, v in r.items()}})
    return rows


def ci_groups_png(rows, ylabel, title):
    """Draw mean +/- 95% CI per group (square markers, as in your script)."""
    fig, ax = plt.subplots(figsize=(7.5, 4.4), dpi=130)
    plotted = [r for r in rows if r["lower"] is not None]
    if not plotted:
        ax.text(0.5, 0.5, "Not enough data\n(each group needs at least 2 values)",
                ha="center", va="center", color=MUTED, fontsize=11, transform=ax.transAxes)
        ax.set_axis_off()
    else:
        x = list(range(len(plotted)))
        means = [r["mean"] for r in plotted]
        err = [[r["mean"] - r["lower"] for r in plotted], [r["upper"] - r["mean"] for r in plotted]]
        ax.errorbar(x, means, yerr=err, fmt="s", capsize=6, color=SERIES, elinewidth=2,
                    capthick=2, markersize=8, markeredgecolor="white", markeredgewidth=1.5, zorder=3)
        for xi, r in zip(x, plotted):
            ax.annotate(f"{r['mean']:.2f}", (xi, r["upper"]), xytext=(0, 7),
                        textcoords="offset points", ha="center", color=INK, fontsize=9)
        lo = min(r["lower"] for r in plotted)
        hi = max(r["upper"] for r in plotted)
        pad = (hi - lo) * 0.25 or abs(hi) * 0.05 or 1
        ax.set_ylim(lo - pad, hi + pad)
        ax.set_xlim(-0.8, len(plotted) - 0.2)
        ax.set_xticks(x)
        ax.set_xticklabels([f"{r['group']}\n(n={r['n']})" for r in plotted], color=INK, fontsize=9)
        ax.set_ylabel(ylabel, color=MUTED, fontsize=9)
        ax.set_title(title, loc="left", color=INK, fontsize=12, pad=14)
        ax.yaxis.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.tick_params(axis="y", colors=MUTED, labelsize=9, length=0)
        ax.tick_params(axis="x", length=0)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def main(argv=None):
    p = argparse.ArgumentParser(description="95% CI chart per group from a CSV file")
    p.add_argument("csv")
    p.add_argument("column", help="numeric column, e.g. Mg")
    p.add_argument("group_column", help="column holding the groups, e.g. Block")
    p.add_argument("groups", nargs="*", help="groups to compare (default: all)")
    p.add_argument("--out", default="ci_chart.png")
    a = p.parse_args(argv)
    df = pd.read_csv(a.csv)
    rows = group_stats(df, a.column, a.group_column, a.groups)
    for r in rows:
        if r["lower"] is None:
            print(f"{r['group']}:  n={r['n']} (not enough data for a CI)")
        else:
            print(f"{r['group']}:  mean={r['mean']:.2f}, 95% CI=({r['lower']:.2f}, {r['upper']:.2f})")
    title = f"{a.column} with 95% confidence interval"
    with open(a.out, "wb") as f:
        f.write(ci_groups_png(rows, a.column, title))
    print("chart saved to", a.out)


if __name__ == "__main__":
    main()
