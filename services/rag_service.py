"""
RAG (Retrieval-Augmented Generation) service
Handles document ingestion, embedding, and retrieval using FAISS
"""
import os
import json
import pickle
import uuid
from typing import List, Dict, Optional
import logging
from pathlib import Path

import numpy as np
from langchain_ollama import OllamaEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

from config import CHROMA_DIR, OLLAMA_BASE_URL, EMBEDDING_MODEL

logger = logging.getLogger(__name__)

# Use CHROMA_DIR for storing FAISS index (reusing the config)
FAISS_DIR = CHROMA_DIR


class RAGService:
    """Manages document ingestion and retrieval for resume data using FAISS"""
    
    def __init__(self):
        self._embeddings = None
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        # In-memory storage per session
        self._sessions: Dict[str, Dict] = {}
        self._load_sessions()
    
    def _load_sessions(self):
        """Load existing sessions from disk"""
        sessions_file = FAISS_DIR / "sessions.json"
        if sessions_file.exists():
            try:
                with open(sessions_file, 'r') as f:
                    self._sessions = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load sessions: {e}")
                self._sessions = {}
    
    def _save_sessions(self):
        """Save sessions to disk"""
        FAISS_DIR.mkdir(parents=True, exist_ok=True)
        sessions_file = FAISS_DIR / "sessions.json"
        try:
            with open(sessions_file, 'w') as f:
                json.dump(self._sessions, f)
        except Exception as e:
            logger.error(f"Could not save sessions: {e}")
    
    @property
    def embeddings(self) -> OllamaEmbeddings:
        """Lazy initialization of embedding model"""
        if self._embeddings is None:
            self._embeddings = OllamaEmbeddings(
                base_url=OLLAMA_BASE_URL,
                model=EMBEDDING_MODEL
            )
        return self._embeddings
    
    def ingest_documents(
        self, 
        documents: List[Dict],
        session_id: str
    ) -> int:
        """
        Ingest resume documents into the vector store
        
        Args:
            documents: List of document dicts with 'id', 'name', 'source_file', 'raw_text'
            session_id: Session identifier for grouping documents
            
        Returns:
            Number of chunks ingested
        """
        total_chunks = 0
        
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "candidates": {},
                "embeddings": [],
                "chunks": [],
                "metadatas": []
            }
        
        session = self._sessions[session_id]
        
        for doc in documents:
            try:
                # Split document into chunks
                chunks = self._text_splitter.split_text(doc['raw_text'])
                
                if not chunks:
                    logger.warning(f"No chunks created for document: {doc['name']}")
                    continue
                
                # Generate embeddings for all chunks
                embeddings = self.embeddings.embed_documents(chunks)
                
                # Store candidate info
                session["candidates"][doc['id']] = {
                    "id": doc['id'],
                    "name": doc['name'],
                    "source_file": doc['source_file'],
                    "full_text": doc['raw_text']
                }
                
                # Store chunks and embeddings
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    session["chunks"].append(chunk)
                    session["embeddings"].append(embedding)
                    session["metadatas"].append({
                        "candidate_id": doc['id'],
                        "candidate_name": doc['name'],
                        "source_file": doc['source_file'],
                        "chunk_index": i,
                        "total_chunks": len(chunks)
                    })
                
                total_chunks += len(chunks)
                logger.info(f"Ingested {len(chunks)} chunks for: {doc['name']}")
                
            except Exception as e:
                logger.error(f"Failed to ingest document {doc['name']}: {e}")
                continue
        
        self._save_sessions()
        return total_chunks
    
    def get_candidate_documents(
        self, 
        session_id: str
    ) -> List[Dict]:
        """
        Retrieve all unique candidates from a session
        
        Args:
            session_id: Session to query
            
        Returns:
            List of candidate info dicts
        """
        if session_id not in self._sessions:
            return []
        
        session = self._sessions[session_id]
        return list(session["candidates"].values())
    
    def search_candidates(
        self,
        query: str,
        session_id: str,
        n_results: int = 10
    ) -> List[Dict]:
        """
        Search for relevant candidate chunks based on query
        
        Args:
            query: Search query (e.g., job description)
            session_id: Session to search within
            n_results: Maximum number of results
            
        Returns:
            List of relevant chunks with metadata
        """
        if session_id not in self._sessions:
            return []
        
        session = self._sessions[session_id]
        
        if not session["embeddings"]:
            return []
        
        # Generate query embedding
        query_embedding = self.embeddings.embed_query(query)
        
        # Calculate cosine similarity
        embeddings_array = np.array(session["embeddings"])
        query_array = np.array(query_embedding)
        
        # Normalize for cosine similarity
        embeddings_norm = embeddings_array / np.linalg.norm(embeddings_array, axis=1, keepdims=True)
        query_norm = query_array / np.linalg.norm(query_array)
        
        similarities = np.dot(embeddings_norm, query_norm)
        
        # Get top results
        top_indices = np.argsort(similarities)[::-1][:n_results]
        
        results = []
        for idx in top_indices:
            results.append({
                "document": session["chunks"][idx],
                "metadata": session["metadatas"][idx],
                "similarity": float(similarities[idx])
            })
        
        return results
    
    def get_full_resume_text(
        self, 
        candidate_id: str,
        session_id: str
    ) -> str:
        """
        Get the complete resume text for a candidate
        
        Args:
            candidate_id: Candidate's unique ID
            session_id: Session identifier
            
        Returns:
            Full resume text
        """
        if session_id not in self._sessions:
            return ""
        
        session = self._sessions[session_id]
        candidate = session["candidates"].get(candidate_id)
        
        if candidate:
            return candidate.get("full_text", "")
        
        return ""
    
    def clear_session(self, session_id: str):
        """Remove all documents from a session"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._save_sessions()
            logger.info(f"Cleared session {session_id}")
    
    def reset_database(self):
        """Clear all data (use with caution)"""
        self._sessions = {}
        self._save_sessions()
        logger.info("Database reset complete")
