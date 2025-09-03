# tests/test_uploads.py
# Integration tests for file upload functionality

import pytest
import io
import os
from PIL import Image
from werkzeug.datastructures import FileStorage

from pykes.utils import (
    save_uploaded_file, save_base64_image, 
    validate_file_type, validate_file_size, validate_image_content,
    allowed_file, generate_secure_filename
)
from tests.conftest import assert_valid_response

@pytest.mark.integration
@pytest.mark.upload
class TestFileUploadValidation:
    """Test file upload validation functions"""
    
    def test_allowed_file_valid_extensions(self):
        """Test allowed_file function with valid extensions"""
        valid_files = [
            'test.jpg', 'test.jpeg', 'test.png', 
            'test.gif', 'test.webp', 'TEST.JPG'
        ]
        
        for filename in valid_files:
            assert allowed_file(filename) is True
    
    def test_allowed_file_invalid_extensions(self):
        """Test allowed_file function with invalid extensions"""
        invalid_files = [
            'test.txt', 'test.pdf', 'test.exe', 
            'test.doc', 'test', 'test.'
        ]
        
        for filename in invalid_files:
            assert allowed_file(filename) is False
    
    def test_validate_file_type_success(self, mock_file_upload):
        """Test successful file type validation"""
        is_valid, message = validate_file_type(mock_file_upload)
        
        assert is_valid is True
        assert "validation passed" in message.lower()
    
    def test_validate_file_type_invalid_extension(self):
        """Test file type validation with invalid extension"""
        invalid_file = FileStorage(
            stream=io.BytesIO(b"test"),
            filename='test.txt',
            content_type='text/plain'
        )
        
        is_valid, message = validate_file_type(invalid_file)
        
        assert is_valid is False
        assert "not allowed" in message
    
    def test_validate_file_size_success(self, mock_file_upload):
        """Test successful file size validation"""
        is_valid, message = validate_file_size(mock_file_upload)
        
        assert is_valid is True
        assert "validation passed" in message.lower()
    
    def test_validate_file_size_too_large(self):
        """Test file size validation with oversized file"""
        # Create file larger than 1MB
        large_data = b"x" * (2 * 1024 * 1024)  # 2MB
        large_file = FileStorage(
            stream=io.BytesIO(large_data),
            filename='large.jpg',
            content_type='image/jpeg'
        )
        
        is_valid, message = validate_file_size(large_file, max_size=1024*1024)  # 1MB limit
        
        assert is_valid is False
        assert "exceeds maximum" in message
    
    def test_validate_image_content_success(self, sample_image_file):
        """Test successful image content validation"""
        file_storage = FileStorage(
            stream=sample_image_file,
            filename='test.jpg',
            content_type='image/jpeg'
        )
        
        is_valid, message = validate_image_content(file_storage)
        
        assert is_valid is True
        assert "validation passed" in message.lower()
    
    def test_validate_image_content_invalid_image(self):
        """Test image content validation with invalid image data"""
        invalid_file = FileStorage(
            stream=io.BytesIO(b"not an image"),
            filename='fake.jpg',
            content_type='image/jpeg'
        )
        
        is_valid, message = validate_image_content(invalid_file)
        
        assert is_valid is False
        assert "invalid image" in message.lower()

@pytest.mark.integration
@pytest.mark.upload
class TestFileUploadOperations:
    """Test file upload operations"""
    
    def test_generate_secure_filename(self):
        """Test secure filename generation"""
        original = "test file.jpg"
        filename = generate_secure_filename(original, "before")
        
        assert filename.startswith("before_")
        assert filename.endswith(".jpg")
        assert " " not in filename
        assert "_" in filename
    
    def test_save_uploaded_file_success(self, mock_file_upload, upload_folder):
        """Test successful file upload"""
        result = save_uploaded_file(
            mock_file_upload, 
            str(upload_folder), 
            prefix="test"
        )
        
        assert result is not None
        assert 'filename' in result
        assert 'file_size' in result
        assert 'upload_time' in result
        
        # Verify file was actually saved
        saved_file = upload_folder / result['filename']
        assert saved_file.exists()
    
    def test_save_uploaded_file_invalid_type(self, upload_folder):
        """Test file upload with invalid file type"""
        invalid_file = FileStorage(
            stream=io.BytesIO(b"test"),
            filename='test.txt',
            content_type='text/plain'
        )
        
        result = save_uploaded_file(
            invalid_file, 
            str(upload_folder), 
            prefix="test"
        )
        
        assert result is None
    
    def test_save_base64_image_success(self, upload_folder):
        """Test successful base64 image save"""
        # Create a simple base64 image
        img = Image.new('RGB', (50, 50), color='blue')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_data = img_bytes.getvalue()
        
        import base64
        base64_data = f"data:image/jpeg;base64,{base64.b64encode(img_data).decode()}"
        
        filename = save_base64_image(
            base64_data, 
            prefix="captured", 
            upload_folder=str(upload_folder)
        )
        
        assert filename is not None
        assert filename.startswith("captured_")
        assert filename.endswith(".jpg")
        
        # Verify file was saved
        saved_file = upload_folder / filename
        assert saved_file.exists()
    
    def test_save_base64_image_invalid_format(self, upload_folder):
        """Test base64 image save with invalid format"""
        invalid_data = "not a valid base64 image"
        
        filename = save_base64_image(
            invalid_data, 
            prefix="test", 
            upload_folder=str(upload_folder)
        )
        
        assert filename is None
    
    def test_save_base64_image_invalid_mime_type(self, upload_folder):
        """Test base64 image save with invalid MIME type"""
        invalid_data = "data:text/plain;base64,dGVzdA=="
        
        filename = save_base64_image(
            invalid_data, 
            prefix="test", 
            upload_folder=str(upload_folder)
        )
        
        assert filename is None

