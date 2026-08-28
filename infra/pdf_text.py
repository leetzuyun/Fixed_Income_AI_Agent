"""
infra/pdf_text.py
最小、共用的 PDF 純文字擷取工具。

跟 pipelines/market_report/get_outlook_email.py 裡的 extract_pdf_content()
不一樣——那支是為了信件附件設計的，除了文字還會擷取表格跟嵌入圖片；法規
wiki 目前只需要純文字，用這支輕量版本就好，避免 domains/regulation_kb
這個 domain 反過來 import market_report pipeline 底下的模組（跨 domain
import 方向會很奇怪，也會讓 regulation_kb 平白多一層跟晨報 pipeline的耦
合）。之後如果法規 PDF 也需要抽表格，再回頭讓兩邊共用同一套邏輯。
"""
import pdfplumber


def extract_text(path: str) -> str:
    """讀一份 PDF，回傳所有頁面的純文字，頁與頁之間用換行隔開。"""
    parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n".join(parts)
