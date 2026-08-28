"""
pipelines/market_report/nodes/make_chart.py
Graph node（LangChain Runnable）：圖表產生。目前行為跟現在的 main.py
完全一致——analyze.py / chart.py 還沒有實際接上（config.ENABLE_CHARTS
開了也只是印出提示訊息），因為現有的 email pipeline 沒有可以餵給
analyze.py 的表格資料來源。

等你決定好要從哪裡拿表格資料，把下面標記 TODO 的地方換成真正呼叫
pipelines.market_report.analyze / pipelines.market_report.chart 即可，
其他 node 都不用改。
"""
from langchain_core.runnables import chain

import infra.config as config


@chain
def make_chart(state: dict) -> dict:
    if state.get("skipped"):
        return state

    chart_paths = []
    if config.ENABLE_CHARTS:
        print("      (ENABLE_CHARTS is on, but the email pipeline has no table "
              "source for it yet — skipping.)")
        # TODO: 接上 analyze.py / chart.py
        # from pipelines.market_report.analyze import build_metrics_dataset
        # from pipelines.market_report.chart import generate_charts
        # metrics_df = build_metrics_dataset(extracted_reports)
        # chart_paths = generate_charts(metrics_df, config.OUTPUT_DIR)

    return {**state, "chart_paths": chart_paths}
