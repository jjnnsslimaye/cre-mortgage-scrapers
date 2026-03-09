#!/usr/bin/env python3
"""
Broward County Mortgage Data Scraper
Main entry point for downloading and extracting ALL mortgage loan data
"""
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import sys

# Add parent directories to path to find lib package
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from lib.logging_config import setup_logging, get_logger
from lib.s3_uploader import upload_to_s3
from lib.notifications import NotificationManager, MetricsTracker, ScraperMetrics

from broward_ftp_client import BrowardFTPClient
from parser import parse_broward_data
from exporter import MortgageExporter

# Setup logging will be called in main() after parsing arguments
logger = None


def download_and_analyze_daily(
    date: datetime,
    output_dir: Path,
    upload_s3: bool = False,
    skip_if_exists: bool = True,
    notification_manager: Optional[NotificationManager] = None,
    metrics_tracker: Optional[MetricsTracker] = None
) -> bool:
    """
    Download data for a specific date and extract ALL mortgages

    Args:
        date: Date to download
        output_dir: Output directory for results
        upload_s3: Whether to upload results to S3
        skip_if_exists: Skip S3 upload if file already exists (idempotency)
        notification_manager: Optional notification manager for alerts
        metrics_tracker: Optional metrics tracker for persistence

    Returns:
        True if successful, False otherwise
    """
    date_str = date.strftime("%Y-%m-%d")
    date_prefix = date.strftime("%m-%d-%Y")

    # Initialize metrics
    start_time = datetime.now()
    metrics = ScraperMetrics(
        start_time=start_time,
        end_time=start_time,  # Will be updated at the end
        success=False,
        data_type="daily",
        date_or_year=date_str
    )

    logger.info(f"Processing daily data for {date_str}")

    try:
        # Create directories
        download_dir = output_dir / "raw" / "daily" / date_str
        export_dir = output_dir / "processed" / "daily" / date_str
        download_dir.mkdir(parents=True, exist_ok=True)
        export_dir.mkdir(parents=True, exist_ok=True)

        # Download data from FTP
        logger.info("Connecting to Broward County FTP...")
        with BrowardFTPClient() as client:
            files = client.download_daily_files(
                date_prefix,
                download_dir,
                include_images=False
            )

            if not files:
                logger.error(f"No files downloaded for {date_str}")
                metrics.error_message = f"No files downloaded for {date_str}"
                return False

        metrics.files_downloaded = len(files)

        # Parse data
        doc_ver_path = files.get('doc-ver.txt')
        nme_ver_path = files.get('nme-ver.txt')

        if not doc_ver_path or not nme_ver_path:
            logger.error("Missing required data files")
            metrics.error_message = "Missing required data files"
            return False

        logger.info("Parsing ALL mortgage data...")
        mortgages = parse_broward_data(doc_ver_path, nme_ver_path)

        if not mortgages:
            logger.warning("No mortgages found")
            metrics.error_message = "No mortgages found"
            return False

        # Track metrics
        metrics.mortgages_count = len(mortgages)
        metrics.mortgages_over_1m = len([m for m in mortgages if m.document.amount >= 1_000_000])
        metrics.total_volume = sum(float(m.document.amount) for m in mortgages)

        # Export data (JSON only)
        logger.info("Exporting to JSON...")
        json_path = export_dir / f"mortgages_{date_str}.json"
        MortgageExporter.to_json(mortgages, json_path)

        # Upload to S3 if requested
        if upload_s3:
            logger.info("Uploading to S3...")
            success = upload_to_s3(
                json_path,
                date_str=date_str,
                state="florida",
                county="broward",
                skip_if_exists=skip_if_exists
            )
            if not success:
                logger.error("S3 upload failed")
                metrics.error_message = "S3 upload failed"
                return False
            metrics.s3_uploaded = True

        # Log summary
        logger.info(f"Date: {date_str} | Mortgages: {metrics.mortgages_count} | ≥$1M: {metrics.mortgages_over_1m} | Volume: ${metrics.total_volume:,.2f}")
        logger.info(f"Output: {json_path.absolute()}")

        # Mark as successful
        metrics.success = True
        return True

    except Exception as e:
        logger.error(f"Failed to process daily data for {date_str}: {e}", exc_info=True)
        metrics.error_message = str(e)
        return False

    finally:
        # Update end time
        metrics.end_time = datetime.now()

        # Send notifications
        if notification_manager:
            if metrics.success:
                notification_manager.send_success_notification(metrics)
            else:
                notification_manager.send_failure_notification(metrics)

        # Save metrics
        if metrics_tracker:
            metrics_tracker.save_metrics(metrics)


