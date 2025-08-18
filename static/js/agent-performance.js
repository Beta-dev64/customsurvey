// Agent Performance Report

function loadAgentPerformanceReport() {
    showReportLoader('agentPerformanceReport');
    
    fetch('/api/agent_performance')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch agent performance data');
            }
            return response.json();
        })
        .then(data => {
            hideReportLoader('agentPerformanceReport');
            createAgentPerformanceElements();
            displayAgentPerformance(data);
        })
        .catch(error => {
            console.error('Error loading agent performance report:', error);
            showReportError('agentPerformanceReport', error.message);
        });
}

function createAgentPerformanceElements() {
    const reportContainer = document.getElementById('agentPerformanceReport');
    
    // Check if elements already exist
    if (document.getElementById('agentPerformanceTable')) {
        return;
    }
    
    reportContainer.innerHTML = `
        <div class="row mb-4">
            <div class="col-md-12">
                <div class="card">
                    <div class="card-header bg-primary text-white">
                        <h5 class="mb-0">Agent Performance Overview</h5>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table id="agentPerformanceTable" class="table table-striped table-hover">
                                <thead>
                                    <tr>
                                        <th>Agent ID</th>
                                        <th>Name</th>
                                        <th>Username</th>
                                        <th>Region</th>
                                        <th>State</th>
                                        <th>LGA</th>
                                        <th>Executions</th>
                                        <th>Outlets Visited</th>
                                        <th>Outlets Assigned</th>
                                        <th>Coverage %</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="agentPerformanceTableBody">
                                    <!-- Data will be inserted here -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header bg-primary text-white">
                        <h5 class="mb-0">Executions by Agent</h5>
                    </div>
                    <div class="card-body">
                        <canvas id="executionsByAgentChart" height="300"></canvas>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header bg-primary text-white">
                        <h5 class="mb-0">Coverage by Agent</h5>
                    </div>
                    <div class="card-body">
                        <canvas id="coverageByAgentChart" height="300"></canvas>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function displayAgentPerformance(data) {
    // Populate table
    const tableBody = document.getElementById('agentPerformanceTableBody');
    tableBody.innerHTML = '';
    
    data.forEach(agent => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${agent.id}</td>
            <td>${agent.full_name}</td>
            <td>${agent.username}</td>
            <td>${agent.region || 'N/A'}</td>
            <td>${agent.state || 'N/A'}</td>
            <td>${agent.lga || 'N/A'}</td>
            <td>${agent.executions_performed}</td>
            <td>${agent.outlets_visited}</td>
            <td>${agent.outlets_assigned}</td>
            <td>${agent.coverage_percentage}%</td>
            <td>
                <button class="btn btn-sm btn-info" onclick="viewAgentDetails(${agent.id})">
                    <i class="fas fa-eye"></i> Details
                </button>
            </td>
        `;
        tableBody.appendChild(row);
    });
    
    // Create charts
    createExecutionsByAgentChart(data);
    createCoverageByAgentChart(data);
}

function createExecutionsByAgentChart(data) {
    const ctx = document.getElementById('executionsByAgentChart');
    
    // Extract data for chart
    const labels = data.map(agent => agent.full_name);
    const executionsData = data.map(agent => agent.executions_performed);
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Executions Performed',
                data: executionsData,
                backgroundColor: 'rgba(54, 162, 235, 0.7)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Number of Executions'
                    }
                }
            }
        }
    });
}

function createCoverageByAgentChart(data) {
    const ctx = document.getElementById('coverageByAgentChart');
    
    // Extract data for chart
    const labels = data.map(agent => agent.full_name);
    const coverageData = data.map(agent => agent.coverage_percentage);
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Coverage Percentage',
                data: coverageData,
                backgroundColor: 'rgba(75, 192, 192, 0.7)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: {
                        display: true,
                        text: 'Coverage %'
                    }
                }
            }
        }
    });
}

function viewAgentDetails(agentId) {
    // Redirect to a detailed view for this agent
    // This could be implemented in the future
    alert(`View details for agent ID: ${agentId} - Feature coming soon!`);
}

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the reports page and the tab is active
    const agentPerformanceTab = document.getElementById('agent-performance-tab');
    if (agentPerformanceTab) {
        agentPerformanceTab.addEventListener('click', function() {
            loadAgentPerformanceReport();
        });
        
        // If this tab is active by default, load the report
        if (agentPerformanceTab.classList.contains('active')) {
            loadAgentPerformanceReport();
        }
    }
});