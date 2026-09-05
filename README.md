# TPE-NRT 全服務航空機票價格追蹤

每天自動查「台北桃園(TPE) <-> 成田(NRT) 來回直飛」，追蹤**兩組**行程日期：

| 組合 | 去程 | 回程 |
|---|---|---|
| A | 2026-12-17 | 2026-12-23 |
| B | 2026-12-16 | 2026-12-22 |

篩選全服務航空（華航、長榮、日航、全日空、星宇、國泰；**排除廉航**），
結果寫進 `data/price_history.csv`。

## 時段偏好

`in_time_window` 欄位標記是否符合以下偏好（`[起, 迄)`，迄不含）：

- **去程**：抵達成田 **12:00–18:00**
- **回程**：抵達桃園 **23:00–24:00**

不符合的班次仍會被記錄（標 `FALSE`），方便比價，不會被丟掉。

## ⚠️ 兩個資料限制（很重要）

1. **回程資料來自另一次「單程」查詢。** Google Flights 的來回搜尋結果頁只列出
   *去程* 選項，回程時間這層抓不到（見 `fast_flights` 的 `parse_response`）。
   所以腳本對每組日期跑兩次查詢：來回查詢取去程（`price_type=round_trip`，
   價格是**來回總價**），單程查詢取回程（`price_type=one_way`，價格是**單程價**）。
   **回程那列的價格不能跟去程相加**，它只是用來確認班表與時段。
2. **拿不到「指定去程＋指定回程」這組合的來回票價。** 來回總價是掛在去程航班上的，
   系統配的回程不一定是你要的那班。實際金額請點 `booking_url` 進去確認。

## ⚠️ 第一次跑完務必手動核對

`price` 欄位（`price_type=round_trip` 那些列）是根據「Google Flights 來回搜尋結果頁
顯示的是去程航班清單 + 已含回程的來回總價」這個假設寫的。麻煩自己上 Google Flights
網頁用同樣的日期/機場/航空公司查一次，確認 CSV 裡的價格跟網頁上的來回總價對得起來。
如果對不上，回報給我，需要調整解析邏輯。

## CSV 欄位說明

| 欄位 | 意義 |
|---|---|
| `query_date` | 執行這次查詢的日期（今天），用來畫「同一航班隨時間價格變化」的走勢 |
| `outbound_date` / `return_date` | 這列屬於哪一組行程日期（見上方 A／B 表） |
| `leg` | `outbound`（去程 TPE→NRT）或 `return`（回程 NRT→TPE） |
| `airline` | 航空公司名稱 |
| `departure` / `arrival` | **這一段**的起飛／抵達當地時間 |
| `duration` | 飛行時長 |
| `stops` | 轉機次數，本專案固定只查 `0`（直飛） |
| `price` | 價格。搭配 `price_type` 解讀 |
| `price_type` | `round_trip`＝來回總價（只出現在 `leg=outbound`）；`one_way`＝單程價（只出現在 `leg=return`）。**兩者不可相加** |
| `in_time_window` | 是否符合你的時段偏好（去程抵達 12:00–18:00／回程抵達 23:00–24:00） |
| `is_best` | Google Flights 演算法標記的推薦選項。注意它是照**價格與總時長**挑的，**不會考慮你的時段偏好** — 要找符合時段的班次請看 `in_time_window` |
| `current_price_level` | Google Flights 對這次查詢整體價格水位的評語，通常是 `low`/`typical`/`high` |
| `booking_url` | 還原「產生這列的那次搜尋」的 Google Flights 深連結。去程列＝來回搜尋連結（可直接訂），回程列＝單程搜尋連結（對應它的單程價）。這是**搜尋層級**連結，不是跳到單一航班訂票頁——這個爬蟲抓不到各航班的專屬網址 |

## 每次執行的查詢次數

每組日期要跑 2 次查詢（來回 + 單程回程），共 **4 次**（原本是 2 次）。
查詢之間會間隔 `QUERY_DELAY_SECONDS`（預設 10 秒）降低被判定為機器人流量的風險，
所以一次執行約多花 30 秒。Actions 若開始失敗，先往「查詢次數變多被擋」這個方向查，
必要時調高間隔或減少 `DATE_COMBOS`。

## 歷史資料

`data/price_history.csv` 的欄位結構在導入時段偏好時改過，舊資料無法沿用，
已封存於 `data/archive/`：

