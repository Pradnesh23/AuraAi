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
graph TB
    subgraph Client["🖥️ Client Layer"]
        UI[Web Browser]
    end

    subgraph Server["⚙️ FastAPI Server"]
        API[REST API]
        
        subgraph DocProcess["📄 Document Processing"]
            DE[Document Extractor]
            IP[Image Processor]
            OCR[Tesseract OCR]
        end
        
        subgraph AI["🤖 AI Layer"]
            RAG[RAG Service]
            LLM[LLM Ranker]
        end
    end

    subgraph External["🔌 External Services"]
        OL[Ollama Server]
        EM[Embedding Model]
        LM[Language Model]
    end

    subgraph Storage["💾 Storage"]
        FS[File System]
        VS[Vector Store]
    end

    UI -->|HTTP| API
    API --> DE
    DE --> IP
    IP --> OCR
    DE --> RAG
    RAG --> OL
    OL --> EM
    API --> LLM
    LLM --> OL
    OL --> LM
    DE --> FS
    RAG --> VS

    style Client fill:#e1f5fe
    style Server fill:#fff3e0
    style External fill:#f3e5f5
    style Storage fill:#e8f5e9
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

## 🔄 Project Flow (Data Pipeline)

```mermaid
flowchart TD
    subgraph Input["📥 Input"]
        A[ZIP / PDF / DOCX / Image]
    end

    subgraph Extract["📑 Extraction"]
        B{File Type?}
        C[Poppler: PDF → Images]
        D[python-docx: Parse DOCX]
        E[Direct: Load Image]
    end

    subgraph Preprocess["🔧 Preprocessing"]
        F[Grayscale]
        G[Denoise]
        H[Deskew]
        I[Enhance Contrast]
        J[Threshold]
    end

    subgraph OCR["📝 Text Extraction"]
        K[Tesseract OCR]
        L[Name Detection]
    end

    subgraph RAG["🧠 RAG Pipeline"]
        M[Text Chunking]
        N[nomic-embed-text]
        O[Vector Storage]
    end

    subgraph LLM["🤖 LLM Analysis"]
        P[Job Description]
        Q[Extract Required Skills]
        R[Analyze Resume]
        S[Identify Demonstrated Skills]
        T[Identify Mentioned Skills]
        U[Find Missing Skills]
    end

    subgraph Score["📊 Scoring"]
        V[Apply Weights]
        W[Calculate Score]
        X[Rank Candidates]
    end

    subgraph Output["📤 Output"]
        Y[Ranked Results JSON]
    end

    A --> B
    B -->|PDF| C
    B -->|DOCX| D
    B -->|Image| E
    C --> F
    E --> F
    D --> M
    F --> G --> H --> I --> J
    J --> K --> L --> M
    M --> N --> O
    
    P --> Q
    O --> R
    Q --> R
    R --> S
    R --> T
    R --> U
    S --> V
    T --> V
    U --> V
    V --> W --> X --> Y

    style Input fill:#ffeb3b
    style Extract fill:#ff9800
    style Preprocess fill:#03a9f4
    style OCR fill:#4caf50
    style RAG fill:#9c27b0
    style LLM fill:#e91e63
    style Score fill:#00bcd4
    style Output fill:#8bc34a
```

---

## ⚖️ Scoring Algorithm

```mermaid
graph LR
    subgraph Skills["Skill Analysis"]
        A[Demonstrated Skills] -->|×2.0| D[Weighted Score]
        B[Mentioned Skills] -->|×0.5| D
        C[Experience Years] -->|×0.3| D
    end
    
    D --> E[Final Score %]
    
    style A fill:#4caf50
    style B fill:#ffeb3b
    style C fill:#2196f3
```

| Type | Weight | Description |
|------|--------|-------------|
| **Demonstrated** | 2.0x | Skills with evidence (projects, experience) |
| **Mentioned** | 0.5x | Skills listed but unproven |
| **Experience** | 0.3x | Years of work experience bonus |

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