@pytest.mark.integration
@pytest.mark.upload
class TestImageProcessing:
    """Test image processing functionality"""
    
    def test_image_optimization(self, mock_file_upload, upload_folder):
        """Test image optimization during upload"""
        result = save_uploaded_file(
            mock_file_upload, 
            str(upload_folder), 
            prefix="test",
            create_thumbnail=True
        )
        
        assert result is not None
        
        # Check if optimized version was created
        if 'optimized_filename' in result:
            optimized_file = upload_folder / result['optimized_filename']
            assert optimized_file.exists()
    
    def test_thumbnail_creation(self, mock_file_upload, upload_folder):
        """Test thumbnail creation during upload"""
        result = save_uploaded_file(
            mock_file_upload, 
            str(upload_folder), 
            prefix="test",
            create_thumbnail=True
        )
        
        assert result is not None
        
        # Check if thumbnail was created
        if 'thumbnail_filename' in result:
            thumbnail_file = upload_folder / result['thumbnail_filename']
            assert thumbnail_file.exists()

@pytest.mark.integration
@pytest.mark.api
class TestUploadEndpoints:
    """Test file upload API endpoints"""
    
    @pytest.mark.auth
    def test_execution_upload_endpoint(self, client, auth_headers, mock_file_upload, create_test_outlet):
        """Test execution file upload endpoint"""
        outlet_id = create_test_outlet
        
        data = {
            'before_image': mock_file_upload,
            'latitude': '6.5244',
            'longitude': '3.3792',
            'notes': 'Test execution'
        }
        
        response = client.post(
            f'/execution/new/{outlet_id}',
            data=data,
            headers=auth_headers,
            content_type='multipart/form-data'
        )
        
        # Should redirect on success
        assert 300 <= response.status_code < 400
    
    @pytest.mark.auth
    def test_execution_upload_invalid_file(self, client, auth_headers, create_test_outlet):
        """Test execution upload with invalid file"""
        outlet_id = create_test_outlet
        
        invalid_file = FileStorage(
            stream=io.BytesIO(b"not an image"),
            filename='test.txt',
            content_type='text/plain'
        )
        
        data = {
            'before_image': invalid_file,
            'latitude': '6.5244',
            'longitude': '3.3792',
            'notes': 'Test execution'
        }
        
        response = client.post(
            f'/execution/new/{outlet_id}',
            data=data,
            headers=auth_headers,
            content_type='multipart/form-data'
        )
        
        # Should handle invalid file gracefully
        assert response.status_code in [200, 400, 302]

@pytest.mark.integration
@pytest.mark.slow
class TestLargeFileHandling:
    """Test handling of large files and edge cases"""
    
    def test_maximum_file_size_enforcement(self, upload_folder):
        """Test that maximum file size is enforced"""
        # Create a file larger than the maximum allowed size
        large_data = b"x" * (20 * 1024 * 1024)  # 20MB
        large_file = FileStorage(
            stream=io.BytesIO(large_data),
            filename='huge.jpg',
            content_type='image/jpeg'
        )
        
        result = save_uploaded_file(
            large_file, 
            str(upload_folder), 
            prefix="large"
        )
        
        # Should reject large files
        assert result is None
    
    def test_concurrent_uploads(self, upload_folder, sample_image_file):
        """Test handling of concurrent file uploads"""
        import threading
        import time
        
        results = []
        errors = []
        
        def upload_file(thread_id):
            try:
                file_storage = FileStorage(
                    stream=sample_image_file,
                    filename=f'concurrent_{thread_id}.jpg',
                    content_type='image/jpeg'
                )
                
                result = save_uploaded_file(
                    file_storage, 
                    str(upload_folder), 
                    prefix=f"thread_{thread_id}"
                )
                results.append(result)
            except Exception as e:
                errors.append(str(e))
        
        # Create multiple threads to upload files simultaneously
        threads = []
        for i in range(5):
            thread = threading.Thread(target=upload_file, args=(i,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(errors) == 0, f"Upload errors occurred: {errors}"
        assert len(results) == 5
        assert all(result is not None for result in results)
