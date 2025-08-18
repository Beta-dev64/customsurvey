import os
import uuid
import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Set
from werkzeug.utils import secure_filename

# Constants
ALLOWED_EXTENSIONS: Set[str] = {'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_FOLDER: str = 'static/uploads'
MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB limit

# Dangote product list
DANGOTE_PRODUCTS: list[str] = [
    "Table",
    "Chair",
    "Parasol",
    "Parasol Stand",
    "Tarpaulin",
    "Hawker Jacket",
    "Cups"
]

# Utility functions
def allowed_file(filename: str) -> bool:
    """
    Check if the uploaded file has an allowed extension.
    
    Args:
        filename (str): The name of the file to check
        
    Returns:
        bool: True if file extension is allowed, False otherwise
    """
    if not filename or '.' not in filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS

def ensure_upload_directory() -> None:
    """
    Ensure the upload directory exists, create it if it doesn't.
    """
    upload_path = Path(UPLOAD_FOLDER)
    upload_path.mkdir(parents=True, exist_ok=True)

def generate_unique_filename(prefix: str, extension: str) -> str:
    """
    Generate a unique filename with datetime and UUID.
    
    Args:
        prefix (str): Prefix for the filename
        extension (str): File extension
        
    Returns:
        str: Unique filename with datetime and UUID
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_id = str(uuid.uuid4())[:8]  # Use shorter UUID for cleaner filenames
    return f"{prefix}_{timestamp}_{unique_id}.{extension}"

def validate_base64_image(image_data: str) -> tuple[bool, Optional[str]]:
    """
    Validate base64 image data and extract format information.
    
    Args:
        image_data (str): Base64 encoded image data
        
    Returns:
        tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if not image_data:
        return False, "No image data provided"
    
    if not image_data.startswith('data:image'):
        return False, "Invalid image data format"
    
    try:
        # Check if the data URL is properly formatted
        if ';base64,' not in image_data:
            return False, "Invalid base64 data URL format"
        
        format_part, base64_str = image_data.split(';base64,', 1)
        
        # Validate the format part
        if not format_part.startswith('data:image/'):
            return False, "Invalid image MIME type"
        
        # Extract and validate extension
        ext = format_part.split('/')[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"Unsupported image format: {ext}"
        
        # Validate base64 string
        if not base64_str:
            return False, "Empty base64 data"
        
        # Test base64 decoding
        try:
            decoded_data = base64.b64decode(base64_str, validate=True)
            if len(decoded_data) > MAX_FILE_SIZE:
                return False, f"Image size exceeds maximum limit of {MAX_FILE_SIZE // (1024*1024)}MB"
        except Exception:
            return False, "Invalid base64 encoding"
        
        return True, None
        
    except ValueError as e:
        return False, f"Invalid data URL format: {str(e)}"
    except Exception as e:
        return False, f"Validation error: {str(e)}"

def save_base64_image(image_data: str, prefix: str) -> Optional[str]:
    """
    Save base64 encoded image data to file with datetime in filename.
    
    Args:
        image_data (str): Base64 encoded image data in Data URL format
        prefix (str): Prefix for the filename
        
    Returns:
        Optional[str]: Filename if successful, None if failed
    """
    try:
        # Validate input parameters
        if not prefix or not isinstance(prefix, str):
            logging.error("Invalid prefix provided")
            return None
        
        # Sanitize prefix
        prefix = secure_filename(prefix.strip())
        if not prefix:
            logging.error("Empty prefix after sanitization")
            return None
        
        # Validate image data
        is_valid, error_message = validate_base64_image(image_data)
        if not is_valid:
            logging.error(f"Image validation failed: {error_message}")
            return None
        
        # Extract format and base64 data
        format_part, base64_str = image_data.split(';base64,', 1)
        ext = format_part.split('/')[-1].lower()
        
        # Ensure upload directory exists
        ensure_upload_directory()
        
        # Generate unique filename with datetime
        filename = generate_unique_filename(prefix, ext)
        filepath = Path(UPLOAD_FOLDER) / filename
        
        # Decode and save the image
        binary_data = base64.b64decode(base64_str)
        
        # Write file atomically
        temp_filepath = filepath.with_suffix(f"{filepath.suffix}.tmp")
        try:
            with open(temp_filepath, 'wb') as f:
                f.write(binary_data)
            
            # Atomic move to final location
            temp_filepath.rename(filepath)
            
            logging.info(f"Successfully saved image: {filename}")
            return filename
            
        except Exception as e:
            # Clean up temporary file if it exists
            if temp_filepath.exists():
                temp_filepath.unlink()
            raise e
        
    except Exception as e:
        logging.error(f"Error saving base64 image: {e}")
        return None

def get_file_info(filename: str) -> dict:
    """
    Get information about an uploaded file.
    
    Args:
        filename (str): Name of the file
        
    Returns:
        dict: File information including size, extension, and path
    """
    filepath = Path(UPLOAD_FOLDER) / filename
    
    if not filepath.exists():
        return {'exists': False}
    
    try:
        stat = filepath.stat()
        return {
            'exists': True,
            'size': stat.st_size,
            'extension': filepath.suffix.lower(),
            'created': datetime.fromtimestamp(stat.st_ctime),
            'modified': datetime.fromtimestamp(stat.st_mtime),
            'path': str(filepath)
        }
    except Exception as e:
        logging.error(f"Error getting file info for {filename}: {e}")
        return {'exists': False, 'error': str(e)}

def cleanup_old_files(days_old: int = 30) -> int:
    """
    Clean up old uploaded files.
    
    Args:
        days_old (int): Files older than this many days will be deleted
        
    Returns:
        int: Number of files deleted
    """
    try:
        upload_path = Path(UPLOAD_FOLDER)
        if not upload_path.exists():
            return 0
        
        cutoff_time = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
        deleted_count = 0
        
        for file_path in upload_path.iterdir():
            if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    deleted_count += 1
                    logging.info(f"Deleted old file: {file_path.name}")
                except Exception as e:
                    logging.error(f"Error deleting file {file_path.name}: {e}")
        
        return deleted_count
        
    except Exception as e:
        logging.error(f"Error during cleanup: {e}")
        return 0