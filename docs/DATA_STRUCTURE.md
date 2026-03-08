# Broward County Official Records Data Structure

## Complete Data Breakdown: What We Download, Use, and Ignore

---

## RAW FILES DOWNLOADED FROM FTP

For each date, Broward County provides 5 text files + 1 optional image archive:

### 1. **doc-ver.txt** - Document Records (MAIN FILE)
- **Size**: ~2,700 records/day, ~230KB
- **Format**: Pipe-delimited (20 fields)
- **Contains**: Core document information for ALL recorded documents

#### Complete Field Structure:
```
Field  1: Document Number (e.g., 120722908) - UNIQUE ID
Field  2: Record Date Numeric (e.g., 20260302) - YYYYMMDD
Field  3: Record Date String (e.g., 03/02/2026) - MM/DD/YYYY
Field  4: Record Time (e.g., 084327) - HHMMSS
Field  5: Document Type (e.g., M, D, RST, AST, NOC, AFF)
Field  6: Amount/Consideration (e.g., 2600000.00)
Field  7: [UNKNOWN] - Usually empty
Field  8: [UNKNOWN] - Usually empty
Field  9: Status (e.g., O = Official Record)
Field 10: Legal Description (e.g., "PARKWOOD V 140-6 B LOT 28")
Field 11: Parcel ID (e.g., 484208040280)
Field 12: Documentary Stamps (e.g., 9100.00)
Field 13: Intangible Tax (e.g., 5200.00)
Field 14: Page Count (e.g., 3)
Field 15: [UNKNOWN] - Usually 0
Field 16: Verification Status (e.g., V = Verified)
Field 17: [UNKNOWN] - Usually empty
Field 18: Record Type (e.g., E = Electronic)
Field 19: [UNKNOWN] - Usually empty
Field 20: Case/Reference Number (e.g., COINX-25-054771) - Sometimes present
```

#### What We EXTRACT from doc-ver.txt:
- ✅ Document Number (Field 1) - Our primary key
- ✅ Record Date (Field 2) - Converted to datetime
- ✅ Record Time (Field 4) - Stored as string
- ✅ Document Type (Field 5) - Used for filtering (M, D, RST, etc.)
- ✅ Amount (Field 6) - Converted to Decimal, main CRE filter
- ✅ Status (Field 9) - Stored but not actively used
- ✅ Legal Description (Field 10) - Stored when available
- ✅ Parcel ID (Field 11) - Stored when available
- ✅ Documentary Stamps (Field 12) - Stored, useful for analysis
- ✅ Intangible Tax (Field 13) - Stored, useful for analysis
- ✅ Page Count (Field 14) - Stored but not actively used

#### What We IGNORE from doc-ver.txt:
- ❌ Record Date String (Field 3) - Redundant with Field 2
- ❌ Fields 7, 8 - Unknown purpose, usually empty
- ❌ Field 15 - Unknown purpose
- ❌ Verification Status (Field 16) - Not relevant for our analysis
- ❌ Field 17 - Unknown purpose
- ❌ Record Type (Field 18) - Not actively filtered
- ❌ Field 19 - Unknown purpose
- ❌ Case/Reference Number (Field 20) - Not currently used

---

### 2. **nme-ver.txt** - Name/Party Records (CRITICAL)
- **Size**: ~6,900 records/day, ~260KB
- **Format**: Pipe-delimited (5 fields)
- **Contains**: ALL parties associated with each document

#### Complete Field Structure:
```
Field 1: Document Number (e.g., 120722908) - FOREIGN KEY to doc-ver
Field 2: Name (e.g., "CONSTELLATION ARTHUR LLC", "SMITH,JOHN")
Field 3: Role Code
         D = Debtor/Grantor/Borrower (person taking out loan or selling property)
         R = Creditor/Grantee/Lender (bank/lender or property buyer)
Field 4: Sequence Number (1, 2, 3...) - Order of parties
Field 5: Additional Info - Usually empty
```

#### Key Characteristics:
- **Multiple rows per document**: One document can have 2-10+ party records
- **Example**: A mortgage typically has:
  - 1-3 borrowers (Role = D)
  - 1-2 lenders (Role = R, often including MERS)

#### What We EXTRACT from nme-ver.txt:
- ✅ Document Number (Field 1) - Used to join with doc-ver
- ✅ Name (Field 2) - Stored as borrower or lender
- ✅ Role (Field 3) - Used to separate borrowers (D) from lenders (R)
- ✅ Sequence (Field 4) - Determines "primary" party (sequence=1)

