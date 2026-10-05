# PredictMP_GeneExprPredict-Web

以 Streamlit 建立的網頁工具，提供兩個分析：

| 頁面 | 輸入 | 做什麼 |
|---|---|---|
| **📊 PredictMP Analysis** | PrediXcan 預測結果（`*_predicted_expression.txt`） | 用 PredictMP 把每個人每個基因的預測表現量，對 gnomAD v4.1 九個族群的模擬參考分布算 percentile rank，並附 KS test（vs NFE）結果 |
| **🧬 GA-Calibrated Gene Expression Prediction** | VCF 基因型檔 | 用 GA 校正後（或原始 PrediXcan）的權重，直接從基因型預測基因表現量，並給每個基因 QC 狀態 |
| **🔒 Privacy & Data Retention** | — | 給使用者看的隱私與資料保存說明 |

## 目錄

```
PredictMP_GeneExprPredict-Web/
├── app/                        Streamlit 程式（以 volume 掛進容器，改了重新整理頁面就生效）
│   ├── main.py                 入口：側邊欄導覽 + 資料保存提示
│   ├── pages/
│   │   ├── predictmp_analysis.py
│   │   ├── ga_predict.py
│   │   └── privacy.py
│   └── core/                   計算與儲存邏輯（不 import streamlit，之後換前端可以直接沿用）
│       ├── tissues.py          49 個 GTEx 組織代碼 x1–x49、9 個族群
│       ├── storage.py          Session UUID 資料夾、UUID 格式檢查、過期自動刪除
│       ├── ga_pipeline.py      VCF → plink2 dosage → 預測 → 輸出檔
│       └── ga_predict.py       權重 × dosage 的預測與 QC summary（也可單獨當 CLI 用）
├── wheels/                     PredictMP 套件安裝檔（.whl）
├── tools/
│   ├── upload_data.sh          把參考資料和 GA 權重上傳到 Google Drive（部署到另一台主機用）
│   └── measure_upload.py       在自己電腦上量測上傳 / 預測時間的工具（不進 image）
├── sample_data/                測試用 VCF
├── Dockerfile, docker-compose.yml, entrypoint.sh, requirements.txt
├── .env.example                設定範本（複製成 .env 後修改）
└── .streamlit/config.toml
```

## 架設

### 1. 準備 PredictMP 套件（wheel）

wheel（`.whl`）是 Python 套件的安裝檔。建 image 時會用 `pip install` 把它裝進容器，網站就不必再去讀主機上的套件資料夾。

PredictMP 的原始碼在 `PredictMP/code/PredictMP_pkg/`。**只有改了套件程式**才需要重新打包：

```bash
cd /home/betty0101/Project/PredictMP/code/PredictMP_pkg
rm -f /home/betty0101/Project/PredictMP_GeneExprPredict-Web/wheels/predictmp-*.whl
pip wheel --no-deps -w /home/betty0101/Project/PredictMP_GeneExprPredict-Web/wheels .
```

wheel 只包含程式碼（約 6 KB）。參考資料（`data/tissue/` 約 12 GB）**不打包**，改用 volume 掛進容器，見下一步。

### 2. 設定 `.env`

```bash
cp .env.example .env     # 再依實際路徑修改
```

| 變數 | 說明 |
|---|---|
| `PREDICTMP_WEB_PORT` | 主機上的 port（只綁 127.0.0.1，對外請用 nginx 反向代理） |
| `PREDICTMP_REFERENCE_DATA_HOST_PATH` | PredictMP 參考資料所在的主機資料夾，裡面要有 `tissue/`、`result_table/`、`ks/`（由 `PredictMP/code/08_build_package_data.py` 產生） |
| `PREDICTMP_DATA_DIR` | 容器內參考資料的位置。PredictMP 套件會讀這個變數，**名稱不要改** |
| `RESULTS_DIR` | 容器內存放上傳檔與結果的位置（Docker volume `predictmp_geneexprpredict-web_session_results`） |
| `RESULTS_RETENTION_DAYS` | 結果保存天數，預設 7 |
| `GA_WEIGHTS_DB_HOST_PATH` | GA 權重資料庫所在的主機資料夾 |
| `GA_WEIGHTS_DB_PATH` | 「Original PrediXcan Weight」使用的資料庫（容器內路徑） |
| `GA_WEIGHT_COLUMN`、`PLINK2_CMD` | 權重欄位預設值、plink2 指令 |
| `STREAMLIT_MAX_UPLOAD_MB` | 上傳大小上限（MB） |
| `PREDICTMP_UID`、`PREDICTMP_GID` | 容器執行時的使用者（主機上 `id` 的結果）。不用 root：公開網站比較安全，也才能讀 NFS 上的資料 |

