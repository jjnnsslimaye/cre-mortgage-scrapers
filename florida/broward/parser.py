"""
Parser for Broward County Official Records data files
"""
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from decimal import Decimal, InvalidOperation
import logging

from models import DocumentRecord, PartyRecord, MortgageRecord

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BrowardRecordsParser:
    """Parser for Broward County pipe-delimited data files"""

    @staticmethod
    def parse_doc_ver_file(file_path: Path) -> List[DocumentRecord]:
        """
        Parse doc-ver.txt file containing document records

        Format (pipe-delimited):
        doc_number|date_num|date_str|time|doc_type|amount|...|status|legal_desc|parcel_id|doc_stamps|intangible_tax|pages|...
        """
        records = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        fields = line.strip().split('|')

                        if len(fields) < 15:
                            continue

                        # Parse fields
                        doc_number = fields[0]
                        date_num = fields[1]
                        time_str = fields[3]
                        doc_type = fields[4]
                        amount_str = fields[5]
                        status = fields[8]
                        legal_desc = fields[9] if len(fields) > 9 and fields[9] else None
                        parcel_id = fields[10] if len(fields) > 10 and fields[10] else None
                        doc_stamps_str = fields[11] if len(fields) > 11 else None
                        intangible_str = fields[12] if len(fields) > 12 else None
                        page_count_str = fields[13] if len(fields) > 13 else "0"

                        # Convert date (format: YYYYMMDD)
                        try:
                            record_date = datetime.strptime(date_num, '%Y%m%d')
                        except ValueError:
                            logger.warning(f"Invalid date format at line {line_num}: {date_num}")
                            continue

                        # Convert amount
                        try:
                            amount = Decimal(amount_str) if amount_str else Decimal('0.00')
                        except (InvalidOperation, ValueError):
                            amount = Decimal('0.00')

                        # Convert doc stamps and intangible tax
                        try:
                            doc_stamps = Decimal(doc_stamps_str) if doc_stamps_str else None
                        except (InvalidOperation, ValueError):
                            doc_stamps = None

                        try:
                            intangible_tax = Decimal(intangible_str) if intangible_str else None
                        except (InvalidOperation, ValueError):
                            intangible_tax = None

                        # Convert page count
                        try:
                            page_count = int(page_count_str) if page_count_str else 0
                        except ValueError:
                            page_count = 0

                        record = DocumentRecord(
                            doc_number=doc_number,
                            record_date=record_date,
                            record_time=time_str,
                            doc_type=doc_type,
                            amount=amount,
                            status=status,
                            legal_description=legal_desc,
                            parcel_id=parcel_id,
                            doc_stamps=doc_stamps,
                            intangible_tax=intangible_tax,
                            page_count=page_count
                        )

                        records.append(record)

                    except Exception as e:
                        logger.debug(f"Error parsing line {line_num}: {e}")
                        continue

            logger.info(f"Parsed {len(records)} documents from {file_path.name}")
            return records

        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return []

    @staticmethod
    def parse_nme_ver_file(file_path: Path) -> List[PartyRecord]:
        """
        Parse nme-ver.txt file containing party/name records

        Format (pipe-delimited):
        doc_number|name|role|sequence|additional_info
        Role: D=Debtor/Grantor/Borrower, R=Lender/Grantee
        """
        records = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        fields = line.strip().split('|')

                        if len(fields) < 4:
                            continue

                        doc_number = fields[0]
                        name = fields[1]
                        role = fields[2]
                        sequence_str = fields[3]
                        additional = fields[4] if len(fields) > 4 and fields[4] else None

                        try:
                            sequence = int(sequence_str)
                        except ValueError:
                            sequence = 0

                        record = PartyRecord(
                            doc_number=doc_number,
                            name=name,
                            role=role,
                            sequence=sequence,
                            additional_info=additional
                        )

                        records.append(record)

                    except Exception as e:
                        logger.debug(f"Error parsing line {line_num}: {e}")
                        continue

            logger.info(f"Parsed {len(records)} party records from {file_path.name}")
            return records

        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return []

    @staticmethod
    def combine_records(
        documents: List[DocumentRecord],
        parties: List[PartyRecord]
    ) -> Dict[str, DocumentRecord]:
        """
        Combine document and party records

        Returns:
            Dictionary mapping doc_number to DocumentRecord with parties attached
        """
        # Create document lookup
        doc_dict = {doc.doc_number: doc for doc in documents}

        # Attach parties to documents
        for party in parties:
            if party.doc_number in doc_dict:
                doc_dict[party.doc_number].parties.append(party)

        return doc_dict

    @staticmethod
    def extract_mortgages(
        doc_dict: Dict[str, DocumentRecord]
    ) -> List[MortgageRecord]:
        """
        Extract ALL mortgage records from combined document/party data
        No filtering - export everything and filter downstream in your analysis

        Args:
            doc_dict: Dictionary of documents with parties

        Returns:
            List of MortgageRecord objects (all mortgages, no amount filtering)
        """
        mortgages = []

        for doc in doc_dict.values():
            # Filter for mortgages only
            if not doc.is_mortgage:
                continue

            # Separate borrowers and lenders
            borrowers = [p for p in doc.parties if p.is_borrower]
            lenders = [p for p in doc.parties if p.is_lender]

            mortgage = MortgageRecord(
                document=doc,
                borrowers=borrowers,
                lenders=lenders
            )

            mortgages.append(mortgage)

        return mortgages


def parse_broward_data(
    doc_ver_path: Path,
    nme_ver_path: Path
) -> List[MortgageRecord]:
    """
    Convenience function to parse Broward data files and extract ALL mortgages

    Args:
        doc_ver_path: Path to doc-ver.txt file
        nme_ver_path: Path to nme-ver.txt file

    Returns:
        List of ALL MortgageRecord objects (no filtering)
    """
    parser = BrowardRecordsParser()

    # Parse files
    logger.info("Parsing document records...")
    documents = parser.parse_doc_ver_file(doc_ver_path)

    logger.info("Parsing party records...")
    parties = parser.parse_nme_ver_file(nme_ver_path)

    # Combine
    logger.info("Combining records...")
    doc_dict = parser.combine_records(documents, parties)

    # Extract ALL mortgages (no filtering)
    logger.info("Extracting ALL mortgage records...")
    mortgages = parser.extract_mortgages(doc_dict)

    logger.info(f"Found {len(mortgages)} mortgage records")

    return mortgages
