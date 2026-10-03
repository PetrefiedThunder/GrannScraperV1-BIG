// GrandmaScrape Dashboard JavaScript

const API_BASE = '/api/v1';

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function appendTextElement(parent, tag, text, className) {
    const element = document.createElement(tag);
    element.textContent = text;
    if (className) element.className = className;
    parent.appendChild(element);
    return element;
}

function appendLabeledValue(parent, label, value) {
    const paragraph = appendTextElement(parent, 'p', '');
    appendTextElement(paragraph, 'strong', label);
    paragraph.append(` ${value}`);
    return paragraph;
}

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

        await apiCall(`/jobs/${encodeURIComponent(jobId)}/run?concurrent=${concurrent}&incremental=false`, {
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

                const info = appendTextElement(li, 'div', '', 'job-info');
                appendTextElement(info, 'h3', job.name);
                const metadata = appendTextElement(info, 'p', '');
                [
                    ['URL:', job.start_url],
                    ['ID:', job.id],
                    ['Created:', new Date(job.created_at).toLocaleString()],
                ].forEach(([label, value], index) => {
                    if (index) metadata.appendChild(document.createElement('br'));
                    appendTextElement(metadata, 'strong', label);
                    metadata.append(` ${value}`);
                });

                const actions = appendTextElement(li, 'div', '', 'job-actions');
                const viewButton = appendTextElement(actions, 'button', 'View Details', 'btn');
                viewButton.addEventListener('click', () => viewJobDetails(job.id));
                const deleteButton = appendTextElement(actions, 'button', 'Delete', 'btn btn-secondary');
                deleteButton.addEventListener('click', () => deleteJob(job.id));

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
        await apiCall(`/jobs/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
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
        // Build dynamic content using text nodes, including API errors and job IDs.
        const encodedJobId = encodeURIComponent(jobId);
        const status = await apiCall(`/jobs/${encodedJobId}/status`);
        const content = document.createDocumentFragment();
        appendTextElement(content, 'h3', `Job: ${jobId}`);
        appendLabeledValue(content, 'Running:', status.is_running ? 'Yes' : 'No');
        appendLabeledValue(content, 'Has Results:', status.has_result ? 'Yes' : 'No');

        if (status.has_result) {
            const statusRow = appendLabeledValue(content, 'Status:', '');
            const badge = appendTextElement(statusRow, 'span', status.status, 'status-badge');
            if (['running', 'success', 'failed'].includes(status.status)) {
                badge.classList.add(`status-${status.status}`);
            }
            appendLabeledValue(content, 'Items Scraped:', status.items_scraped);
            appendLabeledValue(content, 'Pages Visited:', status.pages_visited);
            appendLabeledValue(content, 'Errors:', status.errors);
            appendLabeledValue(content, 'Duration:', `${status.duration?.toFixed(2)}s`);

            try {
                const results = await apiCall(`/jobs/${encodedJobId}/results?limit=10`);
                appendTextElement(content, 'h3', 'Results (first 10 items):');

                if (results.items.length > 0) {
                    const fields = Object.keys(results.items[0]);
                    const table = appendTextElement(content, 'table', '', 'results-table');
                    const head = appendTextElement(table, 'thead', '');
                    const headerRow = appendTextElement(head, 'tr', '');
                    fields.forEach(field => appendTextElement(headerRow, 'th', field));
                    const body = appendTextElement(table, 'tbody', '');
                    results.items.forEach(item => {
                        const row = appendTextElement(body, 'tr', '');
                        fields.forEach(field => {
                            const value = item[field];
                            appendTextElement(row, 'td', value !== null && value !== undefined ? value : '-');
                        });
                    });

                    if (results.pagination.has_more) {
                        const preview = appendTextElement(content, 'p', '');
                        preview.style.marginTop = '10px';
                        preview.style.color = '#666';
                        appendTextElement(preview, 'em', `Showing 10 of ${results.total_items} items`);
                    }
                } else {
                    appendTextElement(content, 'p', 'No results yet.');
                }
            } catch (error) {
                appendTextElement(content, 'p', `Failed to load results: ${error.message}`).style.color = '#dc3545';
            }
        } else if (status.is_running) {
            const message = appendTextElement(content, 'p', '');
            appendTextElement(message, 'em', 'Job is still running. Refresh to see updates.');
            const refresh = appendTextElement(content, 'button', 'Refresh', 'btn');
            refresh.addEventListener('click', () => viewJobDetails(jobId));
        } else {
            const message = appendTextElement(content, 'p', '');
            appendTextElement(message, 'em', 'No results available yet.');
        }

        contentDiv.replaceChildren(content);

    } catch (error) {
        contentDiv.replaceChildren();
        appendTextElement(contentDiv, 'p', `Error loading job details: ${error.message}`).style.color = '#dc3545';
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