### 3. 啟動

```bash
cd /home/betty0101/Project/PredictMP_GeneExprPredict-Web
docker compose up -d --build
# 本機打開 http://127.0.0.1:8503
```

| 情況 | 指令 |
|---|---|
| 只改了 `app/` 的程式 | 不用做任何事，重新整理網頁即可 |
| 改了 `.env` | `docker compose up -d --force-recreate` |
| 換了 wheel、`requirements.txt`、`Dockerfile`、`entrypoint.sh` | `docker compose up -d --build` |
| 重建了 PredictMP 參考資料（08） | `docker compose restart`（清掉套件的記憶體快取） |
| 看 log | `docker compose logs -f predictmp_geneexprpredict-web` |
| 停止 | `docker compose down` |

## 部署到另一台主機

兩台主機在不同 VPN、彼此連不到時，用 Google Drive 當中繼：這台上傳，新主機下載。

| 東西 | 怎麼到新主機 |
|---|---|
| 網站程式（含 PredictMP wheel） | GitHub：`git clone` |
| Docker image | 不傳，新主機用 `docker compose up -d --build` 自己 build（需要能上網） |
| PredictMP 參考資料（約 12 GB）、GA 權重（約 105 MB） | Google Drive + rclone |
| `.env` | 不傳，在新主機依 `.env.example` 重寫 |
| 使用者的 session 結果 | 不傳 |

### 1. 設定 rclone 的 Google Drive（兩台主機各做一次）

伺服器沒有瀏覽器，授權要借用有瀏覽器的電腦：

1. 在**有瀏覽器的電腦**安裝 rclone（<https://rclone.org/downloads/>），執行 `rclone authorize "drive"`，登入 Google 後，終端機會印出一段 token（`{"access_token":...}`）。
2. 在**伺服器**執行 `rclone config`：
   - `n`（New remote）→ name 輸入 `gdrive` → storage 選 `drive`
   - `client_id`、`client_secret` 直接 Enter → scope 選 `1`（Full access）→ 其餘 Enter
   - `Use web browser to automatically authenticate?` 選 **`n`**，貼上第 1 步的 token
   - `Configure this as a Shared Drive?` 選 `n` → `y` 儲存
3. 測試：`rclone lsd gdrive:`

### 2. 這台主機：上傳

```bash
bash tools/upload_data.sh gdrive:PredictMP_GeneExprPredict-Web
```

雲端上的配置：

| 位置 | 內容 |
|---|---|
| `reference_data/ks/`、`reference_data/result_table/` | 小檔案，逐檔上傳 |
| `reference_data_tar/tissue_<pop>.tar` | 每個族群 49 個 tissue parquet 包成一個 tar（約 1.3 GB） |
| `ga_weights/` | 6 個 GA 權重 `.db` |

tissue 打包上傳的原因：Google Drive 處理大量中小檔案很慢（約 1 MB/s），大檔則有約 20 MB/s。打包是邊讀邊傳，本機不會產生 tar 檔，也不會改動原始檔；每個 tar 傳完會比對 MD5。只更新部分族群時：`POPS="eas nfe" bash tools/upload_data.sh gdrive:PredictMP_GeneExprPredict-Web`。

### 3. 新主機：下載並架設（需要 Docker + Docker Compose）

