"""
infra/paths.py
所有需要用到「專案根目錄」路徑的地方都從這裡拿 PROJECT_ROOT，不要自己用
os.path.dirname(__file__) 疊層數去猜——資料夾搬過一次，猜的層數就全部要
重算，非常容易漏改、漏測，是這次重構最容易踩到的坑。

這支檔案本身在 infra/ 底下（根目錄下一層），往上兩層 dirname 就是專案根目
錄，其他檔案不管巢狀多深，都直接 import 這裡算好的 PROJECT_ROOT 就好。
"""
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
