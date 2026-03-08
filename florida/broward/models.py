"""
Data models for Broward County Official Records
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from decimal import Decimal


@dataclass
class DocumentRecord:
    """Official record document"""
    doc_number: str
    record_date: datetime
    record_time: str
    doc_type: str
    amount: Decimal
    status: str
    legal_description: Optional[str] = None
    parcel_id: Optional[str] = None
    doc_stamps: Optional[Decimal] = None
    intangible_tax: Optional[Decimal] = None
    page_count: int = 0
    consideration: Optional[Decimal] = None
    recording_info: Optional[str] = None

    # Computed fields
    parties: List['PartyRecord'] = field(default_factory=list)

    @property
    def is_mortgage(self) -> bool:
        """Check if document is a mortgage"""
        return self.doc_type in ['M', 'MTG', 'MORTGAGE']

    @property
    def is_deed(self) -> bool:
        """Check if document is a deed"""
        return self.doc_type in ['D', 'DEED', 'WD', 'QCD']

    @property
    def is_satisfaction(self) -> bool:
        """Check if document is a satisfaction/release"""
        return self.doc_type in ['RST', 'SAT', 'SATISFACTION']

    @property
    def is_assignment(self) -> bool:
        """Check if document is an assignment"""
        return self.doc_type in ['AST', 'ASSIGN', 'ASSIGNMENT']

    # Removed is_commercial property - filter downstream in your analysis

    def __str__(self):
        return (
            f"Doc #{self.doc_number} | {self.doc_type} | "
            f"{self.record_date.strftime('%Y-%m-%d')} | "
            f"${self.amount:,.2f}"
        )


@dataclass
class PartyRecord:
    """Party (name) associated with a document"""
    doc_number: str
    name: str
    role: str  # D=Debtor/Grantor, R=Lender/Grantee
    sequence: int
    additional_info: Optional[str] = None

    @property
    def is_borrower(self) -> bool:
        """Check if party is borrower/debtor/grantor"""
        return self.role == 'D'

    @property
    def is_lender(self) -> bool:
        """Check if party is lender/creditor/grantee"""
        return self.role == 'R'

    def __str__(self):
        role_name = "Borrower" if self.is_borrower else "Lender"
        return f"{role_name}: {self.name}"


@dataclass
class MortgageRecord:
    """
    Complete mortgage record with all parties
    Combines document and party data
    """
    document: DocumentRecord
    borrowers: List[PartyRecord] = field(default_factory=list)
    lenders: List[PartyRecord] = field(default_factory=list)

    @property
    def primary_borrower(self) -> Optional[str]:
        """Get primary borrower name"""
        if self.borrowers:
            return self.borrowers[0].name
        return None

    @property
    def primary_lender(self) -> Optional[str]:
        """Get primary lender name"""
        if self.lenders:
            return self.lenders[0].name
        return None

    @property
    def all_borrowers_str(self) -> str:
        """Get all borrower names as comma-separated string"""
        return ", ".join([b.name for b in self.borrowers])

    @property
    def all_lenders_str(self) -> str:
        """Get all lender names as comma-separated string"""
        return ", ".join([l.name for l in self.lenders])

    def to_dict(self) -> dict:
        """Convert to dictionary for export"""
        return {
            'doc_number': self.document.doc_number,
            'record_date': self.document.record_date.strftime('%Y-%m-%d'),
            'record_time': self.document.record_time,
            'doc_type': self.document.doc_type,
            'loan_amount': float(self.document.amount),
            'borrowers': self.all_borrowers_str,
            'lenders': self.all_lenders_str,
            'parcel_id': self.document.parcel_id,
            'legal_description': self.document.legal_description,
            'doc_stamps': float(self.document.doc_stamps) if self.document.doc_stamps else None,
            'intangible_tax': float(self.document.intangible_tax) if self.document.intangible_tax else None,
            'page_count': self.document.page_count,
        }

    def __str__(self):
        return (
            f"\n{'='*80}\n"
            f"MORTGAGE: Doc #{self.document.doc_number}\n"
            f"Date: {self.document.record_date.strftime('%Y-%m-%d')}\n"
            f"Amount: ${self.document.amount:,.2f}\n"
            f"Borrower(s): {self.all_borrowers_str}\n"
            f"Lender(s): {self.all_lenders_str}\n"
            f"Property: {self.document.legal_description or 'N/A'}\n"
            f"Parcel ID: {self.document.parcel_id or 'N/A'}\n"
            f"Commercial: {'Yes' if self.document.is_commercial else 'No'}\n"
            f"{'='*80}"
        )


# Document type codes reference
DOC_TYPE_CODES = {
    'M': 'Mortgage',
    'MTG': 'Mortgage',
    'D': 'Deed',
    'WD': 'Warranty Deed',
    'QCD': 'Quit Claim Deed',
    'RST': 'Release/Satisfaction',
    'SAT': 'Satisfaction',
    'AST': 'Assignment',
    'AFF': 'Affidavit',
    'NOC': 'Notice of Commencement',
    'LIS': 'Lis Pendens',
    'CP': 'Court Paper',
    'NL': 'Notice of Lien',
    'RL': 'Release of Lien',
}
