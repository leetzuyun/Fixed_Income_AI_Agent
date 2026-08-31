r"""
infra/downloads.py
取得目前執行這支程式的使用者，其 Windows「下載」資料夾的實際路徑。

不是單純用 os.path.expanduser("~") + "Downloads"——使用者可能透過
Windows 設定把下載資料夾重新導向到別的磁碟/路徑（例如公司機器常見的
D:\Downloads，因為 C 槽有容量限制），那種情況下 ~\Downloads 這個路徑
可能不存在，或是一個沒人在用的舊資料夾。改成讀 Windows 登錄檔裡
Explorer 記錄的「已知資料夾」路徑，才能保證抓到的是使用者當下真正在用
的下載資料夾。

之所以要動態抓、不能寫死路徑：這個 pipeline 之後會在「公機」（不一定是
你自己的電腦，見 README 的待開發事項）上執行，output 要能對應到「不管
在哪台電腦、哪個使用者身分執行，都存到那個使用者自己的下載資料夾」。
"""
import os

# Windows 的「下載」資料夾在登錄檔裡的已知資料夾 GUID（微軟官方定義，不
# 會因語系或使用者自訂資料夾名稱而改變，比用資料夾名稱字串比對可靠）。
_DOWNLOADS_FOLDER_GUID = "{374DE290-123F-4565-9164-39C4925E467B}"


def get_downloads_folder() -> str:
    """回傳目前執行這支程式的使用者，其「下載」資料夾的實際路徑。

    Windows 上優先讀登錄檔（尊重使用者把下載資料夾重新導向到別的路徑的
    設定）；讀不到（登錄檔權限問題、或根本不是 Windows，例如之後有人在
    Mac/Linux 上測試這支程式）就退回 ~/Downloads。任何失敗都不會拋出例
    外，因為找不到「真正」的下載資料夾時，退回一個合理的預設值比讓整個
    呼叫端出錯更實用。
    """
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            ) as key:
                path, _ = winreg.QueryValueEx(key, _DOWNLOADS_FOLDER_GUID)
                # 登錄檔裡的路徑可能包含環境變數（例如 %USERPROFILE%\Downloads），
                # 要展開成實際路徑。
                return os.path.expandvars(path)
        except Exception:
            pass  # 讀不到登錄檔，退回下面的預設值

    return os.path.join(os.path.expanduser("~"), "Downloads")
