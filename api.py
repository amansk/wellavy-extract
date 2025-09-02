from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Header, Body, Form
from typing import Optional, List, Dict
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile
from pathlib import Path
from pdf_to_csv import BloodTestExtractor, generate_csv_content
import os
import json
import uuid
from unified_ai_extractor import UnifiedAIExtractor
from wellavy_ai_extractor import WellavyAIExtractor
from smart_ai_extractor import SmartAIExtractor
from logging_config import setup_logging, RequestLogger

# Configure logging with BetterStack
logger = setup_logging("wellavy-extract-api")

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
    request_id = str(uuid.uuid4())
    
    with RequestLogger(logger, request_id, "/api/v1/ai-extract") as req_logger:
        # Check API key
        api_secret_key = os.getenv("API_SECRET_KEY")
        if not api_secret_key:
            req_logger.error("API_SECRET_KEY not configured in environment")
            raise HTTPException(status_code=500, detail="Server configuration error")
        
        if x_api_key != api_secret_key:
            req_logger.warning("Invalid API key attempt")
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Log received file
        req_logger.info("Received file for ai-extract", 
                       filename=file.filename, 
                       include_ranges=include_ranges)
        
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            req_logger.warning("Invalid file type attempted", file_type=file.filename.split('.')[-1])
            raise HTTPException(status_code=400, detail="File must be a PDF")
        
        try:
            # Create a temporary file to store the uploaded PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                content = await file.read()
                temp_pdf.write(content)
                temp_pdf_path = temp_pdf.name
            
            req_logger.info("PDF uploaded and stored temporarily", file_size=len(content))
            
            try:
                # Initialize the AI extractor with Claude as default
                extractor = UnifiedAIExtractor(service="claude")
                req_logger.info("Initialized AI extractor", service="claude")
                
                # Extract data
                results = extractor.extract(temp_pdf_path)
                
                # Check if we got results
                if not results.get("results"):
                    req_logger.warning("No data extracted from PDF")
                    raise HTTPException(
                        status_code=400,
                        detail="No valid data could be extracted from the PDF"
                    )
                
                marker_count = len(results.get("results", []))
                req_logger.info("Data extraction successful", 
                               marker_count=marker_count,
                               test_date=results.get("test_date"))
                
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
                    "marker_count": marker_count,
                    "results": results.get("results", [])
                }
            
            finally:
                # Clean up the temporary file
                Path(temp_pdf_path).unlink(missing_ok=True)
                req_logger.info("Temporary file cleaned up")
                
        except HTTPException:
            raise
        except Exception as e:
            req_logger.exception("Error processing PDF with AI", error_message=str(e))
            raise HTTPException(
                status_code=500,
                detail=f"Error processing PDF: {str(e)}"
            )

