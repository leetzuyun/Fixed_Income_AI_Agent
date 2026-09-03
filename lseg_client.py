"""
lseg_client.py
LSEG MCP 的連線模組，用 service account 的 client_credentials 驗證方式
（照 LSEG 官方文件的 Service Account / Machine Access 段落）——不用瀏覽器
互動、不用動態註冊，適合排程/背景執行的腳本。

前提：要先照 LSEG 的 PPA User Guide 建立一個 service account，拿到
client id + secret，然後在 config.py 加上：

    LSEG_CLIENT_ID = "XX-XXXXXXXXXX"
    LSEG_CLIENT_SECRET = "YYYYYYYY-YYYY-YYYY-YYYY-YYYYYYYYYYYY"

（或用環境變數 LSEG_CLIENT_ID / LSEG_CLIENT_SECRET，這裡兩種都支援，
config.py 沒設就會去讀環境變數。）

需要安裝：
    pip install requests mcp httpx
（requests 應該本來就有裝；mcp / httpx 之前接 OAuth 那版已經裝過了。）
"""
import asyncio
import os
import time

import httpx
import requests

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

import config

LSEG_TOKEN_URL = "https://login.ciam.refinitiv.com/as/token.oauth2"
LSEG_MCP_URL = "https://api.analytics.lseg.com/lfa/mcp"  # 注意：machine access 用這個，沒有 /server-cl
LSEG_SCOPE = "lfa"

LSEG_CLIENT_ID = getattr(config, "LSEG_CLIENT_ID", None) or os.environ.get("LSEG_CLIENT_ID")
LSEG_CLIENT_SECRET = getattr(config, "LSEG_CLIENT_SECRET", None) or os.environ.get("LSEG_CLIENT_SECRET")

_token_cache = {"access_token": None, "expires_at": 0}


def get_access_token(force_refresh: bool = False) -> str:
    """用 client_credentials 換一個 access token。token 存活 2 小時，這裡
    做了簡單的記憶體快取，同一次執行內重複呼叫不會一直打 token endpoint。
    """
    now = time.time()
    if not force_refresh and _token_cache["access_token"] and now < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    if not LSEG_CLIENT_ID or not LSEG_CLIENT_SECRET:
        raise RuntimeError(
            "LSEG_CLIENT_ID / LSEG_CLIENT_SECRET 未設定。請先照 LSEG 的 PPA "
            "User Guide 建立 service account 拿到這兩個值，再加進 config.py "
            "或設成環境變數。"
        )

    response = requests.post(
        LSEG_TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "client_credentials",
            "client_id": LSEG_CLIENT_ID,
            "client_secret": LSEG_CLIENT_SECRET,
            "scope": LSEG_SCOPE,
        },
    )
    response.raise_for_status()
    data = response.json()

    token = data["access_token"]
    expires_in = data.get("expires_in", 7200)  # 秒數，沒回傳就假設 2 小時
    _token_cache["access_token"] = token
    _token_cache["expires_at"] = now + expires_in - 60  # 提前 60 秒視為過期，避免邊界問題
    return token


async def _with_session(coro_fn):
    """開一個帶著 bearer token 的 MCP session，跑完 coro_fn(session) 就關掉連線。"""
    token = get_access_token()
    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}) as http_client:
        async with streamable_http_client(LSEG_MCP_URL, http_client=http_client) as (
            read_stream, write_stream, _get_session_id,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                return await coro_fn(session)


def list_tools():
    """列出 LSEG MCP 實際提供的工具（同步呼叫，內部包了 asyncio.run）。"""
    return asyncio.run(_with_session(lambda session: session.list_tools()))


def call_tool(name: str, arguments: dict):
    """呼叫指定的 LSEG MCP 工具（同步呼叫）。等知道實際工具名稱/參數後，
    get_lseg_data.py 會用這個函式去實際拉資料。"""
    return asyncio.run(_with_session(lambda session: session.call_tool(name, arguments)))
