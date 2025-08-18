/**
 * Centralized Nigeria geographical data
 * Contains regions, states, and their relationships
 */

// Nigeria regions
const NIGERIA_REGIONS = [
    { id: 'SW', name: 'South West' },
    { id: 'SE', name: 'South East' },
    { id: 'SS', name: 'South South' },
    { id: 'NC', name: 'North Central' },
    { id: 'NE', name: 'North East' },
    { id: 'NW', name: 'North West' }
];

// Nigeria states with their regions
const NIGERIA_STATES = [
    // South West (SW)
    {name: 'Ekiti', region: 'SW'},
    {name: 'Lagos', region: 'SW'},
    {name: 'Ogun', region: 'SW'},
    {name: 'Ondo', region: 'SW'},
    {name: 'Osun', region: 'SW'},
    {name: 'Oyo', region: 'SW'},
    
    // South East (SE)
    {name: 'Abia', region: 'SE'},
    {name: 'Anambra', region: 'SE'},
    {name: 'Ebonyi', region: 'SE'},
    {name: 'Enugu', region: 'SE'},
    {name: 'Imo', region: 'SE'},
    
    // South South (SS)
    {name: 'Akwa Ibom', region: 'SS'},
    {name: 'Bayelsa', region: 'SS'},
    {name: 'Cross River', region: 'SS'},
    {name: 'Delta', region: 'SS'},
    {name: 'Edo', region: 'SS'},
    {name: 'Rivers', region: 'SS'},
    
    // North Central (NC)
    {name: 'Benue', region: 'NC'},
    {name: 'FCT', region: 'NC'},
    {name: 'Kogi', region: 'NC'},
    {name: 'Kwara', region: 'NC'},
    {name: 'Nasarawa', region: 'NC'},
    {name: 'Niger', region: 'NC'},
    {name: 'Plateau', region: 'NC'},
    
    // North East (NE)
    {name: 'Adamawa', region: 'NE'},
    {name: 'Bauchi', region: 'NE'},
    {name: 'Borno', region: 'NE'},
    {name: 'Gombe', region: 'NE'},
    {name: 'Taraba', region: 'NE'},
    {name: 'Yobe', region: 'NE'},
    
    // North West (NW)
    {name: 'Jigawa', region: 'NW'},
    {name: 'Kaduna', region: 'NW'},
    {name: 'Kano', region: 'NW'},
    {name: 'Katsina', region: 'NW'},
    {name: 'Kebbi', region: 'NW'},
    {name: 'Sokoto', region: 'NW'},
    {name: 'Zamfara', region: 'NW'}
];

// Helper function to get states by region
function getStatesByRegion(regionId) {
    if (regionId === 'all') return NIGERIA_STATES;
    return NIGERIA_STATES.filter(state => state.region === regionId);
}

// Helper function to populate region dropdown
function populateRegionDropdown(selectElement, includeAllOption = true) {
    if (!selectElement) return;
    
    // Clear existing options
    selectElement.innerHTML = '';
    
    // Add "All Regions" option if needed
    if (includeAllOption) {
        const allOption = document.createElement('option');
        allOption.value = 'all';
        allOption.textContent = 'All Regions';
        selectElement.appendChild(allOption);
    }
    
    // Add region options
    NIGERIA_REGIONS.forEach(region => {
        const option = document.createElement('option');
        option.value = region.id;
        option.textContent = region.name;
        selectElement.appendChild(option);
    });
}

// Helper function to populate state dropdown
function populateStateDropdown(selectElement, regionId = 'all', includeAllOption = true) {
    if (!selectElement) return;
    
    // Clear existing options
    selectElement.innerHTML = '';
    
    // Add "All States" option if needed
    if (includeAllOption) {
        const allOption = document.createElement('option');
        allOption.value = 'all';
        allOption.textContent = 'All States';
        selectElement.appendChild(allOption);
    }
    
    // Get states for the selected region
    const states = getStatesByRegion(regionId);
    
    // Add state options
    states.forEach(state => {
        const option = document.createElement('option');
        option.value = state.name;
        option.textContent = state.name;
        option.dataset.region = state.region;
        selectElement.appendChild(option);
    });
}

// Setup region-state relationship
function setupRegionStateRelationship(regionSelect, stateSelect) {
    if (!regionSelect || !stateSelect) return;
    
    // Update states when region changes
    regionSelect.addEventListener('change', function() {
        populateStateDropdown(stateSelect, this.value);
    });
}