def download_and_analyze_yearly(
    year: int,
    output_dir: Path,
    upload_s3: bool = False,
    skip_if_exists: bool = True,
    notification_manager: Optional[NotificationManager] = None,
    metrics_tracker: Optional[MetricsTracker] = None
) -> bool:
    """
    Download full year of data and extract ALL mortgages

    Args:
        year: Year to download (e.g., 2024)
        output_dir: Output directory for results
        upload_s3: Whether to upload results to S3
        skip_if_exists: Skip S3 upload if file already exists (idempotency)
        notification_manager: Optional notification manager for alerts
        metrics_tracker: Optional metrics tracker for persistence

    Returns:
        True if successful, False otherwise
    """
    # Initialize metrics
    start_time = datetime.now()
    metrics = ScraperMetrics(
        start_time=start_time,
        end_time=start_time,  # Will be updated at the end
        success=False,
        data_type="yearly",
        date_or_year=str(year)
    )

    logger.info(f"Processing yearly data for {year}")

    try:
        # Create directories
        download_dir = output_dir / "raw" / "yearly" / str(year)
        export_dir = output_dir / "processed" / "yearly" / str(year)
        download_dir.mkdir(parents=True, exist_ok=True)
        export_dir.mkdir(parents=True, exist_ok=True)

        # Download data from FTP
        logger.info("Connecting to Broward County FTP...")
        with BrowardFTPClient() as client:
            files = client.download_yearly_export(year, download_dir)

            if not files:
                logger.error(f"No files downloaded for year {year}")
                metrics.error_message = f"No files downloaded for year {year}"
                return False

        metrics.files_downloaded = len(files)

        # Parse data (yearly files have same format as daily, just different names)
        doc_rec_path = files.get('doc-rec.txt')
        nme_rec_path = files.get('nme-rec.txt')

        if not doc_rec_path or not nme_rec_path:
            logger.error("Missing required data files")
            metrics.error_message = "Missing required data files"
            return False

        logger.info("Parsing ALL mortgage data for entire year...")
        logger.info("NOTE: This may take several minutes for a full year of data...")
        mortgages = parse_broward_data(doc_rec_path, nme_rec_path)

        if not mortgages:
            logger.warning("No mortgages found")
            metrics.error_message = "No mortgages found"
            return False

        # Track metrics
        metrics.mortgages_count = len(mortgages)
        metrics.mortgages_over_1m = len([m for m in mortgages if m.document.amount >= 1_000_000])
        metrics.total_volume = sum(float(m.document.amount) for m in mortgages)

        # Export data (JSON only)
        logger.info("Exporting to JSON...")
        json_path = export_dir / f"mortgages_{year}.json"
        MortgageExporter.to_json(mortgages, json_path)

        # Upload to S3 if requested
        if upload_s3:
            logger.info("Uploading to S3...")
            success = upload_to_s3(
                json_path,
                year=year,
                state="florida",
                county="broward",
                skip_if_exists=skip_if_exists
            )
            if not success:
                logger.error("S3 upload failed")
                metrics.error_message = "S3 upload failed"
                return False
            metrics.s3_uploaded = True

        # Log summary
        logger.info(f"Year: {year} | Mortgages: {metrics.mortgages_count} | ≥$1M: {metrics.mortgages_over_1m} | Volume: ${metrics.total_volume:,.2f}")
        logger.info(f"Output: {json_path.absolute()}")

        # Mark as successful
        metrics.success = True
        return True

    except Exception as e:
        logger.error(f"Failed to process yearly data for {year}: {e}", exc_info=True)
        metrics.error_message = str(e)
        return False

    finally:
        # Update end time
        metrics.end_time = datetime.now()

        # Send notifications
        if notification_manager:
            if metrics.success:
                notification_manager.send_success_notification(metrics)
            else:
                notification_manager.send_failure_notification(metrics)

        # Save metrics
        if metrics_tracker:
            metrics_tracker.save_metrics(metrics)


