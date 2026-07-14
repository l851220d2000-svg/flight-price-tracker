# TPE-NRT 傳統航空機票價格追蹤

每天自動查一次「台北桃園(TPE) <-> 成田(NRT) 來回」（去程 2026-12-17／回程 2026-12-22），
篩選出傳統航空（華航、長榮、日航、全日空），把來回票總價附加寫進 `data/price_history.csv`。

## ⚠️ 第一次跑完務必手動核對

這個 CSV 的 `round_trip_price` 欄位是根據「Google Flights 來回搜尋結果頁顯示的是
去程航班清單 + 已含回程的來回總價」這個假設寫的，**我沒有實際連線測試過**（見腳本
開頭註解）。你第一次跑出資料後，麻煩自己上 Google Flights 網頁用同樣的日期/機場/
航空公司查一次，確認 CSV 裡的價格跟網頁上的來回總價對得起來。如果對不上，回報給我，
需要調整解析邏輯。

## CSV 欄位說明

| 欄位 | 意義 |
|---|---|
| `query_date` | 執行這次查詢的日期（今天），用來畫「同一航班隨時間價格變化」的走勢 |
| `airline` | 航空公司名稱 |
| `outbound_departure` / `outbound_arrival` | **去程**那一段的起飛／抵達時間（回程細節這層資料抓不到） |
| `outbound_duration` | 去程飛行時長 |
| `outbound_stops` | 去程轉機次數，`0` 為直飛 |
| `round_trip_price` | 來回票總價（幣別依查詢當下地區而定，見下方限制） |
| `is_best` | Google Flights 演算法標記的推薦選項 |
| `current_price_level` | Google Flights 對這次查詢整體價格水位的評語，通常是 `low`/`typical`/`high` |

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
| `OUTBOUND_DATE` / `RETURN_DATE` | 去程／回程日期 |
| `FROM_AIRPORT` / `TO_AIRPORT` | 出發／目的地機場代碼 |
| `SEAT` | 艙等 |
| `PASSENGERS` | 人數 |
| `TRADITIONAL_AIRLINES` | 傳統航空白名單關鍵字，依需求增減 |

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
