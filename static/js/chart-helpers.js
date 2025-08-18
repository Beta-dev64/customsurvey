// Chart helper functions for Dangote Cement Execution Tracker

// Safely destroy a chart if it exists
function safelyDestroyChart(chartInstance) {
    if (chartInstance && typeof chartInstance.destroy === 'function') {
        chartInstance.destroy();
        return true;
    }
    return false;
}

// Safely get chart context with error handling
function getChartContext(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) {
        console.error(`Canvas element with ID '${canvasId}' not found`);
        return null;
    }
    
    try {
        return canvas.getContext('2d');
    } catch (error) {
        console.error(`Error getting context for canvas '${canvasId}':`, error);
        return null;
    }
}

// Create a new chart with error handling
function createChart(canvasId, chartType, data, options) {
    const ctx = getChartContext(canvasId);
    if (!ctx) return null;
    
    try {
        return new Chart(ctx, {
            type: chartType,
            data: data,
            options: options || {}
        });
    } catch (error) {
        console.error(`Error creating ${chartType} chart on '${canvasId}':`, error);
        return null;
    }
}