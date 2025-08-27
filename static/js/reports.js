// Reports functionality for Dangote Cement Execution Tracker

// Product Availability Report
function loadProductAvailabilityReport() {
    showReportLoader('productAvailabilityReport');
    
    fetch('/reports/product_availability')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch product availability data');
            }
            return response.json();
        })
        .then(data => {
            hideReportLoader('productAvailabilityReport');
            createProductAvailabilityElements();
            displayProductAvailability(data);
        })
        .catch(error => {
            hideReportLoader('productAvailabilityReport');
            showReportError('productAvailabilityReport', error.message);
            console.error('Error fetching product availability data:', error);
        });
}

// Create canvas elements for product availability report
function createProductAvailabilityElements() {
    const reportContainer = document.getElementById('productAvailabilityReport');
    
    // Check if elements already exist
    if (document.getElementById('productAvailabilityChart') && 
        document.getElementById('productByRegionChart') &&
        document.getElementById('productBreakdownTableBody')) {
        return;
    }
    
    // Create report structure
    reportContainer.innerHTML = `
        <div class="row mb-4">
            <div class="col-md-6 mb-4">
                <div class="chart-container">
                    <canvas id="productAvailabilityChart"></canvas>
                </div>
            </div>
            <div class="col-md-6 mb-4">
                <div class="chart-container">
                    <canvas id="productByRegionChart"></canvas>
                </div>
            </div>
        </div>
        
        <!-- Product Breakdown Table -->
        <div class="table-responsive">
            <table class="table table-sm table-bordered">
                <thead class="table-light">
                    <tr>
                        <th>Product</th>
                        <th>SW</th>
                        <th>SE</th>
                        <th>NC</th>
                        <th>NW</th>
                        <th>NE</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody id="productBreakdownTableBody">
                    <!-- Table content will be populated by JavaScript -->
                </tbody>
            </table>
        </div>
    `;
}

function displayProductAvailability(data) {
    // Product Availability Chart
    const ctx1 = document.getElementById('productAvailabilityChart');
    if (!ctx1) {
        console.error('Product availability chart canvas not found');
        return;
    }
    
    const productLabels = Object.keys(data.product_stats);
    const availableCounts = productLabels.map(product => data.product_stats[product].available);
    const notAvailableCounts = productLabels.map(product => data.product_stats[product].not_available);
    
    // Destroy existing chart if it exists
    if (window.productAvailabilityChart) {
        window.productAvailabilityChart.destroy();
    }
    
    // Create new chart
    window.productAvailabilityChart = new Chart(ctx1.getContext('2d'), {
        type: 'bar',
        data: {
            labels: productLabels,
            datasets: [
                {
                    label: 'Available',
                    data: availableCounts,
                    backgroundColor: 'rgba(75, 192, 192, 0.8)',
                    borderWidth: 1
                },
                {
                    label: 'Not Available',
                    data: notAvailableCounts,
                    backgroundColor: 'rgba(255, 99, 132, 0.8)',
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    stacked: true
                },
                y: {
                    stacked: true,
                    beginAtZero: true
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Product Availability Across All Outlets',
                    font: {
                        size: 16
                    }
                }
            }
        }
    });
    
    // Product by Region Chart
    const ctx2 = document.getElementById('productByRegionChart');
    if (!ctx2) {
        console.error('Product by region chart canvas not found');
        return;
    }
    
    const regions = Object.keys(data.product_by_region);
    
    // Calculate availability percentage by region
    const availabilityByRegion = regions.map(region => {
        let totalAvailable = 0;
        let totalProducts = 0;
        
        Object.keys(data.product_by_region[region]).forEach(product => {
            totalAvailable += data.product_by_region[region][product].available;
            totalProducts += data.product_by_region[region][product].available + 
                          data.product_by_region[region][product].not_available;
        });
        
        return (totalAvailable / totalProducts) * 100;
    });
    
    // Destroy existing chart if it exists
    if (window.productByRegionChart) {
        window.productByRegionChart.destroy();
    }
    
    // Create new chart
    window.productByRegionChart = new Chart(ctx2.getContext('2d'), {
        type: 'bar',
        data: {
            labels: regions,
            datasets: [{
                label: 'Product Availability (%)',
                data: availabilityByRegion,
                backgroundColor: 'rgba(54, 162, 235, 0.8)',
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
                    text: 'Product Availability by Region',
                    font: {
                        size: 16
                    }
                }
            }
        }
    });
    
    // Update table with breakdown by product and region
    populateProductBreakdownTable(data);
}

