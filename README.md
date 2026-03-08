# CRE Mortgage Scrapers

Automated scrapers for collecting commercial real estate mortgage data from county recorders across multiple states.

## Overview

This monorepo contains scrapers for multiple counties across the United States. Each scraper downloads public mortgage records, processes them, and uploads to S3 for downstream enrichment and analysis.

**Current Coverage:**
- ✅ Florida → Broward County
- 🚧 Florida → Miami-Dade County (planned)
- 🚧 Florida → Palm Beach County (planned)
- 🚧 Texas → Harris County (planned)

## Repository Structure

```
cre-mortgage-scrapers/
├── lib/                          # Shared utilities across all scrapers
│   ├── notifications.py          # Multi-channel alerting
│   ├── s3_uploader.py            # S3 upload with retry logic
│   └── logging_config.py         # Structured logging
├── florida/
│   └── broward/                  # Broward County, FL scraper
│       ├── main.py
│       ├── broward_ftp_client.py
│       ├── parser.py
│       ├── exporter.py
│       └── models.py
├── docs/                         # Documentation
│   ├── S3_UPLOAD_GUIDE.md
│   ├── ERROR_HANDLING_IMPROVEMENTS.md
│   ├── DATA_STRUCTURE.md
│   ├── TEST_RESULTS.md
│   └── YEARLY_DATA_GUIDE.md
├── requirements.txt
├── .env.example
└── README.md
```

## S3 Data Structure

```
s3://your-bucket/
└── {state}/
    └── {county}/
        ├── daily/YYYY/MM/DD/mortgages.json
        └── yearly/YYYY/mortgages.json
```

## Quick Start

### Local Development

```bash
# Clone and install
git clone <repo-url>
cd cre-mortgage-scrapers
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your AWS credentials

# Run Broward scraper
cd florida/broward
python main.py --year 2024 --upload-to-s3
```

### Railway Deployment

**Per-County Service Configuration:**

1. **Root Directory:** `florida/broward`
2. **Build Command:** `pip install -r ../../requirements.txt`
3. **Cron Schedule:** `0 6 * * *`
4. **Cron Command:** `cd florida/broward && python main.py --date $(date -d yesterday +%Y-%m-%d) --upload-to-s3`

## Features

- ✅ Automatic retry logic (FTP + S3)
- ✅ Idempotency (skip if exists)
- ✅ Multi-channel notifications (Email, Slack, Discord)
- ✅ Metrics tracking and persistence
- ✅ Structured logging
- ✅ State/county partitioning in S3

## Documentation

- [S3 Upload Guide](S3_UPLOAD_GUIDE.md)
- [Error Handling](ERROR_HANDLING_IMPROVEMENTS.md)
- [Data Structure](DATA_STRUCTURE.md)

