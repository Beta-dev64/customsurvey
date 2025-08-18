// Camera functionality for Dangote Cement Execution Tracker
let beforeStream = null;
let afterStream = null;
let beforeImageCaptured = false;
let afterImageCaptured = false;

// Initialize camera functionality
document.addEventListener('DOMContentLoaded', function() {
    // Before image capture
    document.getElementById('beforeCaptureBtn').addEventListener('click', function() {
        if (document.getElementById('beforeVideo').style.display === 'none') {
            startCamera('before');
        } else {
            captureImage('before');
        }
    });
    
    document.getElementById('beforeUploadBtn').addEventListener('click', function() {
        document.getElementById('beforeFileInput').click();
    });
    
    document.getElementById('beforeFileInput').addEventListener('change', function(e) {
        handleFileUpload(e, 'before');
    });
    
    document.getElementById('beforeResetBtn').addEventListener('click', function() {
        resetCamera('before');
    });
    
    // After image capture
    document.getElementById('afterCaptureBtn').addEventListener('click', function() {
        if (document.getElementById('afterVideo').style.display === 'none') {
            startCamera('after');
        } else {
            captureImage('after');
        }
    });
    
    document.getElementById('afterUploadBtn').addEventListener('click', function() {
        document.getElementById('afterFileInput').click();
    });
    
    document.getElementById('afterFileInput').addEventListener('change', function(e) {
        handleFileUpload(e, 'after');
    });
    
    document.getElementById('afterResetBtn').addEventListener('click', function() {
        resetCamera('after');
    });
    
    // Form submission validation
    document.getElementById('executionForm').addEventListener('submit', function(e) {
        // Prevent form submission
        e.preventDefault();
        
        // Validate before image
        if (!beforeImageCaptured) {
            showToast('Please capture a before image', 'danger');
            return false;
        }
        
        // Validate after image
        if (!afterImageCaptured) {
            showToast('Please capture an after image', 'danger');
            return false;
        }
        
        // Validate location
        const lat = document.getElementById('latitude').value;
        const lng = document.getElementById('longitude').value;
        
        if (!lat || !lng) {
            showToast('Location data is required. Please allow location access.', 'danger');
            return false;
        }
        
        // Show confirmation modal
        showImageConfirmation();
    });
    
    // Confirm image submission
    document.getElementById('confirmSubmitBtn').addEventListener('click', function() {
        // Disable buttons to prevent double submission
        document.getElementById('submitBtn').disabled = true;
        if (document.getElementById('mobileSubmitBtn')) {
            document.getElementById('mobileSubmitBtn').disabled = true;
        }
        
        document.getElementById('confirmSubmitBtn').disabled = true;
        document.getElementById('confirmSubmitBtn').innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Submitting...';
        
        // Submit the form
        document.getElementById('executionForm').submit();
    });
});

// Camera functions
function startCamera(type) {
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        // Optimize for mobile devices
        const isMobile = window.innerWidth < 768;
        const constraints = {
            video: {
                facingMode: 'environment',
                width: { ideal: isMobile ? 1280 : 1920 },
                height: { ideal: isMobile ? 720 : 1080 }
            }
        };
        
        navigator.mediaDevices.getUserMedia(constraints)
            .then(function(stream) {
                const video = document.getElementById(`${type}Video`);
                const placeholder = document.getElementById(`${type}Placeholder`);
                
                if (type === 'before') {
                    beforeStream = stream;
                } else {
                    afterStream = stream;
                }
                
                video.srcObject = stream;
                video.style.display = 'block';
                placeholder.style.display = 'none';
                
                // Update button text
                const isMobile = window.innerWidth < 768;
                document.getElementById(`${type}CaptureBtn`).innerHTML = isMobile ? 
                    '<i class="fas fa-camera"></i>' : 
                    '<i class="fas fa-camera me-1"></i> Take Photo';
                document.getElementById(`${type}ResetBtn`).style.display = 'block';
                
                // Add pulsing effect to indicate camera is active
                document.getElementById(`${type}CaptureBtn`).classList.add('btn-pulse');
                
                // Set flag to false until photo is captured
                if (type === 'before') {
                    beforeImageCaptured = false;
                    updateStatusBadge('before', 'waiting');
                } else {
                    afterImageCaptured = false;
                    updateStatusBadge('after', 'waiting');
                }
            })
            .catch(function(error) {
                console.error('Camera error:', error);
                
                // Show error message
                if (error.name === 'NotAllowedError') {
                    showToast('Camera access denied. Please grant camera permissions.', 'danger');
                } else {
                    showToast('Unable to access camera. Please try the upload button instead.', 'danger');
                }
            });
    } else {
        showToast('Your browser does not support camera access. Please use the upload button.', 'warning');
    }
}

