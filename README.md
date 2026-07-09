# metaFinder

License: GNU General Public License v3.0

`metaFinder` 把目前整理 Calibre 書庫時使用的 metadata 查找邏輯抽成獨立 Python 工具。

它做的事：

- 以書名、作者或 ISBN 查找候選資料頁。
- 優先找官方或主要書店/平台來源。
- 解析書名、作者、譯者、出版社、出版日、ISBN/eISBN、簡介、標籤、封面 URL。
- 使用專案內相依的 `opencc-python-reimplemented` 的 `OpenCC('s2tw')` 將簡體資料轉成臺灣正體。
- 保留多個候選來源與分數，不自動推測 Calibre 的來源欄位。

## 安裝

建議使用 Python 3.10 以上。這個專案目前沒有綁定 Calibre DB，只負責查 metadata 候選。

### 一般安裝

```powershell
cd D:\project\metaFinder
python -m pip install -e .
```

這會同時安裝本專案與 `opencc-python-reimplemented`，是建議的使用方式。

### 直接從原始碼執行

```powershell
$env:PYTHONPATH="D:\project\metaFinder\src"
python -m metafinder.cli search "9786263151758"
```

如果你已經安裝過一次，之後只是改 Python 程式碼，通常不用重裝。
如果有改到 `pyproject.toml` 的依賴，建議再跑一次 `python -m pip install -e .`。

### 匯入自訂詞

如果你已經整理好 `原詞<TAB>翻譯` 的 txt 或 tsv，可以直接匯入到專案內的替換檔：

```powershell
metafinder-import-replacements D:\path\to\your_words.txt
```

預設會更新 `[src/metafinder/custom_replacements.tsv](D:/project/metaFinder/src/metafinder/custom_replacements.tsv)`。
你也可以一次丟多個檔案，後面的檔案會覆寫前面的同名詞條。

## 執行方式

### 以 ISBN 查詢

ISBN 是最穩定的查詢方式。若候選中有 ISBN 精準命中，工具會只保留命中候選，避免混入無關搜尋結果。

```powershell
metafinder search "9786263151758"
metafinder search "9786263151758" --json
```

### 以書名或作者查詢

書名查詢會比較依賴搜尋結果品質。若沒有可靠候選，工具會回傳空結果，而不是硬塞看起來相似但不正確的資料。

```powershell
python -m metafinder.cli search "S級保鏢 多笑天"
python -m metafinder.cli search "迷宮飯 14" --limit 5
```

### 直接解析指定網址

如果已經知道來源頁，直接給 URL 最穩。這會跳過搜尋階段，直接解析該頁。

```powershell
python -m metafinder.cli search "https://ixdzs8.com/read/236949/" --json
```

### 下載最佳候選封面

`--download-cover` 會下載分數最高且有 `cover_url` 的候選封面。下載前仍建議先看 JSON 或表格輸出確認候選是否正確。

```powershell
metafinder search "9786263151758" --download-cover D:\project\CalibreAbout\work\cover.jpg
```

## 查找策略

來源優先序大致為：

1. 出版社官方頁
2. 博客來
3. Readmoo
4. Pubu
5. Kobo
6. BOOKWALKER
7. 政府/文化部相關書目
8. 其他候選頁

工具會把搜尋結果解析成候選清單並打分。分數只協助排序，不代表一定正確；整理書庫時仍應檢查候選來源是否可靠。

## 輸出欄位

每個候選會包含：

- `source_name`：解析到的來源名稱，例如 `Readmoo`、`博客來`、`青文出版社`。
- `source_url`：實際查證頁網址。
- `source_kind`：來源類型，例如 `publisher`、`store`、`government`、`web-novel`。
- `score`：候選排序分數，只用來排序，不代表絕對正確。
- `evidence`：解析依據，例如 `meta-tags`、`json-ld`、`visible-labels`。
- `metadata.title`：書名。
- `metadata.authors`：作者清單。
- `metadata.translators`：譯者清單。
- `metadata.publisher`：出版社。
- `metadata.published_date`：來源頁日期字串。
- `metadata.isbn` / `metadata.eisbn`：紙本 ISBN / 電子 ISBN。
- `metadata.description`：簡介。
- `metadata.tags`：短標籤候選。
- `metadata.awards`：只在目前來源頁本身是可信得獎紀錄時輸出，包含 `name`、`status`、`international`、`evidence`、`source_name`、`source_url`。
- `metadata.cover_url`：封面 URL。

## Calibre 慣例

- 不會自動填 Calibre 的來源 custom column。
- 作者名稱會盡量維持官方中文名；若頁面只有外文名，就保留來源拼法。
- metadata 候選輸出的 `source_url` 只是查證來源，不等同 Calibre `來源` 欄位。
- 出版日輸出為頁面日期字串，寫入 Calibre DB 時仍需依書庫慣例轉 UTC。

## 注意事項

