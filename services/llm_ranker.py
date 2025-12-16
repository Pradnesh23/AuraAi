"""
LLM-based candidate ranking service
Uses Ollama to semantically rank candidates against job descriptions
Differentiates between mentioned and demonstrated skills
"""
import json
import re
from typing import List, Dict, Tuple
import logging

from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate

from config import (
    OLLAMA_BASE_URL, 
    OLLAMA_MODEL,
    DEMONSTRATED_SKILL_WEIGHT,
    MENTIONED_SKILL_WEIGHT,
    EXPERIENCE_WEIGHT
)
from models.schemas import SkillAnalysis, CandidateResult

logger = logging.getLogger(__name__)


# Prompt for extracting skills from job description
JD_ANALYSIS_PROMPT = PromptTemplate(
    input_variables=["job_description"],
    template="""Analyze this job description and extract the required skills and qualifications.

Job Description:
{job_description}

Return a JSON object with the following structure:
{{
    "required_skills": ["skill1", "skill2", ...],
    "preferred_skills": ["skill1", "skill2", ...],
    "experience_requirements": "description of experience needed",
    "key_responsibilities": ["responsibility1", "responsibility2", ...]
}}

Focus on technical skills, tools, technologies, and soft skills mentioned.
Return ONLY the JSON object, no other text."""
)


# Prompt for analyzing a candidate's resume against job requirements
CANDIDATE_ANALYSIS_PROMPT = PromptTemplate(
    input_variables=["resume_text", "required_skills", "preferred_skills", "experience_requirements"],
    template="""Analyze this resume against the job requirements and differentiate between skills that are:
1. DEMONSTRATED - Skills with concrete evidence like projects, achievements, work experience
2. MENTIONED - Skills listed without practical evidence or just in a skills section

Resume:
{resume_text}

Required Skills: {required_skills}
Preferred Skills: {preferred_skills}
Experience Requirements: {experience_requirements}

Return a JSON object with this exact structure:
{{
    "candidate_name": "extracted name or 'Unknown'",
    "demonstrated_skills": ["skill1", "skill2"],
    "mentioned_skills": ["skill1", "skill2"],
    "missing_required_skills": ["skill1", "skill2"],
    "missing_preferred_skills": ["skill1", "skill2"],
    "years_experience": 0,
    "experience_summary": "Brief summary of relevant experience",
    "match_explanation": "Detailed explanation of how well the candidate matches"
}}

Be strict: Only list a skill as DEMONSTRATED if there's clear evidence in projects, work history, or achievements.
Skills only listed in a "Skills" section without context should be MENTIONED.
Return ONLY the JSON object, no other text."""
)


