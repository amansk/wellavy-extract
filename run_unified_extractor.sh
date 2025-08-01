#!/bin/bash

# Run unified AI extractor with various options
# Usage: ./run_unified_extractor.sh <pdf_file> [options]

# Check if at least one argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <pdf_file> [options]"
    echo ""
    echo "Options:"
    echo "  -s, --service <service>    AI service to use: claude (default), openai, gpt4o"
    echo "  -o, --output <file>        Output file path (default: input_name.csv)"
    echo "  -r, --include-ranges       Include reference ranges in output"
    echo "  --json                     Output as JSON instead of CSV"
    echo ""
    echo "Examples:"
    echo "  $0 test.pdf                          # Use Claude (default)"
    echo "  $0 test.pdf -s gpt4o                 # Use GPT-4o"
    echo "  $0 test.pdf -r --json -o result.json # Include ranges, output as JSON"
    exit 1
fi

# Run the unified extractor
python3 unified_ai_extractor.py "$@"