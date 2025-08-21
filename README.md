Created by vibe coding with Claude Code. Excuse the code quality.

# Blood Test PDF to CSV Extractor

A robust CLI tool to extract blood test information from lab report PDFs and output the results as CSV files. Supports multiple lab formats including Quest Diagnostics, LabCorp, and Cleveland HeartLab.

## Scripts Overview

### Core Extraction Scripts
- **`pdf_to_csv.py`** - Original rule-based PDF extractor for Quest/LabCorp formats using pattern matching
- **`unified_ai_extractor.py`** - AI-powered extractor using Claude or OpenAI for any PDF format
- **`wellavy_ai_extractor.py`** - Wellavy-specific extractor with intelligent database marker mapping

### API Service
- **`api.py`** - FastAPI service providing HTTP endpoints for PDF extraction
  - `/api/v1/ai-extract` - Basic AI extraction
  - `/api/v1/ai-extract-mapped` - AI extraction with Wellavy database marker mapping
  - `/convert` - Legacy rule-based extraction

### Test Scripts
- **`test_api.py`** - Tests for the API endpoints
- **`test_ai_api.py`** - Tests specifically for AI extraction endpoints

### Utility Scripts
- **`run_unified_extractor.sh`** - Shell script to run the unified AI extractor
- **`install.sh`** - Installation script for dependencies

## Features

- **Multi-format Support**: Handles Quest Diagnostics (Analyte/Value), LabCorp, Function Health Dashboard, and Vibrant America formats
- **Intelligent Format Detection**: Automatically detects and uses the appropriate extraction method
- **Optional Format Override**: Force specific lab format (`--format=quest`, `--format=labcorp`, or `--format=function_health`) when needed
- **Reference Range Extraction**: Optional extraction of reference ranges with `--include-ranges` flag
- **Comprehensive Extraction**: Extracts 80+ markers including CBC, CMP, hormones, lipids, and fatty acids
- **Single CSV Output**: All markers in one file, preserving the original PDF order
- **Flexible Output Formats**: Standard CSV or enhanced CSV with reference ranges
- **Date Auto-detection**: Automatically extracts test dates from PDF content
- **Value Validation**: Validates extracted values against realistic medical ranges
- **API Support**: FastAPI web service for programmatic access
- **Fallback PDF Reading**: Uses PyPDF2 with pdfplumber fallback for robust text extraction
- **Configurable**: JSON-based configuration for markers and extraction settings

## Installation

1. Install Python dependencies:
```bash
pip3 install -r requirements.txt
```

2. Make the script executable:
```bash
chmod +x pdf_to_csv.py
```

Or use the install script:
```bash
./install.sh
```

## Usage

### Basic Usage
```bash
python3 pdf_to_csv.py your_lab_report.pdf
```

This will create a single CSV file: `your_lab_report.csv` containing all extracted markers in the order they appear in the PDF.

### Specify Output File
```bash
python3 pdf_to_csv.py your_lab_report.pdf --output results.csv
```

This creates: `results.csv` with all extracted markers.

### Verbose Output
```bash
python3 pdf_to_csv.py your_lab_report.pdf --verbose
```

### Extract with Reference Ranges
```bash
python3 pdf_to_csv.py your_lab_report.pdf --include-ranges
# or
python3 pdf_to_csv.py your_lab_report.pdf -r
```

### Force Specific Lab Format
```bash
python3 pdf_to_csv.py your_lab_report.pdf --format quest
python3 pdf_to_csv.py your_lab_report.pdf --format labcorp
python3 pdf_to_csv.py your_lab_report.pdf --format function_health
```

### Command Line Options
- `--output, -o`: Specify the output CSV file path
- `--verbose, -v`: Enable verbose output to see extracted data
- `--include-ranges, -r`: Include reference ranges (MinRange, MaxRange) in output
- `--format`: Force specific lab format (`quest`, `labcorp`, or `function_health`) - auto-detects if not specified
- `--config-dir`: Specify custom configuration directory (default: config)
- `--help`: Show help message