function populateProductBreakdownTable(data) {
    const tableBody = document.getElementById('productBreakdownTableBody');
    if (!tableBody) {
        console.error('Product breakdown table body not found');
        return;
    }
    
    tableBody.innerHTML = '';
    
    const products = Object.keys(data.product_stats);
    const regions = Object.keys(data.product_by_region);
    
    // Create rows for each product
    products.forEach(product => {
        const row = document.createElement('tr');
        
        // Product name cell
        const nameCell = document.createElement('td');
        nameCell.textContent = product;
        row.appendChild(nameCell);
        
        // Create cells for each region
        regions.forEach(region => {
            const regionData = data.product_by_region[region][product];
            const available = regionData ? regionData.available : 0;
            const total = regionData ? (regionData.available + regionData.not_available) : 0;
            const percentage = total > 0 ? (available / total) * 100 : 0;
            
            const cell = document.createElement('td');
            cell.innerHTML = `
                <div>${available}/${total}</div>
                <div><small>${percentage.toFixed(1)}%</small></div>
            `;
            
            // Add color coding based on percentage
            if (percentage >= 80) {
                cell.classList.add('table-success');
            } else if (percentage >= 50) {
                cell.classList.add('table-warning');
            } else {
                cell.classList.add('table-danger');
            }
            
            row.appendChild(cell);
        });
        
        // Total cell
        const totalAvailable = data.product_stats[product].available;
        const totalAll = totalAvailable + data.product_stats[product].not_available;
        const totalPercentage = totalAll > 0 ? (totalAvailable / totalAll) * 100 : 0;
        
        const totalCell = document.createElement('td');
        totalCell.innerHTML = `
            <div><strong>${totalAvailable}/${totalAll}</strong></div>
            <div><small>${totalPercentage.toFixed(1)}%</small></div>
        `;
        
        // Add color coding based on percentage
        if (totalPercentage >= 80) {
            totalCell.classList.add('table-success');
        } else if (totalPercentage >= 50) {
            totalCell.classList.add('table-warning');
        } else {
            totalCell.classList.add('table-danger');
        }
        
        row.appendChild(totalCell);
        
        tableBody.appendChild(row);
    });
}

// Execution Summary Report
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