#### What We IGNORE from nme-ver.txt:
- ❌ Additional Info (Field 5) - Usually empty

#### How We JOIN nme-ver with doc-ver:
```python
# For each document in doc-ver.txt
doc = DocumentRecord(doc_number="120722910", amount=2600000, ...)

# Find ALL matching parties in nme-ver.txt
parties = [
    PartyRecord(doc_number="120722910", name="CONSTELLATION ARTHUR LLC", role="D", seq=1),
    PartyRecord(doc_number="120722910", name="DEERFIELD PETRO HOLDING LLC", role="D", seq=2),
    PartyRecord(doc_number="120722910", name="STANDARD INSURANCE COMPANY", role="R", seq=1)
]

# Attach parties to document
doc.parties = parties

# Separate by role
borrowers = [p for p in parties if p.role == "D"]  # 2 borrowers
lenders = [p for p in parties if p.role == "R"]     # 1 lender
```

---

### 3. **lgl-ver.txt** - Legal Descriptions (DOWNLOADED BUT NOT PARSED)
- **Size**: ~360 records/day, ~34KB
- **Format**: Pipe-delimited (4 fields)
- **Contains**: Detailed legal descriptions for properties

#### Complete Field Structure:
```
Field 1: Document Number (e.g., 120722915)
Field 2: Legal Description (e.g., "PARKWOOD V 140-6 B LOT 28")
Field 3: Parcel ID (e.g., 484208040280)
Field 4: [UNKNOWN] - Usually empty
```

#### Current Status: **DOWNLOADED BUT NOT USED**

**Why we download it:** The legal descriptions in this file are MORE DETAILED than what's in doc-ver.txt Field 10.

**Why we DON'T currently parse it:**
- Not all documents have entries here (~360/2699 = 13%)
- The doc-ver.txt already contains basic legal description in Field 10
- For MVP, document type + amount is sufficient for CRE identification

**Future Enhancement Opportunity:**
```python
# You COULD parse this file to enrich property data:
def parse_lgl_ver_file(file_path):
    legal_dict = {}
    for line in file:
        fields = line.split('|')
        doc_number = fields[0]
        legal_desc = fields[1]
        parcel_id = fields[2]
        legal_dict[doc_number] = {
            'legal_description': legal_desc,
            'parcel_id': parcel_id
        }
    return legal_dict

# Then enhance documents with this data
if doc.doc_number in legal_dict:
    doc.legal_description = legal_dict[doc.doc_number]['legal_description']
    doc.parcel_id = legal_dict[doc.doc_number]['parcel_id']
```

---

### 4. **lnk-ver.txt** - Document Links (DOWNLOADED BUT NOT PARSED)
- **Size**: ~900 records/day, ~40KB
- **Format**: Pipe-delimited (12 fields)
- **Contains**: Relationships between documents

#### Complete Field Structure:
```
Field  1: Current Document Number (e.g., 120722912)
Field  2-3: [UNKNOWN]
Field  4: Status (e.g., O)
Field  5: Current Document Type (e.g., RST)
Field  6: Related Document Number (e.g., 120428859)
Field  7-8: [UNKNOWN]
Field  9: Related Status
Field 10: Related Document Type (e.g., NOC, M)
Field 11: Description (e.g., "120428859 [NOC]")
Field 12: [UNKNOWN]
```

#### Current Status: **DOWNLOADED BUT NOT USED**

**Why we download it:** Links show relationships like:
- RST (Release/Satisfaction) → Original Mortgage
- AST (Assignment) → Original Mortgage
- Amendments → Original Documents

**Why we DON'T currently parse it:**
- Complex relationships require graph database or sophisticated tracking
- For MVP, we're identifying NEW mortgages, not tracking lifecycle
- Would require historical data to be useful

**Future Enhancement Opportunity:**
```python
# Track mortgage lifecycle for distress signals:
# Example: Mortgage → Assignment → Assignment → Satisfaction
# Multiple assignments could indicate distress

links = {
    '120722912': {  # RST (satisfaction/release)
        'relates_to': '120428859',  # Original mortgage
        'type': 'SATISFACTION'
    }
}

# Could build mortgage lifecycle:
mortgage_lifecycle = {
    'original': '120428859',
    'events': [
        {'date': '2025-01-15', 'type': 'ORIGINATION', 'amount': 500000},
        {'date': '2025-06-20', 'type': 'ASSIGNMENT', 'to': 'NEW LENDER'},
        {'date': '2026-03-02', 'type': 'SATISFACTION', 'doc': '120722912'}
    ]
}
```

---