@app.post("/api/v1/ai-extract-mapped")
async def ai_extract_mapped(
    file: UploadFile = File(...),
    x_api_key: str = Header(..., alias="X-API-Key"),
    include_ranges: bool = Query(True, description="Include reference ranges in output"),
    database_markers: Optional[str] = Form(None, description="JSON string of database markers for mapping")
):
    """
    Extract health data using AI with automatic document type detection.
    Automatically detects if PDF is a blood test or InBody report and uses appropriate extractor.
    Maps extracted markers to provided database markers for accurate imports.
    
    Args:
        file: The PDF file to extract
        x_api_key: API key for authentication
        include_ranges: Whether to include reference ranges in the output
        database_markers: JSON string containing array of database markers with 'id' and 'name' keys
        
    Returns:
        JSON with extracted and mapped health data (blood test or InBody results)
    """
    request_id = str(uuid.uuid4())
    
    with RequestLogger(logger, request_id, "/api/v1/ai-extract-mapped") as req_logger:
        # Check API key
        api_secret_key = os.getenv("API_SECRET_KEY")
        if not api_secret_key:
            req_logger.error("API_SECRET_KEY not configured in environment")
            raise HTTPException(status_code=500, detail="Server configuration error")
        
        if x_api_key != api_secret_key:
            req_logger.warning("Invalid API key attempt")
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Log received file
        req_logger.info("Received file for ai-extract-mapped",
                       filename=file.filename,
                       include_ranges=include_ranges)
        
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            req_logger.warning("Invalid file type attempted", file_type=file.filename.split('.')[-1])
            raise HTTPException(status_code=400, detail="File must be a PDF")
        
        # Parse database markers if provided
        markers_list = []
        if database_markers:
            try:
                markers_list = json.loads(database_markers) if isinstance(database_markers, str) else database_markers
                req_logger.info("Database markers parsed for mapping", marker_count=len(markers_list))
            except json.JSONDecodeError:
                req_logger.warning("Failed to parse database_markers, proceeding without mapping")
        
        temp_pdf_path = None
        try:
            # Create a temporary file to store the uploaded PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                content = await file.read()
                temp_pdf.write(content)
                temp_pdf_path = temp_pdf.name
            
            req_logger.info("PDF uploaded and stored temporarily", file_size=len(content))
            
            # Initialize the Smart AI extractor with automatic document detection
            extractor = SmartAIExtractor(service="claude", database_markers=markers_list)
            req_logger.info("Initialized Smart AI extractor", service="claude", has_markers=bool(markers_list))
            
            # Extract data with automatic type detection and routing
            results = extractor.extract(temp_pdf_path)
            
            # Check if we got results
            if not results.get("results"):
                req_logger.warning("No data extracted from PDF")
                raise HTTPException(
                    status_code=400,
                    detail="No valid data could be extracted from the PDF"
                )
            
            marker_count = len(results.get("results", []))
            
            # Filter out reference ranges if not requested
            if not include_ranges:
                for result in results["results"]:
                    result.pop("min_range", None)
                    result.pop("max_range", None)
            
            # Log mapping statistics if available
            if "mapping_stats" in results:
                stats = results["mapping_stats"]
                req_logger.info("Extraction complete with mapping stats",
                               total_extracted=stats['total_extracted'],
                               successfully_mapped=stats['successfully_mapped'],
                               unmapped=stats['unmapped'])
            
            # Extract document detection info
            doc_detection = results.get("document_detection", {})
            
            req_logger.info("Data extraction successful",
                           document_type=doc_detection.get("document_type", "unknown"),
                           confidence=doc_detection.get("confidence", "unknown"),
                           marker_count=marker_count,
                           test_date=results.get("test_date"))
            
            # Return enhanced response with document type information
            return {
                "success": True,
                "document_type": doc_detection.get("document_type", "unknown"),
                "confidence": doc_detection.get("confidence", "unknown"),
                "test_date": results.get("test_date"),
                "lab_name": doc_detection.get("lab_name") or results.get("lab_name"),
                "marker_count": marker_count,
                "mapping_stats": results.get("mapping_stats"),
                "results": results.get("results", [])
            }
            
        except HTTPException:
            raise
        except Exception as e:
            req_logger.exception("Error processing PDF with mapped extraction", error_message=str(e))
            raise HTTPException(
                status_code=500,
                detail=f"Error processing PDF: {str(e)}"
            )
        finally:
            # Clean up the temporary file
            if temp_pdf_path:
                Path(temp_pdf_path).unlink(missing_ok=True)
                req_logger.info("Temporary file cleaned up")


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
    request_id = str(uuid.uuid4())
    
    with RequestLogger(logger, request_id, "/convert") as req_logger:
        # Log received file
        req_logger.info("Received file for convert",
                       filename=file.filename,
                       include_ranges=include_ranges,
                       format=format)
        
        if not file.filename.lower().endswith('.pdf'):
            req_logger.warning("Invalid file type attempted", file_type=file.filename.split('.')[-1])
            raise HTTPException(status_code=400, detail="File must be a PDF")
        
        try:
            # Create a temporary file to store the uploaded PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                content = await file.read()
                temp_pdf.write(content)
                temp_pdf_path = temp_pdf.name
            
            req_logger.info("PDF uploaded and stored temporarily", file_size=len(content))
            
            try:
                # Initialize the extractor
                extractor = BloodTestExtractor()
                req_logger.info("Initialized BloodTestExtractor")
                
                # Process the PDF
                default_results, other_results, date = extractor.process_pdf(temp_pdf_path, include_ranges, format)
                
                if not default_results and not other_results:
                    req_logger.warning("No data extracted from PDF")
                    raise HTTPException(
                        status_code=400,
                        detail="No valid data could be extracted from the PDF"
                    )
                
                req_logger.info("PDF processing successful",
                               default_results_count=len(default_results) if default_results else 0,
                               other_results_count=len(other_results) if other_results else 0,
                               test_date=date)
                
                # Generate CSV content using the same function as the CLI script
                csv_content = generate_csv_content(default_results, other_results, date, include_ranges)
                
                if not csv_content:
                    req_logger.warning("CSV generation failed")
                    raise HTTPException(
                        status_code=400,
                        detail="No valid data could be extracted from the PDF"
                    )
                
                req_logger.info("CSV generation successful", csv_size=len(csv_content))
                
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
                req_logger.info("Temporary file cleaned up")
                
        except HTTPException:
            raise
        except Exception as e:
            req_logger.exception("Error processing PDF", error_message=str(e))
            raise HTTPException(
                status_code=500,
                detail=f"Error processing PDF: {str(e)}"
            )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 