function captureImage(type) {
    const video = document.getElementById(`${type}Video`);
    const preview = document.getElementById(`${type}Preview`);
    const capturedImage = document.getElementById(`${type}CapturedImage`);
    
    // Create a canvas element to capture from video
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    
    // Check if video is ready
    if (video.readyState !== 4) {
        showToast('Camera is not ready yet. Please wait a moment.', 'warning');
        return;
    }
    
    // Draw the video frame to canvas
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    // Convert to data URL with reduced quality for mobile
    const isMobile = window.innerWidth < 768;
    const dataURL = canvas.toDataURL('image/jpeg', isMobile ? 0.7 : 0.9);
    
    // Check if image is just black or too dark (possible camera not initialized)
    if (isImageBlankOrDark(canvas)) {
        showToast('Image appears to be blank or too dark. Please try again.', 'warning');
        return;
    }
    
    // Display the captured image
    preview.src = dataURL;
    preview.style.display = 'block';
    video.style.display = 'none';
    
    // Store the data URL
    capturedImage.value = dataURL;
    
    // Update buttons
    document.getElementById(`${type}CaptureBtn`).innerHTML = isMobile ? 
        '<i class="fas fa-camera"></i>' : 
        '<i class="fas fa-camera me-1"></i> Retake';
    
    // Remove pulsing effect
    document.getElementById(`${type}CaptureBtn`).classList.remove('btn-pulse');
    
    // Stop the camera stream
    if (type === 'before' && beforeStream) {
        beforeStream.getTracks().forEach(track => track.stop());
        beforeStream = null;
    } else if (type === 'after' && afterStream) {
        afterStream.getTracks().forEach(track => track.stop());
        afterStream = null;
    }
    
    // Set captured flag
    if (type === 'before') {
        beforeImageCaptured = true;
        updateStatusBadge('before', 'captured');
    } else {
        afterImageCaptured = true;
        updateStatusBadge('after', 'captured');
    }
    
    // Show success toast
    showToast(`${type.charAt(0).toUpperCase() + type.slice(1)} image captured successfully!`, 'success');
    
    // Update submit button status
    updateSubmitButtonStatus();
    
    // Play camera shutter sound
    playCameraSound();
}

function resetCamera(type) {
    const video = document.getElementById(`${type}Video`);
    const preview = document.getElementById(`${type}Preview`);
    const placeholder = document.getElementById(`${type}Placeholder`);
    const fileInput = document.getElementById(`${type}FileInput`);
    const capturedImage = document.getElementById(`${type}CapturedImage`);
    
    // Stop any active stream
    if (type === 'before' && beforeStream) {
        beforeStream.getTracks().forEach(track => track.stop());
        beforeStream = null;
    } else if (type === 'after' && afterStream) {
        afterStream.getTracks().forEach(track => track.stop());
        afterStream = null;
    }
    
    // Reset UI
    video.style.display = 'none';
    video.srcObject = null;
    preview.style.display = 'none';
    placeholder.style.display = 'block';
    fileInput.value = '';
    capturedImage.value = '';
    
    // Reset buttons
    const isMobile = window.innerWidth < 768;
    document.getElementById(`${type}CaptureBtn`).innerHTML = isMobile ? 
        '<i class="fas fa-camera"></i>' : 
        '<i class="fas fa-camera me-1"></i> Capture';
    document.getElementById(`${type}CaptureBtn`).classList.remove('btn-pulse');
    document.getElementById(`${type}ResetBtn`).style.display = 'none';
    
    // Reset captured flag
    if (type === 'before') {
        beforeImageCaptured = false;
        updateStatusBadge('before', 'none');
    } else {
        afterImageCaptured = false;
        updateStatusBadge('after', 'none');
    }
    
    // Update submit button status
    updateSubmitButtonStatus();
}