### 5. **doc-ver-rng.txt** - Document Range (METADATA ONLY)
- **Size**: 2 lines, ~4KB
- **Format**: Plain text, 2 numbers
- **Contains**: Start and end document numbers for the day

#### Complete Structure:
```
120722908    ← First document number of the day
120725606    ← Last document number of the day
```

#### Current Status: **DOWNLOADED BUT NOT USED**

**Purpose:** Quality control / validation
- Confirms you have complete data
- Can check if any document numbers are missing

---

### 6. **img.zip** - Scanned Document Images (NOT DOWNLOADED)
- **Size**: ~400-600 MB per day
- **Format**: ZIP archive containing PDF/image files
- **Contains**: Actual scanned images of recorded documents

#### Current Status: **INTENTIONALLY SKIPPED**

**Why we DON'T download images:**
- ❌ Massive file size (500MB vs 0.5MB for text data)
- ❌ Requires OCR/parsing if needed
- ❌ Not necessary for identifying CRE loans (text data sufficient)
- ❌ Would slow down pipeline significantly

**When you WOULD need images:**
- Manual verification of flagged distressed loans
- Extracting data not in text files (rare)
- Legal documentation/evidence
- OCR of handwritten notes or stamps

**Future Enhancement:**
```python
# Could add selective image download:
def download_images_for_docs(doc_numbers: List[str]):
    """Download only images for specific flagged documents"""
    # Download img.zip
    # Extract only files matching doc_numbers
    # Store separately for manual review
```

---

## DATA FLOW: WHAT HAPPENS IN THE PIPELINE

### Step 1: Download (broward_ftp_client.py)
```
FTP Server → Local Disk
├── doc-ver.txt       ✓ DOWNLOADED
├── nme-ver.txt       ✓ DOWNLOADED
├── lgl-ver.txt       ✓ DOWNLOADED (not parsed)
├── lnk-ver.txt       ✓ DOWNLOADED (not parsed)
├── doc-ver-rng.txt   ✓ DOWNLOADED (not parsed)
└── img.zip           ✗ SKIPPED
```

### Step 2: Parse Documents (parser.py)
```
doc-ver.txt (2,699 records)
    ↓
Parse all documents → List[DocumentRecord]
    ↓
Filter by min_amount → 204 mortgages
    ↓
Filter by is_commercial → 17 CRE mortgages (≥$1M)
```

### Step 3: Parse Parties (parser.py)
```
nme-ver.txt (6,935 party records)
    ↓
Parse all parties → List[PartyRecord]
```

### Step 4: Join Data (parser.py)
```
For each DocumentRecord:
    Find matching PartyRecords by doc_number
    Separate into:
        - borrowers (role = 'D')
        - lenders (role = 'R')
    Create MortgageRecord(document, borrowers, lenders)
```

### Step 5: Export (exporter.py)
```
List[MortgageRecord]
    ↓
    ├→ CSV Export (17 CRE mortgages)
    ├→ JSON Export (17 CRE mortgages)
    └→ Summary Report (statistics + rankings)
```

---

## WHAT DATA IS LEFT BEHIND

### 1. Non-Mortgage Documents (81% of records)
From March 2, 2026:
- **Total Documents**: 2,699
- **Mortgages**: 204 (7.6%)
- **Left Behind**: 2,495 (92.4%)

Documents we filter out:
- **D** - Deeds (property sales)
- **RST** - Satisfactions/Releases (loan payoffs)
- **AST** - Assignments (loan transfers)
- **AFF** - Affidavits
- **NOC** - Notices of Commencement (construction)
- **LIS** - Lis Pendens (pending lawsuits)
- **CP** - Court Papers
- Many others...

**Why filter these out:** You're focused on NEW loans, not other document types.

**Future consideration:** You might want RST (satisfactions) to track which loans were paid off (could indicate refinancing or sale under duress).

### 2. Residential Mortgages (91.7% of mortgages)
From March 2, 2026:
- **Total Mortgages**: 204
- **Commercial (≥$1M)**: 17 (8.3%)
- **Residential (<$1M)**: 187 (91.7%)

**Why filter these out:** Your focus is CRE, not residential.

**Limitation:** The $1M threshold is a HEURISTIC, not perfect:
- ❌ Some high-value residential homes (mansion on beach) might be ≥$1M
- ❌ Some small commercial properties might be <$1M (small retail, warehouse)

**Better filtering (future):**
- Check if borrower name contains: LLC, INC, CORP, LP, HOLDINGS, TRUST (commercial indicators)
- Cross-reference with property type in lgl-ver.txt
- Use parcel ID to lookup property use code from property appraiser

