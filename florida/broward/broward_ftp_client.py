"""
Broward County Official Records FTP Client
Handles connection, file listing, and data retrieval
"""
import paramiko
import stat
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BrowardFTPClient:
    """Client for accessing Broward County Official Records SFTP"""

    def __init__(
        self,
        host: str = "BCFTP.Broward.org",
        port: int = 22,
        username: str = "crpublic",
        password: str = "crpublic"
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.ssh = None
        self.sftp = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((paramiko.SSHException, OSError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def connect(self) -> bool:
        """Establish SFTP connection with automatic retries"""
        try:
            logger.info(f"Connecting to {self.host}:{self.port}...")
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            self.ssh.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=30
            )

            self.sftp = self.ssh.open_sftp()
            logger.info("✓ Connected successfully")
            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise  # Re-raise to trigger retry

    def disconnect(self):
        """Close SFTP connection"""
        if self.sftp:
            self.sftp.close()
        if self.ssh:
            self.ssh.close()
        logger.info("Disconnected")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((OSError, IOError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def _download_file_with_retry(self, remote_path: str, local_path: Path) -> int:
        """
        Download a single file with automatic retries

        Args:
            remote_path: Remote file path on SFTP server
            local_path: Local path to save file

        Returns:
            File size in bytes

        Raises:
            FileNotFoundError: If file doesn't exist on server
            Exception: For other download errors after retries exhausted
        """
        if not self.sftp:
            raise ConnectionError("Not connected. Call connect() first.")

        self.sftp.get(remote_path, str(local_path))
        return local_path.stat().st_size

    def list_daily_files(self) -> List[str]:
        """List all files in the daily Official_Records_Download directory"""
        if not self.sftp:
            raise ConnectionError("Not connected. Call connect() first.")

        return self.sftp.listdir("Official_Records_Download")

    def get_available_dates(self) -> List[str]:
        """Get list of available dates in the daily download directory"""
        files = self.list_daily_files()

        # Extract unique date prefixes from doc-ver.txt files
        dates = set()
        for f in files:
            if "doc-ver.txt" in f and not "rng" in f:
                # Extract date prefix (e.g., "03-02-2026" from "03-02-2026doc-ver.txt")
                date_str = f.replace("doc-ver.txt", "")
                dates.add(date_str)

        return sorted(list(dates), reverse=True)

    def download_daily_files(
        self,
        date_prefix: str,
        local_dir: Path,
        include_images: bool = False
    ) -> dict:
        """
        Download all files for a specific date

        Args:
            date_prefix: Date string like "03-02-2026"
            local_dir: Local directory to save files
            include_images: Whether to download the img.zip file (can be very large)

        Returns:
            Dictionary of downloaded file paths
        """
        if not self.sftp:
            raise ConnectionError("Not connected. Call connect() first.")

        local_dir = Path(local_dir)
        local_dir.mkdir(parents=True, exist_ok=True)

        # Define files to download
        file_types = [
            "doc-ver.txt",      # Document records
            "doc-ver-rng.txt",  # Document range
            "nme-ver.txt",      # Name index (parties)
            "lgl-ver.txt",      # Legal descriptions
            "lnk-ver.txt",      # Links between documents
        ]

        if include_images:
            file_types.append("img.zip")

        downloaded = {}

        for file_type in file_types:
            filename = f"{date_prefix}{file_type}"
            remote_path = f"Official_Records_Download/{filename}"
            local_path = local_dir / filename

            try:
                logger.info(f"Downloading {filename}...")
                file_size = self._download_file_with_retry(remote_path, local_path)
                logger.info(f"  ✓ {filename} ({file_size:,} bytes)")
                downloaded[file_type] = local_path

            except FileNotFoundError:
                logger.warning(f"  ✗ {filename} not found on server")
            except Exception as e:
                logger.error(f"  ✗ Error downloading {filename} after retries: {e}")

        return downloaded

    def download_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        local_dir: Path,
        include_images: bool = False
    ) -> List[dict]:
        """
        Download files for a date range

        Args:
            start_date: Starting date
            end_date: Ending date
            local_dir: Base directory for downloads
            include_images: Whether to download image files

        Returns:
            List of downloaded file dictionaries
        """
        all_downloads = []
        current = start_date

        while current <= end_date:
            date_prefix = current.strftime("%m-%d-%Y")
            date_dir = local_dir / current.strftime("%Y-%m-%d")

            logger.info(f"\n{'='*60}")
            logger.info(f"Processing date: {date_prefix}")
            logger.info(f"{'='*60}")

            try:
                downloaded = self.download_daily_files(
                    date_prefix,
                    date_dir,
                    include_images
                )
                if downloaded:
                    all_downloads.append({
                        'date': current,
                        'files': downloaded
                    })
            except Exception as e:
                logger.error(f"Error processing {date_prefix}: {e}")

            current += timedelta(days=1)

        return all_downloads

    def list_yearly_exports(self) -> List[str]:
        """List all available yearly export files"""
        if not self.sftp:
            raise ConnectionError("Not connected. Call connect() first.")

        files = self.sftp.listdir("OR_Yearly_Exports")
        return sorted([f for f in files if f.startswith("CY")])

    def download_yearly_export(
        self,
        year: int,
        local_dir: Path
    ) -> dict:
        """
        Download yearly export files for a specific year

        Args:
            year: Calendar year (e.g., 2024)
            local_dir: Local directory to save files

        Returns:
            Dictionary of downloaded file paths
        """
        if not self.sftp:
            raise ConnectionError("Not connected. Call connect() first.")

        local_dir = Path(local_dir)
        local_dir.mkdir(parents=True, exist_ok=True)

        file_types = [
            "doc-rec.txt",  # Document records
            "lnk-rec.txt",  # Links
            "nme-rec.txt",  # Names
        ]

        downloaded = {}

        for file_type in file_types:
            filename = f"CY{year}{file_type}"
            remote_path = f"OR_Yearly_Exports/{filename}"
            local_path = local_dir / filename

            try:
                logger.info(f"Downloading {filename}...")
                file_size = self._download_file_with_retry(remote_path, local_path)
                logger.info(f"  ✓ {filename} ({file_size:,} bytes)")
                downloaded[file_type] = local_path

            except FileNotFoundError:
                logger.warning(f"  ✗ {filename} not found")
            except Exception as e:
                logger.error(f"  ✗ Error downloading {filename} after retries: {e}")

        return downloaded

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


if __name__ == "__main__":
    # Example usage
    with BrowardFTPClient() as client:
        # List available dates
        print("\nAvailable recent dates:")
        dates = client.get_available_dates()
        for date in dates[:5]:
            print(f"  - {date}")

        # Download most recent date
        if dates:
            most_recent = dates[0]
            print(f"\nDownloading data for {most_recent}...")
            files = client.download_daily_files(
                most_recent,
                Path("data/daily") / most_recent.replace("-", ""),
                include_images=False
            )
            print(f"\nDownloaded {len(files)} files")
