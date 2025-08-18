// Execution Summary Report functionality

// Global chart reference
let executionByRegionChart = null;

// Load Execution Summary Report
function loadExecutionSummaryReport() {
    showReportLoader('executionSummaryReport');
    
    fetch('/reports/execution_summary')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch execution summary data');
            }
            return response.json();
        })
        .then(data => {
            hideReportLoader('executionSummaryReport');
            createExecutionSummaryElements();
            displayExecutionSummary(data);
        })
        .catch(error => {
            hideReportLoader('executionSummaryReport');
            showReportError('executionSummaryReport', error.message);
            console.error('Error fetching execution summary data:', error);
        });
}

// Create elements for execution summary report
function createExecutionSummaryElements() {
    const reportContainer = document.getElementById('executionSummaryReport');
    
    // Check if elements already exist
    if (document.getElementById('executionByRegionChart') && 
        document.getElementById('executionByRegionTableBody')) {
        return;
    }
    
    // Create report structure
    reportContainer.innerHTML = `
        <!-- Summary Stats Cards -->
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-body">
                        <h6 class="card-subtitle mb-3 text-muted">Coverage Statistics</h6>
                        <div class="d-flex justify-content-between mb-2">
                            <div>Total Outlets:</div>
                            <div class="fw-bold" id="totalOutletsCount">-</div>
                        </div>
                        <div class="d-flex justify-content-between mb-2">
                            <div>Executed Outlets:</div>
                            <div class="fw-bold" id="executedOutletsCount">-</div>
                        </div>
                        <div class="d-flex justify-content-between mb-2">
                            <div>Total Executions:</div>
                            <div class="fw-bold" id="totalExecutionsCount">-</div>
                        </div>
                        <div class="d-flex justify-content-between mb-2">
                            <div>Coverage Percentage:</div>
                            <div class="fw-bold" id="coveragePercentage">-</div>
                        </div>
                        <div class="progress mt-3" style="height: 20px">
                            <div class="progress-bar bg-primary-dangote" 
                                 id="coverageProgressBar"
                                 role="progressbar" 
                                 style="width: 0%" 
                                 aria-valuenow="0" 
                                 aria-valuemin="0" 
                                 aria-valuemax="100"></div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="chart-container">
                    <canvas id="executionByRegionChart"></canvas>
                </div>
            </div>
        </div>
        
        <!-- Execution Breakdown Table -->
        <div class="table-responsive">
            <table class="table table-sm table-bordered">
                <thead class="table-light">
                    <tr>
                        <th>Region</th>
                        <th>Executed</th>
                        <th>Total</th>
                        <th>Percentage</th>
                        <th>Progress</th>
                    </tr>
                </thead>
                <tbody id="executionByRegionTableBody">
                    <!-- Table content will be populated by JavaScript -->
                </tbody>
            </table>
        </div>
    `;
}

function displayExecutionSummary(data) {
    // Update summary statistics
    document.getElementById('totalOutletsCount').textContent = data.total_outlets;
    document.getElementById('executedOutletsCount').textContent = data.executed_outlets;
    document.getElementById('coveragePercentage').textContent = data.coverage_percentage + '%';
    document.getElementById('totalExecutionsCount').textContent = data.total_executions;
    
    // Update progress bar
    const progressBar = document.getElementById('coverageProgressBar');
    if (progressBar) {
        progressBar.style.width = data.coverage_percentage + '%';
        progressBar.setAttribute('aria-valuenow', data.coverage_percentage);
    }
    
    // Get canvas for chart
    const canvasId = 'executionByRegionChart';
    const canvas = document.getElementById(canvasId);
    if (!canvas) {
        console.error(`Canvas element with ID '${canvasId}' not found`);
        return;
    }
    
    const regions = Object.keys(data.execution_by_region);
    const executedValues = regions.map(region => data.execution_by_region[region].executed);
    const totalValues = regions.map(region => data.execution_by_region[region].total);
    const percentages = regions.map(region => data.execution_by_region[region].percentage);
    
    // Safely destroy existing chart
    if (executionByRegionChart) {
        try {
            executionByRegionChart.destroy();
        } catch (error) {
            console.warn('Error destroying execution by region chart:', error);
        }
    }
    
    // Create new chart
    try {
        const ctx = canvas.getContext('2d');
        executionByRegionChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: regions,
                datasets: [{
                    label: 'Executed (%)',
                    data: percentages,
                    backgroundColor: 'rgba(255, 102, 0, 0.8)',
                    borderWidth: 1,
                    yAxisID: 'y1'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y1: {
                        type: 'linear',
                        position: 'left',
                        beginAtZero: true,
                        max: 100,
                        title: {
                            display: true,
                            text: 'Percentage (%)'
                        },
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Execution Coverage by Region',
                        font: {
                            size: 16
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const index = context.dataIndex;
                                const executed = executedValues[index];
                                const total = totalValues[index];
                                const percentage = percentages[index];
                                return `${executed}/${total} outlets (${percentage.toFixed(1)}%)`;
                            }
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error creating execution by region chart:', error);
    }
    
    // Populate execution by region table
    populateExecutionByRegionTable(data.execution_by_region);
}