def download_date_range(
    start_date: datetime,
    end_date: datetime,
    output_dir: Path,
    upload_s3: bool = False,
    skip_if_exists: bool = True,
    notification_manager: Optional[NotificationManager] = None,
    metrics_tracker: Optional[MetricsTracker] = None
) -> bool:
    """
    Download and extract ALL mortgage data for a date range

    Args:
        start_date: Starting date
        end_date: Ending date
        output_dir: Output directory for results
        upload_s3: Whether to upload results to S3
        skip_if_exists: Skip S3 upload if file already exists
        notification_manager: Optional notification manager for alerts
        metrics_tracker: Optional metrics tracker for persistence

    Returns:
        True if all dates succeeded, False if any failed
    """
    current = start_date
    success_count = 0
    error_count = 0

    while current <= end_date:
        success = download_and_analyze_daily(
            current, output_dir, upload_s3, skip_if_exists,
            notification_manager, metrics_tracker
        )
        if success:
            success_count += 1
        else:
            error_count += 1

        current += timedelta(days=1)

    logger.info(f"\n{'='*80}")
    logger.info("BATCH PROCESSING COMPLETE")
    logger.info(f"{'='*80}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Errors:     {error_count}")
    logger.info(f"{'='*80}\n")

    return error_count == 0


def download_year_range(
    start_year: int,
    end_year: int,
    output_dir: Path,
    upload_s3: bool = False,
    skip_if_exists: bool = True,
    notification_manager: Optional[NotificationManager] = None,
    metrics_tracker: Optional[MetricsTracker] = None
) -> bool:
    """
    Download and extract ALL mortgage data for a range of years

    Args:
        start_year: Starting year (e.g., 2020)
        end_year: Ending year (e.g., 2024)
        output_dir: Output directory for results
        upload_s3: Whether to upload results to S3
        skip_if_exists: Skip S3 upload if file already exists
        notification_manager: Optional notification manager for alerts
        metrics_tracker: Optional metrics tracker for persistence

    Returns:
        True if all years succeeded, False if any failed
    """
    success_count = 0
    error_count = 0

    for year in range(start_year, end_year + 1):
        success = download_and_analyze_yearly(
            year, output_dir, upload_s3, skip_if_exists,
            notification_manager, metrics_tracker
        )
        if success:
            success_count += 1
        else:
            error_count += 1

    logger.info(f"\n{'='*80}")
    logger.info("BATCH PROCESSING COMPLETE")
    logger.info(f"{'='*80}")
    logger.info(f"Successful: {success_count} years")
    logger.info(f"Errors:     {error_count} years")
    logger.info(f"{'='*80}\n")

    return error_count == 0