```bash
DEST=/srv/predictmp
mkdir -p $DEST && cd $DEST
git clone https://github.com/Coco-0101/PredictMP_GeneExprPredict-Web.git
R=gdrive:PredictMP_GeneExprPredict-Web
rclone copy $R/reference_data     $DEST/reference_data --include "ks/**" --include "result_table/**" -P
rclone copy $R/reference_data_tar $DEST/reference_data_tar -P
for f in $DEST/reference_data_tar/tissue_*.tar; do tar -xf "$f" -C $DEST/reference_data; done
ls $DEST/reference_data/tissue | wc -l          # 應該是 441
rm -r $DEST/reference_data_tar                   # 解開後 tar 可以刪掉
rclone copy $R/ga_weights $DEST/ga_weights -P

cd PredictMP_GeneExprPredict-Web
cp .env.example .env
# 修改 .env：
#   PREDICTMP_REFERENCE_DATA_HOST_PATH=/srv/predictmp/reference_data
#   GA_WEIGHTS_DB_HOST_PATH=/srv/predictmp/ga_weights
#   PREDICTMP_UID / PREDICTMP_GID = 新主機上 `id` 的結果（這個使用者要能讀上面兩個資料夾）
docker compose up -d --build
```

參考資料或權重更新時：這台重跑 `upload_data.sh`，新主機重跑上面的下載和解壓，再 `docker compose restart`。

## 資料保存與隱私

- 每次分析都存在容器內的 `/app/session_results/<Session UUID>/`，實際放在 Docker volume `predictmp_geneexprpredict-web_session_results`（本機硬碟，只有 root 讀得到；不放 `/mnt/data_40T`，因為 NFS 上伺服器其他使用者可能讀到上傳的基因資料，容器也會有權限問題）。使用者可以用 UUID 在側邊欄的「Load UUID」重新載入結果。
- 輸入的 UUID 必須是標準格式，否則不接受，避免有人用 `../` 之類的輸入讀取伺服器上的其他檔案。
- `entrypoint.sh` 每小時執行一次 `python -m core.storage`，刪除超過 `RESULTS_RETENTION_DAYS` 天沒有更新的 session 資料夾。手動執行：
  ```bash
  docker compose exec predictmp_geneexprpredict-web python -m core.storage
  ```
- 查看目前存了哪些 session：`docker compose exec predictmp_geneexprpredict-web ls -la /app/session_results`
- 網站側邊欄有保存期限提示，**Privacy & Data Retention** 頁面有完整說明。改了保存天數，說明會跟著變。

## PredictMP Analysis

1. 上傳 PrediXcan 的預測結果（tab 分隔的 `.txt`，或逗號分隔的 `.csv`），欄位是 `FID, IID, ENSG...`。
2. 選組織和參考族群（AFR、AMI、AMR、ASJ、EAS、FIN、MID、NFE、SAS），按 **Run PredictMP**。
3. 結果可以依受試者或基因篩選，下載完整 CSV。

| 欄位 | 說明 |
|---|---|
| `FID`, `IID` | 使用者資料的 ID |
| `gene` | Ensembl gene ID |
| `expression` | 使用者的預測表現量 |
| `percentile.rank` | 在參考族群分布中的百分位（0–100） |
| `N.snps` | 這個基因模型用到的 SNP 數 |
| `mean`, `sd` | 參考族群的平均與標準差 |
| `ks.test` | 該族群與 NFE 參考分布的 KS test 是否顯著（`Sig.` / `Nonsig.`，門檻 5e-8；選 NFE 時沒有這欄） |
| `NFE.{POP}.mean.diff` | NFE 與所選族群的平均差異（%） |

參考資料怎麼產生，請見 `PredictMP/code/README.md`。

## GA-Calibrated Gene Expression Prediction

### VCF 格式

