"""
pipelines/market_report/get_outlook_email.py
Finds report files and emails directly from Outlook folders and extracts their content.

搬家後唯一改動：`import config` -> `import infra.config as config`。這支
檔案沒有任何 os.path.dirname(__file__) 之類的自我相對路徑，所以除了
import 之外不用改別的。
"""
import os
import datetime
import tempfile
from dataclasses import dataclass, field

import pdfplumber
import pandas as pd
import fitz  # PyMuPDF, used for embedded image extraction
import win32com.client
import pythoncom
from pywintypes import com_error

import infra.config as config

MIN_IMAGE_WIDTH = 150
MIN_IMAGE_HEIGHT = 100


@dataclass
class ExtractedReport:
    path: str
    filename: str
    text: str
    tables: list = field(default_factory=list)
    images: list = field(default_factory=list)


def _dedupe_columns(columns: list) -> list:
    """Ensure column names are unique so df[col] always returns a Series."""
    seen = {}
    result = []
    for col in columns:
        if col not in seen:
            seen[col] = 0
            result.append(col)
        else:
            seen[col] += 1
            result.append(f"{col}_{seen[col]}")
    return result


def extract_pdf_content(path: str) -> ExtractedReport:
    """Extract full text, tables (as DataFrames), and embedded chart images from a PDF."""
    text_parts = []
    tables = []

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

            for raw_table in page.extract_tables():
                if not raw_table or len(raw_table) < 2:
                    continue
                header, *rows = raw_table
                header = [str(c).strip() if c else f"col_{i}" for i, c in enumerate(header)]
                header = _dedupe_columns(header)
                df = pd.DataFrame(rows, columns=header)
                tables.append(df)

    images = extract_embedded_images(path)

    return ExtractedReport(
        path=path,
        filename=os.path.basename(path),
        text="\n".join(text_parts),
        tables=tables,
        images=images,
    )


def extract_embedded_images(path: str) -> list:
    results = []
    doc = fitz.open(path)
    try:
        for page_index in range(len(doc)):
            page = doc[page_index]
            for img in page.get_images(full=True):
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                except Exception:
                    continue
                if base_image["width"] < MIN_IMAGE_WIDTH or base_image["height"] < MIN_IMAGE_HEIGHT:
                    continue
                results.append({
                    "bytes": base_image["image"],
                    "ext": base_image["ext"],
                    "page": page_index + 1,
                })
    finally:
        doc.close()
    return results


# ---------------------------------------------------------------------------
# Outlook MAPI 資料夾讀取與條件篩選
# ---------------------------------------------------------------------------

def _get_outlook_folder(inbox, folder_path_list: list):
    current_folder = inbox
    for name in folder_path_list:
        try:
            current_folder = current_folder.Folders[name]
        except Exception as e:
            print(f"      [warn] 找不到 Outlook 資料夾: {'/'.join(folder_path_list)} (無法開啟: {name})")
            return None
    return current_folder

def _same_week(date_a: datetime.date, date_b: datetime.date) -> bool:
    """True if two dates fall in the same ISO week (Mon–Sun).
    用於週報類信件：只要落在同一週，不論當週哪天執行 pipeline 都能抓到。"""
    if not date_a or not date_b:
        return False
    return date_a.isocalendar()[:2] == date_b.isocalendar()[:2]


def _to_date(com_time) -> datetime.date:
    if not com_time:
        return None
    try:
        return datetime.date(com_time.year, com_time.month, com_time.day)
    except Exception:
        return None


def get_us_yesterday_date(base_date: datetime.date = None) -> datetime.date:
    if base_date is None:
        base_date = datetime.date.today()
    return base_date - datetime.timedelta(days=1)


def get_bbg_target_dates(today_date: datetime.date = None) -> list:
    """
    Candidate "news date" list to look for in BBG News emails.

    Normally just yesterday. But on Monday, US markets were closed all
    weekend, so Monday's BBG News forwards typically carry Friday's (last
    trading day) or weekend-dated content instead of Sunday's — so check
    Friday, Saturday, AND Sunday together rather than just "yesterday"
    (which would be Sunday, and usually matches nothing).
    """
    if today_date is None:
        today_date = datetime.date.today()

    if today_date.weekday() == 0:  # Monday
        friday = today_date - datetime.timedelta(days=3)
        saturday = friday + datetime.timedelta(days=1)
        sunday = friday + datetime.timedelta(days=2)
        return [friday, saturday, sunday]

    return [today_date - datetime.timedelta(days=1)]