def main():
    parser = argparse.ArgumentParser(
        description='Broward County Mortgage Data Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  DAILY DATA (last 10 days available):
    # Download and extract ALL mortgages for a specific date
    python main.py --date 2026-03-01

    # Download last 7 days of data
    python main.py --days 7

    # Download date range
    python main.py --start-date 2026-03-01 --end-date 2026-03-07

  YEARLY DATA (1978-present available):
    # Download full year of data
    python main.py --year 2024

    # Download multiple years
    python main.py --start-year 2020 --end-year 2024

  OUTPUT & S3 UPLOAD:
    # Specify custom output directory
    python main.py --year 2024 --output-dir /path/to/output

    # Upload results to S3 (requires AWS credentials in env vars)
    python main.py --date 2026-03-02 --upload-to-s3

    # S3 bucket structure:
    #   s3://bucket/florida/broward/daily/YYYY/MM/DD/mortgages.json
    #   s3://bucket/florida/broward/yearly/YYYY/mortgages.json

Note: ALL mortgages are exported regardless of amount.
      Filter for CRE loans in your downstream analysis based on your criteria.
      Yearly files contain entire year of data (large files, slower processing).

Required Environment Variables for S3:
  S3_BUCKET              - S3 bucket name
  AWS_ACCESS_KEY_ID      - AWS access key
  AWS_SECRET_ACCESS_KEY  - AWS secret key
        """
    )

    parser.add_argument(
        '--date',
        type=str,
        help='Specific date to download (YYYY-MM-DD format). Limited to last 10 days.'
    )

    parser.add_argument(
        '--days',
        type=int,
        help='Download last N days of data (max 10 days available)'
    )

    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date for range download (YYYY-MM-DD). Limited to last 10 days.'
    )

    parser.add_argument(
        '--end-date',
        type=str,
        help='End date for range download (YYYY-MM-DD). Limited to last 10 days.'
    )

    parser.add_argument(
        '--year',
        type=int,
        help='Specific year to download (YYYY format, e.g., 2024). Historical data from 1978-present.'
    )

    parser.add_argument(
        '--start-year',
        type=int,
        help='Start year for range download (e.g., 2020)'
    )

    parser.add_argument(
        '--end-year',
        type=int,
        help='End year for range download (e.g., 2024)'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='data',
        help='Output directory for downloaded data and reports (default: data)'
    )

    parser.add_argument(
        '--upload-to-s3',
        action='store_true',
        help='Upload results to S3 after processing (requires AWS credentials in env vars)'
    )

    parser.add_argument(
        '--skip-if-exists',
        action='store_true',
        default=True,
        help='Skip S3 upload if file already exists (default: True, idempotency)'
    )

    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging level (default: INFO)'
    )

    parser.add_argument(
        '--log-file',
        type=str,
        help='Optional log file path (logs to stdout by default)'
    )

    args = parser.parse_args()

    # Setup logging
    global logger
    setup_logging(
        log_level=args.log_level,
        log_file=Path(args.log_file) if args.log_file else None
    )
    logger = get_logger(__name__)

    try:
        output_dir = Path(args.output_dir)
        upload_s3 = args.upload_to_s3
        skip_if_exists = args.skip_if_exists
        success = False

        # Initialize notification and metrics tracking
        notification_manager = NotificationManager()
        metrics_tracker = MetricsTracker(output_dir / "metrics")

        # Determine what to download - prioritize yearly over daily
        if args.year:
            # Single year
            success = download_and_analyze_yearly(
                args.year, output_dir, upload_s3, skip_if_exists,
                notification_manager, metrics_tracker
            )

        elif args.start_year and args.end_year:
            # Year range
            success = download_year_range(
                args.start_year, args.end_year, output_dir, upload_s3, skip_if_exists,
                notification_manager, metrics_tracker
            )

        elif args.date:
            # Single date
            date = datetime.strptime(args.date, '%Y-%m-%d')
            success = download_and_analyze_daily(
                date, output_dir, upload_s3, skip_if_exists,
                notification_manager, metrics_tracker
            )

        elif args.days:
            # Last N days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=args.days - 1)
            success = download_date_range(
                start_date, end_date, output_dir, upload_s3, skip_if_exists,
                notification_manager, metrics_tracker
            )

        elif args.start_date and args.end_date:
            # Date range
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
            success = download_date_range(
                start_date, end_date, output_dir, upload_s3, skip_if_exists,
                notification_manager, metrics_tracker
            )

        else:
            # Default: download yesterday's data
            yesterday = datetime.now() - timedelta(days=1)
            logger.info("No arguments provided, downloading yesterday's data")
            success = download_and_analyze_daily(
                yesterday, output_dir, upload_s3, skip_if_exists,
                notification_manager, metrics_tracker
            )

        # Exit with appropriate status code
        if success:
            logger.info("✓ All operations completed successfully")
            sys.exit(0)
        else:
            logger.error("✗ One or more operations failed")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        sys.exit(130)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
