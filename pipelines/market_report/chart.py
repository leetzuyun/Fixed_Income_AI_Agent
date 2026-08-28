"""
pipelines/market_report/chart.py
Generates chart images (PNG) from the tidy metrics dataset produced by analyze.py.
Charts are saved to disk and their paths are handed to report1.py for embedding.

搬家後唯一改動：_bundled_font 原本用 os.path.dirname(os.path.abspath(__file__))
算路徑，假設這支檔案在專案根目錄、fonts/ 資料夾就在旁邊。現在搬進
pipelines/market_report/ 底下，改成從 infra/paths.py 拿 PROJECT_ROOT，
一樣指向專案根目錄的 fonts/，不用搬動 fonts/ 資料夾。

目前還沒有被任何 node 呼叫（make_chart.py 裡是 TODO 狀態），等你決定好
要從哪裡拿表格資料再接上。
"""
import os
import matplotlib
matplotlib.use("Agg")  # no display needed, just render to file
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from infra.paths import PROJECT_ROOT


# Use a font that can render CJK characters if labels are in Chinese.
# First try common OS-installed CJK fonts; if none are found (a bare Windows
# box may not have "Microsoft JhengHei", a fresh Linux box has neither),
# fall back to the Noto Sans TC file bundled in fonts/ so chart labels never
# render as tofu boxes regardless of what's installed on the machine.
plt.rcParams["axes.unicode_minus"] = False
_CJK_FONT_SET = False
for candidate in ["Microsoft JhengHei", "PingFang TC", "Heiti TC", "Arial Unicode MS"]:
    try:
        matplotlib.font_manager.findfont(candidate, fallback_to_default=False)
        plt.rcParams["font.family"] = candidate
        _CJK_FONT_SET = True
        break
    except Exception:
        continue

if not _CJK_FONT_SET:
    _bundled_font = os.path.join(PROJECT_ROOT, "fonts", "NotoSansTC-Regular.ttf")
    if os.path.exists(_bundled_font):
        fm.fontManager.addfont(_bundled_font)
        plt.rcParams["font.family"] = fm.FontProperties(fname=_bundled_font).get_name()


def generate_charts(metrics_df, output_dir: str, max_charts: int = 6) -> list:
    """
    For each distinct metric in the dataset, draw a bar chart of its values
    across labels. Returns a list of PNG file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    chart_paths = []

    if metrics_df.empty:
        return chart_paths

    metrics = metrics_df["metric"].unique()[:max_charts]

    for metric in metrics:
        subset = metrics_df[metrics_df["metric"] == metric].copy()
        # Keep charts readable: cap number of bars, sort descending
        subset = subset.sort_values("value", ascending=False).head(15)

        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.bar(subset["label"], subset["value"], color="#2E5090")
        ax.set_title(str(metric))
        ax.set_ylabel(str(metric))
        ax.tick_params(axis="x", rotation=45, labelsize=8)
        for label in ax.get_xticklabels():
            label.set_ha("right")
        fig.tight_layout()

        safe_name = "".join(c if c.isalnum() else "_" for c in str(metric))[:40]
        out_path = os.path.join(output_dir, f"chart_{safe_name}.png")
        fig.savefig(out_path, dpi=150)
        plt.close(fig)

        chart_paths.append(out_path)

    return chart_paths
