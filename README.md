# metaFinder

License: GNU General Public License v3.0

`metaFinder` 把目前整理 Calibre 書庫時使用的 metadata 查找邏輯抽成獨立 Python 工具。

它做的事：

- 以書名、作者或 ISBN 查找候選資料頁。
- 優先找官方或主要書店/平台來源。
- 解析書名、作者、譯者、出版社、出版日、ISBN/eISBN、簡介、標籤、封面 URL。
- 從常見書名格式解析系列名稱與集數，例如 `～系列之三`、`PART9`、`NO.4`。
- 使用 `D:\github\zhTranslate` 共用轉換層將簡體資料轉成臺灣正體。
- 針對晉江文學城等網路小說頁做站點補丁，清理 `《書名》作者_站名` 這類 SEO 標題並抽取頁面封面。
- 保留多個候選來源與分數，不自動推測 Calibre 的來源欄位。

## 參考來源

- [chihchun/library-helper](https://github.com/chihchun/library-helper)：參考其站點規則集中管理、頁面抽取分層與搜尋出口設計；本專案不是執行時相依。

## 安裝

建議使用 Python 3.10 以上。這個專案目前沒有綁定 Calibre DB，只負責查 metadata 候選。

### 一般安裝

```powershell
cd D:\project\metaFinder
python -m pip install -e .
```

這會安裝本專案所需相依。簡轉正會優先引用 `D:\github\zhTranslate`；若尚未安裝 `zhTranslate`，程式會嘗試從 `D:\github\zhTranslate\src` 載入。

### 直接從原始碼執行

```powershell
$env:PYTHONPATH="D:\project\metaFinder\src"
python -m metafinder.cli search "9786263151758"
```

如果你已經安裝過一次，之後只是改 Python 程式碼，通常不用重裝。
如果有改到 `pyproject.toml` 的依賴，建議再跑一次 `python -m pip install -e .`。

### 匯入自訂詞

如果你已經整理好 `原詞<TAB>翻譯` 的 txt 或 tsv，可以直接匯入到 `zhTranslate` 的共用替換檔：

```powershell
metafinder-import-replacements D:\path\to\your_words.txt
```

預設會更新 `[D:\github\zhTranslate\src\s2tw_converter\custom_replacements.tsv](D:/github/zhTranslate/src/s2tw_converter/custom_replacements.tsv)`。
你也可以一次丟多個檔案，後面的檔案會覆寫前面的同名詞條。

## 執行方式

### 以 ISBN 查詢

ISBN 是最穩定的查詢方式。若候選中有 ISBN 精準命中，工具會只保留命中候選；若沒有任何候選的 `isbn` 或 `eisbn` 精準命中，會回傳空候選，避免混入無關搜尋結果。

```powershell
metafinder search "9786263151758"
metafinder search "9786263151758" --json
```

ISBN 查詢會優先用 ISBN 本身與主要書店/出版社/圖書館來源搜尋，包含博客來、Readmoo、皇冠文化、城邦讀書花園、誠品、Anobii、Google Books 與圖書館來源；不會再展開成大量書名/作者或網路小說提示查詢，避免外部搜尋引擎變慢時整批卡住。

### 以書名或作者查詢

書名查詢會比較依賴搜尋結果品質。若沒有可靠候選，工具會回傳空結果，而不是硬塞看起來相似但不正確的資料。
如果書名前面帶有 Calibre 系列整理用的集數前綴，搜尋時會保留原查詢並額外嘗試集數模糊變體，例如 `01 86-不存在的戰區 安里アサト` 會同時查 `86-不存在的戰區 安里アサト`、`86-不存在的戰區 1 安里アサト`、`86-不存在的戰區 第1集 安里アサト`、`86-不存在的戰區 vol.1 安里アサト` 等常見寫法。
如果查詢含前置集數，候選排序與相關性檢查會比對候選標題或系列欄位中的集數；明顯不同集數會被排除，避免整理第 1 集時拿到第 7 集或第 9 集。
前置集數查詢會優先嘗試顯式集數變體，並限制每個變體收集的 URL 數量，避免原始查詢先塞滿結果上限。

```powershell
python -m metafinder.cli search "S級保鏢 多笑天"
python -m metafinder.cli search "迷宮飯 14" --limit 5
```

### 直接解析指定網址

如果已經知道來源頁，直接給 URL 最穩。這會跳過搜尋階段，直接解析該頁。

```powershell
python -m metafinder.cli search "https://ixdzs8.com/read/236949/" --json
python -m metafinder.cli search "https://www.jjwxc.net/onebook.php?novelid=7370132" --json
```

### 下載最佳候選封面

`--download-cover` 會下載分數最高且有 `cover_url` 的候選封面。下載前仍建議先看 JSON 或表格輸出確認候選是否正確。

```powershell
metafinder search "9786263151758" --download-cover D:\project\CalibreAbout\work\cover.jpg
```

### 搜尋逾時與效能

預設搜尋有時間預算，避免外部搜尋或書店頁面卡住時拖慢 Calibre 整理流程：

- 單一 HTTP 請求逾時：`3` 秒。
- 整體候選收集與解析時間預算：`12` 秒。
- 公開搜尋引擎 query 變體上限：`4` 組。
- 若 DuckDuckGo 暫時逾時或拒絕連線，會繼續嘗試 Bing，不會直接讓該 query 整體失敗。
- 站內搜尋會限制先收集的 URL 數量，也只使用最有價值的前幾個集數變體，避免把時間都花在收 URL，讓候選頁沒有時間解析。
- ISBN 查詢會先嘗試 Open Library 輔助候選；這主要用於外文書 ISBN，在華文書店查不到時提供基本書名、作者、出版社與封面參考。

可視情況調整：

```powershell
metafinder search "9789863842590" --json --request-timeout 2 --max-search-seconds 8 --max-web-queries 3
```

若仍查不到，工具會回傳空候選或 exit code `1`，整理流程應記錄 `No candidates found` 或具體逾時原因，再改用可信來源人工核對。

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
地區標籤用來描述作者或作品來源，不會從出版社名稱推導；例如臺灣代理出版的日本輕小說不會只因出版社是臺灣公司就標成 `臺灣`。
當查詢同時包含完整書名與作者時，完整命中書名與作者的候選會優先於只命中部分泛詞的候選。
當查詢同時包含書名與作者時，不能只因作者命中就接受候選；候選必須至少命中一個書名核心詞，避免同作者不同作品被誤收。
部分來源會把頁面標題寫成 `書名 - 作者`；比對書名核心詞時會先移除尾端作者，避免作者詞被誤算成標題命中。
如果多詞查詢只命中單一泛詞，工具會把它視為不可靠候選並排除；這時應記錄為 `No candidates found`，再由整理流程進行人工驗證。
當查詢是正體中文時，搜尋階段會另外嘗試簡體中文查詢變體，避免晉江等以簡體標題建立索引的官方作品頁漏收。
當查詢書名前面有明確集數前綴時，搜尋階段也會嘗試集數模糊變體，支援 `01 書名`、`第2集 書名`、`（03）書名` 等格式，並展開成 `書名 2`、`書名 第2集`、`書名 第二集`、`書名 vol.2`、`書名（2）` 等有限查詢；但不會把 `5.18光州` 這類日期或事件型書名誤切。
候選相關性比對也會使用正體 / 簡體查詢變體，所以正體查詢可接受簡體官方頁的書名與作者，例如 `女神的煩惱 林綿綿` 可命中 `女神的烦恼 / 林绵绵`。
針對晉江等網路小說頁常見的 `《書名》作者_站名` 標題格式，工具會抽取書名號中的核心書名輔助排序。
對晉江作品會額外嘗試 `晉江文學城`、`晋江文学城` 與 `jjwxc` 查詢提示，並辨識 `onebook.php?novelid=`、`m.jjwxc.net/book2/`、`wap.jjwxc.net/book2/` 這類官方作品頁 URL。
對番茄小說作品頁會辨識 `fanqienovel.com/page/<id>`，並從頁面可見欄位抽取書名、作者、類型標籤、最新更新時間與簡介。
對疑似番茄小說作品，也會額外嘗試 `番茄小說`、`番茄小说` 與 `fanqienovel` 查詢提示，優先找官方作品頁而不是鏡像站。
對 QQ 閱讀 `ubook.reader.qq.com/book-detail/` 與起點中文網 `qidian.com/book/` 會辨識為網文來源；若搜尋入口是動態或反爬頁，工具不會硬解析熱門推薦，以免誤收。
對 Anobii 這類讀者目錄頁，只把它當輔助來源；若頁面回傳通用登入/歡迎標題，工具會從 URL 抽 ISBN，但不把通用頁標題寫成書名。
博客來站內搜尋頁若回傳 `redirect/move/.../item/<產品編號>/...`，工具會轉成標準產品頁再解析。
公開搜尋命中未知網域時，若頁面只有標題、沒有作者、出版社、ISBN 或封面等 metadata 證據，會被視為低證據候選並排除；動畫播放頁與 Wikipedia 不會自動當成書籍 metadata 候選，但使用者直接貼 URL 時仍可作為人工查證來源。

## 輸出欄位

每個候選會包含：

- `source_name`：解析到的來源名稱，例如 `Readmoo`、`博客來`、`青文出版社`。
- `source_url`：實際查證頁網址。
- `source_kind`：來源類型，例如 `publisher`、`store`、`government`、`web-novel`。
- `score`：候選排序分數，只用來排序，不代表絕對正確。
- `evidence`：解析依據，例如 `meta-tags`、`json-ld`、`visible-labels`。
- `cover_url`：若候選頁有找到封面，會在候選頂層直接輸出封面 URL，方便批次腳本取用。
- `metadata.title`：書名。
- `metadata.authors`：作者清單。
- `metadata.translators`：譯者清單。
- `metadata.publisher`：出版社。
- `metadata.published_date`：來源頁日期字串。
- `metadata.isbn` / `metadata.eisbn`：紙本 ISBN / 電子 ISBN。
- `metadata.series` / `metadata.series_index`：從來源標題或頁面書名推得的系列名稱與集數；這是候選值，寫入 Calibre 前仍需核對。
- `metadata.description`：簡介。
- `metadata.tags`：短標籤候選。
- `metadata.awards`：只在目前來源頁本身是可信得獎紀錄時輸出，包含 `name`、`status`、`international`、`evidence`、`source_name`、`source_url`。
- `metadata.cover_url`：封面 URL，內容與頂層 `cover_url` 相同。

## Calibre 慣例

- 不會自動填 Calibre 的來源 custom column。
- 作者名稱會盡量維持官方中文名；若頁面只有外文名，就保留來源拼法。
- metadata 候選輸出的 `source_url` 只是查證來源，不等同 Calibre `來源` 欄位。
- 標籤推論不會因書店頁面導覽或活動文案出現裸字 `BL` 就標為 `BL`；只有 `BL小說`、`BL漫畫`、`耽美` 或 `boy's love` 這類明確類型文字才會觸發。
- 出版日輸出為頁面日期字串，寫入 Calibre DB 時仍需依書庫慣例轉 UTC。

## 注意事項

- 這是查找工具，不會修改 Calibre DB、EPUB 或封面檔。
- 書名查詢可能找不到資料，尤其是網路小說、冷門書、下架書或搜尋引擎暫時擋爬時。
- 找不到候選時，CLI 會顯示 `No candidates found.` 並以 exit code `1` 結束。
- 直接 URL 解析比關鍵字搜尋可靠；整理書庫時若已知來源頁，優先貼 URL。
- `source_url` 是查證用來源，不要拿來自動填 Calibre 的 `來源` custom column。
- `series` / `series_index` 只從明確格式解析，例如 `～鳳凰奇俠之五`、`【小肥肥的猛男日記 PART9】`、`City Hunter NO.4`；不會從模糊簡介或人物關係臆測系列。
- 系列證據有優先序：明確嵌在書名中的系列標記最高，作品表/來源頁系列欄位其次；單純上下冊或尾端數字只作弱證據，避免把單本書名本體誤判成系列名。
- `published_date` 沒有自動轉 UTC；寫入 Calibre 時要依書庫慣例處理時區。
- `score` 只是排序輔助；高分候選仍可能是同名書或搜尋頁推薦項，使用前要人工確認。
- 封面 URL 可能是低解析、站方占位圖或 R18 占位圖；換封面前要先看圖。
- 有些站台會回 403、空搜尋頁或動態載入內容，這種情況工具會跳過該候選。
- 簡轉繁使用 `D:\github\zhTranslate`；如果共用轉換層不可用，metadata 正規化會保留原文字，避免查找流程中斷。
- 標籤與獎項是輔助判斷，不會直接修改 Calibre；寫入前仍要檢查候選是否合理。

## 擴充詞庫

簡轉正詞庫集中維護於 `D:\github\zhTranslate`，`metaFinder` 不再自行維護主要自訂詞表。

如果未來只需要修少數詞彙，請直接補到：

```text
D:\github\zhTranslate\src\s2tw_converter\custom_replacements.tsv
```

或使用：

```powershell
metafinder-import-replacements D:\path\to\your_words.txt
```

`zhTranslate` 會在 OpenCC 轉換前後各套用一次自訂替換，所以簡體 key 與正體 key 都能命中。

如果真的需要擴充成一整套自訂詞庫，因為這個套件本身沒有提供自訂字典路徑參數，做法通常是：

1. 把 `opencc` 原始碼與字典檔 fork 到 `D:\github\zhTranslate`。
2. 在 fork 版本的 `config/*.json` 和 `dictionary/*.txt` 裡加入你的詞條。
3. 讓 `zhTranslate` 改用那份本地 `opencc` 實作，而不是外部套件。

也就是說，少量修正常用「`zhTranslate` 共用覆寫」，大量詞庫維護才考慮「vendor 一份本地 OpenCC」。

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
- 常見系列標題格式會解析為 `metadata.series` / `metadata.series_index`：
  - `巧玉玲瓏～鳳凰奇俠之五` -> `鳳凰奇俠 #5`
  - `寶貝大猛男(下)【小肥肥的猛男日記 PART9】` -> `小肥肥的猛男日記 #9`
  - `木頭猛男追新娘～City Hunter NO.4` -> `City Hunter #4`
  - `黑魔王傳說 Part 2` -> `黑魔王傳說 #2`
- 系列候選衝突時，`series_evidence_priority()` 會讓可靠證據優先：
  - `【小肥肥的猛男日記 PART9】` 這種明確系列資訊高於外部資料。
  - 外部作品表系列欄位高於單純 `(上)/(下)` 或尾端集數拆法。
  - `溫馨` 這類常見分類字樣會被視為較弱證據，不覆蓋明確書名系列。
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
  - 地區標籤不可從任意簡介地名推論；例如故事舞台提到美國、英國、義大利，不代表作者地區標籤要加入這些國家。
  - 地區標籤只應來自明確作者國籍/地區、來源分類、既有可信 metadata，或整理者已確認的資料。
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
