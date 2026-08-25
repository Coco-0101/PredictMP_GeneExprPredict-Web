# 🧬 GA-Calibrated Gene Expression Prediction Web UI

> **Language / 語言**: [English](#english) | [繁體中文](#繁體中文)

---

## English

### Overview

A web-based tool for predicting gene expression using **GA-calibrated weights** from genotype VCF files. The application integrates:

- **VCF Upload Interface**: Simple drag-and-drop support
- **Weight Selection**: Choose between GA-Calibrated or Original PrediXcan weights
- **Real-time Processing**: Progress tracking with three pipeline stages
- **Result Visualization**: Summary metrics, QC distribution, detailed tables
- **CSV Download**: Export predicted expression and QC summary

### Quick Start

```bash
cd /home/betty0101/Predixcan_materials/PredictAP_WebUI
docker compose up -d
# Open http://127.0.0.1:8503
```

Navigate to: **🧬 GA-Calibrated Gene Expression Prediction** in the sidebar

### System Requirements

- Docker & Docker Compose
- 4GB+ RAM
- Network access (if using remote databases)
- Storage for results (save_tmp/)

### Key Features

✅ **GA-Calibrated Weights** - GA-optimized prediction models  
✅ **Original PrediXcan Weights** - Standard prediction weights  
✅ **Real-time Progress** - Three-stage processing pipeline  
✅ **QC Metrics** - Per-gene SNP coverage & variance statistics  
✅ **Status Indicators** - Clear prediction quality classification  
✅ **Download Results** - CSV format for downstream analysis  

### Project Structure

```
.
├── app/
│   ├── main.py                          # Navigation entry point
│   ├── pages/
│   │   └── GA_GeneExpression_Predict.py # Main application (UPDATED ✨)
│   └── lib/
│       ├── genexpr_pipeline.py          # Pipeline orchestration
│       └── GeneExpression_Predict.py    # Core prediction logic
├── sample_data/
│   └── test_sample.vcf.gz              # Example VCF file
├── save_tmp/                           # Results storage
├── Dockerfile                          # Container configuration
├── docker-compose.yml                  # Service orchestration
├── requirements.txt                    # Python dependencies
├── .env                               # Environment configuration
├── .env.example                       # Configuration template
└── README_UNIFIED.md                  # This file (NEW ✨)
```

### VCF Input Requirements

**Format Specifications:**
- VCF version: 4.0+
- Variant IDs: **Must be rsids** (e.g., `rs1000068`)
  - ❌ NOT `chr:pos` format
  - ❌ NOT `.` (missing IDs)
- Genotype format: GT (0/1, 1/1, etc.)
- Max file size: 500 MB (configurable via `STREAMLIT_MAX_UPLOAD_MB`)

**Example VCF Header:**
```
##fileformat=VCFv4.2
##contig=<ID=1>
#CHROM  POS   ID        REF ALT QUAL FILTER INFO FORMAT sample1 sample2 sample3
1       1000  rs1000068 A   G   .    .      .    GT     0/0     0/1     1/1
```

**Convert to rsid Format (if needed):**
```bash
# Using bcftools
bcftools annotate -c ID -a dbSNP.vcf.gz input.vcf.gz -Oz -o output_rsid.vcf.gz
gunzip output_rsid.vcf.gz
```

### Usage Workflow

#### Step 1: Prepare VCF
- Ensure variant IDs are rsids
- Check file size (< 500 MB by default)
- Compress if needed: `bgzip genotype.vcf > genotype.vcf.gz`

#### Step 2: Upload & Configure
1. Click **VCF file uploader** → select your file
2. Choose **Weight Type** (sidebar):
   - **GA-Calibrated Weights** → Select database version
   - **Original PrediXcan Weight** → Auto-uses built-in database
3. Click **Run Prediction** button

#### Step 3: Monitor Progress
Watch three processing stages:
- 📊 Extracting SNP list from weights... (10%)
- 📊 Computing SNP dosage with plink2... (30%)
- 📊 Computing predicted expression... (70%)

#### Step 4: Review Results
- **Results Summary**: Samples, predicted genes, PASS/WARNING counts
- **Prediction Status Distribution**: Bar chart of QC status breakdown
- **Detailed Results Tabs**:
  - **Predicted Expression**: Sample × gene expression matrix
  - **Predicted Summary**: Gene-level QC metrics
  - **Prediction Status Reference**: Status code explanations

#### Step 5: Download Results
- **predicted_expression_{timestamp}.csv**: Wide format (samples × genes)
- **predicted_summary_{timestamp}.csv**: Gene-level QC report

### Prediction Status Codes

| Status | Display | Help | Recommendation |
|--------|---------|------|-----------------|
| OK | **PASS** | SNP coverage ≥50%, high confidence | ✓ Use in analysis |
| LOW_SNP_COVERAGE | **WARNING** | SNP coverage <50%, use with caution | ⚠ Use carefully, note coverage |
| NO_SNPS_IN_VCF | **NO_DATA** | No SNPs found in VCF | ✗ Cannot predict |
| NO_MODEL_SNPS | **FILTERED** | Gene pruned in GA stage, no usable weights | ✗ Gene model invalid |
| ZERO_VARIANCE | **NO_VARIANCE** | Predicted values have no variance (no discriminative power) | ✗ Do not use |

### Output Files

#### predicted_expression.csv
```
FID,IID,ENSG00000000971,ENSG00000001167,...
1,sample1,0.1234,-0.5678,...
1,sample2,0.4567,0.1234,...
```
- **Format**: Wide (one row = one sample)
- **Columns**: FID | IID | [gene expression values]
- **Values**: Raw scale (unstandardized)
- **Recommendation**: Standardize before downstream analysis

#### predicted_summary.csv
```
gene,n_snps_in_model,n_snps_used,pct_snps_used,pred_mean,pred_sd,var_g,status
ENSG00000000971,234,180,0.77,0.05,0.32,0.1024,OK
ENSG00000001167,156,78,0.5,0.02,0.18,0.0324,LOW_SNP_COVERAGE
```
- **Format**: One row per gene
- **Key Metrics**:
  - `n_snps_in_model`: SNPs with non-zero weights in GA model
  - `n_snps_used`: SNPs from VCF actually used in prediction
  - `pct_snps_used`: Coverage = n_snps_used / n_snps_in_model
  - `var_g`: Genetic variance (predicted expression variance across samples)
  - `status`: QC status code

**Best Practice**: Filter `status == 'OK'` before downstream analysis

### Standardize Predicted Expression

The output values are in raw scale. Standardize for downstream analysis:

**Python:**
```python
import pandas as pd
import numpy as np

expr = pd.read_csv('predicted_expression_run1.csv', index_col='IID')
expr_z = (expr - expr.mean()) / expr.std()
expr_z.to_csv('predicted_expression_normalized.csv')
```

**R:**
```r
expr <- read.csv('predicted_expression_run1.csv', row.names = 'IID')
expr_z <- scale(expr)
write.csv(expr_z, 'predicted_expression_normalized.csv')
```

### Configuration

Edit `.env` to customize:

| Variable | Default | Description |
|----------|---------|-------------|
| `GA_WEIGHTS_DB_PATH` | `/ga_weights/V4_3Fold_Sign_weights.db` | Weights database path (container) |
| `GA_WEIGHTS_DB_HOST_PATH` | `/mnt/data_40T/anywaycheng/UploadFile/GA/GA_Weight_DataBase` | Weights database path (host) |
| `GA_WEIGHT_COLUMN` | `GA_W` | Weight column name (GA_W or PrediXcan_W) |
| `PLINK2_CMD` | `plink2` | plink2 executable command |
| `SAVE_TMP_DIR` | `/app/save_tmp` | Results storage directory |
| `STREAMLIT_MAX_UPLOAD_MB` | `500` | Max upload file size (MB) |

**Change weights database:**
```bash
# Edit .env
GA_WEIGHTS_DB_PATH=/ga_weights/V4_LOOCV_Sign_weights.db

# Restart service
docker compose up -d --force-recreate
```

### Docker Management

```bash
# Check service status
docker compose ps

# View logs
docker compose logs -f predictap-web

# Restart (code changes)
docker compose restart predictap-web

# Rebuild (dependency changes)
docker compose up --build -d

# Full rebuild (.env changes)
docker compose up --build -d --force-recreate

# Stop service
docker compose down
```

### Recent Updates ✨

**UI/UX Improvements (Latest):**
- ✅ Weight type names: **GA-Calibrated Weights** | **Original PrediXcan Weight**
- ✅ Status codes redesigned with clear labels:
  - `OK` → **PASS** (high confidence)
  - `LOW_SNP_COVERAGE` → **WARNING** (use carefully)
  - `NO_SNPS_IN_VCF` → **NO_DATA** (not found)
  - `NO_MODEL_SNPS` → **FILTERED** (model invalid)
  - `ZERO_VARIANCE` → **NO_VARIANCE** (no discriminative power)
- ✅ Improved configuration flow: Select weight type first, then database
- ✅ PrediXcan weight auto-selects built-in database (no selection needed)
- ✅ Help tooltips on all status codes
- ✅ Results labels: PASS/WARNING counts in summary metrics

### Troubleshooting

**"Cannot upload file"**
- Check file size (< 500 MB default)
- Check browser connection
- Try different browser or private/incognito window

**"Run button is disabled"**
- Upload a VCF file first

**"Prediction results are all zero"**
- Check `predicted_summary.csv` status codes
- If `n_snps_used == 0` for most genes → VCF variant IDs are not rsids
- Use bcftools to convert to rsid format

**"Results take too long"**
- Depends on VCF size and sample count
- Check Docker logs: `docker compose logs -f predictap-web`

**"File too large"**
- Compress: `bgzip genotype.vcf > genotype.vcf.gz`
- Increase `STREAMLIT_MAX_UPLOAD_MB` in `.env`

### FAQ

**Q: Can I use these predictions for S-PrediXcan/GWAS analysis?**  
A: Yes! Typical workflow:
1. Filter genes with `status == 'OK'`
2. Standardize predicted expression (z-score)
3. Test association with phenotype (linear regression)
4. Apply multiple testing correction

**Q: How long does prediction take?**  
A: Depends on VCF size:
- Small (< 100 MB, < 1K samples): seconds to tens of seconds
- Medium (100-500 MB): tens of seconds to minutes
- Large (> 500 MB): minutes to hours

**Q: Where are results stored?**  
A: In `save_tmp/` directory (host machine). Not auto-deleted. Clean up periodically or set file retention policy.

**Q: Can I change the weight database?**  
A: Yes! Edit `.env`:
```bash
# V4 3-Fold (default)
GA_WEIGHTS_DB_PATH=/ga_weights/V4_3Fold_Sign_weights.db

# V4 LOOCV
GA_WEIGHTS_DB_PATH=/ga_weights/V4_LOOCV_Sign_weights.db

# V4 Unsigned
GA_WEIGHTS_DB_PATH=/ga_weights/V4_3Fold_Unsign_weights.db
```
Then restart: `docker compose up -d --force-recreate`

---

## 繁體中文

### 概述

一個基於網頁的工具，使用 **GA 校準權重** 從基因型 VCF 檔案進行基因表現量預測。應用程式整合了：

- **VCF 上傳介面**：簡單的拖拉放置支持
- **權重選擇**：在 GA 校準或原始 PrediXcan 權重之間選擇
- **實時處理**：包含三個流程階段的進度追蹤
- **結果可視化**：摘要指標、QC 分佈、詳細表格
- **CSV 下載**：導出預測表現量和 QC 摘要

### 快速開始

```bash
cd /home/betty0101/Predixcan_materials/PredictAP_WebUI
docker compose up -d
# 打開 http://127.0.0.1:8503
```

在側邊欄導航至：**🧬 GA-Calibrated Gene Expression Prediction**

### 系統要求

- Docker & Docker Compose
- 4GB+ RAM
- 網路連接（如使用遠端數據庫）
- 結果儲存空間 (save_tmp/)

### 核心功能

✅ **GA 校準權重** - GA 優化的預測模型  
✅ **原始 PrediXcan 權重** - 標準預測權重  
✅ **實時進度顯示** - 三階段處理流程  
✅ **QC 指標** - 每個基因的 SNP 覆蓋率和方差統計  
✅ **狀態指示器** - 清晰的預測品質分類  
✅ **下載結果** - CSV 格式用於下游分析  

### 項目結構

```
.
├── app/
│   ├── main.py                          # 導航入口
│   ├── pages/
│   │   └── GA_GeneExpression_Predict.py # 主應用程式（已更新 ✨）
│   └── lib/
│       ├── genexpr_pipeline.py          # 流程編排
│       └── GeneExpression_Predict.py    # 預測核心邏輯
├── sample_data/
│   └── test_sample.vcf.gz              # 示例 VCF 檔案
├── save_tmp/                           # 結果儲存目錄
├── Dockerfile                          # 容器配置
├── docker-compose.yml                  # 服務配置
├── requirements.txt                    # Python 依賴
├── .env                               # 環境配置
├── .env.example                       # 配置模板
└── README_UNIFIED.md                  # 本文件（新增 ✨）
```

### VCF 輸入要求

**格式規範：**
- VCF 版本：4.0+
- 變異 ID：**必須是 rsid**（例如 `rs1000068`）
  - ❌ 不可以是 `chr:pos` 格式
  - ❌ 不可以是 `.`（缺失 ID）
- 基因型格式：GT (0/1, 1/1 等)
- 最大檔案大小：500 MB（可通過 `STREAMLIT_MAX_UPLOAD_MB` 配置）

**VCF 標頭範例：**
```
##fileformat=VCFv4.2
##contig=<ID=1>
#CHROM  POS   ID        REF ALT QUAL FILTER INFO FORMAT sample1 sample2 sample3
1       1000  rs1000068 A   G   .    .      .    GT     0/0     0/1     1/1
```

**轉換為 rsid 格式（如需要）：**
```bash
# 使用 bcftools
bcftools annotate -c ID -a dbSNP.vcf.gz input.vcf.gz -Oz -o output_rsid.vcf.gz
gunzip output_rsid.vcf.gz
```

### 使用工作流程

#### 步驟 1：準備 VCF
- 確保變異 ID 是 rsid
- 檢查檔案大小（預設 < 500 MB）
- 如需壓縮：`bgzip genotype.vcf > genotype.vcf.gz`

#### 步驟 2：上傳和配置
1. 點擊 **VCF 檔案上傳器** → 選擇檔案
2. 選擇 **權重類型**（側邊欄）：
   - **GA-Calibrated Weights** → 選擇數據庫版本
   - **Original PrediXcan Weight** → 自動使用內建數據庫
3. 點擊 **Run Prediction** 按鈕

#### 步驟 3：監控進度
觀看三個處理階段：
- 📊 從權重提取 SNP 列表... (10%)
- 📊 用 plink2 計算 SNP dosage... (30%)
- 📊 計算預測表現量... (70%)

#### 步驟 4：檢查結果
- **結果摘要**：樣本數、預測基因數、PASS/WARNING 計數
- **預測狀態分佈**：QC 狀態分佈的柱狀圖
- **詳細結果標籤**：
  - **預測表現量**：樣本 × 基因表現量矩陣
  - **預測摘要**：基因級 QC 指標
  - **預測狀態參考**：狀態碼解釋

#### 步驟 5：下載結果
- **predicted_expression_{timestamp}.csv**：寬格式（樣本 × 基因）
- **predicted_summary_{timestamp}.csv**：基因級 QC 報告

### 預測狀態碼

| 狀態 | 顯示名稱 | 幫助文本 | 建議 |
|------|--------|---------|------|
| OK | **PASS** | SNP 覆蓋率 ≥50%，信心度高 | ✓ 用於分析 |
| LOW_SNP_COVERAGE | **WARNING** | SNP 覆蓋率 <50%，謹慎使用 | ⚠ 小心使用，標註覆蓋率 |
| NO_SNPS_IN_VCF | **NO_DATA** | VCF 中未找到 SNP | ✗ 無法預測 |
| NO_MODEL_SNPS | **FILTERED** | GA 階段剪除，無可用權重 | ✗ 基因模型無效 |
| ZERO_VARIANCE | **NO_VARIANCE** | 預測值無變異（無區分力） | ✗ 勿使用 |

### 輸出檔案

#### predicted_expression.csv
```
FID,IID,ENSG00000000971,ENSG00000001167,...
1,sample1,0.1234,-0.5678,...
1,sample2,0.4567,0.1234,...
```
- **格式**：寬格式（一行 = 一個樣本）
- **欄位**：FID | IID | [基因表現量值]
- **數值**：原始尺度（未標準化）
- **建議**：下游分析前先標準化

#### predicted_summary.csv
```
gene,n_snps_in_model,n_snps_used,pct_snps_used,pred_mean,pred_sd,var_g,status
ENSG00000000971,234,180,0.77,0.05,0.32,0.1024,OK
ENSG00000001167,156,78,0.5,0.02,0.18,0.0324,LOW_SNP_COVERAGE
```
- **格式**：一行一基因
- **關鍵指標**：
  - `n_snps_in_model`：GA 模型中有非零權重的 SNP 數
  - `n_snps_used`：VCF 中實際用於預測的 SNP 數
  - `pct_snps_used`：覆蓋率 = n_snps_used / n_snps_in_model
  - `var_g`：遺傳方差（預測表現量跨樣本的方差）
  - `status`：QC 狀態碼

**最佳實踐**：在下游分析前篩選 `status == 'OK'` 的基因

### 標準化預測表現量

輸出值為原始尺度。用於下游分析前先標準化：

**Python：**
```python
import pandas as pd
import numpy as np

expr = pd.read_csv('predicted_expression_run1.csv', index_col='IID')
expr_z = (expr - expr.mean()) / expr.std()
expr_z.to_csv('predicted_expression_normalized.csv')
```

**R：**
```r
expr <- read.csv('predicted_expression_run1.csv', row.names = 'IID')
expr_z <- scale(expr)
write.csv(expr_z, 'predicted_expression_normalized.csv')
```

### 配置選項

編輯 `.env` 自訂設定：

| 變數 | 預設值 | 說明 |
|-----|--------|------|
| `GA_WEIGHTS_DB_PATH` | `/ga_weights/V4_3Fold_Sign_weights.db` | 權重數據庫路徑（容器內） |
| `GA_WEIGHTS_DB_HOST_PATH` | `/mnt/data_40T/anywaycheng/UploadFile/GA/GA_Weight_DataBase` | 權重數據庫路徑（主機） |
| `GA_WEIGHT_COLUMN` | `GA_W` | 權重欄名稱 (GA_W 或 PrediXcan_W) |
| `PLINK2_CMD` | `plink2` | plink2 執行檔命令 |
| `SAVE_TMP_DIR` | `/app/save_tmp` | 結果儲存目錄 |
| `STREAMLIT_MAX_UPLOAD_MB` | `500` | 最大上傳檔案大小（MB） |

**更改權重數據庫：**
```bash
# 編輯 .env
GA_WEIGHTS_DB_PATH=/ga_weights/V4_LOOCV_Sign_weights.db

# 重啟服務
docker compose up -d --force-recreate
```

### Docker 管理

```bash
# 檢查服務狀態
docker compose ps

# 查看日誌
docker compose logs -f predictap-web

# 重啟（代碼改動）
docker compose restart predictap-web

# 重建（依賴改動）
docker compose up --build -d

# 完整重建（.env 改動）
docker compose up --build -d --force-recreate

# 停止服務
docker compose down
```

### 最新更新 ✨

**UI/UX 改進（最新）：**
- ✅ 權重類型名稱：**GA-Calibrated Weights** | **Original PrediXcan Weight**
- ✅ 狀態碼重新設計，清晰的標籤：
  - `OK` → **PASS**（高信心度）
  - `LOW_SNP_COVERAGE` → **WARNING**（謹慎使用）
  - `NO_SNPS_IN_VCF` → **NO_DATA**（未找到）
  - `NO_MODEL_SNPS` → **FILTERED**（模型無效）
  - `ZERO_VARIANCE` → **NO_VARIANCE**（無區分力）
- ✅ 改進的配置流程：先選擇權重類型，再選擇數據庫
- ✅ PrediXcan 權重自動選擇內建數據庫（無需選擇）
- ✅ 所有狀態碼上都有幫助工具提示
- ✅ 結果標籤：摘要指標中的 PASS/WARNING 計數

### 故障排除

**"無法上傳檔案"**
- 檢查檔案大小（預設 < 500 MB）
- 檢查瀏覽器連接
- 嘗試不同的瀏覽器或無痕模式

**"運行按鈕已禁用"**
- 先上傳一個 VCF 檔案

**"預測結果全是零"**
- 檢查 `predicted_summary.csv` 狀態碼
- 如果大多數基因的 `n_snps_used == 0` → VCF 變異 ID 不是 rsid
- 使用 bcftools 轉換為 rsid 格式

**"結果耗時太長"**
- 取決於 VCF 大小和樣本數
- 檢查 Docker 日誌：`docker compose logs -f predictap-web`

**"檔案太大"**
- 壓縮：`bgzip genotype.vcf > genotype.vcf.gz`
- 增加 `.env` 中的 `STREAMLIT_MAX_UPLOAD_MB`

### 常見問題

**Q: 我可以將這些預測用於 S-PrediXcan/GWAS 分析嗎？**  
A: 可以！典型工作流程：
1. 篩選 `status == 'OK'` 的基因
2. 標準化預測表現量（z-score）
3. 測試與表型的關聯（線性回歸）
4. 應用多重檢驗校正

**Q: 預測需要多長時間？**  
A: 取決於 VCF 大小：
- 小型 (< 100 MB, < 1K 樣本)：秒到數十秒
- 中型 (100-500 MB)：數十秒到數分鐘
- 大型 (> 500 MB)：數分鐘到數小時

**Q: 結果儲存在哪裡？**  
A: 在 `save_tmp/` 目錄（主機）。不自動刪除。定期清理或設置檔案保留策略。

**Q: 我可以更改權重數據庫嗎？**  
A: 可以！編輯 `.env`：
```bash
# V4 3-Fold（預設）
GA_WEIGHTS_DB_PATH=/ga_weights/V4_3Fold_Sign_weights.db

# V4 LOOCV
GA_WEIGHTS_DB_PATH=/ga_weights/V4_LOOCV_Sign_weights.db

# V4 無符號
GA_WEIGHTS_DB_PATH=/ga_weights/V4_3Fold_Unsign_weights.db
```
然後重啟：`docker compose up -d --force-recreate`

---

## Technical Architecture

### Processing Pipeline

```
User VCF
    ↓
[1] SNP Extraction (from weights.db)
    ↓
[2] Plink2 Dosage Computation
    ↓
[3] Allele Alignment & QC
    ↓
[4] PrediXcan Prediction (W @ D)
    ↓
[5] QC Summary Generation
    ↓
Results CSV + Summary CSV
```

### Key Components

- **genexpr_pipeline.py** - Pipeline orchestration class
- **GeneExpression_Predict.py** - Core prediction logic (sparse matrix multiplication)
- **GA_GeneExpression_Predict.py** - Streamlit web interface (UPDATED ✨)

### Dependencies

```
pandas >= 2.0          # Data processing
numpy >= 1.26          # Numerical computing
scipy >= 1.11          # Sparse matrix operations
streamlit >= 1.35      # Web UI
```

---

## Version History

### v2.0 (2026-08-25) - UI Improvements ✨
- **Redesigned Status Codes**: PASS, WARNING, NO_DATA, FILTERED, NO_VARIANCE
- **Improved Weight Type Names**: GA-Calibrated Weights, Original PrediXcan Weight
- **Better Configuration Flow**: Select weight type first, database second
- **Help Tooltips**: All status codes now have hover explanations
- **Better Metric Labels**: PASS/WARNING instead of OK/Low Coverage
- **Unified Documentation**: Combined English + Chinese support

### v1.0 (2026-08-21) - Initial Release
- GA-Calibrated weights prediction
- VCF upload and processing
- Real-time progress tracking
- Results visualization and download

---

## Support & Resources

- **Documentation**: This README file (unified)
- **Quick Start**: See Quick Start section above
- **Configuration**: Edit `.env` file
- **Logs**: `docker compose logs -f predictap-web`
- **Issues**: Check Troubleshooting section above

---

**Status**: Production Ready ✅  
**Last Updated**: 2026-08-25  
**Maintained By**: Betty  

🎉 **Ready to predict! Start with the Quick Start section above.**