## Supported Lab Formats

### Quest Diagnostics (Most Common)
- **Format**: Analyte/Value structured tables
- **Detection**: Looks for "Analyte" and "Value" headers
- **Examples**: Wild Health reports, most Quest lab reports
- **Extraction**: 80-90 markers typically extracted

### LabCorp + Cleveland HeartLab Combination
- **Format**: LabCorp structured results + Cleveland fatty acid profiles
- **Detection**: Identifies both LabCorp codes (01, 02, 03, 04) and Cleveland HeartLab sections
- **Examples**: Combination reports with comprehensive panels + specialized fatty acid analysis
- **Extraction**: 80+ markers from both lab formats

### Cleveland HeartLab Only
- **Format**: Specialized fatty acid and cardiovascular markers
- **Detection**: Cleveland HeartLab headers with fatty acid data
- **Examples**: Cardiometabolic reports
- **Extraction**: Omega-3, Omega-6, EPA, DHA, ratios

### Function Health Dashboard
- **Format**: Function Health's comprehensive biomarker dashboard export
- **Detection**: Looks for "In Range", "Out of Range", "Biomarkers" patterns and characteristic layout
- **Examples**: Function Health dashboard PDF exports
- **Extraction**: 80-110+ markers including autoimmunity, biological age, hormones, vitamins, minerals
- **Note**: PDFs may have spaced text extraction issues with PyPDF2; the tool automatically uses pdfplumber for better results

## Extracted Markers

The tool extracts a comprehensive set of blood markers across multiple categories:

### Complete Blood Count (CBC)
WBC, RBC, Hemoglobin, Hematocrit, MCV, MCH, MCHC, RDW, Platelets, MPV, Neutrophils, Lymphocytes, Monocytes, Eosinophils, Basophils (both % and absolute counts)

### Comprehensive Metabolic Panel (CMP)  
Glucose, BUN, Creatinine, eGFR, Sodium, Potassium, Chloride, CO2, Calcium, Total Protein, Albumin, Globulin, Bilirubin, Alkaline Phosphatase, AST, ALT

### Lipid Panel & Advanced Lipids
Total Cholesterol, HDL, LDL, Triglycerides, Non-HDL Cholesterol, LDL Particle Number, LDL Small, HDL Large, Apolipoprotein A1, Apolipoprotein B, Lipoprotein(a)

### Hormones
Testosterone (Total & Free), DHEA Sulfate, Sex Hormone Binding Globulin, Cortisol, Estradiol, Progesterone, TSH, Free T4, Free T3

### Fatty Acids & Inflammation
Omega-3 Total, Omega-6 Total, EPA, DHA, DPA, Arachidonic Acid, Linoleic Acid, Omega-6/Omega-3 Ratio, Arachidonic Acid/EPA Ratio, hs-CRP, LP-PLA2

### Vitamins & Metabolic
Vitamin D, Vitamin B12, Vitamin B6, Folate (Serum & RBC), Hemoglobin A1c, Insulin, Ferritin, Iron, TIBC, Homocysteine, Uric Acid, TMAO, Coenzyme Q10

## Output Format

### Standard CSV Format
The CSV file contains all extracted markers in the order they appear in the PDF:
```csv
Marker Name,2024-04-04
GLUCOSE,83
UREA NITROGEN (BUN),14
CREATININE,0.98
EGFR,100
WHITE BLOOD CELL COUNT,6.4
HEMOGLOBIN,16.6
LDL-CHOLESTEROL,80
HDL CHOLESTEROL,72
TESTOSTERONE, TOTAL, MS,589
VITAMIN D, 25-OH, TOTAL,42.6
```

### CSV Format with Reference Ranges
When using the `--include-ranges` flag, the CSV includes reference range columns:
```csv
Marker,MinRange,MaxRange,2025-06-10
LDL-P,,1000,1258
LDL-C (NIH Calc),0,99,113
HDL-C,39,,69
Triglycerides,0,149,40
Glucose,70,99,101
BUN,6,24,15
Creatinine,0.57,1.00,0.67
WBC,3.4,10.8,6.2
Hemoglobin,11.1,15.9,14.4
TSH,0.450,4.500,1.240
```

