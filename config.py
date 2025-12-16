"""
Configuration settings for the Resume Ranking Service
"""
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "processed"
CHROMA_DIR = BASE_DIR / "chroma_db"

# Create directories
UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)
CHROMA_DIR.mkdir(exist_ok=True)

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
EMBEDDING_MODEL = "nomic-embed-text"

# ChromaDB configuration
CHROMA_COLLECTION_NAME = "resumes"

# Upload settings
MAX_UPLOAD_SIZE_MB = 50
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".docx", ".doc"}

# OCR settings
OCR_LANGUAGES = ["eng"]

# Scoring weights for ranking
DEMONSTRATED_SKILL_WEIGHT = 2.0
MENTIONED_SKILL_WEIGHT = 0.5
EXPERIENCE_WEIGHT = 0.3
