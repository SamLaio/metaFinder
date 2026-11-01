# metaFinder

以 ISBN、書名與作者，或商品網址查找書籍資料的 Python 工具。它將不同來源整理成可比較的候選清單，適合補查書名、譯者、出版社、出版日、ISBN／eISBN、簡介、系列、標籤與封面網址。

工具會回傳來源、分數與判斷證據；使用者核對版本後再採用資料。它不會修改 Calibre 書庫、EPUB 或既有封面。

目前版本：**0.1.20**。版本異動見 [CHANGELOG](CHANGELOG.md)。

## 安裝與快速開始

需要 Python 3.10 以上與網路連線。在專案根目錄執行：

```powershell
python -m pip install -e .
metafinder search "9786263151758" --json
```

查詢順序建議為 ISBN → 書名加作者 → 已核實的商品網址：

```powershell
metafinder search "書名 作者" --limit 5
metafinder search "https://www.jjwxc.net/onebook.php?novelid=7370132" --json
```

網址模式直接解析指定頁面，跳過搜尋。請使用單本書商品頁或作品頁。

## 查詢參數

| 參數 | 用途 | 預設 |
| --- | --- | --- |
| `query` | ISBN、書名與作者，或 URL | 必填 |
| `--limit` | 回傳候選數上限 | 8 |
| `--json` | 輸出 JSON 陣列，便於程式讀取 | 關閉 |
| `--download-cover 路徑` | 下載排名最高且有封面的候選圖片 | 不下載 |
| `--request-timeout 秒` | 單次 HTTP 請求逾時 | 3 |
| `--max-search-seconds 秒` | 整體查找時間預算 | 12 |
| `--max-web-queries 數量` | 公開搜尋的查詢變體上限 | 4 |

```powershell
metafinder search "9786263151758" --json --max-search-seconds 20
metafinder search "9786263151758" --download-cover .\cover.jpg
```

先檢查候選與版本，再決定是否下載封面。下載指令會寫入指定的圖片路徑；不會替換書庫封面。

## 如何閱讀結果

未加 `--json` 時顯示精簡表格；JSON 最外層為候選陣列。每個候選包含：

| 欄位 | 說明 |
| --- | --- |
| `source_name`、`source_url`、`source_kind` | 資料來源與頁面類型 |
| `score`、`evidence` | 排序分數與判斷依據；分數不是正確率 |
| `metadata` | 書目資料，缺值可能為 `null` 或空陣列 |
| `cover_url` | 封面網址，也可在 `metadata.cover_url` 取得 |

`metadata` 的欄位與採用原則見 [書目欄位與查找規則](docs/metadata.md)。

結束碼 `0` 表示有候選，`1` 表示沒有候選或整體查找逾時。JSON 空陣列 `[]` 不代表查詢到空白書目。逾時原因寫在 stderr；呼叫程式時應同時讀取輸出、錯誤與結束碼。

## 查不到或資料不完整

1. 確認 ISBN 對應同書同版；不要以商品碼或占位識別碼代替。
2. 改查「主書名 作者」，必要時去除行銷副標、作者英文括號，或改用其他集數寫法。
3. 有可信商品網址時直接解析。搜尋列表、登入頁、商店首頁不適合作為單本書資料。
4. 只有逾時時才視需要調高時間預算。反爬或網頁版型改變仍可能造成空結果。

沒有可靠候選時保留缺項，改用可信來源核對；不要因排名第一就直接套用。

## 簡轉正與自訂詞

書目文字只在共用轉換層偵測到明確簡體時轉為臺灣正體。一般使用者請先安裝 [zhTranslate](https://github.com/SamLaio/zhTranslate)，讓 Python 可匯入 `s2tw_converter`。本機另支援從 `D:\github\zhTranslate\src` 載入；無法載入時保留原文字。

匯入 `原詞<TAB>正體詞` 格式的文字檔：

```powershell
metafinder-import-replacements .\words.tsv
```

這是**會更新字典**的維護指令，預設目標為 `D:\github\zhTranslate\src\s2tw_converter\custom_replacements.tsv`。可傳入多個檔案，後面的同名詞條覆蓋前面的詞條；一般查書不需要執行。

## 開發與授權

原始碼入口與已安裝指令等效：`python -m metafinder.cli search "書名 作者"`。未安裝時先設定 `$env:PYTHONPATH="D:\project\metaFinder\src"`，並準備專案相依套件。

測試：`python -m pytest -q`。授權：GNU GPL v3，見 [LICENSE](LICENSE)。

設計參考：[chihchun/library-helper](https://github.com/chihchun/library-helper)，參考站點規則分層與搜尋出口設計，非執行時相依。
