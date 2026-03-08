"""
S3 uploader for mortgage data
Uploads JSON files to S3 with proper partitioning
"""
import os
import logging
from pathlib import Path
from typing import Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class S3Uploader:
    """Upload mortgage data to S3 with proper partitioning"""

    def __init__(
        self,
        bucket: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region: str = "us-east-1"
    ):
        """
        Initialize S3 uploader

        Args:
            bucket: S3 bucket name (or use S3_BUCKET env var)
            aws_access_key_id: AWS access key (or use AWS_ACCESS_KEY_ID env var)
            aws_secret_access_key: AWS secret key (or use AWS_SECRET_ACCESS_KEY env var)
            region: AWS region
        """
        self.bucket = bucket or os.getenv("S3_BUCKET")

        if not self.bucket:
            raise ValueError("S3 bucket name required. Set S3_BUCKET env var or pass bucket parameter.")

        # Initialize S3 client
        session_kwargs = {"region_name": region}

        # Use provided credentials or fall back to env vars/IAM role
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = aws_access_key_id
            session_kwargs["aws_secret_access_key"] = aws_secret_access_key
        elif os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
            session_kwargs["aws_access_key_id"] = os.getenv("AWS_ACCESS_KEY_ID")
            session_kwargs["aws_secret_access_key"] = os.getenv("AWS_SECRET_ACCESS_KEY")

        self.s3_client = boto3.client("s3", **session_kwargs)
        logger.info(f"S3 uploader initialized for bucket: {self.bucket}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ClientError, OSError, IOError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def upload_file(
        self,
        local_path: Path,
        s3_key: str,
        content_type: str = "application/json",
        skip_if_exists: bool = False
    ) -> bool:
        """
        Upload a single file to S3 with automatic retries

        Args:
            local_path: Local file path
            s3_key: S3 object key (path in bucket)
            content_type: Content type for the file
            skip_if_exists: Skip upload if file already exists in S3 (idempotency)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if file already exists (idempotency)
            if skip_if_exists and self.check_exists(s3_key):
                logger.info(f"⊙ File already exists in S3, skipping: s3://{self.bucket}/{s3_key}")
                return True

            file_size = local_path.stat().st_size
            logger.info(f"Uploading {local_path.name} ({file_size:,} bytes) to s3://{self.bucket}/{s3_key}")

            self.s3_client.upload_file(
                str(local_path),
                self.bucket,
                s3_key,
                ExtraArgs={"ContentType": content_type}
            )

            logger.info(f"✓ Upload successful: s3://{self.bucket}/{s3_key}")
            return True

        except FileNotFoundError:
            logger.error(f"✗ File not found: {local_path}")
            return False
        except NoCredentialsError:
            logger.error("✗ AWS credentials not found. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY env vars.")
            return False
        except ClientError as e:
            # Don't retry on credential or permission errors
            if e.response['Error']['Code'] in ['NoSuchBucket', 'AccessDenied', 'InvalidAccessKeyId']:
                logger.error(f"✗ S3 upload failed (non-retryable): {e}")
                return False
            logger.error(f"✗ S3 upload failed: {e}")
            raise  # Re-raise to trigger retry
        except Exception as e:
            logger.error(f"✗ Unexpected error during upload: {e}")
            raise  # Re-raise to trigger retry

    def upload_daily_mortgages(
        self,
        local_json_path: Path,
        date_str: str,
        state: str = "florida",
        county: str = "broward",
        skip_if_exists: bool = False
    ) -> bool:
        """
        Upload daily mortgage JSON to S3 with date partitioning

        Path format: s3://bucket/state/county/daily/YYYY/MM/DD/mortgages.json

        Args:
            local_json_path: Path to local JSON file
            date_str: Date string in YYYY-MM-DD format
            state: State name (lowercase)
            county: County name (lowercase)
            skip_if_exists: Skip upload if file already exists in S3

        Returns:
            True if successful
        """
        # Parse date for partitioning
        year, month, day = date_str.split("-")

        # Build S3 key
        s3_key = f"{state}/{county}/daily/{year}/{month}/{day}/mortgages.json"

        return self.upload_file(local_json_path, s3_key, skip_if_exists=skip_if_exists)

    def upload_yearly_mortgages(
        self,
        local_json_path: Path,
        year: int,
        state: str = "florida",
        county: str = "broward",
        skip_if_exists: bool = False
    ) -> bool:
        """
        Upload yearly mortgage JSON to S3 with year partitioning

        Path format: s3://bucket/state/county/yearly/YYYY/mortgages.json

        Args:
            local_json_path: Path to local JSON file
            year: Year (e.g., 2024)
            state: State name (lowercase)
            county: County name (lowercase)
            skip_if_exists: Skip upload if file already exists in S3

        Returns:
            True if successful
        """
        # Build S3 key
        s3_key = f"{state}/{county}/yearly/{year}/mortgages.json"

        return self.upload_file(local_json_path, s3_key, skip_if_exists=skip_if_exists)

    def check_exists(self, s3_key: str) -> bool:
        """
        Check if a file exists in S3

        Args:
            s3_key: S3 object key

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=s3_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                logger.error(f"Error checking if file exists: {e}")
                raise


def upload_to_s3(
    local_json_path: Path,
    date_str: Optional[str] = None,
    year: Optional[int] = None,
    state: str = "florida",
    county: str = "broward",
    skip_if_exists: bool = False
) -> bool:
    """
    Convenience function to upload mortgage data to S3

    Args:
        local_json_path: Path to local JSON file
        date_str: Date string (YYYY-MM-DD) for daily uploads
        year: Year for yearly uploads
        state: State name (lowercase)
        county: County name (lowercase)
        skip_if_exists: Skip upload if file already exists in S3

    Returns:
        True if successful

    Example:
        # Daily upload
        upload_to_s3(Path("mortgages_2026-03-02.json"), date_str="2026-03-02")

        # Yearly upload
        upload_to_s3(Path("mortgages_2024.json"), year=2024)
    """
    try:
        uploader = S3Uploader()

        # Upload based on type
        if date_str:
            return uploader.upload_daily_mortgages(
                local_json_path, date_str, state, county, skip_if_exists
            )
        elif year:
            return uploader.upload_yearly_mortgages(
                local_json_path, year, state, county, skip_if_exists
            )
        else:
            raise ValueError("Must provide either date_str or year")

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return False


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) < 3:
        print("Usage:")
        print("  Daily:  python s3_uploader.py <json_file> --date 2026-03-02")
        print("  Yearly: python s3_uploader.py <json_file> --year 2024")
        sys.exit(1)

    json_file = Path(sys.argv[1])

    if "--date" in sys.argv:
        date_idx = sys.argv.index("--date")
        date_str = sys.argv[date_idx + 1]
        success = upload_to_s3(json_file, date_str=date_str)
    elif "--year" in sys.argv:
        year_idx = sys.argv.index("--year")
        year = int(sys.argv[year_idx + 1])
        success = upload_to_s3(json_file, year=year)
    else:
        print("Must specify --date or --year")
        sys.exit(1)

    sys.exit(0 if success else 1)
