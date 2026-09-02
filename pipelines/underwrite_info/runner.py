"""
pipelines/underwrite_info/runner.py
手動觸發承銷公告 PDF 解析流程的入口。

用法（從專案根目錄）：
    python -m pipelines.underwrite_info.runner
會掃描 domains/underwriting_kb/sources/ 底下全部 PDF，逐一解析並寫入
SQLite + Excel。
"""
from pipelines.underwrite_info.graph import underwrite_info_graph


def run_pipeline() -> dict:
    result = underwrite_info_graph.invoke({})
    if result.get("skipped"):
        print("domains/underwriting_kb/sources/ 底下沒有找到任何 PDF 檔案。")
        return result
    print(f"\n完成，共處理 {result.get('saved_count', 0)} 筆公告。")
    return result


if __name__ == "__main__":
    run_pipeline()
