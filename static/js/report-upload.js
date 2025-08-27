/**
 * Report Upload JS
 * Handles XLSX file upload, parsing, and preview functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const browseBtn = document.getElementById('browseBtn');
    const uploadStatus = document.getElementById('uploadStatus');
    const uploadProgress = document.getElementById('uploadProgress');
    const uploadStatusText = document.getElementById('uploadStatusText');
    const previewSection = document.getElementById('previewSection');
    const sheetTabs = document.getElementById('sheetTabs');
    const previewTable = document.getElementById('previewTable');
    const previewTableHead = document.getElementById('previewTableHead');
    const previewTableBody = document.getElementById('previewTableBody');
    const rowCount = document.getElementById('rowCount');
    const validationSummary = document.getElementById('validationSummary');
    const validationIssuesList = document.getElementById('validationIssuesList');
    const mappingSection = document.getElementById('mappingSection');
    const columnMappings = document.getElementById('columnMappings');
    const configureBtn = document.getElementById('configureBtn');
    const importBtn = document.getElementById('importBtn');
    const cancelBtn = document.getElementById('cancelBtn');
    const refreshPreviewBtn = document.getElementById('refreshPreviewBtn');
    const resultsSection = document.getElementById('resultsSection');
    const successAlert = document.getElementById('successAlert');
    const errorAlert = document.getElementById('errorAlert');
    const successMessage = document.getElementById('successMessage');
    const errorMessage = document.getElementById('errorMessage');
    const importSummary = document.getElementById('importSummary');
    
    // State variables
    let workbook = null;
    let activeSheet = null;
    let sheetData = {};
    let columnMap = {};
    let validationErrors = [];
    
    // Required fields for different report types
    const requiredFields = {
        'posm': ['Agent Name', 'URN', 'Retail Point Name', 'Address', 'State', 'LGA'],
        'agent': ['Name', 'Username', 'Role', 'Region', 'State'],
        'execution': ['Agent', 'Retail Point', 'Date', 'Status']
    };
    
    // Initialize event listeners
    initEventListeners();
    
    /**
     * Initialize all event listeners
     */
    function initEventListeners() {
        // Browse button click
        browseBtn.addEventListener('click', function() {
            fileInput.click();
        });
        
        // File input change
        fileInput.addEventListener('change', handleFileSelect);
        
        // Drag and drop events
        uploadArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', function() {
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', function(e) {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            
            if (e.dataTransfer.files.length) {
                handleFile(e.dataTransfer.files[0]);
            }
        });
        
        // Cancel button click
        cancelBtn.addEventListener('click', resetUpload);
        
        // Configure mapping button click
        configureBtn.addEventListener('click', toggleMappingSection);
        
        // Import button click
        importBtn.addEventListener('click', importToDatabase);
        
        // Refresh preview button click
        refreshPreviewBtn.addEventListener('click', refreshPreview);
    }
    
    /**
     * Handle file selection from input
     */
    function handleFileSelect(e) {
        if (e.target.files.length) {
            handleFile(e.target.files[0]);
        }
    }
    
    /**
     * Process the selected file
     */
    function handleFile(file) {
        // Check if file is Excel
        if (!file.name.match(/\.(xlsx|xls)$/i)) {
            alert('Please select a valid Excel file (.xlsx or .xls)');
            return;
        }
        
        // Show upload status
        uploadStatus.classList.remove('d-none');
        uploadProgress.style.width = '0%';
        uploadStatusText.textContent = 'Reading file...';
        
        // Create FileReader
        const reader = new FileReader();
        
        reader.onprogress = function(e) {
            if (e.lengthComputable) {
                const percentLoaded = Math.round((e.loaded / e.total) * 100);
                uploadProgress.style.width = percentLoaded + '%';
                uploadProgress.setAttribute('aria-valuenow', percentLoaded);
            }
        };
        
        reader.onload = function(e) {
            try {
                // Parse workbook
                const data = new Uint8Array(e.target.result);
                workbook = XLSX.read(data, { type: 'array' });
                
                // Update status
                uploadProgress.style.width = '100%';
                uploadProgress.setAttribute('aria-valuenow', 100);
                uploadStatusText.textContent = 'File loaded successfully!';
                
                // Process workbook
                processWorkbook();
            } catch (error) {
                console.error('Error parsing Excel file:', error);
                uploadStatusText.textContent = 'Error parsing file: ' + error.message;
                uploadProgress.classList.remove('bg-success');
                uploadProgress.classList.add('bg-danger');
            }
        };
        
        reader.onerror = function() {
            uploadStatusText.textContent = 'Error reading file';
            uploadProgress.classList.remove('bg-success');
            uploadProgress.classList.add('bg-danger');
        };
        
        // Read file as array buffer
        reader.readAsArrayBuffer(file);
    }
    
    /**
     * Process the workbook and display sheet tabs
     */
    function processWorkbook() {
        // Clear previous sheet tabs
        sheetTabs.innerHTML = '';
        
        // Create tabs for each sheet
        workbook.SheetNames.forEach(function(sheetName) {
            const tab = document.createElement('div');
            tab.className = 'sheet-tab';
            tab.textContent = sheetName;
            tab.dataset.sheet = sheetName;
            tab.addEventListener('click', function() {
                selectSheet(sheetName);
            });
            
            sheetTabs.appendChild(tab);
        });
        
        // Select first sheet by default
        if (workbook.SheetNames.length > 0) {
            selectSheet(workbook.SheetNames[0]);
        }
        
        // Show preview section
        previewSection.classList.remove('d-none');
    }
    
    /**
     * Select a sheet and display its data
     */
    function selectSheet(sheetName) {
        // Update active tab
        document.querySelectorAll('.sheet-tab').forEach(function(tab) {
            tab.classList.remove('active');
            if (tab.dataset.sheet === sheetName) {
                tab.classList.add('active');
            }
        });
        
        // Set active sheet
        activeSheet = sheetName;
        
        // Convert sheet to JSON
        const worksheet = workbook.Sheets[sheetName];
        const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
        
        // Store sheet data
        sheetData[sheetName] = jsonData;
        
        // Display preview
        displayPreview(jsonData);
        
        // Validate data
        validateData(jsonData);
        
        // Initialize column mapping
        initializeColumnMapping(jsonData);
    }
    
    /**
     * Display preview of the sheet data
     */
    function displayPreview(data) {
        // Clear previous preview
        previewTableHead.innerHTML = '';
        previewTableBody.innerHTML = '';
        
        // Check if data exists
        if (!data || data.length === 0) {
            previewTableBody.innerHTML = '<tr><td colspan="5" class="text-center">No data found in this sheet</td></tr>';
            rowCount.textContent = '0 rows';
            return;
        }
        
        // Get headers (first row)
        const headers = data[0];
        
        // Create header row
        const headerRow = document.createElement('tr');
        headers.forEach(function(header) {
            const th = document.createElement('th');
            th.textContent = header || 'Unnamed Column';
            headerRow.appendChild(th);
        });
        previewTableHead.appendChild(headerRow);
        
        // Create data rows (limit to 100 for performance)
        const rowLimit = Math.min(data.length - 1, 100);
        for (let i = 1; i <= rowLimit; i++) {
            const row = data[i];
            const tr = document.createElement('tr');
            
            // Fill cells
            headers.forEach(function(header, index) {
                const td = document.createElement('td');
                td.textContent = row[index] !== undefined ? row[index] : '';
                tr.appendChild(td);
            });
            
            previewTableBody.appendChild(tr);
        }
        
        // Show row count
        rowCount.textContent = (data.length - 1) + ' rows';
    }
    
    /**
     * Validate the data against required fields
     */
    function validateData(data) {
        // Reset validation
        validationErrors = [];
        validationIssuesList.innerHTML = '';
        validationSummary.classList.add('d-none');
        
        // Check if data exists
        if (!data || data.length <= 1) {
            validationErrors.push('No data found in this sheet');
            showValidationErrors();
            return;
        }
        
        // Get headers (first row)
        const headers = data[0];
        
        // Auto-detect report type based on headers
        let reportType = null;
        let matchScore = {
            'posm': 0,
            'agent': 0,
            'execution': 0
        };
        
        // Calculate match score for each report type
        Object.keys(requiredFields).forEach(function(type) {
            requiredFields[type].forEach(function(field) {
                if (headers.some(h => h && h.toString().toLowerCase().includes(field.toLowerCase()))) {
                    matchScore[type]++;
                }
            });
        });
        
        // Determine report type with highest match score
        reportType = Object.keys(matchScore).reduce((a, b) => matchScore[a] > matchScore[b] ? a : b);
        
        // Check for missing required fields
        const missingFields = [];
        requiredFields[reportType].forEach(function(field) {
            if (!headers.some(h => h && h.toString().toLowerCase().includes(field.toLowerCase()))) {
                missingFields.push(field);
            }
        });
        
        if (missingFields.length > 0) {
            validationErrors.push(`Missing required fields for ${reportType} report: ${missingFields.join(', ')}`);
        }
        
        // Check for empty cells in required columns
        const requiredIndices = [];
        requiredFields[reportType].forEach(function(field) {
            headers.forEach(function(header, index) {
                if (header && header.toString().toLowerCase().includes(field.toLowerCase())) {
                    requiredIndices.push(index);
                }
            });
        });
        
        // Check each row for empty required cells
        let emptyCount = 0;
        for (let i = 1; i < data.length; i++) {
            const row = data[i];
            requiredIndices.forEach(function(index) {
                if (row[index] === undefined || row[index] === null || row[index] === '') {
                    emptyCount++;
                    // Limit the number of errors to avoid overwhelming the UI
                    if (emptyCount <= 5) {
                        validationErrors.push(`Row ${i + 1}: Missing value for ${headers[index]}`);
                    }
                }
            });
        }
        
        if (emptyCount > 5) {
            validationErrors.push(`And ${emptyCount - 5} more empty required cells`);
        }
        
        // Show validation errors if any
        showValidationErrors();
    }
    
    /**
     * Display validation errors
     */
    function showValidationErrors() {
        if (validationErrors.length > 0) {
            validationIssuesList.innerHTML = '';
            validationErrors.forEach(function(error) {
                const li = document.createElement('li');
                li.textContent = error;
                validationIssuesList.appendChild(li);
            });
            validationSummary.classList.remove('d-none');
        } else {
            validationSummary.classList.add('d-none');
        }
    }
    
    /**
     * Initialize column mapping based on headers
     */
    function initializeColumnMapping(data) {
        // Reset column mapping
        columnMap = {};
        columnMappings.innerHTML = '';
        
        // Check if data exists
        if (!data || data.length === 0) {
            return;
        }
        
        // Get headers (first row)
        const headers = data[0];
        
        // Create mapping UI
        headers.forEach(function(header, index) {
            const headerText = header || `Column ${index + 1}`;
            
            // Create mapping row
            const row = document.createElement('div');
            row.className = 'mapping-row d-flex align-items-center';
            
            // Source column
            const sourceCol = document.createElement('div');
            sourceCol.className = 'col-5';
            sourceCol.innerHTML = `<strong>${headerText}</strong>`;
            
            // Arrow
            const arrow = document.createElement('div');
            arrow.className = 'col-2 text-center';
            arrow.innerHTML = '<i class="fas fa-arrow-right"></i>';
            
            // Target field
            const targetCol = document.createElement('div');
            targetCol.className = 'col-5';
            
            // Create select for mapping
            const select = document.createElement('select');
            select.className = 'form-select form-select-sm';
            select.dataset.sourceIndex = index;
            
            // Add options
            const defaultOption = document.createElement('option');
            defaultOption.value = '';
            defaultOption.textContent = '-- Select Field --';
            select.appendChild(defaultOption);
            
            // Add field options based on detected report type
            const allFields = [
                // POSM fields
                'Agent Name', 'URN', 'Retail Point Name', 'Address', 'Phone', 'Retail Point Type',
                'Region', 'State', 'LGA', 'Visits', 'Assigned', 'Visited', 'Coverage',
                'Table', 'Chair', 'Parasol', 'Tarpaulin', 'Hawker Jacket', 'Cup',
                'Geolocation', 'Before Image', 'After Image',
                
                // Agent fields
                'ID', 'Name', 'Username', 'Role', 'Visitations',
                'Retail Points Assigned', 'Retail Points Visited', 'Coverage (%)',
                
                // Execution fields
                'Agent', 'Retail Point', 'Date', 'Status', 'Products Available',
                'Compliance Score', 'Notes'
            ];
            
            allFields.forEach(function(field) {
                const option = document.createElement('option');
                option.value = field;
                option.textContent = field;
                
                // Auto-select if header matches field
                if (headerText.toLowerCase().includes(field.toLowerCase())) {
                    option.selected = true;
                    columnMap[index] = field;
                }
                
                select.appendChild(option);
            });
            
            // Add change event
            select.addEventListener('change', function() {
                columnMap[index] = this.value;
            });
            
            targetCol.appendChild(select);
            
            // Add to row
            row.appendChild(sourceCol);
            row.appendChild(arrow);
            row.appendChild(targetCol);
            
            // Add to mapping section
            columnMappings.appendChild(row);
        });
    }
    
    /**
     * Toggle mapping section visibility
     */
    function toggleMappingSection() {
        if (mappingSection.classList.contains('d-none')) {
            mappingSection.classList.remove('d-none');
            configureBtn.innerHTML = '<i class="fas fa-times me-1"></i> Hide Mapping';
        } else {
            mappingSection.classList.add('d-none');
            configureBtn.innerHTML = '<i class="fas fa-cog me-1"></i> Configure Mapping';
        }
    }
    
    /**
     * Refresh the preview
     */
    function refreshPreview() {
        if (activeSheet) {
            selectSheet(activeSheet);
        }
    }
    
    /**
     * Reset the upload form
     */
    function resetUpload() {
        // Reset file input
        fileInput.value = '';
        
        // Hide sections
        uploadStatus.classList.add('d-none');
        previewSection.classList.add('d-none');
        mappingSection.classList.add('d-none');
        resultsSection.classList.add('d-none');
        
        // Reset progress
        uploadProgress.style.width = '0%';
        uploadProgress.setAttribute('aria-valuenow', 0);
        uploadProgress.classList.remove('bg-danger');
        uploadProgress.classList.add('bg-success');
        
        // Reset state
        workbook = null;
        activeSheet = null;
        sheetData = {};
        columnMap = {};
        validationErrors = [];
    }
    
    /**
     * Import data to database
     */
    function importToDatabase() {
        // Check if data is valid
        if (validationErrors.length > 0) {
            if (!confirm('There are validation issues with this data. Do you want to proceed anyway?')) {
                return;
            }
        }
        
        // Get active sheet data
        const data = sheetData[activeSheet];
        if (!data || data.length <= 1) {
            alert('No data to import');
            return;
        }
        
        // Prepare data for import
        const headers = data[0];
        const rows = data.slice(1);
        
        // Map data according to column mapping
        const mappedData = rows.map(function(row) {
            const mappedRow = {};
            
            Object.keys(columnMap).forEach(function(index) {
                const field = columnMap[index];
                if (field) {
                    mappedRow[field] = row[index];
                }
            });
            
            return mappedRow;
        });
        
        // Show loading state
        importBtn.disabled = true;
        importBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Importing...';
        
        // Send data to server
        fetch('/reports/upload', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                sheet_name: activeSheet,
                data: mappedData
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Import failed');
            }
            return response.json();
        })
        .then(result => {
            // Show results
            showImportResults(result);
        })
        .catch(error => {
            // Show error
            showImportError(error.message);
        })
        .finally(() => {
            // Reset button state
            importBtn.disabled = false;
            importBtn.innerHTML = '<i class="fas fa-database me-1"></i> Import to Database';
        });
    }
    
    /**
     * Show import results
     */
    function showImportResults(result) {
        // Show results section
        resultsSection.classList.remove('d-none');
        
        // Show success message
        successAlert.classList.remove('d-none');
        errorAlert.classList.add('d-none');
        successMessage.textContent = result.message || 'Data imported successfully!';
        
        // Show import summary
        let summaryHTML = '<div class="card mt-3">';
        summaryHTML += '<div class="card-header bg-white"><h6 class="mb-0">Import Summary</h6></div>';
        summaryHTML += '<div class="card-body">';
        summaryHTML += '<table class="table table-sm">';
        summaryHTML += '<tbody>';
        
        // Add summary rows
        if (result.total) {
            summaryHTML += `<tr><td>Total Records</td><td>${result.total}</td></tr>`;
        }
        if (result.imported) {
            summaryHTML += `<tr><td>Successfully Imported</td><td>${result.imported}</td></tr>`;
        }
        if (result.updated) {
            summaryHTML += `<tr><td>Updated Records</td><td>${result.updated}</td></tr>`;
        }
        if (result.skipped) {
            summaryHTML += `<tr><td>Skipped Records</td><td>${result.skipped}</td></tr>`;
        }
        if (result.errors) {
            summaryHTML += `<tr><td>Errors</td><td>${result.errors}</td></tr>`;
        }
        
        summaryHTML += '</tbody></table>';
        
        // Add details if available
        if (result.details && result.details.length > 0) {
            summaryHTML += '<h6 class="mt-3">Details</h6>';
            summaryHTML += '<ul class="mb-0">';
            result.details.forEach(function(detail) {
                summaryHTML += `<li>${detail}</li>`;
            });
            summaryHTML += '</ul>';
        }
        
        summaryHTML += '</div></div>';
        
        importSummary.innerHTML = summaryHTML;
    }
    
    /**
     * Show import error
     */
    function showImportError(error) {
        // Show results section
        resultsSection.classList.remove('d-none');
        
        // Show error message
        errorAlert.classList.remove('d-none');
        successAlert.classList.add('d-none');
        errorMessage.textContent = error || 'An error occurred during import';
        
        // Clear summary
        importSummary.innerHTML = '';
    }
});

