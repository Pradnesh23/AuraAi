# AuraAI - AI-Powered Resume Ranking Service

AI-powered resume analysis that ranks candidates using **semantic analysis** and differentiates between **demonstrated skills** (proven experience) and **mentioned skills** (just listed).

---

## ✨ Features

- 📤 **Multi-Format Upload** - ZIP, PDF, DOCX, or images (PNG/JPG/TIFF)
- 🖼️ **OpenCV Preprocessing** - Denoise, deskew, enhance scanned images
- 📝 **Smart OCR** - Tesseract for images, direct parsing for DOCX
- 🤖 **LLM Ranking** - Ollama (llama3) for intelligent skill analysis
- ⚖️ **Skill Differentiation** - Weighted scoring for demonstrated vs mentioned skills

---

## 🏗️ System Architecture

```mermaid
flowchart TB
    subgraph Client["🖥️ CLIENT"]
        UI[Web Browser]
    end

    subgraph Server["⚙️ FASTAPI SERVER"]
        direction TB
        API[REST API]
        
        subgraph Processing["📄 Document Processing"]
            direction LR
            DE[Document Extractor] --> IP[Image Processor] --> OCR[Tesseract OCR]
        end
        
        subgraph Intelligence["🤖 AI Layer"]
            direction LR
            RAG[RAG Service] --> LLM[LLM Ranker]
        end
    end

    subgraph External["🔌 EXTERNAL"]
        direction LR
        OL[Ollama] --> EM[Embeddings]
        OL --> LM[LLM]
    end

    subgraph Storage["💾 STORAGE"]
        direction LR
        FS[Files] --> VS[Vectors]
    end

    UI ==>|HTTP Request| API
    API ==> Processing
    Processing ==> Intelligence
    Intelligence ==> External
    Processing ==> Storage

    linkStyle 0,1,2,3,4 stroke:#333,stroke-width:2px
```

---

## 👤 User Flow

```mermaid
flowchart TB
    subgraph Phase1["1️⃣ UPLOAD"]
        direction LR
        A[🗂️ Select Files] --> B[📁 Drag & Drop]
        B --> C[⬆️ Upload]
    end

    subgraph Phase2["2️⃣ PROCESS"]
        direction LR
        D[📄 Extract Text] --> E[🔢 Embeddings]
        E --> F[💾 Store]
    end

    subgraph Phase3["3️⃣ ANALYZE"]
        direction LR
        G[📝 Enter Job Desc] --> H[🔍 Analyze]
        H --> I[🤖 AI Ranking]
    end

    subgraph Phase4["4️⃣ RESULTS"]
        direction LR
        J[📊 View Rankings] --> K[✅ Demonstrated]
        K --> L[📋 Mentioned]
        L --> M[❌ Missing]
    end

    Phase1 --> Phase2
    Phase2 --> Phase3
    Phase3 --> Phase4

    style Phase1 fill:#c8e6c9,stroke:#4caf50,stroke-width:2px
    style Phase2 fill:#fff9c4,stroke:#ffc107,stroke-width:2px
    style Phase3 fill:#bbdefb,stroke:#2196f3,stroke-width:2px
    style Phase4 fill:#f8bbd0,stroke:#e91e63,stroke-width:2px
```

---

## 🔄 Data Pipeline

```mermaid
flowchart LR
    subgraph INPUT["📥 INPUT"]
        A[Files]
    end

    subgraph EXTRACT["📑 EXTRACT"]
        direction TB
        B[PDF] --> B1[Poppler]
        C[DOCX] --> C1[python-docx]
        D[Image] --> D1[OpenCV]
    end

    subgraph PROCESS["⚙️ PROCESS"]
        direction TB
        E[Grayscale]
        E --> F[Denoise]
        F --> G[Deskew]
        G --> H[OCR]
    end

    subgraph STORE["💾 STORE"]
        direction TB
        I[Chunk Text]
        I --> J[Embed]
        J --> K[Vector DB]
    end

    subgraph ANALYZE["🤖 ANALYZE"]
        direction TB
        L[Parse JD]
        L --> M[Match Skills]
        M --> N[Score]
    end

    subgraph OUTPUT["📊 OUTPUT"]
        O[Rankings]
    end

    INPUT ==> EXTRACT
    EXTRACT ==> PROCESS
    PROCESS ==> STORE
    STORE ==> ANALYZE
    ANALYZE ==> OUTPUT

    style INPUT fill:#ffeb3b,stroke:#f57f17,stroke-width:2px
    style EXTRACT fill:#ff9800,stroke:#e65100,stroke-width:2px
    style PROCESS fill:#03a9f4,stroke:#01579b,stroke-width:2px
    style STORE fill:#9c27b0,stroke:#4a148c,stroke-width:2px
    style ANALYZE fill:#e91e63,stroke:#880e4f,stroke-width:2px
    style OUTPUT fill:#4caf50,stroke:#1b5e20,stroke-width:2px
```

### Pipeline Stages

| Stage | Components | Output |
|-------|------------|--------|
| **Extract** | Poppler, python-docx, OpenCV | Raw content |
| **Process** | Grayscale → Denoise → Deskew → OCR | Clean text |
| **Store** | Chunking → Embeddings → Vector DB | Searchable vectors |
| **Analyze** | JD Parsing → Skill Matching → Scoring | Match scores |

---

## ⚖️ Scoring Algorithm (Industry Standard ATS)

```mermaid
graph LR
    subgraph ATS["ATS Scoring"]
        A[Matched Skills] --> D[Base Score]
        B[Total Required] --> D
        C[Experience Years] -->|+5%/year| E[Bonus]
    end
    
    D --> F[Final Score %]
    E --> F
    
    style A fill:#4caf50
    style B fill:#2196f3
    style C fill:#ff9800
```

### Formula
```
Score = (Matched Skills / Total Required Skills) × 100 + Experience Bonus
```

| Factor | Weight | Description |
|--------|--------|-------------|
| **Required Skills** | 1.0x | Must-have skills from JD |
| **Preferred Skills** | 0.5x | Nice-to-have skills |
| **Experience Bonus** | +5%/year | Max 15% bonus |

### Why This Formula?
- **Industry Standard**: Used by major ATS systems (Taleo, Workday, Greenhouse)
- **Fair & Objective**: No distinction between "demonstrated" vs "mentioned" (both can be fabricated)
- **Keyword-Based**: Matches how real ATS systems work

---

## 🚀 Quick Start

```powershell
# Prerequisites
ollama pull llama3
ollama pull nomic-embed-text

# Install
pip install -r requirements.txt

# Run
uvicorn main:app --reload
```

Access at **http://localhost:8000**

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Frontend UI |
| `/upload-resumes` | POST | Upload files |
| `/rank-candidates` | POST | Rank against JD |
| `/candidates/{id}` | GET | List candidates |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| API | FastAPI |
| OCR | Tesseract |
| PDF | Poppler |
| Image | OpenCV |
| LLM | Ollama + llama3 |
| Embeddings | nomic-embed-text |

---

## 📁 Project Structure

```
AuraAi/
├── main.py              # API endpoints
├── config.py            # Settings
├── frontend/            # Web UI (HTML/CSS/JS)
├── models/schemas.py    # Pydantic models
└── services/
    ├── document_extractor.py
    ├── image_processor.py
    ├── rag_service.py
    └── llm_ranker.py
```

---

## 📚 Documentation

- **Swagger**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
