/**
 * AuraAI Resume Ranking Service - Frontend Application
 */

// API Configuration
const API_BASE_URL = 'http://127.0.0.1:8000';

// State
let currentSessionId = null;
let uploadedCandidates = [];

// DOM Elements
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const uploadStatus = document.getElementById('uploadStatus');
const uploadResult = document.getElementById('uploadResult');
const progressFill = document.getElementById('progressFill');
const resultSubtitle = document.getElementById('resultSubtitle');
const candidatesList = document.getElementById('candidatesList');

const jobDescription = document.getElementById('jobDescription');
const charCount = document.getElementById('charCount');
const rankBtn = document.getElementById('rankBtn');
const rankingStatus = document.getElementById('rankingStatus');
const rankingStatusText = document.getElementById('rankingStatusText');

const resultsSection = document.getElementById('results');
const resultsList = document.getElementById('resultsList');
const totalCandidates = document.getElementById('totalCandidates');
const processingTime = document.getElementById('processingTime');

// Navigation
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        link.classList.add('active');

        const targetId = link.getAttribute('href').slice(1);
        const targetEl = document.getElementById(targetId);
        if (targetEl) {
            targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
});

// ===== File Upload =====

// Click to upload
dropZone.addEventListener('click', () => fileInput.click());

// File selected
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileUpload(e.target.files);
    }
});

// Drag and drop
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileUpload(files);
    }
});

async function handleFileUpload(files) {
    // Show status
    uploadStatus.classList.remove('hidden');
    uploadResult.classList.add('hidden');
    progressFill.style.width = '0%';

    // Simulate progress
    let progress = 0;
    const progressInterval = setInterval(() => {
        progress += Math.random() * 15;
        if (progress > 90) progress = 90;
        progressFill.style.width = `${progress}%`;
    }, 500);

    try {
        const formData = new FormData();

        // Add all files to FormData
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }

        const response = await fetch(`${API_BASE_URL}/upload-resumes`, {
            method: 'POST',
            body: formData
        });

        clearInterval(progressInterval);
        progressFill.style.width = '100%';

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }

        const data = await response.json();
        currentSessionId = data.session_id;
        uploadedCandidates = data.candidates_extracted;

        // Show result
        setTimeout(() => {
            uploadStatus.classList.add('hidden');
            showUploadResult(data);
        }, 500);

    } catch (error) {
        clearInterval(progressInterval);
        uploadStatus.classList.add('hidden');
        showError(error.message);
    }
}

function showUploadResult(data) {
    uploadResult.classList.remove('hidden');
    resultSubtitle.textContent = `${data.files_processed} resumes processed`;

    candidatesList.innerHTML = data.candidates_extracted
        .map(name => `<span class="candidate-tag">${escapeHtml(name)}</span>`)
        .join('');

    // Enable rank button if job description is valid
    updateRankButton();

    // Scroll to ranking section
    setTimeout(() => {
        document.getElementById('rank').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 500);
}

// ===== Job Description =====

jobDescription.addEventListener('input', () => {
    const length = jobDescription.value.length;
    charCount.textContent = length;
    updateRankButton();
});

function updateRankButton() {
    const isValid = currentSessionId && jobDescription.value.length >= 20;
    rankBtn.disabled = !isValid;
}

// ===== Ranking =====

rankBtn.addEventListener('click', handleRanking);

async function handleRanking() {
    if (!currentSessionId) {
        showError('Please upload resumes first');
        return;
    }

    // Show status
    rankingStatus.classList.remove('hidden');
    rankBtn.disabled = true;
    resultsSection.classList.add('hidden');

    const statusMessages = [
        'Analyzing job requirements...',
        'Extracting skills from resumes...',
        'Identifying demonstrated experience...',
        'Calculating match scores...',
        'Generating rankings...'
    ];

    let messageIndex = 0;
    const messageInterval = setInterval(() => {
        messageIndex = (messageIndex + 1) % statusMessages.length;
        rankingStatusText.textContent = statusMessages[messageIndex];
    }, 3000);

    try {
        const response = await fetch(`${API_BASE_URL}/rank-candidates`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                job_description: jobDescription.value,
                session_id: currentSessionId
            })
        });

        clearInterval(messageInterval);

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ranking failed');
        }

        const data = await response.json();
        showResults(data);

    } catch (error) {
        clearInterval(messageInterval);
        showError(error.message);
    } finally {
        rankingStatus.classList.add('hidden');
        updateRankButton();
    }
}

