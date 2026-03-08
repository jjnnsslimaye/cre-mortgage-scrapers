# S3 Upload Guide

## Overview

The scraper now supports automatic uploading of mortgage data to AWS S3. This is essential for the production deployment where daily cron jobs on Railway will upload results to S3 for your enrichment pipeline to consume.

---

## S3 Bucket Structure

Data is partitioned by county, time period, and date:

```
s3://your-bucket/
└── florida/
    └── broward/
        ├── daily/
        │   └── 2026/
        │       ├── 03/
        │       │   ├── 01/mortgages.json  (204 mortgages from that day)
        │       │   ├── 02/mortgages.json
        │       │   └── 03/mortgages.json
        │       └── 04/
        │           ├── 01/mortgages.json
        │           └── ...
        └── yearly/
            ├── 2024/mortgages.json  (44,959 mortgages from entire year)
            ├── 2023/mortgages.json
            └── 2022/mortgages.json
```

**Why this structure?**
- **state/** - Top-level namespace for multi-state support (florida, texas, etc.)
- **county/** - County namespace for multi-county support (broward, miami-dade, etc.)
- **daily/** - Recent data from rolling 10-day window
- **yearly/** - Historical backfill data
- **YYYY/MM/DD/** - Date partitioning for easy querying

---

## Setup

### 1. Install Dependencies

```bash
pip install boto3>=1.28.0
```

### 2. Configure AWS Credentials

**Option A: Environment Variables (Recommended)**

```bash
# Create .env file
cp .env.example .env

# Edit .env with your credentials
export S3_BUCKET=your-bucket-name
export AWS_ACCESS_KEY_ID=your-aws-access-key-id
export AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
```

**Option B: AWS CLI Configuration**

```bash
aws configure
# Enter your credentials when prompted
```

**Option C: IAM Role (for Railway/EC2)**

No credentials needed if running on Railway/EC2 with IAM role attached.

### 3. Create S3 Bucket

```bash
# Create bucket
aws s3 mb s3://your-cre-data-bucket --region us-east-1

# Verify bucket
aws s3 ls
```

---

## Usage

### Daily Upload (Production Use Case)

```bash
# Download yesterday's data and upload to S3
python main.py --date 2026-03-02 --upload-to-s3

# Result:
# Local: data/processed/daily/2026-03-02/mortgages_2026-03-02.json
# S3:    s3://bucket/florida/broward/daily/2026/03/02/mortgages.json
```

### Yearly Upload (Backfill Use Case)

```bash
# Download 2024 data and upload to S3
python main.py --year 2024 --upload-to-s3

# Result:
# Local: data/processed/yearly/2024/mortgages_2024.json
# S3:    s3://bucket/florida/broward/yearly/2024/mortgages.json
```

### Bulk Backfill

```bash
# Upload multiple years to S3
python main.py --start-year 2020 --end-year 2024 --upload-to-s3

# Result:
# S3: s3://bucket/florida/broward/yearly/2020/mortgages.json
# S3: s3://bucket/florida/broward/yearly/2021/mortgages.json
# S3: s3://bucket/florida/broward/yearly/2022/mortgages.json
# S3: s3://bucket/florida/broward/yearly/2023/mortgages.json
# S3: s3://bucket/florida/broward/yearly/2024/mortgages.json
```

---

## Verification

### Check Upload Success

```bash
# List all daily files for March 2026
aws s3 ls s3://your-bucket/florida/broward/daily/2026/03/ --recursive

# Check specific file
aws s3 ls s3://your-bucket/florida/broward/daily/2026/03/02/mortgages.json

# Download file to verify
aws s3 cp s3://your-bucket/florida/broward/daily/2026/03/02/mortgages.json - | jq . | head
```

### Monitor Upload Progress

Logs will show upload progress:

```
INFO:s3_uploader:S3 uploader initialized for bucket: your-bucket
INFO:s3_uploader:Uploading mortgages_2026-03-02.json (70,234 bytes) to s3://your-bucket/florida/broward/daily/2026/03/02/mortgages.json
INFO:s3_uploader:✓ Upload successful: s3://your-bucket/florida/broward/daily/2026/03/02/mortgages.json
```

---

## Railway Deployment

### Environment Variables

In Railway dashboard, set:

```
S3_BUCKET=your-cre-data-bucket
AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
AWS_SECRET_ACCESS_KEY=your-secret-key
```

### Cron Configuration

**railway.json** (or equivalent):

```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "schedule": "0 6 * * *",
    "command": "python main.py --date $(date -d yesterday +%Y-%m-%d) --upload-to-s3"
  }
}
```

This runs daily at 6 AM, scrapes yesterday's data, and uploads to S3.

---

## Error Handling

### Missing Credentials

```
ERROR:s3_uploader:✗ AWS credentials not found. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY env vars.
```

**Fix:** Set environment variables or run `aws configure`

### Bucket Not Found

```
ERROR:s3_uploader:✗ S3 upload failed: NoSuchBucket: The specified bucket does not exist
```

**Fix:** Create bucket with `aws s3 mb s3://your-bucket-name`

### Permission Denied

```
ERROR:s3_uploader:✗ S3 upload failed: AccessDenied: Access Denied
```

**Fix:** Ensure IAM user/role has `s3:PutObject` permission:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name",
        "arn:aws:s3:::your-bucket-name/*"
      ]
    }
  ]
}
```

---

## Advanced Usage

### Standalone S3 Upload

Upload an existing JSON file without re-scraping:

```bash
# Daily file
python s3_uploader.py data/processed/daily/2026-03-02/mortgages_2026-03-02.json --date 2026-03-02

# Yearly file
python s3_uploader.py data/processed/yearly/2024/mortgages_2024.json --year 2024
```

### Skip Upload if File Exists

Modify `s3_uploader.py` to use `skip_if_exists=True`:

```python
upload_to_s3(json_path, date_str=date_str, skip_if_exists=True)
```

Useful for backfills where you don't want to re-upload existing data.

### Custom State/County Configuration

When adding new counties or states, change the `state` and `county` parameters:

```python
upload_to_s3(json_path, date_str=date_str, state="florida", county="miami-dade")
```

Results in: `s3://bucket/florida/miami-dade/daily/2026/03/02/mortgages.json`

---

## Integration with Enrichment Pipeline

Your enrichment pipeline can read from S3:

```python
import boto3
import json

s3 = boto3.client('s3')

# Read daily file
response = s3.get_object(
    Bucket='your-bucket',
    Key='florida/broward/daily/2026/03/02/mortgages.json'
)
mortgages = json.loads(response['Body'].read())

# Process and enrich
for mortgage in mortgages:
    # Cross-reference with UCC filings
    # Add property details
    # Calculate distress scores
    pass

# Write enriched data to PostgreSQL
```

Or use AWS Lambda triggered by S3 events:

```python
# Lambda function triggered on s3:ObjectCreated
def lambda_handler(event, context):
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    # Download, enrich, write to PostgreSQL
```

---

## Cost Considerations

### S3 Storage Costs

**Daily Files:**
- ~70 KB per day
- ~2.5 MB per month
- ~30 MB per year
- Cost: ~$0.001/month

**Yearly Files:**
- ~10 MB per year
- 10 years = ~100 MB
- Cost: ~$0.002/month

**Total: < $0.01/month for storage**

### S3 Request Costs

- PUT requests: $0.005 per 1,000 requests
- GET requests: $0.0004 per 1,000 requests
- Daily uploads: 365/year × $0.000005 = ~$0.002/year

**Total cost: Negligible (< $1/year)**

---

## Troubleshooting

### Verify Credentials

```bash
aws sts get-caller-identity
```

Should return your AWS account ID and user.

### Test S3 Access

```bash
# Write test file
echo '{"test": true}' > test.json
aws s3 cp test.json s3://your-bucket/test/test.json

# Read test file
aws s3 cp s3://your-bucket/test/test.json - | jq .

# Delete test file
aws s3 rm s3://your-bucket/test/test.json
```

### Debug Upload Issues

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Then run your command to see detailed boto3 logs.

---

## Next Steps

1. **Test locally**: Run `python main.py --date 2026-03-02 --upload-to-s3`
2. **Verify S3**: Check file exists in S3 console or via AWS CLI
3. **Deploy to Railway**: Set env vars and configure cron
4. **Build enrichment pipeline**: Read from S3, enrich, write to PostgreSQL
5. **Monitor**: Set up CloudWatch alerts on S3 upload failures

---

## Summary

✅ **Local Development**: Set `.env` with AWS credentials
✅ **Production (Railway)**: Set env vars in Railway dashboard
✅ **Daily Cron**: `python main.py --date yesterday --upload-to-s3`
✅ **Historical Backfill**: `python main.py --start-year 2020 --end-year 2024 --upload-to-s3`
✅ **S3 Structure**: `s3://bucket/state/county/{daily|yearly}/YYYY/MM/DD/mortgages.json`
✅ **Cost**: < $1/year for S3 storage + requests

You're ready for production deployment! 🚀