// Update validation rules
const VALIDATION_RULES = {
    outlet: {
        required: ['URN', 'Retail Point Name', 'Address', 'Region', 'State', 'LGA'],
        optional: ['Phone', 'Retail Point Type', 'Table', 'Chair', 'Parasol', 'Tarpaulin', 'Hawker Jacket']
    },
    agent: {
        required: ['Name', 'Username', 'Role', 'Region'],
        optional: ['State', 'LGA', 'Phone', 'Email']
    },
    execution: {
        required: ['URN', 'Retail Point Name', 'Address', 'Region', 'State', 'LGA'],
        optional: ['Phone', 'Retail Point Type', 'Table', 'Chair', 'Parasol', 'Tarpaulin', 'Hawker Jacket']
    },
};

// Update the required fields for different report types
const REQUIRED_FIELDS = {
    outlet: ['URN', 'Retail Point Name', 'Address', 'Phone', 'Retail Point Type', 'Region', 'State', 'LGA'],
    posm: ['URN', 'Retail Point Name', 'Address', 'Phone', 'Retail Point Type', 'Region', 'State', 'LGA'],
    agent: ['Name', 'Username', 'Role', 'Region'],
    execution: ['Retail Point URN', 'Agent Username', 'Date', 'Status']
};

// Update the detectReportType function
function detectReportType(headers) {
    const headerSet = new Set(headers.map(h => h.trim()));
    
    // Check for outlet/POSM data (based on CSV structure)
    if (headerSet.has('URN') && headerSet.has('Retail Point Name') && headerSet.has('Address')) {
        return 'outlet';
    }
    
    // Check for agent data
    if (headerSet.has('Name') && headerSet.has('Username') && headerSet.has('Role')) {
        return 'agent';
    }
    
    // Check for execution data
    if (headerSet.has('Outlet URN') && headerSet.has('Agent Username') && headerSet.has('Date')) {
        return 'execution';
    }
    
    return 'unknown';
}