function handleFileUpload(event, type) {
    const file = event.target.files[0];
    if (file) {
        // Validate file type
        if (!file.type.match('image.*')) {
            showToast('Please select an image file (JPEG, PNG)', 'danger');
            return;
        }
        
        // Validate file size (max 10MB)
        if (file.size > 10 * 1024 * 1024) {
            showToast('Image file is too large (max 10MB)', 'danger');
            return;
        }
        
        const preview = document.getElementById(`${type}Preview`);
        const placeholder = document.getElementById(`${type}Placeholder`);
        const reader = new FileReader();
        
        reader.onload = function(e) {
            preview.src = e.target.result;
            preview.style.display = 'block';
            placeholder.style.display = 'none';
            
            // Stop any active stream
            if (type === 'before' && beforeStream) {
                beforeStream.getTracks().forEach(track => track.stop());
                beforeStream = null;
                document.getElementById('beforeVideo').style.display = 'none';
            } else if (type === 'after' && afterStream) {
                afterStream.getTracks().forEach(track => track.stop());
                afterStream = null;
                document.getElementById('afterVideo').style.display = 'none';
            }
            
            // Set captured flag
            if (type === 'before') {
                beforeImageCaptured = true;
                updateStatusBadge('before', 'captured');
            } else {
                afterImageCaptured = true;
                updateStatusBadge('after', 'captured');
            }
            
            // Update submit button status
            updateSubmitButtonStatus();
            
            // Show success toast
            showToast(`${type.charAt(0).toUpperCase() + type.slice(1)} image uploaded successfully!`, 'success');
            
            // Show reset button
            document.getElementById(`${type}ResetBtn`).style.display = 'block';
        };
        
        // Read the image file
        reader.readAsDataURL(file);
    }
}

// Helper functions
function isImageBlankOrDark(canvas) {
    const ctx = canvas.getContext('2d');
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const data = imageData.data;
    
    let totalBrightness = 0;
    const pixelCount = data.length / 4;
    
    // Sample pixels to determine brightness (every 10th pixel)
    for (let i = 0; i < data.length; i += 40) {
        const r = data[i];
        const g = data[i+1];
        const b = data[i+2];
        totalBrightness += (r + g + b) / 3;
    }
    
    const avgBrightness = totalBrightness / (pixelCount / 10);
    return avgBrightness < 20; // threshold for "too dark"
}

function updateStatusBadge(type, status) {
    const statusBadge = document.getElementById(`${type}Status`);
    if (!statusBadge) return;
    
    statusBadge.className = 'badge';
    
    switch(status) {
        case 'none':
            statusBadge.classList.add('bg-secondary');
            statusBadge.textContent = 'Not Captured';
            break;
        case 'waiting':
            statusBadge.classList.add('bg-warning');
            statusBadge.textContent = 'Camera Ready';
            break;
        case 'captured':
            statusBadge.classList.add('bg-success');
            statusBadge.textContent = 'Captured';
            break;
    }
}

function updateSubmitButtonStatus() {
    const submitBtn = document.getElementById('submitBtn');
    const mobileSubmitBtn = document.getElementById('mobileSubmitBtn');
    
    if (beforeImageCaptured && afterImageCaptured) {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.classList.add('btn-success');
            submitBtn.classList.remove('btn-secondary');
        }
        if (mobileSubmitBtn) {
            mobileSubmitBtn.disabled = false;
            mobileSubmitBtn.classList.add('btn-success');
            mobileSubmitBtn.classList.remove('btn-secondary');
        }
    } else {
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.classList.remove('btn-success');
            submitBtn.classList.add('btn-secondary');
        }
        if (mobileSubmitBtn) {
            mobileSubmitBtn.disabled = true;
            mobileSubmitBtn.classList.remove('btn-success');
            mobileSubmitBtn.classList.add('btn-secondary');
        }
    }
}

function showImageConfirmation() {
    const beforePreview = document.getElementById('beforePreview').src;
    const afterPreview = document.getElementById('afterPreview').src;
    
    // Set the images in the confirmation modal
    document.getElementById('confirmBeforeImage').src = beforePreview;
    document.getElementById('confirmAfterImage').src = afterPreview;
    
    // Show the modal
    const confirmModal = new bootstrap.Modal(document.getElementById('confirmModal'));
    confirmModal.show();
}

function showToast(message, type) {
    const toastContainer = document.getElementById('toastContainer');
    
    // Create toast if container exists
    if (toastContainer) {
        const toastId = 'toast-' + Date.now();
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        toast.setAttribute('id', toastId);
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        
        const bsToast = new bootstrap.Toast(toast, {
            autohide: true,
            delay: 3000
        });
        
        bsToast.show();
        
        // Remove toast from DOM after it's hidden
        toast.addEventListener('hidden.bs.toast', function() {
            toast.remove();
        });
    } else {
        // Fallback if toast container doesn't exist
        alert(message);
    }
}

function playCameraSound() {
    const sound = document.getElementById('cameraSound');
    if (sound) {
        sound.currentTime = 0;
        sound.play().catch(e => {
            // Silent error - browser may block autoplay
            console.log('Could not play camera sound:', e);
        });
    }
}