// Create canvas elements for execution summary report
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
                            <div>Total Retail Points:</div>
                            <div class="fw-bold" id="totalOutletsCount">-</div>
                        </div>
                        <div class="d-flex justify-content-between mb-2">
                            <div>Visited Retail Point:</div>
                            <div class="fw-bold" id="executedOutletsCount">-</div>
                        </div>
                        <div class="d-flex justify-content-between mb-2">
                            <div>Total Visitations:</div>
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
                        <th>Visited</th>
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
    
    // Execution by Region Chart
    const ctx = document.getElementById('executionByRegionChart');
    if (!ctx) {
        console.error('Visitation by region chart canvas not found');
        return;
    }
    
    const regions = Object.keys(data.execution_by_region);
    const executedValues = regions.map(region => data.execution_by_region[region].executed);
    const totalValues = regions.map(region => data.execution_by_region[region].total);
    const percentages = regions.map(region => data.execution_by_region[region].percentage);
    
    // Destroy existing chart if it exists
    if (window.executionByRegionChart) {
        window.executionByRegionChart.destroy();
    }
    
    // Create new chart
    window.executionByRegionChart = new Chart(ctx.getContext('2d'), {
        type: 'bar',
        data: {
            labels: regions,
            datasets: [{
                label: 'Visited (%)',
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
                    text: 'Visitation Coverage by Region',
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
    
    // Populate execution by region table
    populateExecutionByRegionTable(data.execution_by_region);
}

function populateExecutionByRegionTable(executionByRegion) {
    const tableBody = document.getElementById('executionByRegionTableBody');
    if (!tableBody) {
        console.error('Visitations by region table body not found');
        return;
    }
    
    tableBody.innerHTML = '';
    
    // Sort regions by percentage descending
    const regions = Object.keys(executionByRegion).sort((a, b) => {
        return executionByRegion[b].percentage - executionByRegion[a].percentage;
    });
    
    // Create rows for each region
    regions.forEach(region => {
        const executed = executionByRegion[region].executed;
        const total = executionByRegion[region].total;
        const percentage = executionByRegion[region].percentage;
        
        const row = document.createElement('tr');
        
        // Region name
        const regionCell = document.createElement('td');
        regionCell.textContent = region;
        row.appendChild(regionCell);
        
        // Executed count
        const executedCell = document.createElement('td');
        executedCell.textContent = executed;
        row.appendChild(executedCell);
        
        // Total count
        const totalCell = document.createElement('td');
        totalCell.textContent = total;
        row.appendChild(totalCell);
        
        // Percentage
        const percentageCell = document.createElement('td');
        percentageCell.innerHTML = `${percentage.toFixed(1)}%`;
        row.appendChild(percentageCell);
        
        // Progress bar
        const progressCell = document.createElement('td');
        progressCell.innerHTML = `
            <div class="progress" style="height: 15px">
                <div class="progress-bar ${getProgressBarColorClass(percentage)}" 
                     role="progressbar" 
                     style="width: ${percentage}%" 
                     aria-valuenow="${percentage}" 
                     aria-valuemin="0" 
                     aria-valuemax="100"></div>
            </div>
        `;
        row.appendChild(progressCell);
        
        tableBody.appendChild(row);
    });
}

// Image Analysis Report
function loadImageAnalysisReport() {
    showReportLoader('imageAnalysisReport');
    
    fetch('/reports/image_analysis')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch image analysis data');
            }
            return response.json();
        })
        .then(data => {
            hideReportLoader('imageAnalysisReport');
            createImageAnalysisElements();
            displayImageAnalysis(data);
        })
        .catch(error => {
            hideReportLoader('imageAnalysisReport');
            showReportError('imageAnalysisReport', error.message);
            console.error('Error fetching image analysis data:', error);
        });
}

// Create canvas elements for image analysis report
function createImageAnalysisElements() {
    const reportContainer = document.getElementById('imageAnalysisReport');
    
    // Check if elements already exist
    if (document.getElementById('complianceScoreChart') && 
        document.getElementById('complianceByRegionChart') &&
        document.getElementById('complianceByCategoryChart')) {
        return;
    }
    
    // Create report structure
    reportContainer.innerHTML = `
        <!-- Compliance Score Overview -->
        <div class="row mb-4">
            <div class="col-md-4 text-center mb-4">
                <div class="card h-100">
                    <div class="card-body d-flex flex-column justify-content-center">
                        <h6 class="card-subtitle mb-3 text-muted">Overall Compliance</h6>
                        <div class="compliance-score text-success" id="compliancePercentage">-</div>
                        <div class="text-muted mb-3">
                            <span id="compliantCount">-</span> out of <span id="totalImagesCount">-</span> executions
                        </div>
                        <div class="small text-muted">Based on image analysis of before/after pictures</div>
                    </div>
                </div>
            </div>
            <div class="col-md-8 mb-4">
                <div class="row h-100">
                    <div class="col-md-6">
                        <div class="chart-container h-100">
                            <canvas id="complianceScoreChart"></canvas>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="chart-container h-100">
                            <canvas id="complianceByRegionChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row mb-4">
            <div class="col-md-6 mb-4">
                <div class="chart-container">
                    <canvas id="complianceByCategoryChart"></canvas>
                </div>
            </div>
            <div class="col-md-6 mb-4">
                <div class="card h-100">
                    <div class="card-header bg-white">
                        <h6 class="card-title mb-0">Example Analysis</h6>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-6 mb-2">
                                <div class="position-relative">
                                    <img src="https://i.imgur.com/7KY7ntJ.jpg" class="comparison-image w-100" alt="Before">
                                    <div class="image-label">BEFORE</div>
                                </div>
                            </div>
                            <div class="col-6 mb-2">
                                <div class="position-relative">
                                    <img src="https://i.imgur.com/4Hbgn3R.jpg" class="comparison-image w-100" alt="After">
                                    <div class="image-label">AFTER</div>
                                </div>
                            </div>
                        </div>
                        <div class="mt-2">
                            <div class="text-success mb-1"><i class="fas fa-check-circle me-1"></i> <strong>Compliance Score: 92%</strong></div>
                            <small class="text-muted">Improvements detected: Product visibility, organization, branding placement</small>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function displayImageAnalysis(data) {
    // Compliance Score Chart
    const ctx1 = document.getElementById('complianceScoreChart');
    if (!ctx1) {
        console.error('Compliance score chart canvas not found');
        return;
    }
    
    // Destroy existing chart if it exists
    if (window.complianceScoreChart) {
        window.complianceScoreChart.destroy();
    }
    
    // Create new doughnut chart for overall compliance
    window.complianceScoreChart = new Chart(ctx1.getContext('2d'), {
        type: 'doughnut',
        data: {
            labels: ['Compliant', 'Non-Compliant'],
            datasets: [{
                data: [data.overall.compliant_percentage, 100 - data.overall.compliant_percentage],
                backgroundColor: ['rgba(75, 192, 192, 0.8)', 'rgba(255, 99, 132, 0.8)'],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Overall Compliance Score',
                    font: {
                        size: 16
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const index = context.dataIndex;
                            const value = context.dataset.data[index];
                            return `${context.label}: ${value.toFixed(1)}%`;
                        }
                    }
                }
            }
        }
    });
    
    // Compliance by Region Chart
    const ctx2 = document.getElementById('complianceByRegionChart');
    if (!ctx2) {
        console.error('Compliance by region chart canvas not found');
        return;
    }
    
    const regions = Object.keys(data.by_region);
    const complianceByRegion = regions.map(region => data.by_region[region].compliant_percentage);
    
    // Destroy existing chart if it exists
    if (window.complianceByRegionChart) {
        window.complianceByRegionChart.destroy();
    }
    
    // Create new chart
    window.complianceByRegionChart = new Chart(ctx2.getContext('2d'), {
        type: 'bar',
        data: {
            labels: regions,
            datasets: [{
                label: 'Compliance Score (%)',
                data: complianceByRegion,
                backgroundColor: 'rgba(54, 162, 235, 0.8)',
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
                    text: 'Compliance Score by Region',
                    font: {
                        size: 16
                    }
                }
            }
        }
    });
    
    // Compliance by Category
    const ctx3 = document.getElementById('complianceByCategoryChart');
    if (!ctx3) {
        console.error('Compliance by category chart canvas not found');
        return;
    }
    
    const categories = Object.keys(data.by_category);
    const complianceByCategory = categories.map(category => data.by_category[category].score);
    
    // Destroy existing chart if it exists
    if (window.complianceByCategoryChart) {
        window.complianceByCategoryChart.destroy();
    }
    
    // Create new radar chart
    window.complianceByCategoryChart = new Chart(ctx3.getContext('2d'), {
        type: 'radar',
        data: {
            labels: categories,
            datasets: [{
                label: 'Compliance Score',
                data: complianceByCategory,
                fill: true,
                backgroundColor: 'rgba(255, 102, 0, 0.2)',
                borderColor: 'rgba(255, 102, 0, 1)',
                borderWidth: 2,
                pointBackgroundColor: 'rgba(255, 102, 0, 1)',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: 'rgba(255, 102, 0, 1)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    angleLines: {
                        display: true
                    },
                    suggestedMin: 0,
                    suggestedMax: 100
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Compliance Score by Category',
                    font: {
                        size: 16
                    }
                }
            }
        }
    });
    
    // Update compliant count
    document.getElementById('totalImagesCount').textContent = data.overall.total_images;
    document.getElementById('compliantCount').textContent = data.overall.compliant_count;
    document.getElementById('compliancePercentage').textContent = data.overall.compliant_percentage.toFixed(1) + '%';
    
    // Set compliance score color
    const compliancePercentageElement = document.getElementById('compliancePercentage');
    if (compliancePercentageElement) {
        if (data.overall.compliant_percentage >= 80) {
            compliancePercentageElement.className = 'compliance-score text-success';
        } else if (data.overall.compliant_percentage >= 50) {
            compliancePercentageElement.className = 'compliance-score text-warning';
        } else {
            compliancePercentageElement.className = 'compliance-score text-danger';
        }
    }
}

// Helper Functions
function showReportLoader(reportId) {
    const reportElement = document.getElementById(reportId);
    if (reportElement) {
        reportElement.innerHTML = `
            <div class="d-flex justify-content-center align-items-center" style="height: 300px">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <span class="ms-2">Loading report data...</span>
            </div>
        `;
    }
}

function hideReportLoader(reportId) {
    // The loader will be replaced by the report content
}

function showReportError(reportId, errorMessage) {
    const reportElement = document.getElementById(reportId);
    if (reportElement) {
        reportElement.innerHTML = `
            <div class="alert alert-danger" role="alert">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <strong>Error loading report:</strong> ${errorMessage}
            </div>
        `;
    }
}

function getProgressBarColorClass(percentage) {
    if (percentage >= 80) {
        return 'bg-success';
    } else if (percentage >= 50) {
        return 'bg-warning';
    } else {
        return 'bg-danger';
    }
}