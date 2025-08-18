// Utility functions for reports

// Loading and error handling
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

// Helper for execution report table
function populateExecutionByRegionTable(executionByRegion) {
    const tableBody = document.getElementById('executionByRegionTableBody');
    if (!tableBody) {
        console.error('Execution by region table body not found');
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

// Helper for product availability table
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

function getProgressBarColorClass(percentage) {
    if (percentage >= 80) {
        return 'bg-success';
    } else if (percentage >= 50) {
        return 'bg-warning';
    } else {
        return 'bg-danger';
    }
}