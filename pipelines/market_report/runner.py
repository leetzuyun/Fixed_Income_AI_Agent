"""
pipelines/market_report/runner.py
包住 infra/status_store.py 的 start_run / finish_run，跟原本 main.py 的
run() 行為一致：檢查是否已有流程在跑、開始/結束都寫進 run_history.db。

main.py（排程用）和 orchestrator/tools.py（chat 觸發用）都呼叫這支
run_pipeline()，兩邊共用同一份邏輯與同一個 market_report_graph，不會
分岔成兩份要各自維護的程式碼。
"""
import datetime

import infra.config as config
import infra.status_store as status
from pipelines.market_report.graph import market_report_graph


def run_pipeline() -> str:
    if status.is_run_in_progress():
        print("已有一個流程正在執行中，本次跳過。")
        return None

    run_id = status.start_run(provider=config.LLM_PROVIDER)
    today_date = datetime.date.today()

    try:
        result = market_report_graph.invoke({
            "run_id": run_id,
            "today_date": today_date,
        })

        if result.get("skipped"):
            print("No relevant emails or reports found for today. Nothing to do.")
            status.finish_run(run_id, success=True, output_path=None,
                               bbg_count=0, sinopac_count=0)
            return None

        output_path = result.get("output_path")
        print(f"\nDone. Report saved to: {output_path}")
        if result.get("downloads_path"):
            print(f"Also copied to: {result.get('downloads_path')}")
        status.finish_run(
            run_id, success=True, output_path=output_path,
            bbg_count=len(result.get("bbg_news", [])),
            sinopac_count=len(result.get("sinopac_views", [])),
        )
        return output_path

    except Exception as e:
        status.finish_run(run_id, success=False, error=str(e))
        raise