- VCF 4.0 以上，`GT` 欄位。
- **ID 欄必須是 rsid**（例如 `rs1000068`）。不能是 `chr:pos`，也不能是 `.`。可以用 bcftools 補上：
  ```bash
  bcftools annotate -c ID -a dbSNP.vcf.gz input.vcf.gz -Oz -o output_rsid.vcf.gz
  ```

### 權重選擇

| 選項 | 使用的資料庫 |
|---|---|
| GA-Calibrated Weights → Sign-flipped（建議） | `V4_LOOCV_Sign_weights.db` |
| GA-Calibrated Weights → Unsigned | `V4_LOOCV_Unsign_weights.db` |
| Original PrediXcan Weight | `.env` 的 `GA_WEIGHTS_DB_PATH` |

### 流程

```
VCF → [1] 從權重資料庫取出要用的 SNP → [2] plink2 算 dosage
    → [3] 檢查 allele 方向（counted allele ≠ effect allele 時用 2 − dosage）
    → [4] 預測表現量 = Σ weight × dosage → [5] 每個基因的 QC summary
```

上傳完成後預設會自動開始預測（可以在側邊欄關掉）。

### 輸出

**`ga_predicted_expression.csv`**：一列一個樣本，欄位是 `FID, IID, <gene...>`。數值是原始尺度，下游分析前建議先標準化（z-score）。

**`ga_summary.csv`**：一列一個基因。

| 欄位 | 說明 |
|---|---|
| `n_snps_in_model` | 模型中權重非 0 的 SNP 數 |
| `n_snps_used` | VCF 裡實際找到的 SNP 數 |
| `pct_snps_used` | `n_snps_used / n_snps_in_model` |
| `pred_mean`, `pred_sd`, `var_g` | 這批樣本預測值的平均、標準差、變異數 |
| `status` | QC 狀態，見下表 |

| `status` | 網頁顯示 | 意思 | 建議 |
|---|---|---|---|
| `OK` | PASS | SNP 覆蓋率 ≥ 50% | 可以使用 |
| `LOW_SNP_COVERAGE` | WARNING | SNP 覆蓋率 < 50% | 謹慎使用 |
| `NO_SNPS_IN_VCF` | NO_DATA | VCF 裡找不到模型的 SNP | 無法預測 |
| `NO_MODEL_SNPS` | FILTERED | GA 階段把這個基因的權重都刪光了 | 無法預測 |
| `ZERO_VARIANCE` | NO_VARIANCE | 所有樣本的預測值都一樣 | 不要使用 |

下游分析一般先留 `status == "OK"` 的基因，標準化後再做關聯分析。

### 常見問題

- **大多數基因 `n_snps_used = 0`**：VCF 的 ID 不是 rsid，用上面的 bcftools 指令補上。
- **上傳太慢**：先用 `bgzip` 壓縮成 `.vcf.gz`。
- **單獨用 CLI 跑預測**（已經有 plink2 `--export A` 的 `.raw` 檔時）：
  ```bash
  python app/core/ga_predict.py --dosage_raw dosage.raw --weights_db V4_LOOCV_Sign_weights.db --out_prefix ga
  ```

## 量測工具：`tools/measure_upload.py`

在**自己的電腦**（例如 Windows）上執行，用真的瀏覽器上傳 VCF，量測上傳時間，也可以一起量預測時間。不會打包進 image。

```powershell
pip install playwright
playwright install chromium

python tools/measure_upload.py --url http://<server>:8503 --file "C:\path\to\big.vcf.gz"
python tools/measure_upload.py --url http://<server>:8503 --file "C:\path\to\big.vcf.gz" --wait-predict   # 連預測一起量
python tools/measure_upload.py --url http://<server>:8503 --file "C:\path\to\big.vcf.gz" --headless       # 不開視窗
```

每次執行會在腳本旁的 `upload_log.csv` 加一列（時間、檔案大小、Session UUID、上傳秒數、預測秒數、狀態），可以用 `--log-file` 改位置。
這個工具是靠頁面標題「GA-Calibrated Gene Expression Prediction」切換頁面的，改頁面標題時要一起改。