| 檔案 | 內容 |
|---|---|
| `price_history_2026-1217_ret1222-1223.csv` | 舊結構，去程固定 12/17、回程 12/22 與 12/23，累積到 2026-09-05 |

舊檔的來回價與新的 12/16 出發組合不可直接比較（行程不同），僅供參考趨勢。

## 先在本機測試一次（強烈建議）

```
pip install -r requirements.txt
playwright install chromium
python track_flight_prices.py
```

`playwright install chromium` 只需執行一次，會下載約 300MB 的瀏覽器執行檔到你電腦上。
如果這步驟成功、`data/price_history.csv` 有正常寫入資料，再進行下面的部署步驟。

## 部署步驟

1. 在 GitHub 建一個新的**空 repository**（public 或 private 都可以）。
2. 把這個資料夾裡的所有檔案（含 `.github/workflows/track-flights.yml`）推上去：
   ```bash
   git init
   git add .
   git commit -m "init flight price tracker"
   git branch -M main
   git remote add origin <你的 repo URL>
   git push -u origin main
   ```
3. 到 repo 的 **Settings → Actions → General → Workflow permissions**，
   選擇 **Read and write permissions**，儲存。
   （沒開這個，Actions 會因為沒有寫入權限而 push 失敗。）
4. 到 **Actions** 分頁，選 `Track TPE-NRT Flight Prices` → **Run workflow**，
   手動跑一次確認能成功查價、寫入 CSV。
5. 之後就會照 cron 設定（台灣時間每天 09:00）自動執行，結果會累積在
   `data/price_history.csv`，可以直接在 GitHub 網頁上看，或 clone 下來用
   Excel／Numbers 打開畫趨勢圖。

## 想改查詢條件

打開 `track_flight_prices.py` 最上面幾個變數：

| 變數 | 說明 |
|---|---|
| `DATE_COMBOS` | 要追蹤的 `(去程日, 回程日)` 組合，可增減幾組就查幾組（每組 2 次查詢） |
| `OUTBOUND_ARRIVAL_WINDOW` | 去程抵達偏好時段，單位是「距午夜的分鐘數」的 `(起, 迄)`，迄不含。例：`(12*60, 18*60)` = 12:00–18:00 |
| `RETURN_ARRIVAL_WINDOW` | 回程抵達偏好時段，格式同上 |
| `FROM_AIRPORT` / `TO_AIRPORT` | 出發／目的地機場代碼 |
| `SEAT` | 艙等 |
| `PASSENGERS` | 人數 |
| `MAX_STOPS` | 轉機次數上限，`0` = 只要直飛 |
| `AIRLINE_WHITELIST` | 航空白名單關鍵字（目前為全服務航空，不含廉航），依需求增減 |

## 已知限制（跑之前先知道）

- 這是逆向工程 Google Flights 的非官方爬蟲（`fast-flights` 套件），不是官方 API，
  Google 前端一改版就可能失效，需要留意 Actions 執行紀錄，失敗了要去看
  [套件的 GitHub issues](https://github.com/AWeirdDev/flights/issues) 有沒有更新。
  這個套件 PyPI 最新穩定版停在 2025/3，作者原本內建的代管 fallback 服務目前已
  故障（回傳 401 no token provided），所以改用 `fetch_mode="local"` 繞開它，
  改吃你自己（或 CI runner）跑的 Playwright 瀏覽器。
- 價格幣別由查詢來源 IP 的地區決定。本機在台灣執行通常會顯示台幣，但 GitHub
  Actions runner 在美國，**第一次在 CI 上跑完務必人工檢查 CSV 裡的幣別**，
  很可能不是台幣。
- 航空公司篩選是用名稱關鍵字比對，代碼共享航班可能顯示成別的名稱而被漏掉，
  建議跑個幾天後人工核對一次結果有沒有漏掉你想追蹤的航空公司。
- 個人查詢用途風險低，但這仍是爬蟲行為，不建議拿來做高頻率或商業用途查詢。
- 如果 local 模式在 GitHub Actions 上也持續失敗（例如 Google 對資料中心 IP
  做了更嚴格的封鎖），代表這個免費方案的可靠度到頂了，屆時可考慮改用付費的
  Google Flights 資料服務（例如 SerpApi），穩定性會好很多，但要收費。
