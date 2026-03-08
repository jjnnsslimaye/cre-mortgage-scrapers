# Yearly Historical Data Guide

## Overview

You can now download and process historical mortgage data from Broward County going back to **1978**. The yearly data is formatted **identically** to the daily data, making it perfect for seeding your database.

---

## Data Availability

### Daily Data (Recent)
- **Location**: `/Official_Records_Download/`
- **Availability**: Last **10 days only** (rolling window)
- **Update Frequency**: New files added daily, old files deleted after 10 days
- **File Size**: ~570 KB per day (5 text files)
- **Use Case**: Ongoing monitoring, cron jobs, recent data

### Yearly Data (Historical)
- **Location**: `/OR_Yearly_Exports/`
- **Availability**: **1978 - present** (full years)
- **Update Frequency**: Annual (current year updated periodically)
- **File Size**: ~120 MB per year (3 files, entire year)
- **Use Case**: Database seeding, historical analysis, backfill

---

## Usage Examples

### Download Single Year
```bash
# Download all 2024 mortgages
python main.py --year 2024

# Outputs:
#   data/raw/yearly/2024/CY2024doc-rec.txt
#   data/raw/yearly/2024/CY2024nme-rec.txt
#   data/raw/yearly/2024/CY2024lnk-rec.txt
#   data/processed/yearly/2024/mortgages_2024.csv
#   data/processed/yearly/2024/mortgages_2024.json
#   data/processed/yearly/2024/analysis_report_2024.txt
```

### Download Multiple Years
```bash
# Download 5 years of data (2020-2024)
python main.py --start-year 2020 --end-year 2024

# Outputs:
#   data/processed/yearly/2020/mortgages_2020.csv
#   data/processed/yearly/2021/mortgages_2021.csv
#   data/processed/yearly/2022/mortgages_2022.csv
#   data/processed/yearly/2023/mortgages_2023.csv
#   data/processed/yearly/2024/mortgages_2024.csv
```

### Seed Historical Database
```bash
# Download all data from 2015 onwards
python main.py --start-year 2015 --end-year 2024 --output-dir /path/to/db_seed

# Then load CSVs into your database:
# - PostgreSQL: COPY command
# - S3: aws s3 sync
# - Pandas: pd.read_csv() → write to DB
```

---

## Output Format (Identical to Daily Data)

### CSV Columns
```
doc_number         - Unique document ID
record_date        - Date recorded (YYYY-MM-DD)
record_time        - Time recorded (HHMMSS)
doc_type           - Document type (M = Mortgage)
loan_amount        - Loan amount in dollars
borrowers          - All borrower names (comma-separated)
lenders            - All lender names (comma-separated)
parcel_id          - Property parcel ID (when available)
legal_description  - Property legal description (when available)
doc_stamps         - Documentary stamp tax
intangible_tax     - Intangible tax
page_count         - Number of pages in document
```

### Directory Structure
```
data/
├── raw/
│   ├── daily/
│   │   ├── 2026-03-01/  (5 files, 570KB)
│   │   ├── 2026-03-02/  (5 files, 570KB)
│   │   └── ...
│   └── yearly/
│       ├── 2020/  (3 files, ~120MB)
│       ├── 2021/  (3 files, ~120MB)
│       ├── 2022/  (3 files, ~120MB)
│       ├── 2023/  (3 files, ~120MB)
│       └── 2024/  (3 files, ~120MB)
└── processed/
    ├── daily/
    │   ├── 2026-03-01/  (CSV + JSON + report)
    │   └── ...
    └── yearly/
        ├── 2020/  (CSV + JSON + report)
        ├── 2021/  (CSV + JSON + report)
        ├── 2022/  (CSV + JSON + report)
        ├── 2023/  (CSV + JSON + report)
        └── 2024/  (CSV + JSON + report)
```

---

## 2024 Data Sample

From the test run:

```
Total Mortgages:        44,959
Loans ≥ $1M:            2,317 (5.2%)
Loans ≥ $5M:            324 (0.7%)
Total Volume:           $25.4 billion
Average Loan:           $565,935

Largest Loan:           $910,104,500 (Flagler Village Owner LLC)
Top Lender (Volume):    Wells Fargo Bank ($1.55B)
Top Lender (Count):     MERS (130 loans ≥$1M)
```

---

## Processing Time & File Sizes

| Year | Documents | Mortgages | File Size | Parse Time |
|------|-----------|-----------|-----------|------------|
| 2024 | 667,287   | 44,959    | ~120 MB   | ~2-3 min   |
| 2023 | ~650,000  | ~44,000   | ~115 MB   | ~2-3 min   |
| 2022 | ~710,000  | ~52,000   | ~130 MB   | ~3-4 min   |
| 2021 | ~650,000  | ~49,000   | ~120 MB   | ~2-3 min   |
| 2020 | ~600,000  | ~41,000   | ~110 MB   | ~2-3 min   |

**Full backfill (2015-2024)**: ~15-20 minutes, ~450,000+ mortgages