- 這是查找工具，不會修改 Calibre DB、EPUB 或封面檔。
- 書名查詢可能找不到資料，尤其是網路小說、冷門書、下架書或搜尋引擎暫時擋爬時。
- 找不到候選時，CLI 會顯示 `No candidates found.` 並以 exit code `1` 結束。
- 直接 URL 解析比關鍵字搜尋可靠；整理書庫時若已知來源頁，優先貼 URL。
- `source_url` 是查證用來源，不要拿來自動填 Calibre 的 `來源` custom column。
- `published_date` 沒有自動轉 UTC；寫入 Calibre 時要依書庫慣例處理時區。
- `score` 只是排序輔助；高分候選仍可能是同名書或搜尋頁推薦項，使用前要人工確認。
- 封面 URL 可能是低解析、站方占位圖或 R18 占位圖；換封面前要先看圖。
- 有些站台會回 403、空搜尋頁或動態載入內容，這種情況工具會跳過該候選。
- 簡轉繁使用 `opencc-python-reimplemented`，若套件不可用，工具會保留原文字。
- 標籤與獎項是輔助判斷，不會直接修改 Calibre；寫入前仍要檢查候選是否合理。

## 擴充詞庫

目前這個專案採的是最小方案，直接依賴 `opencc-python-reimplemented`，不另外維護一份完整 OpenCC fork。

如果未來只需要修少數專案特有詞彙，建議先在 `src/metafinder/normalize.py` 做一層很小的前後處理替換，成本最低，也最容易回退。
對應的來源檔是 `[src/metafinder/custom_replacements.tsv](D:/project/metaFinder/src/metafinder/custom_replacements.tsv)`，直接補 `原詞<TAB>翻譯` 就行，或用 `metafinder-import-replacements` 匯入整理好的 txt。

如果真的需要擴充成一整套自訂詞庫，因為這個套件本身沒有提供自訂字典路徑參數，做法通常是：

1. 把 `opencc` 原始碼與字典檔 fork 到本專案內。
2. 在 fork 版本的 `config/*.json` 和 `dictionary/*.txt` 裡加入你的詞條。
3. 讓本專案改用那份本地 `opencc` 實作，而不是外部套件。

也就是說，少量修正常用「專案內小型覆寫」，大量詞庫維護才考慮「vendor 一份本地 OpenCC」。

## 已知限制

- 目前 parser 以通用 HTML、meta tag、JSON-LD 與可見欄位為主，不是每個站台都有專屬 parser。
- 博客來商品頁有時會拒絕直接抓取；可改用 Readmoo、出版社頁或其他可讀來源交叉確認。
- 書名/作者拆詞仍是啟發式，遇到符號、外文名或特殊站名時可能需要後續修 parser。
- 網路搜尋頁結果不穩定，所以工具也會嘗試站內搜尋；若兩者都失敗，建議直接提供 URL。

## 已沉澱的判斷規則

- 多集數書名若只差尾端集數，整理成兩位數集數前綴：
  - `我獨自升級8` -> `08 我獨自升級`
  - `書名(12)` -> `12 書名`
- 同時把共享書名視為 series title，尾端數字視為 `series_index`。
- Readmoo 等電子書頁若同時出現 `eISBN` 與 `ISBN`，兩者要分開解析：
  - `eISBN` 寫入電子 ISBN。
  - 獨立的 `ISBN` 才寫入紙本 ISBN。
  - 不可讓 `ISBN` 規則誤吃 `eISBN` 裡的字串。
- 來源頁若把中文輸出成 HTML entity，例如 `&#x6211;`，解析後要先還原成正常文字再進行 metadata 正規化。
- `shogakukan.co.jp`、`gagagabunko.jp` 屬於小學館/ガガガ系官方出版社來源，來源優先序應高於一般站台。
- 標籤要短而精準：
  - 地區：`臺灣`、`日本`、`韓國`、`美國` 等。
  - 類型/題材：`小說`、`輕小說`、`奇幻`、`推理`、`科幻`、`言情`、`戰記` 等。
  - 避免輸出過長複合詞，例如優先用 `言情`、`小說`，不要用 `言情小說`。
- 國際大獎/得獎標籤採「不反查、不臆測」規則：
  - 書店、出版社、簡介、推薦文裡提到得獎，只能視為文字內容，不自動標成得獎。
  - 若需要再反查、需要人工判斷、或來源不是實際得獎紀錄頁，就當作沒有得獎。
  - 只有目前解析的 `source_url` 本身是可信得獎紀錄來源，例如獎項官網、Wikipedia、Wikidata，且頁面同時能對上書名/作者與得獎或入圍語境，才輸出 `metadata.awards`。
  - 驗證成立時，得獎加入 `得獎作品`、具體獎名；入圍/短名單加入 `入圍作品`、具體獎名。
  - 驗證成立且屬國際性獎項時，另外加入 `國際大獎`。
  - 目前獎項表包含諾貝爾文學獎、布克獎、國際布克獎、普立茲獎、美國國家圖書獎、國際都柏林文學獎、女性小說獎、龔古爾獎、雨果獎、星雲獎、軌跡獎、愛倫坡獎、匕首獎、紐伯瑞獎、凱迪克獎、卡內基獎、安徒生獎、林格倫紀念獎等。

## 建議工作流

1. 先用 ISBN 查：

```powershell
metafinder search "9786263151758" --json
```

2. 若 ISBN 沒結果，改用書名加作者：

```powershell
metafinder search "書名 作者" --limit 5
```

3. 若知道官方或書店頁，直接解析 URL：

```powershell
metafinder search "https://example.com/book-page" --json
```

4. 確認候選後，再把 metadata 套入 Calibre；不要讓工具自動推測 Calibre 來源欄位。

5. 若要換封面，先下載候選封面到工作資料夾並人工檢查：

```powershell
metafinder search "9786263151758" --download-cover D:\project\CalibreAbout\work\cover.jpg
```