def _find_matching_us_date(text: str, candidate_dates) -> datetime.date:
    """
    Return whichever candidate date appears as an MM/DD/YYYY string
    (zero-padded or not) in `text`, or None if none match. Used for BBG
    News specifically, since those are forwarded emails — Outlook's
    Received/Sent time reflects when it was forwarded, not the actual
    Bloomberg news date, which is only reliable as text embedded in the
    subject/body.
    """
    if not text:
        return None
    if isinstance(candidate_dates, datetime.date):
        candidate_dates = [candidate_dates]
    for d in candidate_dates:
        forms = (d.strftime("%m/%d/%Y"), f"{d.month}/{d.day}/{d.year}")
        if any(f in text for f in forms):
            return d
    return None


def load_bbg_news_from_outlook(today_date: datetime.date = None) -> list:
    """
    第一區：重點債市新聞與數據評析
    來源與時間條件：
      1. 收件夾 / BBG News -> 條件：內文/主旨中含有目標美國日期文字 (MM/DD/YYYY)。
         平常是前一天；週一則涵蓋上週五、六、日（因為週末美股休市，週一轉寄的
         新聞通常是週五最後交易日或週末的內容），不使用 Outlook 收件時間
         （轉寄信件的時間不可靠）。
      2. 收件夾 / 金融市場短觀 -> 條件：Outlook 收件時間為當天 (today_date)
    內容：直接讀取信件主旨與內文 (Body)
    """
    if today_date is None:
        today_date = datetime.date.today()

    bbg_target_dates = get_bbg_target_dates(today_date)

    pythoncom.CoInitialize()
    bbg_items = []

    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        inbox = outlook.GetDefaultFolder(6)  # 6 = olFolderInbox

        bbg_folder = _get_outlook_folder(inbox, ["BBG News"])
        mkt_view_folder = _get_outlook_folder(inbox, ["金融市場短觀"])

        if not bbg_folder:
            print("      [warn] 找不到 BBG News 資料夾，跳過此資料夾。")
        if not mkt_view_folder:
            print("      [warn] 找不到 金融市場短觀 資料夾，跳過此資料夾。")

        target_mails = []  # (item, source_tag, resolved_date)

        # 1.「BBG News」-> 偵測內文/主旨中是否含有 bbg_target_dates 其中一個日期
        if bbg_folder:
            for item in bbg_folder.Items:
                try:
                    if item.Class != 43:  # 43 代表 olMail
                        continue
                    subject = item.Subject or ""
                    body = item.Body or ""
                    matched_date = _find_matching_us_date(f"{subject}\n{body}", bbg_target_dates)
                    if matched_date:
                        target_mails.append((item, "BBG News", matched_date))
                except Exception as e:
                    print(f"      [warn] 檢查 BBG News 郵件時發生錯誤: {e}")

        # 2.「金融市場短觀」-> 維持原本邏輯，使用 Outlook 收件時間 == today_date
        if mkt_view_folder:
            for item in mkt_view_folder.Items:
                try:
                    if item.Class != 43:
                        continue
                    m_date = _to_date(item.ReceivedTime) or _to_date(item.SentOn)
                    if m_date == today_date:
                        target_mails.append((item, "金融市場短觀", m_date))
                except Exception as e:
                    print(f"      [warn] 檢查 金融市場短觀 郵件時發生錯誤: {e}")

        # 3. 統一解析所有符合條件的信件
        for item, source_tag, m_date in target_mails:
            try:
                subject = item.Subject or ""
                sender = item.SenderName or ""
                body = item.Body or ""

                bbg_items.append({
                    "subject": subject,
                    "sender": sender,
                    "date": m_date,
                    "text": f"【來源：{source_tag}】\n主旨：{subject}\n時間：{m_date}\n\n{body}",
                    "type": source_tag,
                })
            except Exception as e:
                print(f"      [warn] 讀取 [{source_tag}] 郵件內文失敗: {e}")

    except com_error as e:
        print(f"      [error] 連線 Outlook MAPI 失敗: {e}")
    finally:
        pythoncom.CoUninitialize()

    return bbg_items

