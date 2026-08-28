---
type: Index
title: 法規知識庫
description: 固定收益／債券交易部門相關法規整理
---

# 法規知識庫

這是用 [[INSTRUCTIONS|LLM Wiki 規則]] 自動維護的法規知識庫，來源文件放
在 `domains/regulation_kb/sources/`，執行
`python -m pipelines.regulation_wiki.runner` 後會自動寫入/更新
`regulations/` 底下的頁面。

用 Obsidian 打開這個資料夾（`domains/regulation_kb/wiki/`）當 vault，
可以直接瀏覽、也可以手動編輯頁面內容——手動編輯完全不會影響查詢，因為
查詢是直接讀檔案，沒有另外的索引需要重建。

## 分類

- [[regulations/index|法規]]
