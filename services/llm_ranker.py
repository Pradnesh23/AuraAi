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
    REQUIRED_SKILL_WEIGHT,
    PREFERRED_SKILL_WEIGHT,
    EXPERIENCE_BONUS
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
        Calculate ATS-style score for a candidate
        
        Standard ATS Formula:
        Score = (Matched Skills / Total Required Skills) × 100
        
        With additional factors:
        - Required skills: 1.0x weight
        - Preferred skills: 0.5x weight  
        - Experience bonus: 5% per year (max 15%)
        
        Args:
            analysis: Candidate analysis results
            job_requirements: Job requirements for reference
            
        Returns:
            Normalized score between 0 and 1
        """
        required_skills = set(s.lower() for s in job_requirements.get("required_skills", []))
        preferred_skills = set(s.lower() for s in job_requirements.get("preferred_skills", []))
        
        if not required_skills and not preferred_skills:
            return 0.5  # Neutral score if no skills to compare
        
        # Get all candidate skills (both demonstrated and mentioned count equally in ATS)
        demonstrated = set(s.lower() for s in analysis.get("demonstrated_skills", []))
        mentioned = set(s.lower() for s in analysis.get("mentioned_skills", []))
        all_candidate_skills = demonstrated | mentioned
        
        # Calculate matched skills
        matched_required = len(all_candidate_skills & required_skills)
        matched_preferred = len(all_candidate_skills & preferred_skills)
        
        # ATS Score Calculation
        # Required skills: full weight
        # Preferred skills: half weight
        total_weight = (len(required_skills) * REQUIRED_SKILL_WEIGHT) + \
                       (len(preferred_skills) * PREFERRED_SKILL_WEIGHT)
        
        if total_weight == 0:
            total_weight = 1
        
        matched_weight = (matched_required * REQUIRED_SKILL_WEIGHT) + \
                         (matched_preferred * PREFERRED_SKILL_WEIGHT)
        
        # Base score: percentage of skills matched
        base_score = matched_weight / total_weight
        
        # Experience bonus: 5% per year, max 15%
        years_exp = analysis.get("years_experience", 0)
        exp_bonus = min(years_exp * EXPERIENCE_BONUS, 0.15)
        
        # Final score (capped at 1.0)
        final_score = min(base_score + exp_bonus, 1.0)
        
        return round(final_score, 3)
    
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
