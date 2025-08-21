from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Header, Body
from typing import Optional, List, Dict
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile
from pathlib import Path
from pdf_to_csv import BloodTestExtractor, generate_csv_content
import os
import logging
import json
from unified_ai_extractor import UnifiedAIExtractor
from wellavy_ai_extractor import WellavyAIExtractor

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

@app.post("/api/v1/ai-extract")
async def ai_extract(
    file: UploadFile = File(...),
    x_api_key: str = Header(..., alias="X-API-Key"),
    include_ranges: bool = Query(False, description="Include reference ranges in output")
):
    """
    Extract blood test results using AI (Claude).
    Requires API key authentication via X-API-Key header.
    
    Args:
        file: The PDF file to extract
        x_api_key: API key for authentication
        include_ranges: Whether to include reference ranges in the output
        
    Returns:
        JSON with extracted blood test results
    """
    # Check API key
    api_secret_key = os.getenv("API_SECRET_KEY")
    if not api_secret_key:
        logger.error("API_SECRET_KEY not configured in environment")
        raise HTTPException(status_code=500, detail="Server configuration error")
    
    if x_api_key != api_secret_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        # Create a temporary file to store the uploaded PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            content = await file.read()
            temp_pdf.write(content)
            temp_pdf_path = temp_pdf.name
        
        try:
            # Initialize the AI extractor with Claude as default
            extractor = UnifiedAIExtractor(service="claude")
            
            # Extract data
            results = extractor.extract(temp_pdf_path)
            
            # Check if we got results
            if not results.get("results"):
                raise HTTPException(
                    status_code=400,
                    detail="No valid data could be extracted from the PDF"
                )
            
            # Filter results based on include_ranges parameter
            if not include_ranges:
                # Remove reference ranges from results if not requested
                for result in results["results"]:
                    result.pop("min_range", None)
                    result.pop("max_range", None)
            
            # Return JSON response
            return {
                "success": True,
                "test_date": results.get("test_date"),
                "marker_count": len(results.get("results", [])),
                "results": results.get("results", [])
            }
        
        finally:
            # Clean up the temporary file
            Path(temp_pdf_path).unlink(missing_ok=True)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing PDF with AI: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PDF: {str(e)}"
        )

@app.post("/api/v1/ai-extract-mapped")
async def ai_extract_mapped(
    file: UploadFile = File(...),
    x_api_key: str = Header(..., alias="X-API-Key"),
    include_ranges: bool = Query(True, description="Include reference ranges in output"),
    database_markers: Optional[str] = Body(None, description="JSON string of database markers for mapping")
):
    """
    Extract blood test results using AI with intelligent marker mapping to database.
    Maps extracted markers to provided database markers for accurate imports.
    
    Args:
        file: The PDF file to extract
        x_api_key: API key for authentication
        include_ranges: Whether to include reference ranges in the output
        database_markers: JSON string containing array of database markers with 'id' and 'name' keys
        
    Returns:
        JSON with extracted and mapped blood test results
    """
    # Check API key
    api_secret_key = os.getenv("API_SECRET_KEY")
    if not api_secret_key:
        logger.error("API_SECRET_KEY not configured in environment")
        raise HTTPException(status_code=500, detail="Server configuration error")
    
    if x_api_key != api_secret_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    # Parse database markers if provided
    markers_list = []
    if database_markers:
        try:
            markers_list = json.loads(database_markers) if isinstance(database_markers, str) else database_markers
            logger.info(f"Received {len(markers_list)} database markers for mapping")
        except json.JSONDecodeError:
            logger.warning("Failed to parse database_markers, proceeding without mapping")
    
    try:
        # Create a temporary file to store the uploaded PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            content = await file.read()
            temp_pdf.write(content)
            temp_pdf_path = temp_pdf.name
        
        try:
            # Initialize the Wellavy AI extractor with mapping capability
            extractor = WellavyAIExtractor(service="claude", database_markers=markers_list)
            
            # Extract data with mapping
            results = extractor.extract(temp_pdf_path)
            
            # Check if we got results
            if not results.get("results"):
                raise HTTPException(
                    status_code=400,
                    detail="No valid data could be extracted from the PDF"
                )
            
            # Filter out reference ranges if not requested
            if not include_ranges:
                for result in results["results"]:
                    result.pop("min_range", None)
                    result.pop("max_range", None)
            
            # Log mapping statistics if available
            if "mapping_stats" in results:
                stats = results["mapping_stats"]
                logger.info(f"Extraction complete: {stats['total_extracted']} markers, "
                          f"{stats['successfully_mapped']} mapped, {stats['unmapped']} unmapped")
            
            # Return enhanced response
            return {
                "success": True,
                "test_date": results.get("test_date"),
                "lab_name": results.get("lab_name"),
                "marker_count": len(results.get("results", [])),
                "mapping_stats": results.get("mapping_stats"),
                "results": results.get("results", [])
            }
        
        finally:
            # Clean up the temporary file
            Path(temp_pdf_path).unlink(missing_ok=True)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing PDF with mapped extraction: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PDF: {str(e)}"
        )

@app.post("/convert")
async def convert_pdf_to_csv(
    file: UploadFile = File(...),
    include_ranges: bool = Query(False, description="Include reference ranges (MinRange, MaxRange) in output"),
    format: Optional[str] = Query(None, description="Force specific lab format: 'quest' or 'labcorp' (auto-detects if not specified)")
):
    """
    Convert a blood test PDF report to CSV format.
    
    Args:
        file: The PDF file to convert
        include_ranges: Whether to include reference ranges in the output
        format: Force specific lab format ('quest' or 'labcorp'), auto-detects if not specified
        
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
            default_results, other_results, date = extractor.process_pdf(temp_pdf_path, include_ranges, format)
            
            if not default_results and not other_results:
                raise HTTPException(
                    status_code=400,
                    detail="No valid data could be extracted from the PDF"
                )
            
            # Generate CSV content using the same function as the CLI script
            csv_content = generate_csv_content(default_results, other_results, date, include_ranges)
            
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