## Installation as a Command Line Tool

To install as a system-wide command:

```bash
pip3 install -e .
```

Then you can use it as:
```bash
pdf-to-csv your_lab_report.pdf
```

## API Usage

The tool includes a FastAPI web service with two extraction methods:

1. **Pattern-based extraction** (public, no auth required)
2. **AI-powered extraction** (secured with API key)

### Starting the API Server

```bash
# Start locally
python api.py

# Or deploy on Railway (automatic from GitHub)
```

### API Endpoints

#### 1. Pattern-Based Extraction (Public)

**POST** `/convert` - Extract using regex patterns

Query Parameters:
- `include_ranges` (boolean, optional): Include reference ranges in output (default: false)
- `format` (string, optional): Force specific lab format (`quest`, `labcorp`, or `function_health`) - auto-detects if not specified

**Example:**
```bash
curl -X POST "http://localhost:8000/convert?include_ranges=true" \
  -F "file=@your_lab_report.pdf" \
  -o results.csv
```

#### 2. AI-Powered Extraction (Secured)

**POST** `/api/v1/ai-extract` - Extract using Claude AI

**Authentication Required:** Include API key in header
```
X-API-Key: your-api-key-here
```

Query Parameters:
- `include_ranges` (boolean, optional): Include reference ranges in output (default: false)

**Response Format:**
```json
{
  "success": true,
  "test_date": "2024-01-15",
  "marker_count": 85,
  "results": [
    {
      "marker": "Glucose",
      "value": "95",
      "min_range": "70",    // Only if include_ranges=true
      "max_range": "100"     // Only if include_ranges=true
    }
  ]
}
```

**Example:**
```bash
# Basic extraction
curl -X POST "https://bloodpdftocsv.amandeep.app/api/v1/ai-extract" \
  -H "X-API-Key: your-api-key" \
  -F "file=@blood_test.pdf"

# With reference ranges
curl -X POST "https://bloodpdftocsv.amandeep.app/api/v1/ai-extract?include_ranges=true" \
  -H "X-API-Key: your-api-key" \
  -F "file=@blood_test.pdf"
```

#### 3. AI Extraction with Database Marker Mapping (Wellavy)

**POST** `/api/v1/ai-extract-mapped` - Extract and map to database markers

This endpoint is designed specifically for Wellavy integration, intelligently mapping extracted markers to a provided database schema.

**Authentication Required:** Include API key in header
```
X-API-Key: your-api-key-here
```

**Request:**
- `file`: PDF file to extract (multipart/form-data)
- `database_markers`: JSON array of database markers (in form data)

**Database Markers Format:**
```json
[
  {"id": "be9a1341-7ce3-4e18-b3d8-4147d5bb6366", "name": "Glucose"},
  {"id": "b562e4ad-2f5d-4da6-8eb7-4b7ece904d69", "name": "Cholesterol, Total"},
  {"id": "340c24f2-6e6b-4ab8-9a3b-719d4b557d88", "name": "WBC"}
]
```

**Response Format:**
```json
{
  "success": true,
  "test_date": "07/22/2025",
  "lab_name": "Wild Health",
  "marker_count": 83,
  "mapping_stats": {
    "total_extracted": 83,
    "successfully_mapped": 75,
    "unmapped": 8,
    "mapping_rate": 0.90
  },
  "results": [
    {
      "original_marker": "Cholesterol Total",
      "value": "155",
      "unit": "mg/dL",
      "min_range": "100",
      "max_range": "199",
      "mapped_marker_name": "Cholesterol, Total",
      "mapped_marker_id": "b562e4ad-2f5d-4da6-8eb7-4b7ece904d69",
      "confidence": 0.95
    }
  ]
}
```

**Mapping Features:**
- Intelligent marker name matching (handles variations like "Total Cholesterol" → "Cholesterol, Total")
- Confidence scores for each mapping
- Preserves original marker names for audit trail
- Maps common abbreviations (WBC, RBC, CRP, etc.)
- Handles lab-specific naming conventions

