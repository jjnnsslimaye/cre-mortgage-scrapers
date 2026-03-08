"""
Export functionality for mortgage data - JSON only
"""
from pathlib import Path
from typing import List
import json
import logging

from models import MortgageRecord

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MortgageExporter:
    """Export mortgage data to JSON"""

    @staticmethod
    def to_json(
        mortgages: List[MortgageRecord],
        output_path: Path
    ) -> Path:
        """
        Export ALL mortgages to JSON

        Args:
            mortgages: List of MortgageRecord objects
            output_path: Path for output JSON file

        Returns:
            Path to created JSON file
        """
        data = [m.to_dict() for m in mortgages]

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, default=str)

        logger.info(f"Exported {len(mortgages)} mortgages to {output_path}")

        return output_path