function showResults(data) {
    resultsSection.classList.remove('hidden');

    totalCandidates.textContent = `${data.total_candidates} candidates`;
    processingTime.textContent = `Processed in ${data.processing_time_seconds}s`;

    resultsList.innerHTML = data.ranked_candidates
        .map(candidate => createCandidateCard(candidate))
        .join('');

    // Scroll to results
    setTimeout(() => {
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 300);
}

function createCandidateCard(candidate) {
    const rankClass = candidate.rank <= 3 ? `rank-${candidate.rank}` : '';

    const demonstratedSkills = candidate.skill_analysis.demonstrated_skills
        .map(skill => `<span class="skill-tag demonstrated">${escapeHtml(skill)}</span>`)
        .join('') || '<span class="text-muted">None identified</span>';

    const mentionedSkills = candidate.skill_analysis.mentioned_skills
        .map(skill => `<span class="skill-tag mentioned">${escapeHtml(skill)}</span>`)
        .join('') || '<span class="text-muted">None identified</span>';

    const missingSkills = candidate.skill_analysis.missing_skills
        .map(skill => `<span class="skill-tag missing">${escapeHtml(skill)}</span>`)
        .join('') || '<span class="text-muted">None</span>';

    return `
        <div class="candidate-card ${rankClass}">
            <div class="candidate-header">
                <div class="candidate-rank">
                    <div class="rank-badge">${candidate.rank}</div>
                    <div>
                        <div class="candidate-name">${escapeHtml(candidate.candidate_name)}</div>
                        <div class="candidate-source">${escapeHtml(candidate.source_file)}</div>
                    </div>
                </div>
                <div class="score-display">
                    <div class="score-value">${Math.round(candidate.overall_score * 100)}%</div>
                    <div class="score-label">Match Score</div>
                </div>
            </div>
            
            <div class="candidate-skills">
                <div class="skill-row">
                    <span class="skill-label">Demonstrated:</span>
                    <div class="skill-tags">${demonstratedSkills}</div>
                </div>
                <div class="skill-row">
                    <span class="skill-label">Mentioned:</span>
                    <div class="skill-tags">${mentionedSkills}</div>
                </div>
                <div class="skill-row">
                    <span class="skill-label">Missing:</span>
                    <div class="skill-tags">${missingSkills}</div>
                </div>
            </div>
            
            ${candidate.experience_summary ? `
                <div class="candidate-summary">
                    <div class="summary-title">Experience Summary</div>
                    <div class="summary-text">${escapeHtml(candidate.experience_summary)}</div>
                </div>
            ` : ''}
            
            ${candidate.match_explanation ? `
                <div class="candidate-explanation">${escapeHtml(candidate.match_explanation)}</div>
            ` : ''}
        </div>
    `;
}

// ===== Utilities =====

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showError(message) {
    // Create toast notification
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 24px;
        right: 24px;
        background: hsl(0, 80%, 60%);
        color: white;
        padding: 16px 24px;
        border-radius: 12px;
        font-weight: 500;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        z-index: 1000;
        animation: slideIn 0.3s ease;
    `;
    toast.textContent = message;

    // Add animation keyframes
    if (!document.getElementById('toast-styles')) {
        const style = document.createElement('style');
        style.id = 'toast-styles';
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
        `;
        document.head.appendChild(style);
    }

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Initialize
console.log('AuraAI Resume Ranking Service initialized');