**Example:**
```bash
# Extract with marker mapping
curl -X POST "https://extract.wellavy.co/api/v1/ai-extract-mapped?include_ranges=true" \
  -H "X-API-Key: your-api-key" \
  -F "file=@blood_test.pdf" \
  -F "database_markers=$(cat markers.json)"
```

### Deployment on Railway

1. **Fork/Clone this repository**
2. **Connect to Railway:**
   - Create new project on Railway
   - Connect your GitHub repository
3. **Set Environment Variables:**
   ```
   API_SECRET_KEY=your-secure-random-key
   ANTHROPIC_API_KEY=sk-ant-your-claude-key
   ```
4. **Deploy:** Railway will auto-deploy on push

### API Security

The AI extraction endpoint requires authentication to:
- Protect against unauthorized usage
- Control Claude API costs
- Track usage per client

Generate a secure API key:
```python
import secrets
print(secrets.token_urlsafe(32))
```

### Python Client Example

```python
import requests

class BloodTestClient:
    def __init__(self, api_url, api_key=None):
        self.api_url = api_url
        self.api_key = api_key
    
    def extract_with_ai(self, pdf_path, include_ranges=False):
        """Use AI extraction (requires API key)"""
        url = f"{self.api_url}/api/v1/ai-extract"
        headers = {"X-API-Key": self.api_key}
        params = {"include_ranges": include_ranges}
        
        with open(pdf_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(url, headers=headers, files=files, params=params)
        
        return response.json()
    
    def extract_with_patterns(self, pdf_path, include_ranges=False):
        """Use pattern extraction (no auth required)"""
        url = f"{self.api_url}/convert"
        params = {"include_ranges": include_ranges}
        
        with open(pdf_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(url, files=files, params=params)
        
        return response.text  # CSV content

# Usage
client = BloodTestClient(
    api_url="https://bloodpdftocsv.amandeep.app",
    api_key="your-api-key"
)

# AI extraction
results = client.extract_with_ai("blood_test.pdf", include_ranges=True)
print(f"Found {results['marker_count']} markers")
```

### API Documentation

For comprehensive API documentation including rate limiting, error handling, and more examples, see [API_DOCUMENTATION.md](API_DOCUMENTATION.md).

## AI-Powered Extraction (Unified AI Extractor)

The project includes an AI-powered extractor that uses Claude or GPT-4o to extract blood test results directly from PDFs without relying on text extraction patterns.

### Features
- **Direct PDF Processing**: Sends PDF as base64 to AI models for native OCR/document processing
- **Dual AI Support**: Choose between Claude (Anthropic) or GPT-4o (OpenAI)
- **Structured Output**: Returns JSON with standardized marker names and reference ranges
- **Flexible Output**: Export as CSV or JSON format

### Setup
1. Create a `.env.local` file (see `.env.local.example`):
```bash
ANTHROPIC_API_KEY=your-claude-api-key
OPENAI_API_KEY=your-openai-api-key
```

2. Install additional dependencies:
```bash
pip install anthropic openai python-dotenv
```

### Usage

**Basic usage with Claude (default):**
```bash
python unified_ai_extractor.py your_lab_report.pdf
```

**Use GPT-4o instead:**
```bash
python unified_ai_extractor.py your_lab_report.pdf --service gpt4o
```

**Include reference ranges:**
```bash
python unified_ai_extractor.py your_lab_report.pdf --include-ranges
```

**Output as JSON:**
```bash
python unified_ai_extractor.py your_lab_report.pdf --json --output results.json
```

**Using the shell script:**
```bash
./run_unified_extractor.sh your_lab_report.pdf -s gpt4o -r
```

### AI Extractor Options
- `--service/-s`: Choose AI service (`claude`, `openai`, or `gpt4o`)
- `--output/-o`: Specify output file path
- `--include-ranges/-r`: Include reference ranges in output
- `--json`: Output as JSON instead of CSV

### Output Format

