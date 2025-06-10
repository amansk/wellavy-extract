#!/bin/bash

# Installation script for Blood Test PDF to CSV Extractor

echo "Installing Blood Test PDF to CSV Extractor..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed. Please install Python 3.7 or higher."
    exit 1
fi

# Install dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Make script executable
chmod +x pdf_to_csv.py

echo "Installation complete!"
echo ""
echo "Usage:"
echo "  python3 pdf_to_csv.py your_lab_report.pdf"
echo "  python3 pdf_to_csv.py your_lab_report.pdf --output results.csv"
echo "  python3 pdf_to_csv.py your_lab_report.pdf --verbose"
echo ""
echo "For system-wide installation, run:"
echo "  pip3 install -e ."
echo "Then you can use: pdf-to-csv your_lab_report.pdf"
