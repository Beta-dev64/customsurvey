// Image Analysis Report functionality

// Global chart references
let complianceScoreChart = null;
let complianceByRegionChart = null;
let complianceByCategoryChart = null;

// Load Image Analysis Report
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

// Create elements for image analysis report
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
                        <div class="chart-container h-100" style="height:300px;min-height:300px;max-height:300px;">
                            <canvas id="complianceScoreChart"></canvas>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="chart-container h-100" style="height:300px;min-height:300px;max-height:300px;">
                            <canvas id="complianceByRegionChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row mb-4">
            <div class="col-md-6 mb-4">
                <div class="chart-container" style="height:300px;min-height:300px;max-height:300px;">
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
    const canvasId1 = 'complianceScoreChart';
    const canvas1 = document.getElementById(canvasId1);
    if (!canvas1) {
        console.error(`Canvas element with ID '${canvasId1}' not found`);
        return;
    }
    
    // Safely destroy existing chart
    if (complianceScoreChart) {
        try {
            complianceScoreChart.destroy();
        } catch (error) {
            console.warn('Error destroying compliance score chart:', error);
        }
    }
    
    // Create new doughnut chart for overall compliance
    try {
        const ctx1 = canvas1.getContext('2d');
        complianceScoreChart = new Chart(ctx1, {
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
    } catch (error) {
        console.error('Error creating compliance score chart:', error);
    }
    
    // Compliance by Region Chart
    const canvasId2 = 'complianceByRegionChart';
    const canvas2 = document.getElementById(canvasId2);
    if (!canvas2) {
        console.error(`Canvas element with ID '${canvasId2}' not found`);
        return;
    }
    
    const regions = Object.keys(data.by_region);
    const complianceByRegion = regions.map(region => data.by_region[region].compliant_percentage);
    
    // Safely destroy existing chart
    if (complianceByRegionChart) {
        try {
            complianceByRegionChart.destroy();
        } catch (error) {
            console.warn('Error destroying compliance by region chart:', error);
        }
    }
    
    // Create new chart
    try {
        const ctx2 = canvas2.getContext('2d');
        complianceByRegionChart = new Chart(ctx2, {
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
    } catch (error) {
        console.error('Error creating compliance by region chart:', error);
    }
    
    // Compliance by Category
    const canvasId3 = 'complianceByCategoryChart';
    const canvas3 = document.getElementById(canvasId3);
    if (!canvas3) {
        console.error(`Canvas element with ID '${canvasId3}' not found`);
        return;
    }
    
    const categories = Object.keys(data.by_category);
    const complianceByCategory = categories.map(category => data.by_category[category].score);
    
    // Safely destroy existing chart
    if (complianceByCategoryChart) {
        try {
            complianceByCategoryChart.destroy();
        } catch (error) {
            console.warn('Error destroying compliance by category chart:', error);
        }
    }
    
    // Create new radar chart
    try {
        const ctx3 = canvas3.getContext('2d');
        complianceByCategoryChart = new Chart(ctx3, {
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
    } catch (error) {
        console.error('Error creating compliance by category chart:', error);
    }
    
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