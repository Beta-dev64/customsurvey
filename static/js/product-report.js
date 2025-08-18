// Product Availability Report functionality

// Global chart references
let productAvailabilityChart = null;
let productByRegionChart = null;

// Load Product Availability Report
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
    const canvasId1 = 'productAvailabilityChart';
    const canvas1 = document.getElementById(canvasId1);
    if (!canvas1) {
        console.error(`Canvas element with ID '${canvasId1}' not found`);
        return;
    }
    
    const productLabels = Object.keys(data.product_stats);
    const availableCounts = productLabels.map(product => data.product_stats[product].available);
    const notAvailableCounts = productLabels.map(product => data.product_stats[product].not_available);
    
    // Safely destroy existing chart
    if (productAvailabilityChart) {
        try {
            productAvailabilityChart.destroy();
        } catch (error) {
            console.warn('Error destroying product availability chart:', error);
        }
    }
    
    // Create new chart
    try {
        const ctx1 = canvas1.getContext('2d');
        productAvailabilityChart = new Chart(ctx1, {
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
    } catch (error) {
        console.error('Error creating product availability chart:', error);
    }
    
    // Product by Region Chart
    const canvasId2 = 'productByRegionChart';
    const canvas2 = document.getElementById(canvasId2);
    if (!canvas2) {
        console.error(`Canvas element with ID '${canvasId2}' not found`);
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
    
    // Safely destroy existing chart
    if (productByRegionChart) {
        try {
            productByRegionChart.destroy();
        } catch (error) {
            console.warn('Error destroying product by region chart:', error);
        }
    }
    
    // Create new chart
    try {
        const ctx2 = canvas2.getContext('2d');
        productByRegionChart = new Chart(ctx2, {
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
    } catch (error) {
        console.error('Error creating product by region chart:', error);
    }
    
    // Update table with breakdown by product and region
    populateProductBreakdownTable(data);
}

// POSM Deployment Report functionality

// Global chart references
let posmDeploymentChart = null;
let posmByRegionChart = null;

// Load POSM Deployment Report
function loadProductAvailabilityReport() {
    showReportLoader('productAvailabilityReport');
    
    fetch('/reports/posm_deployment')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch POSM deployment data');
            }
            return response.json();
        })
        .then(data => {
            hideReportLoader('productAvailabilityReport');
            createPosmDeploymentElements();
            displayPosmDeployment(data);
        })
        .catch(error => {
            hideReportLoader('productAvailabilityReport');
            showReportError('productAvailabilityReport', error.message);
            console.error('Error fetching POSM deployment data:', error);
        });
}

// Create canvas elements for POSM deployment report
function createPosmDeploymentElements() {
    const reportContainer = document.getElementById('productAvailabilityReport');
    
    // Check if elements already exist
    if (document.getElementById('posmDeploymentChart') && 
        document.getElementById('posmByRegionChart') &&
        document.getElementById('posmBreakdownTableBody')) {
        return;
    }
    
    // Create report structure
    reportContainer.innerHTML = `
        <div class="row mb-4">
            <div class="col-md-6 mb-4">
                <div class="chart-container">
                    <canvas id="posmDeploymentChart"></canvas>
                </div>
            </div>
            <div class="col-md-6 mb-4">
                <div class="chart-container">
                    <canvas id="posmByRegionChart"></canvas>
                </div>
            </div>
        </div>
        
        <!-- POSM Breakdown Table -->
        <div class="table-responsive">
            <table class="table table-sm table-bordered">
                <thead class="table-light">
                    <tr>
                        <th>POSM Item</th>
                        <th>SW</th>
                        <th>SE</th>
                        <th>NC</th>
                        <th>NW</th>
                        <th>NE</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody id="posmBreakdownTableBody">
                    <!-- Table content will be populated by JavaScript -->
                </tbody>
            </table>
        </div>
    `;
}

function displayPosmDeployment(data) {
    // POSM Deployment Chart
    const canvasId1 = 'posmDeploymentChart';
    const canvas1 = document.getElementById(canvasId1);
    if (!canvas1) {
        console.error(`Canvas element with ID '${canvasId1}' not found`);
        return;
    }
    
    const posmLabels = Object.keys(data.posm_stats);
    const deployedCounts = posmLabels.map(posm => data.posm_stats[posm].available);
    const notDeployedCounts = posmLabels.map(posm => data.posm_stats[posm].not_available);
    
    // Safely destroy existing chart
    if (posmDeploymentChart) {
        try {
            posmDeploymentChart.destroy();
        } catch (error) {
            console.warn('Error destroying POSM deployment chart:', error);
        }
    }
    
    // Create new chart
    try {
        const ctx1 = canvas1.getContext('2d');
        posmDeploymentChart = new Chart(ctx1, {
            type: 'bar',
            data: {
                labels: posmLabels,
                datasets: [
                    {
                        label: 'Deployed',
                        data: deployedCounts,
                        backgroundColor: 'rgba(75, 192, 192, 0.8)',
                        borderWidth: 1
                    },
                    {
                        label: 'Not Deployed',
                        data: notDeployedCounts,
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
                        text: 'POSM Deployment Across All Outlets',
                        font: {
                            size: 16
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error creating POSM deployment chart:', error);
    }
    
    // POSM by Region Chart
    const canvasId2 = 'posmByRegionChart';
    const canvas2 = document.getElementById(canvasId2);
    if (!canvas2) {
        console.error(`Canvas element with ID '${canvasId2}' not found`);
        return;
    }
    
    const regions = Object.keys(data.posm_by_region);
    
    // Calculate deployment percentage by region
    const deploymentByRegion = regions.map(region => {
        let totalDeployed = 0;
        let totalPosm = 0;
        
        Object.keys(data.posm_by_region[region]).forEach(posm => {
            totalDeployed += data.posm_by_region[region][posm].available;
            totalPosm += data.posm_by_region[region][posm].available + 
                          data.posm_by_region[region][posm].not_available;
        });
        
        return (totalDeployed / totalPosm) * 100;
    });
    
    // Safely destroy existing chart
    if (posmByRegionChart) {
        try {
            posmByRegionChart.destroy();
        } catch (error) {
            console.warn('Error destroying POSM by region chart:', error);
        }
    }
    
    // Create new chart
    try {
        const ctx2 = canvas2.getContext('2d');
        posmByRegionChart = new Chart(ctx2, {
            type: 'bar',
            data: {
                labels: regions,
                datasets: [{
                    label: 'POSM Deployment (%)',
                    data: deploymentByRegion,
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
                        text: 'POSM Deployment by Region',
                        font: {
                            size: 16
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error creating POSM by region chart:', error);
    }
    
    // Update table with breakdown by POSM and region
    populatePosmBreakdownTable(data);
}

// Populate the POSM breakdown table
function populatePosmBreakdownTable(data) {
    const tableBody = document.getElementById('posmBreakdownTableBody');
    if (!tableBody) {
        console.error('POSM breakdown table body element not found');
        return;
    }
    
    tableBody.innerHTML = '';
    
    const posmItems = Object.keys(data.posm_stats);
    const regions = Object.keys(data.posm_by_region);
    
    posmItems.forEach(posm => {
        const row = document.createElement('tr');
        
        // POSM name cell
        const nameCell = document.createElement('td');
        nameCell.textContent = posm;
        row.appendChild(nameCell);
        
        // Region cells
        let totalDeployed = 0;
        
        regions.forEach(region => {
            const regionCell = document.createElement('td');
            const deployedCount = data.posm_by_region[region][posm]?.available || 0;
            totalDeployed += deployedCount;
            
            regionCell.textContent = deployedCount;
            row.appendChild(regionCell);
        });
        
        // Total cell
        const totalCell = document.createElement('td');
        totalCell.textContent = totalDeployed;
        totalCell.className = 'fw-bold';
        row.appendChild(totalCell);
        
        tableBody.appendChild(row);
    });
    
    // Add a summary row
    const summaryRow = document.createElement('tr');
    summaryRow.className = 'table-light fw-bold';
    
    const summaryLabelCell = document.createElement('td');
    summaryLabelCell.textContent = 'Total Deployment';
    summaryRow.appendChild(summaryLabelCell);
    
    let grandTotal = 0;
    
    regions.forEach(region => {
        const regionSummaryCell = document.createElement('td');
        let regionTotal = 0;
        
        posmItems.forEach(posm => {
            regionTotal += data.posm_by_region[region][posm]?.available || 0;
        });
        
        grandTotal += regionTotal;
        regionSummaryCell.textContent = regionTotal;
        summaryRow.appendChild(regionSummaryCell);
    });
    
    const grandTotalCell = document.createElement('td');
    grandTotalCell.textContent = grandTotal;
    summaryRow.appendChild(grandTotalCell);
    
    tableBody.appendChild(summaryRow);
}