**JSON output structure:**
```json
{
  "results": [
    {
      "marker": "Glucose",
      "value": "95",
      "min_range": "70",
      "max_range": "100"
    },
    {
      "marker": "Cholesterol",
      "value": "180",
      "min_range": null,
      "max_range": "200"
    }
  ],
  "test_date": "2024-01-15"
}
```

### AI Models Used
- **Claude**: `claude-sonnet-4-20250514` (Anthropic's latest Sonnet model)
- **GPT-4o**: `gpt-4o` (OpenAI's multimodal model with vision capabilities)

### When to Use AI Extraction
The AI extractor is particularly useful for:
- PDFs with complex layouts that pattern-based extraction struggles with
- Scanned documents or images where OCR is needed
- Reports from labs not yet supported by pattern-based extractors
- Quick extraction without needing to configure patterns

## Real Examples

### Quest Diagnostics Report (2025 April Wild Health)
**Extracted 85 markers** including comprehensive CBC, CMP, hormones, advanced lipids, and fatty acid profiles:

```csv
Marker Name,2025-04-04
WHITE BLOOD CELL COUNT,6.4
HEMOGLOBIN,16.6
GLUCOSE,83
TESTOSTERONE, TOTAL, MS,589
LDL PARTICLE NUMBER,1605
OMEGA-3 TOTAL,7.6
EPA,1.6
DHA,4.0
VITAMIN D, 25-OH, TOTAL,42.6
HEMOGLOBIN A1c,5.3
```

### LabCorp + Cleveland HeartLab Combination (2024 October)
**Extracted 82 markers** from both lab formats in a single comprehensive report:

```csv
Marker Name,2024-10-30
WBC,4.3
Hemoglobin,15.6
Glucose,82
Testosterone,789
Arachidonic Acid/EPA Ratio,11.4
Omega3 Total,6.2
EPA,1.0
DHA,3.5
TMAO (Trimethylamine N-oxide),3.3
Vitamin D, 25-Hydroxy,50.4
```

## Configuration

The tool uses JSON configuration files in the `config/` directory:

### `config/markers.json`
Defines marker patterns, validation ranges, and categories. Organized by:
- `default_markers`: Core lab markers by category (CBC, CMP, hormones, etc.)
- `other_markers`: Additional specialized markers

### `config/settings.json` 
Contains extraction settings:
- `date_patterns`: Regex patterns for date extraction
- `value_patterns`: Patterns for marker-value extraction
- `exclusion_lists`: Keywords to filter out noise
- `extraction_settings`: Thresholds and parameters

## Troubleshooting

### Common Issues
- **No data extracted**: PDF format not recognized. Use `--verbose` to see extracted text
- **Low marker count**: May indicate wrong format detection. Check if PDF has Analyte/Value structure
- **Wrong date**: Date extraction failed, current date used. Edit CSV header manually if needed
- **Missing specific markers**: Pattern matching may need adjustment in `config/markers.json`

### Format-Specific Issues
- **Quest reports**: Should detect Analyte/Value structure and extract 80+ markers
- **LabCorp combination**: Needs both LabCorp codes and Cleveland sections for full extraction
- **Fragmented PDFs**: Tool will attempt fragmented extraction method

### Debug Tips
- Use `--verbose` flag to see extraction method and marker counts
- Check that pdfplumber is installed for problematic PDFs: `pip install pdfplumber`
- Examine extracted text patterns if markers are missing

## Requirements

- Python 3.7+
- PyPDF2 
- pdfplumber (optional, for fallback PDF reading)
- click
- python-dateutil

## Architecture

The tool uses a modular object-oriented design:
- **ConfigLoader**: Manages JSON configuration files
- **ValueValidator**: Validates extracted values against medical ranges  
- **PatternMatcher**: Compiles and manages regex patterns
- **TextProcessor**: Cleans and processes PDF text
- **DateExtractor**: Extracts dates from text
- **LabReportExtractor**: Main extraction logic for different formats
- **BloodTestExtractor**: Orchestrates the entire extraction process
