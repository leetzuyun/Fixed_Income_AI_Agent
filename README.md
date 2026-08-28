# 金交處 AI Agent
因應公司需求，以 Spade 的 OpenAI LLM 作為主要使用的語言模型，設計處內各部門所需的 agent 功能。    
目前開發進度如下：  
1. 市場晨報 agent - 工作流以及內容**品管**
2. 法規資料庫問答 agent - 已建立資料庫以及問答 skill  
3. 可轉債資料庫問答以及部位計算 agent - 尚未確認需求以及資料來源  

## 開發環境
### 建立虛擬環境
```
cd ~檔案路徑
python3.12 -m venv .venv
.venv\Scripts\activate #啟動
```
### 安裝需要的套件
```
pip install -r requirements.txt
```
### 自行設定 API key
在 infra/ 檔案夾中建立一個檔案 .env，範例如下：
```
OPENAI_API_KEY = "your_open_api_key" # default from SPADE
GEMINI_API_KEY = " your_gemini_api_key" # 預設不會用到
```
### 切換使用模型
到 infra/config.py 中，設定 LLM_PROVIDER

### 啟動入口網站
```
chainlit run chainlit_app.py
```
## pipeline 功能
### 1. market_report
* 產出晨報(可以指定日期)
* 查詢產出歷史
* 查詢產出進度

*注意：此 agent 的資料來源為本機 outlook，若設定不符需要從 `pipelines/market_report/get_outlook_email.py` 中調整。待正式使用公機操作時會更改資料來源*    
### 2. regulation_wiki
* 查詢法規資料庫

*注意：法規 pdf 儲存在 `domains/regulation_kb/sources/`  
若該資料夾有增減需要輸入此指令以重新整合 `python -m pipelines.regulation_wiki.runner` (也可透過 Obsidian 手動整理)*

## 待開發
### 1. market_report
* 資料來源
* 數據分析圖表(目前是預設的範例)
* 報告格式(尚未確認)

### 2. regulation_wiki
* 是否需要新增出題功能？

### 3. CB Agent
* 確認需求
* 取得資料來源
