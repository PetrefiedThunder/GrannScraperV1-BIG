// GrandmaScrape Dashboard JavaScript

const API_BASE = 'http://localhost:8000/api/v1';

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function showAlert(message, type = 'info') {
    const container = document.getElementById('alert-container');
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    container.appendChild(alert);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        alert.remove();
    }, 5000);
}

async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'API request failed');
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showAlert(`Error: ${error.message}`, 'error');
        throw error;
    }
}

// ============================================================================
// STATS & INFO
// ============================================================================

async function loadStats() {
    try {
        const info = await apiCall('/info');
        const stats = info.statistics;

        document.getElementById('stat-jobs').textContent = stats.total_jobs;
        document.getElementById('stat-running').textContent = stats.running_jobs;
        document.getElementById('stat-completed').textContent = stats.completed_jobs;
        document.getElementById('stat-workflows').textContent = stats.workflows;
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

// ============================================================================
// AUTO-SCRAPE FORM
// ============================================================================

document.getElementById('auto-scrape-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const url = document.getElementById('url').value;
    const maxPages = parseInt(document.getElementById('max-pages').value);
    const exportFormat = document.getElementById('export-format').value;
    const concurrent = document.getElementById('concurrent').checked;

    const submitBtn = e.target.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Analyzing...';

    try {
        // Step 1: Analyze URL
        showAlert(`Analyzing ${url}...`, 'info');

        const analysis = await apiCall('/analyze', {
            method: 'POST',
            body: JSON.stringify({ url, max_pages: 1 }),
        });

        showAlert(`Auto-detected ${Object.keys(analysis.fields || {}).length} fields!`, 'success');

        // Step 2: Create job
        submitBtn.textContent = 'Creating job...';

        const jobData = {
            job: {
                id: `job_${Date.now()}`,
                name: `Auto-scraped: ${url}`,
                start_url: url,
                item_selector: analysis.item_selector,
                fields: analysis.fields || {},
                pagination: analysis.pagination || {},
                max_pages: maxPages,
                export: { format: exportFormat },
                browser: { enabled: false },
                rate_limit: { requests_per_second: 2 },
                enabled: true,
            },
        };

        const createResult = await apiCall('/jobs', {
            method: 'POST',
            body: JSON.stringify(jobData),
        });

        const jobId = createResult.job_id;

        // Step 3: Run job
        submitBtn.textContent = 'Starting scrape...';

        await apiCall(`/jobs/${jobId}/run?concurrent=${concurrent}&incremental=false`, {
            method: 'POST',
        });

        showAlert(`Job ${jobId} started! Check the job list below.`, 'success');

        // Reset form
        submitBtn.textContent = 'Start Auto-Scrape';
        submitBtn.disabled = false;
        e.target.reset();

        // Reload jobs
        await loadJobs();

    } catch (error) {
        submitBtn.textContent = 'Start Auto-Scrape';
        submitBtn.disabled = false;
        showAlert(`Failed to start scrape: ${error.message}`, 'error');
    }
});

// ============================================================================
// JOB LIST
// ============================================================================

async function loadJobs() {
    const listElement = document.getElementById('job-list');
    const loadingElement = document.getElementById('job-list-loading');

    loadingElement.classList.remove('hidden');
    listElement.innerHTML = '';

    try {
        const data = await apiCall('/jobs');
        const jobs = data.jobs;

        if (jobs.length === 0) {
            listElement.innerHTML = '<li style="text-align: center; padding: 20px; color: #999;">No jobs yet. Start an auto-scrape above!</li>';
        } else {
            jobs.forEach(job => {
                const li = document.createElement('li');
                li.className = 'job-item';

                li.innerHTML = `
                    <div class="job-info">
                        <h3>${job.name}</h3>
                        <p>
                            <strong>URL:</strong> ${job.start_url}<br>
                            <strong>ID:</strong> ${job.id}<br>
                            <strong>Created:</strong> ${new Date(job.created_at).toLocaleString()}
                        </p>
                    </div>
                    <div class="job-actions">
                        <button class="btn" onclick="viewJobDetails('${job.id}')">View Details</button>
                        <button class="btn btn-secondary" onclick="deleteJob('${job.id}')">Delete</button>
                    </div>
                `;

                listElement.appendChild(li);
            });
        }

        await loadStats();

    } catch (error) {
        listElement.innerHTML = '<li style="text-align: center; padding: 20px; color: #dc3545;">Failed to load jobs</li>';
    } finally {
        loadingElement.classList.add('hidden');
    }
}

async function deleteJob(jobId) {
    if (!confirm('Are you sure you want to delete this job?')) {
        return;
    }

    try {
        await apiCall(`/jobs/${jobId}`, { method: 'DELETE' });
        showAlert(`Job ${jobId} deleted`, 'success');
        await loadJobs();
    } catch (error) {
        showAlert(`Failed to delete job: ${error.message}`, 'error');
    }
}

// ============================================================================
// JOB DETAILS
// ============================================================================

async function viewJobDetails(jobId) {
    const detailsCard = document.getElementById('job-details');
    const contentDiv = document.getElementById('job-details-content');

    detailsCard.classList.remove('hidden');
    contentDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading...</p></div>';

    try {
        // Get job status
        const status = await apiCall(`/jobs/${jobId}/status`);

        let html = `
            <h3>Job: ${jobId}</h3>
            <p><strong>Running:</strong> ${status.is_running ? 'Yes' : 'No'}</p>
            <p><strong>Has Results:</strong> ${status.has_result ? 'Yes' : 'No'}</p>
        `;

        if (status.has_result) {
            html += `
                <p><strong>Status:</strong> <span class="status-badge status-${status.status}">${status.status}</span></p>
                <p><strong>Items Scraped:</strong> ${status.items_scraped}</p>
                <p><strong>Pages Visited:</strong> ${status.pages_visited}</p>
                <p><strong>Errors:</strong> ${status.errors}</p>
                <p><strong>Duration:</strong> ${status.duration?.toFixed(2)}s</p>
            `;

            // Get results
            try {
                const results = await apiCall(`/jobs/${jobId}/results?limit=10`);

                html += '<h3>Results (first 10 items):</h3>';

                if (results.items.length > 0) {
                    // Create table
                    const fields = Object.keys(results.items[0]);

                    html += '<table class="results-table"><thead><tr>';
                    fields.forEach(field => {
                        html += `<th>${field}</th>`;
                    });
                    html += '</tr></thead><tbody>';

                    results.items.forEach(item => {
                        html += '<tr>';
                        fields.forEach(field => {
                            const value = item[field];
                            html += `<td>${value !== null && value !== undefined ? value : '-'}</td>`;
                        });
                        html += '</tr>';
                    });

                    html += '</tbody></table>';

                    if (results.pagination.has_more) {
                        html += `<p style="margin-top: 10px; color: #666;"><em>Showing 10 of ${results.total_items} items</em></p>`;
                    }
                } else {
                    html += '<p>No results yet.</p>';
                }

            } catch (error) {
                html += `<p style="color: #dc3545;">Failed to load results: ${error.message}</p>`;
            }
        } else if (status.is_running) {
            html += '<p><em>Job is still running. Refresh to see updates.</em></p>';
            html += '<button class="btn" onclick="viewJobDetails(\'' + jobId + '\')">Refresh</button>';
        } else {
            html += '<p><em>No results available yet.</em></p>';
        }

        contentDiv.innerHTML = html;

    } catch (error) {
        contentDiv.innerHTML = `<p style="color: #dc3545;">Error loading job details: ${error.message}</p>`;
    }

    // Scroll to details
    detailsCard.scrollIntoView({ behavior: 'smooth' });
}

function hideJobDetails() {
    document.getElementById('job-details').classList.add('hidden');
}

// ============================================================================
// INITIALIZATION
// ============================================================================

async function init() {
    // Load initial data
    await loadStats();
    await loadJobs();

    // Auto-refresh every 10 seconds
    setInterval(async () => {
        await loadStats();
    }, 10000);
}

// Start the app
init().catch(console.error);
