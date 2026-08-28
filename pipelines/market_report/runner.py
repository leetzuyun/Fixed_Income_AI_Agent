"""
pipelines/market_report/runner.py
包住 infra/status_store.py 的 start_run / finish_run，跟原本 main.py 的
run() 行為一致：檢查是否已有流程在跑、開始/結束都寫進 run_history.db。

main.py（排程用）和 orchestrator/tools.py（chat 觸發用）都呼叫這支
run_pipeline()，兩邊共用同一份邏輯與同一個 market_report_graph，不會
分岔成兩份要各自維護的程式碼。
"""
import datetime
import re
from typing import Optional

import infra.config as config
import infra.status_store as status
from pipelines.market_report.graph import market_report_graph


def parse_report_date(value: Optional[str] = None) -> datetime.date:
    """Parse an explicit report date; an empty value means today."""
    if value is None or not str(value).strip():
        return datetime.date.today()

    text = str(value).strip()
    today = datetime.date.today()
    relative_dates = {
        "今天": today,
        "今日": today,
        "昨天": today - datetime.timedelta(days=1),
        "前天": today - datetime.timedelta(days=2),
    }
    if text in relative_dates:
        return relative_dates[text]

    normalized = text.replace("年", "-").replace("月", "-").replace("日", "")
    normalized = normalized.replace("/", "-").replace(".", "-")
    if re.fullmatch(r"\d{8}", normalized):
        normalized = f"{normalized[:4]}-{normalized[4:6]}-{normalized[6:]}"
    else:
        match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", normalized)
        if match:
            normalized = "-".join(f"{part:0>2}" for part in match.groups())
    try:
        return datetime.date.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(
            f"日期格式無法辨識：{value}。請使用 YYYY-MM-DD，例如 2026-08-27。"
        ) from exc


def run_pipeline(target_date: Optional[str] = None) -> Optional[str]:
    if status.is_run_in_progress():
        print("已有一個流程正在執行中，本次跳過。")
        return None

    run_id = status.start_run(provider=config.LLM_PROVIDER)
    today_date = parse_report_date(target_date)

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
        status.finish_run(
            run_id, success=True, output_path=output_path,
            bbg_count=len(result.get("bbg_news", [])),
            sinopac_count=len(result.get("sinopac_views", [])),
        )
        return output_path

    except Exception as e:
        status.finish_run(run_id, success=False, error=str(e))
        raise
