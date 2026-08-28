"""
main.py
Daily report agent — Task Scheduler 排程入口。

原本這支檔案裡有完整的抓信→摘要→產 PDF 流程（run() 函式），現在整個流
程邏輯都改寫成 pipelines/market_report/ 底下的 LangGraph chain 了：
  - pipelines/market_report/graph.py    graph 本身（node 怎麼接）
  - pipelines/market_report/runner.py   包 status_store 的 start/finish
  - pipelines/market_report/nodes/      每個處理步驟

這支檔案現在只負責：Windows Task Scheduler 呼叫 `python main.py` 時的
進入點，跟 CLI 錯誤訊息的處理。orchestrator/tools.py 的
trigger_daily_report 工具呼叫的是同一個 run_pipeline()，兩條觸發路徑
（排程 vs. chat 手動觸發）共用同一份邏輯，不會分岔。

Usage:
    python main.py

執行前務必確認：Task Scheduler 設定的「起始位置 (Start in)」是這個專案
的根目錄，不是 scheduling/ 或其他子資料夾——因為 pipelines.market_report
這種寫法是絕對 import，Python 要能在 sys.path 找到專案根目錄才 import
得到，工作目錄設錯的話會直接噴 ModuleNotFoundError。
"""
import argparse
import sys

from pipelines.market_report.runner import run_pipeline
from infra.llm import LLMError


def parse_args():
    parser = argparse.ArgumentParser(description="Run the daily fixed income report agent.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        run_pipeline()
    except LLMError as e:
        print(f"\n[LLM error] {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"\n[Error] {e}", file=sys.stderr)
        sys.exit(1)