def load_sinopac_views_from_outlook(target_date: datetime.date = None) -> list:
    """
    第二區：永豐觀點
    來源：
      1. 收件夾 / 永豐投顧 / 財富管理日報 (當天信件)
      2. 收件夾 / 永豐投顧 (主旨含「台灣指標評析」的當天信件)
      3. 收件夾 / 永豐投顧 (主旨含「國際經濟評論」的當天信件)
      4. 收件夾 / 永豐投顧 (主旨含「永豐總經與產業週報」的『當週』信件 —
         因為是週報，只要跟 target_date 落在同一個 ISO 週內就會被抓，
         代表這週每天執行都會重複抓到同一封)
    內容：讀取附檔中的 PDF 檔，抽取出內文與表格
    """
    if target_date is None:
        target_date = datetime.date.today()

    pythoncom.CoInitialize()
    extracted_views = []

    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        inbox = outlook.GetDefaultFolder(6)

        sinopac_base = _get_outlook_folder(inbox, ["永豐投顧"])
        wm_daily_folder = _get_outlook_folder(inbox, ["永豐投顧", "財富管理日報"])

        target_mails = []

        if wm_daily_folder:
            for item in wm_daily_folder.Items:
                if item.Class != 43:
                    continue
                m_date = _to_date(item.ReceivedTime) or _to_date(item.SentOn)
                if m_date == target_date:
                    target_mails.append((item, "財富管理日報"))

        if sinopac_base:
            for item in sinopac_base.Items:
                if item.Class != 43:
                    continue
                subject = item.Subject or ""
                m_date = _to_date(item.ReceivedTime) or _to_date(item.SentOn)

                if "台灣指標評析" in subject and m_date == target_date:
                    target_mails.append((item, "台灣指標評析"))
                elif "國際經濟評論" in subject and m_date == target_date:
                    target_mails.append((item, "國際經濟評論"))
                elif "永豐總經與產業週報" in subject and _same_week(m_date, target_date):
                    target_mails.append((item, "永豐總經與產業週報"))

        for mail, source_tag in target_mails:
            subject = mail.Subject or ""
            sender = mail.SenderName or ""
            m_date = _to_date(mail.ReceivedTime) or _to_date(mail.SentOn)
            attachments = mail.Attachments

            for i in range(1, attachments.Count + 1):
                att = attachments.Item(i)
                filename = att.FileName or ""

                if filename.lower().endswith(".pdf"):
                    fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
                    os.close(fd)
                    try:
                        att.SaveAsFile(tmp_path)
                        report = extract_pdf_content(tmp_path)
                        report.filename = filename

                        extracted_views.append({
                            "source_tag": source_tag,
                            "subject": subject,
                            "sender": sender,
                            "date": m_date,
                            "pdf_name": filename,
                            "text": f"【來源：永豐觀點-{source_tag}】\n主旨：{subject}\n附件 PDF：{filename}\n\n{report.text}",
                            "report_object": report
                        })
                    except Exception as e:
                        print(f"      [warn] 解析永豐 PDF 附件 {filename} 失敗: {e}")
                    finally:
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)

    except com_error as e:
        print(f"      [error] 連線 Outlook MAPI 失敗: {e}")
    finally:
        pythoncom.CoUninitialize()

    return extracted_views


# ---------------------------------------------------------------------------
# 完整數據匯集中心 (確保全量載入才進行後續整理)
# ---------------------------------------------------------------------------

def load_all_daily_sources(today_date: datetime.date = None) -> dict:
    """
    一鍵式完整載入：確保第一區 (BBG News) 與第二區 (永豐觀點) 全部收集完畢。
    """
    if today_date is None:
        today_date = datetime.date.today()

    print(f"=== 開始讀取今日市場摘要所需信件/報告 ({today_date}) ===")

    print(f"[*] [第一區] 讀取收件夾/BBG News + 金融市場短觀...")
    bbg_news_list = load_bbg_news_from_outlook(today_date=today_date)
    print(f"    └─ 成功擷取 {len(bbg_news_list)} 封 BBG 新聞 + 金融市場短觀")

    print(f"[*] [第二區] 讀取收件夾/永豐投顧 (目標台灣日期: {today_date})...")
    sinopac_views_list = load_sinopac_views_from_outlook(target_date=today_date)
    print(f"    └─ 成功解析 {len(sinopac_views_list)} 份永豐 PDF 報告內容")

    print("=== 所有資料已確保完成載入 ===")

    return {
        "bbg_news": bbg_news_list,
        "sinopac_views": sinopac_views_list
    }