---

## Database Seeding Strategy

### Recommended Approach

1. **Download Historical Data** (one-time):
   ```bash
   # Seed DB with last 10 years
   python main.py --start-year 2015 --end-year 2024 --output-dir data/db_seed
   ```

2. **Load into Database**:
   ```python
   import pandas as pd
   import psycopg2  # or your DB connector

   for year in range(2015, 2025):
       df = pd.read_csv(f'data/db_seed/processed/yearly/{year}/mortgages_{year}.csv')
       df.to_sql('mortgages', con=engine, if_exists='append', index=False)
   ```

3. **Setup Daily Cron** (ongoing):
   ```bash
   # Run daily at 6 AM to get yesterday's data
   0 6 * * * /path/to/python /path/to/main.py --date $(date -d yesterday +\%Y-\%m-\%d)
   ```

4. **Upload to S3** (if using Railway → S3):
   ```bash
   # After daily cron
   aws s3 sync data/processed/daily/ s3://your-bucket/broward/daily/
   ```

---

## Comparison: Daily vs Yearly

| Feature | Daily Data | Yearly Data |
|---------|-----------|-------------|
| **Availability** | Last 10 days | 1978 - present |
| **File Size** | ~570 KB/day | ~120 MB/year |
| **Files per Period** | 5 files | 3 files |
| **Processing Time** | ~5 seconds | ~2-3 minutes |
| **Use Case** | Cron jobs, recent data | DB seeding, historical |
| **Format** | Identical | Identical |
| **File Names** | `MM-DD-YYYYdoc-ver.txt` | `CYYYYYdoc-rec.txt` |

---

## Important Notes

### File Format Differences
Despite different file names, the data format is **identical**:
- Daily: `doc-ver.txt`, `nme-ver.txt` (20 fields, 5 fields)
- Yearly: `doc-rec.txt`, `nme-rec.txt` (20 fields, 5 fields)

The parser handles both seamlessly.

### What's NOT Available in Yearly Files
- Document images (img.zip) - only in daily files, too large
- Daily breakdown - yearly files don't segment by day within the year

### Current Year (2026)
- `CY2026` files may be incomplete (year not finished yet)
- Use daily data for current year until year end
- Next January, `CY2026` will contain complete 2026 data

### Overlapping Data
- If you download `--year 2024` AND `--date 2024-03-02`, you'll have the same data twice
- For DB seeding: Use yearly for historical, daily for ongoing
- Avoid duplicate imports by filtering on `record_date`

---

## Production Deployment Plan

### Phase 1: Historical Backfill (One-Time)
```bash
# Download 2015-2024 (~450k mortgages)
python main.py --start-year 2015 --end-year 2024 --output-dir /tmp/backfill

# Load into database
python load_to_db.py --source /tmp/backfill/processed/yearly/

# Or upload to S3
aws s3 sync /tmp/backfill/processed/yearly/ s3://your-bucket/broward/historical/
```

### Phase 2: Daily Cron (Railway)
```yaml
# railway.json or similar
cron:
  schedule: "0 6 * * *"  # Daily at 6 AM
  command: "python main.py --date $(date -d yesterday +%Y-%m-%d)"

post_process:
  command: "aws s3 cp data/processed/daily/ s3://your-bucket/broward/daily/ --recursive"
```

### Phase 3: Weekly Backfill Check
```bash
# Every Monday, backfill missed days (in case cron failed)
python main.py --days 7
```

---

## Troubleshooting

### Large Files Taking Too Long?
```bash
# Process years sequentially instead of in one command
for year in {2015..2024}; do
    python main.py --year $year
done
```

### Out of Memory?
```python
# Process yearly data in chunks (modify parser.py):
# Read files in chunks instead of all at once
# Or process per month if needed
```

### Missing Year?
```bash
# Check available years on FTP
python explore_ftp.py | grep "CY20"
```

### Duplicate Data in DB?
```sql
-- Add unique constraint on doc_number
ALTER TABLE mortgages ADD CONSTRAINT unique_doc_number UNIQUE (doc_number);

-- Remove duplicates before adding constraint
DELETE FROM mortgages a USING mortgages b
WHERE a.id < b.id AND a.doc_number = b.doc_number;
```

---

## Next Steps

1. **Test with single year**: `python main.py --year 2024`
2. **Download historical range**: `python main.py --start-year 2020 --end-year 2024`
3. **Load CSVs into your database** (PostgreSQL, S3, etc.)
4. **Setup Railway cron** for daily updates
5. **Begin UCC cross-referencing** for distress signals

---

## File Size Estimates

Full historical backfill (1978-2024):
- **Raw files**: ~5.5 GB (47 years × ~120 MB)
- **Processed CSV**: ~3 GB (estimated ~2M mortgages)
- **Processed JSON**: ~5 GB (more verbose than CSV)
- **Total**: ~13-14 GB for complete history

Recommendation: Start with 2015-2024 (last 10 years) for MVP.
