"""
Resume Ranking Service - FastAPI Application
Processes resume images, ingests into RAG, and ranks candidates against job descriptions
"""
import time
import tempfile
import logging
from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from config import UPLOAD_DIR, MAX_UPLOAD_SIZE_MB, BASE_DIR
from models.schemas import (
    UploadResponse, 
    RankingRequest, 
    RankingResponse,
    CandidateResult
)
from services.document_extractor import DocumentExtractor
from services.rag_service import RAGService
from services.llm_ranker import LLMRanker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Service instances
rag_service: Optional[RAGService] = None
llm_ranker: Optional[LLMRanker] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup"""
    global rag_service, llm_ranker
    
    logger.info("Initializing services...")
    rag_service = RAGService()
    llm_ranker = LLMRanker()
    logger.info("Services initialized successfully")
    
    yield
    
    logger.info("Shutting down services...")


# Create FastAPI app
app = FastAPI(
    title="Resume Ranking Service",
    description="""
    A service that processes resume images from ZIP files, extracts text using OCR,
    ingests data into a RAG system, and uses LLM to semantically rank candidates
    against job descriptions.
    
    ## Features
    - **ZIP Upload**: Upload multiple resumes as a ZIP file
    - **OpenCV Preprocessing**: Denoise, deskew, and enhance images for better OCR
    - **RAG Integration**: Store and retrieve resume data using vector embeddings
    - **Semantic Ranking**: Differentiate between mentioned and demonstrated skills
    """,
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for frontend
frontend_path = BASE_DIR / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


@app.get("/")
async def root():
    """Redirect to frontend UI"""
    return RedirectResponse(url="/static/index.html")


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Resume Ranking Service",
        "version": "1.0.0"
    }


@app.post("/upload-resumes", response_model=UploadResponse)
async def upload_resumes(
    files: List[UploadFile] = File(..., description="Resume files (ZIP, PDF, DOCX, or images)")
):
    """
    Upload resume documents for processing.
    
    Supported formats:
    - **ZIP file**: Archive containing multiple resumes
    - **PDF files**: Standard PDF documents
    - **DOCX files**: Microsoft Word documents
    - **Images**: PNG, JPG, JPEG, TIFF, BMP (scans/screenshots)
    
    You can upload multiple files at once (individual files or a single ZIP).
    
    The service will:
    1. Extract/save uploaded files
    2. Preprocess images using OpenCV (denoise, deskew, enhance)
    3. Extract text using Tesseract OCR or direct parsing (DOCX)
    4. Ingest into the RAG vector database
    
    Returns a session_id to use for ranking.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    
    # Check total size
    total_size = 0
    file_contents = []
    
    for file in files:
        content = await file.read()
        total_size += len(content)
        file_contents.append((content, file.filename))
    
    size_mb = total_size / (1024 * 1024)
    if size_mb > MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"Total upload too large. Maximum size is {MAX_UPLOAD_SIZE_MB}MB"
        )
    
    try:
        extractor = DocumentExtractor()
        
        # Check if single ZIP file
        if len(file_contents) == 1 and file_contents[0][1].lower().endswith('.zip'):
            # Handle ZIP file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
                tmp.write(file_contents[0][0])
                tmp_path = Path(tmp.name)
            
            session_id, file_paths = extractor.extract_zip(tmp_path)
            tmp_path.unlink(missing_ok=True)
        else:
            # Handle individual files
            valid_files = []
            for content, filename in file_contents:
                ext = Path(filename).suffix.lower()
                allowed = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".docx", ".doc"}
                if ext in allowed:
                    valid_files.append((content, filename))
                else:
                    logger.warning(f"Skipping unsupported file: {filename}")
            
            if not valid_files:
                raise HTTPException(
                    status_code=400,
                    detail="No valid resume files found. Supported: PDF, DOCX, PNG, JPG, TIFF, BMP"
                )
            
            session_id, file_paths = extractor.save_multiple_files(valid_files)
        
        if not file_paths:
            raise HTTPException(
                status_code=400,
                detail="No valid documents found"
            )
        
        logger.info(f"Processing {len(file_paths)} files for session {session_id}")
        
        # Process all documents (OCR/text extraction)
        documents = extractor.process_all_documents(file_paths)
        
        if not documents:
            raise HTTPException(
                status_code=500,
                detail="Failed to process any documents"
            )
        
        # Ingest into RAG
        chunks_ingested = rag_service.ingest_documents(documents, session_id)
        logger.info(f"Ingested {chunks_ingested} chunks into RAG")
        
        return UploadResponse(
            message=f"Successfully processed {len(documents)} resumes",
            files_processed=len(documents),
            candidates_extracted=[doc['name'] for doc in documents],
            session_id=session_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload processing failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Processing failed: {str(e)}"
        )


@app.post("/rank-candidates", response_model=RankingResponse)
async def rank_candidates(request: RankingRequest):
    """
    Rank candidates against a job description.
    
    The ranking uses semantic analysis to:
    - Extract required skills from the job description
    - Identify **demonstrated skills** (with evidence in projects/experience)
    - Identify **mentioned skills** (listed without practical evidence)
    - Calculate weighted scores (demonstrated skills count 2x more)
    
    Returns candidates sorted by match score with detailed skill breakdowns.
    """
    if not request.session_id:
        raise HTTPException(
            status_code=400,
            detail="session_id is required. Upload resumes first."
        )
    
    start_time = time.time()
    
    try:
        # Get candidates from RAG
        candidates = rag_service.get_candidate_documents(request.session_id)
        
        if not candidates:
            raise HTTPException(
                status_code=404,
                detail=f"No candidates found for session: {request.session_id}"
            )
        
        logger.info(f"Found {len(candidates)} candidates to rank")
        
        # Rank candidates using LLM
        ranked_results = llm_ranker.rank_candidates(
            candidates=candidates,
            job_description=request.job_description
        )
        
        processing_time = time.time() - start_time
        
        return RankingResponse(
            job_description=request.job_description[:200] + "..." if len(request.job_description) > 200 else request.job_description,
            total_candidates=len(ranked_results),
            processing_time_seconds=round(processing_time, 2),
            ranked_candidates=ranked_results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ranking failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ranking failed: {str(e)}"
        )


@app.get("/candidates/{session_id}")
async def list_candidates(session_id: str):
    """
    List all candidates in a session without ranking.
    
    Useful for verifying uploaded resumes before ranking.
    """
    try:
        candidates = rag_service.get_candidate_documents(session_id)
        
        if not candidates:
            raise HTTPException(
                status_code=404,
                detail=f"No candidates found for session: {session_id}"
            )
        
        return {
            "session_id": session_id,
            "total_candidates": len(candidates),
            "candidates": [
                {
                    "id": c['id'],
                    "name": c['name'],
                    "source_file": c['source_file'],
                    "text_preview": c['full_text'][:500] + "..." if len(c['full_text']) > 500 else c['full_text']
                }
                for c in candidates
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list candidates: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve candidates: {str(e)}"
        )


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """
    Delete all data for a session.
    
    Removes uploaded files and vector store data.
    """
    try:
        rag_service.clear_session(session_id)
        
        # Clean up uploaded files
        session_dir = UPLOAD_DIR / session_id
        if session_dir.exists():
            import shutil
            shutil.rmtree(session_dir)
        
        return {"message": f"Session {session_id} deleted successfully"}
        
    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete session: {str(e)}"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unexpected errors"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
