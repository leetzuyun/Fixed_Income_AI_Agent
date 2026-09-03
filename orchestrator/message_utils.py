"""
orchestrator/message_utils.py
從 agent 回傳的訊息取出純文字答案。
extract_answer_text() 把 type 是 "text" 的區塊接起來當作答案，忽略
reasoning（模型內部思考過程，是加密內容，看不懂也不該給使用者看）跟
web_search_call（搜尋過程的中繼資訊，不是答案本身）。text 區塊裡的引用
連結（例如「(來源網站)[url]」這種格式）模型自己就會寫進文字內容裡，不
用額外處理 annotations 欄位。
"""


def extract_answer_text(message) -> str:
    """從一則 AIMessage 取出純文字答案，不管 content 是字串還是
    responses/v1 的內容區塊列表都能正確處理。"""
    content = message.content

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        joined = "\n".join(part for part in text_parts if part).strip()
        return joined or "（這輪沒有產生文字答案）"

    return str(content)
