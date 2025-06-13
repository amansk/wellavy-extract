from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile
from pathlib import Path
from pdf_to_csv import BloodTestExtractor, generate_csv_content
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PDF to CSV Converter API",
    description="API for converting blood test PDF reports to CSV format",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy", "message": "PDF to CSV Converter API is running"}

@app.post("/convert")
async def convert_pdf_to_csv(file: UploadFile = File(...)):
    """
    Convert a blood test PDF report to CSV format.
    
    Args:
        file: The PDF file to convert
        
    Returns:
        CSV file as a downloadable attachment
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        # Create a temporary file to store the uploaded PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            content = await file.read()
            temp_pdf.write(content)
            temp_pdf_path = temp_pdf.name
        
        try:
            # Initialize the extractor
            extractor = BloodTestExtractor()
            
            # Process the PDF
            default_results, other_results, date = extractor.process_pdf(temp_pdf_path)
            
            if not default_results and not other_results:
                raise HTTPException(
                    status_code=400,
                    detail="No valid data could be extracted from the PDF"
                )
            
            # Generate CSV content using the same function as the CLI script
            csv_content = generate_csv_content(default_results, other_results, date)
            
            if not csv_content:
                raise HTTPException(
                    status_code=400,
                    detail="No valid data could be extracted from the PDF"
                )
            
            # Create a streaming response with the CSV data
            return StreamingResponse(
                iter([csv_content]),
                media_type="text/csv",
                headers={
                    'Content-Disposition': f'attachment; filename="{Path(file.filename).stem}.csv"'
                }
            )
        
        finally:
            # Clean up the temporary file
            Path(temp_pdf_path).unlink(missing_ok=True)
            
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PDF: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 