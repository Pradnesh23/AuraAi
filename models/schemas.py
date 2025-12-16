"""
Pydantic models for API requests and responses
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class SkillAnalysis(BaseModel):
    """Breakdown of skills found in a resume"""
    mentioned_skills: List[str] = Field(
        default_factory=list,
        description="Skills listed but without evidence of practical use"
    )
    demonstrated_skills: List[str] = Field(
        default_factory=list,
        description="Skills with concrete examples, projects, or achievements"
    )
    missing_skills: List[str] = Field(
        default_factory=list,
        description="Required skills not found in the resume"
    )


class CandidateResult(BaseModel):
    """Individual candidate ranking result"""
    rank: int
    candidate_name: str
    source_file: str
    overall_score: float = Field(ge=0.0, le=1.0)
    skill_analysis: SkillAnalysis
    experience_summary: str
    match_explanation: str


class RankingResponse(BaseModel):
    """Complete ranking response"""
    job_description: str
    total_candidates: int
    processing_time_seconds: float
    ranked_candidates: List[CandidateResult]


class UploadResponse(BaseModel):
    """Response after uploading resumes"""
    message: str
    files_processed: int
    candidates_extracted: List[str]
    session_id: str


class RankingRequest(BaseModel):
    """Request to rank candidates"""
    job_description: str = Field(
        ...,
        min_length=20,
        description="The job description to rank candidates against"
    )
    session_id: Optional[str] = Field(
        None,
        description="Optional session ID to use previously uploaded resumes"
    )


class CandidateDocument(BaseModel):
    """Internal model for storing candidate data"""
    id: str
    name: str
    source_file: str
    raw_text: str
    processed_at: datetime = Field(default_factory=datetime.now)
