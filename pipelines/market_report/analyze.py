"""
pipelines/market_report/analyze.py
Turns the raw tables pulled out of each PDF into a tidy numeric dataset
that's ready to chart.

搬家後完全沒有改動——這支檔案原本就沒有 import config，也沒有任何
os.path.dirname(__file__) 之類的自我相對路徑，純粹是 pandas 運算。目前
還沒有被任何 node 呼叫（make_chart.py 裡是 TODO 狀態），等你決定好要
從哪裡拿表格資料再接上。

Because report table layouts vary, this uses a generic heuristic:
  - the first column that is NOT mostly-numeric is treated as the row label
    (e.g. bond name, tenor, metric name)
  - every other column that IS mostly-numeric becomes a numeric series

This works well for typical "metric | value | value" style tables. If your
actual reports have a different shape once you test with real files, this
is the file to adjust — the rest of the pipeline doesn't care how the
numbers were derived.
"""
import re
import pandas as pd


_NUMERIC_CLEAN_RE = re.compile(r"[,%\s]")


def _to_numeric(series: pd.Series) -> pd.Series:
    cleaned = series.astype(str).str.replace(_NUMERIC_CLEAN_RE, "", regex=True)
    cleaned = cleaned.replace({"": None, "-": None, "None": None, "nan": None})
    return pd.to_numeric(cleaned, errors="coerce")


def tidy_table(df: pd.DataFrame, source_file: str, table_index: int) -> pd.DataFrame:
    """Convert one raw table into long format: label, metric, value, source_file."""
    if df.empty or len(df.columns) < 2:
        return pd.DataFrame(columns=["label", "metric", "value", "source_file"])

    numeric_cols = []
    for col in df.columns:
        numeric = _to_numeric(df[col])
        # Column counts as numeric if most non-null cells convert cleanly
        non_null = df[col].notna().sum()
        if non_null > 0 and numeric.notna().sum() / non_null >= 0.6:
            numeric_cols.append(col)

    label_candidates = [c for c in df.columns if c not in numeric_cols]
    if not label_candidates:
        return pd.DataFrame(columns=["label", "metric", "value", "source_file"])
    label_col = label_candidates[0]

    records = []
    for _, row in df.iterrows():
        label = row[label_col]
        if pd.isna(label) or str(label).strip() == "":
            continue
        for metric_col in numeric_cols:
            value = _to_numeric(pd.Series([row[metric_col]])).iloc[0]
            if pd.notna(value):
                records.append(
                    {
                        "label": str(label).strip(),
                        "metric": str(metric_col).strip(),
                        "value": value,
                        "source_file": source_file,
                    }
                )

    return pd.DataFrame(records)


def build_metrics_dataset(extracted_reports: list) -> pd.DataFrame:
    """Combine all tables from all of a day's reports into one tidy DataFrame."""
    frames = []
    for report in extracted_reports:
        for i, table in enumerate(report.tables):
            tidy = tidy_table(table, report.filename, i)
            if not tidy.empty:
                frames.append(tidy)

    if not frames:
        return pd.DataFrame(columns=["label", "metric", "value", "source_file"])

    return pd.concat(frames, ignore_index=True)