class LLMRanker:
    """Ranks candidates using LLM-based semantic analysis"""
    
    def __init__(self):
        self._llm = None
    
    @property
    def llm(self) -> OllamaLLM:
        """Lazy initialization of Ollama LLM"""
        if self._llm is None:
            self._llm = OllamaLLM(
                base_url=OLLAMA_BASE_URL,
                model=OLLAMA_MODEL,
                temperature=0.1,  # Low temperature for consistent analysis
                num_predict=2000
            )
        return self._llm
    
    def analyze_job_description(self, job_description: str) -> Dict:
        """
        Extract requirements from job description
        
        Args:
            job_description: The job posting text
            
        Returns:
            Parsed job requirements
        """
        prompt = JD_ANALYSIS_PROMPT.format(job_description=job_description)
        
        try:
            response = self.llm.invoke(prompt)
            return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"Failed to analyze job description: {e}")
            # Return minimal structure on failure
            return {
                "required_skills": [],
                "preferred_skills": [],
                "experience_requirements": "",
                "key_responsibilities": []
            }
    
    def analyze_candidate(
        self,
        resume_text: str,
        job_requirements: Dict,
        source_file: str
    ) -> Dict:
        """
        Analyze a single candidate against job requirements
        
        Args:
            resume_text: Full text of the resume
            job_requirements: Parsed job requirements
            source_file: Source filename for reference
            
        Returns:
            Candidate analysis with skill breakdown
        """
        prompt = CANDIDATE_ANALYSIS_PROMPT.format(
            resume_text=resume_text[:8000],  # Limit context length
            required_skills=", ".join(job_requirements.get("required_skills", [])),
            preferred_skills=", ".join(job_requirements.get("preferred_skills", [])),
            experience_requirements=job_requirements.get("experience_requirements", "Not specified")
        )
        
        try:
            response = self.llm.invoke(prompt)
            analysis = self._parse_json_response(response)
            analysis['source_file'] = source_file
            return analysis
        except Exception as e:
            logger.error(f"Failed to analyze candidate from {source_file}: {e}")
            return {
                "candidate_name": "Unknown",
                "demonstrated_skills": [],
                "mentioned_skills": [],
                "missing_required_skills": job_requirements.get("required_skills", []),
                "missing_preferred_skills": job_requirements.get("preferred_skills", []),
                "years_experience": 0,
                "experience_summary": "Analysis failed",
                "match_explanation": "Could not analyze resume",
                "source_file": source_file
            }
    
    def calculate_score(
        self,
        analysis: Dict,
        job_requirements: Dict
    ) -> float:
        """
        Calculate overall score for a candidate
        
        Uses weighted scoring:
        - Demonstrated skills: 2.0x weight
        - Mentioned skills: 0.5x weight
        - Experience: 0.3x weight
        
        Args:
            analysis: Candidate analysis results
            job_requirements: Job requirements for reference
            
        Returns:
            Normalized score between 0 and 1
        """
        required_skills = set(s.lower() for s in job_requirements.get("required_skills", []))
        preferred_skills = set(s.lower() for s in job_requirements.get("preferred_skills", []))
        all_skills = required_skills | preferred_skills
        
        if not all_skills:
            return 0.5  # Neutral score if no skills to compare
        
        demonstrated = set(s.lower() for s in analysis.get("demonstrated_skills", []))
        mentioned = set(s.lower() for s in analysis.get("mentioned_skills", []))
        
        # Calculate skill matches
        demonstrated_required = len(demonstrated & required_skills)
        demonstrated_preferred = len(demonstrated & preferred_skills)
        mentioned_required = len(mentioned & required_skills)
        mentioned_preferred = len(mentioned & preferred_skills)
        
        # Weighted score calculation
        max_score = (
            len(required_skills) * DEMONSTRATED_SKILL_WEIGHT +
            len(preferred_skills) * DEMONSTRATED_SKILL_WEIGHT * 0.5
        )
        
        if max_score == 0:
            max_score = 1
        
        actual_score = (
            (demonstrated_required * DEMONSTRATED_SKILL_WEIGHT) +
            (demonstrated_preferred * DEMONSTRATED_SKILL_WEIGHT * 0.5) +
            (mentioned_required * MENTIONED_SKILL_WEIGHT) +
            (mentioned_preferred * MENTIONED_SKILL_WEIGHT * 0.5)
        )
        
        # Add experience bonus (up to 0.2 extra)
        years_exp = analysis.get("years_experience", 0)
        experience_bonus = min(years_exp * 0.02 * EXPERIENCE_WEIGHT, 0.2)
        
        # Normalize to 0-1 range
        normalized_score = min((actual_score / max_score) + experience_bonus, 1.0)
        
        return round(normalized_score, 3)
    
    def rank_candidates(
        self,
        candidates: List[Dict],
        job_description: str
    ) -> List[CandidateResult]:
        """
        Rank all candidates against the job description
        
        Args:
            candidates: List of candidate dicts with 'full_text', 'name', 'source_file'
            job_description: Job posting text
            
        Returns:
            Sorted list of CandidateResult objects
        """
        logger.info(f"Starting ranking for {len(candidates)} candidates")
        
        # Analyze job description first
        job_requirements = self.analyze_job_description(job_description)
        logger.info(f"Extracted {len(job_requirements.get('required_skills', []))} required skills")
        
        results = []
        
        for candidate in candidates:
            # Analyze candidate
            analysis = self.analyze_candidate(
                resume_text=candidate['full_text'],
                job_requirements=job_requirements,
                source_file=candidate['source_file']
            )
            
            # Calculate score
            score = self.calculate_score(analysis, job_requirements)
            
            # Build result object
            skill_analysis = SkillAnalysis(
                mentioned_skills=analysis.get("mentioned_skills", []),
                demonstrated_skills=analysis.get("demonstrated_skills", []),
                missing_skills=analysis.get("missing_required_skills", [])
            )
            
            result = CandidateResult(
                rank=0,  # Will be set after sorting
                candidate_name=analysis.get("candidate_name", candidate['name']),
                source_file=candidate['source_file'],
                overall_score=score,
                skill_analysis=skill_analysis,
                experience_summary=analysis.get("experience_summary", ""),
                match_explanation=analysis.get("match_explanation", "")
            )
            
            results.append(result)
            logger.info(f"Scored {result.candidate_name}: {score:.3f}")
        
        # Sort by score (descending) and assign ranks
        results.sort(key=lambda x: x.overall_score, reverse=True)
        for i, result in enumerate(results):
            result.rank = i + 1
        
        return results
    
    def _parse_json_response(self, response: str) -> Dict:
        """
        Parse JSON from LLM response, handling common issues
        """
        # Try to extract JSON from response
        response = response.strip()
        
        # Try direct parsing
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON object in response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Try to fix common issues
        try:
            # Replace single quotes with double quotes
            fixed = response.replace("'", '"')
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass
        
        logger.error(f"Failed to parse JSON response: {response[:200]}")
        return {}
