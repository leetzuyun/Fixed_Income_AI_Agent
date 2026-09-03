"""
lseg_mcp_discover.py
連上 LSEG MCP（用 service account 驗證，見 lseg_client.py），列出它實際
提供哪些工具、每個工具要什麼參數。

前提：config.py 要先設好 LSEG_CLIENT_ID / LSEG_CLIENT_SECRET
（見 lseg_client.py 開頭的說明）。

用法：
    python lseg_mcp_discover.py
"""
import json

import lseg_client


def main():
    result = lseg_client.list_tools()
    print(f"連線成功，LSEG MCP 提供 {len(result.tools)} 個工具：\n")
    for t in result.tools:
        print(f"- {t.name}")
        if t.description:
            print(f"    說明：{t.description}")
        if t.inputSchema:
            print(f"    參數：{json.dumps(t.inputSchema, ensure_ascii=False)}")
        print()


if __name__ == "__main__":
    main()