### 3. Legal Description Details
- **Documents with legal descriptions**: ~360 (13%)
- **Currently not parsing lgl-ver.txt file**

What you're missing:
- Detailed property descriptions
- Exact lot/block/plat information
- Property location details (beyond parcel ID)

### 4. Document Relationships
- **Document links**: ~900 relationships/day
- **Currently not parsing lnk-ver.txt file**

What you're missing:
- Which RST satisfies which Mortgage
- Which AST transfers which Mortgage
- Amendment chains
- Cross-references to related documents

### 5. Document Images
- **Not downloaded at all**

What you're missing:
- Actual document scans
- Handwritten notes
- Stamps/endorsements
- Physical signature verification

### 6. Historical Data
- **Only downloading current 10-day window**
- **Yearly exports available from 1978-present but not downloaded**

What you're missing:
- Historical mortgage trends
- Same-borrower previous loans
- Refinance patterns
- Long-term lender relationships

---

## DATA QUALITY & LIMITATIONS

### Empty/Missing Fields
Not all documents have all fields populated:

**Legal Descriptions**:
- In doc-ver.txt Field 10: ~13% populated
- Full descriptions in lgl-ver.txt: ~13% of documents

**Parcel IDs**:
- ~13% of documents (same as legal descriptions)

**Documentary Stamps/Intangible Tax**:
- Present on mortgages and deeds with consideration
- Missing on many other document types

### Data Anomalies Observed

**Multiple borrowers on one mortgage:**
```
Doc 120722910:
    Borrower 1: CONSTELLATION ARTHUR LLC
    Borrower 2: DEERFIELD PETRO HOLDING LLC
    Lender: STANDARD INSURANCE COMPANY
```

**Multiple lenders on one mortgage (MERS + actual lender):**
```
Doc 120722916:
    Borrower: AMIEL,JOE
    Lender 1: MORTGAGE ELECTRONIC REGISTRATION SYSTEMS INC
    Lender 2: THE MORTGAGE FIRM INC
```

**High-value "residential" mortgages:**
```
Doc 120723613: $1.2M
    Borrowers: LICCIARDELLO,EDUARDO JOSE + SHUMATE,MARK TRISTAN
    (Two individuals, not LLC - probably luxury home, not CRE)
```

---

## SUMMARY: CURRENT DATA UTILIZATION

### ✅ FULLY UTILIZED (Parsed & Exported)
- Document numbers
- Recording dates/times
- Document types
- Loan amounts
- Borrower names (all)
- Lender names (all)
- Documentary stamps
- Intangible tax
- Basic legal descriptions (from doc-ver Field 10)
- Basic parcel IDs (from doc-ver Field 11)
- Page counts

### 📥 DOWNLOADED BUT NOT PARSED (Available for future use)
- Detailed legal descriptions (lgl-ver.txt)
- Document links/relationships (lnk-ver.txt)
- Document number ranges (doc-ver-rng.txt)

### ❌ NOT DOWNLOADED (Intentionally skipped)
- Document images (img.zip)

### 🔍 FILTERED OUT (Available but ignored)
- Non-mortgage documents (92% of records)
- Residential mortgages <$1M (92% of mortgages)
- Unknown/empty fields in all files

---

## NEXT STEPS FOR ENHANCED CRE IDENTIFICATION

### 1. Parse lgl-ver.txt for better property details
```python
# Add to parser.py:
def parse_lgl_ver_file(file_path):
    # Extract detailed legal descriptions
    # Match to documents by doc_number
    # Enrich MortgageRecord with better property info
```

### 2. Improve CRE detection beyond amount threshold
```python
def is_likely_commercial(mortgage: MortgageRecord) -> bool:
    # Check amount
    if mortgage.document.amount >= 1_000_000:
        # Check borrower name for commercial indicators
        borrower = mortgage.primary_borrower.upper()
        commercial_indicators = ['LLC', 'INC', 'CORP', 'LP', 'LTD',
                                'HOLDINGS', 'TRUST', 'PARTNERS']
        if any(ind in borrower for ind in commercial_indicators):
            return True
    return False
```

### 3. Parse lnk-ver.txt for lifecycle tracking
```python
# Track mortgage → assignment → satisfaction chains
# Identify distress signals (multiple assignments, etc.)
```

### 4. Download yearly exports for historical analysis
```python
# Build database of historical CRE loans
# Track same borrowers over time
# Identify refinance patterns
```

This gives you the complete picture of what's available, what you're using, and what you're leaving on the table.
