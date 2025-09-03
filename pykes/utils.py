# pykes/utils.py
import os
import uuid
import base64
import logging
import mimetypes
from pathlib import Path
from typing import Optional, Tuple, Union, List
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from PIL import Image, ImageOps
import hashlib
from datetime import datetime

# Configure logger for this module
logger = logging.getLogger(__name__)

# File validation settings
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_MIME_TYPES = {
    'image/png', 'image/jpeg', 'image/jpg', 
    'image/gif', 'image/webp'
}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB
MAX_IMAGE_DIMENSION = 3840  # 4K width/height limit

# Default upload folder
UPLOAD_FOLDER = 'static/uploads'

def validate_file_type(file: FileStorage) -> Tuple[bool, str]:
    """Validate file type by extension and MIME type"""
    if not file or not file.filename:
        return False, "No file provided"
    
    # Check file extension
    if '.' not in file.filename:
        return False, "File must have an extension"
    
    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File extension '{ext}' not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
    
    # Check MIME type
    mime_type = file.content_type or mimetypes.guess_type(file.filename)[0]
    if mime_type not in ALLOWED_MIME_TYPES:
        return False, f"MIME type '{mime_type}' not allowed"
    
    return True, "File type validation passed"

def validate_file_size(file: FileStorage, max_size: int = MAX_FILE_SIZE) -> Tuple[bool, str]:
    """Validate file size"""
    if not file:
        return False, "No file provided"
    
    # Seek to end to get size
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)  # Reset position
    
    if size > max_size:
        size_mb = size / (1024 * 1024)
        max_mb = max_size / (1024 * 1024)
        return False, f"File size ({size_mb:.1f}MB) exceeds maximum ({max_mb:.1f}MB)"
    
    if size == 0:
        return False, "File is empty"
    
    return True, "File size validation passed"

def validate_image_content(file: FileStorage) -> Tuple[bool, str]:
    """Validate image content and dimensions"""
    try:
        # Try to open and validate the image
        image = Image.open(file.stream)
        image.verify()  # Verify it's a valid image
        
        # Reset stream position for further use
        file.seek(0)
        
        # Re-open to get dimensions (verify() closes the image)
        image = Image.open(file.stream)
        width, height = image.size
        
        # Check dimensions
        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            return False, f"Image dimensions ({width}x{height}) exceed maximum ({MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION})"
        
        if width < 10 or height < 10:
            return False, "Image dimensions too small (minimum 10x10 pixels)"
        
        # Reset position again
        file.seek(0)
        
        logger.info(f"Image validation passed: {width}x{height} pixels, format: {image.format}")
        return True, "Image content validation passed"
        
    except Exception as e:
        logger.error(f"Image validation failed: {str(e)}")
        file.seek(0)  # Reset position
        return False, f"Invalid image file: {str(e)}"

def allowed_file(filename: str) -> bool:
    """Check if filename has allowed extension"""
    return ('.' in filename and 
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS)

def generate_secure_filename(original_filename: str, prefix: str = "") -> str:
    """Generate a secure, unique filename"""
    # Secure the original filename
    safe_filename = secure_filename(original_filename) or "unknown"
    
    # Extract extension
    if '.' in safe_filename:
        name, ext = safe_filename.rsplit('.', 1)
        ext = ext.lower()
    else:
        name = safe_filename
        ext = 'jpg'  # default extension
    
    # Generate unique filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    
    if prefix:
        return f"{prefix}_{timestamp}_{unique_id}.{ext}"
    else:
        return f"{timestamp}_{unique_id}_{name}.{ext}"

def save_uploaded_file(file: FileStorage, upload_folder: str = UPLOAD_FOLDER, 
                      prefix: str = "", create_thumbnail: bool = True) -> Optional[dict]:
    """Save uploaded file with validation and optional thumbnail creation"""
    
    try:
        # Validate file type
        valid_type, type_message = validate_file_type(file)
        if not valid_type:
            logger.warning(f"File type validation failed: {type_message}")
            return None
        
        # Validate file size
        valid_size, size_message = validate_file_size(file)
        if not valid_size:
            logger.warning(f"File size validation failed: {size_message}")
            return None
        
        # Validate image content
        valid_image, image_message = validate_image_content(file)
        if not valid_image:
            logger.warning(f"Image validation failed: {image_message}")
            return None
        
        # Ensure upload directory exists
        upload_path = Path(upload_folder)
        upload_path.mkdir(parents=True, exist_ok=True)
        
        # Generate secure filename
        filename = generate_secure_filename(file.filename, prefix)
        filepath = upload_path / filename
        
        # Save the original file
        file.save(str(filepath))
        
        # Process and optimize the image
        result = {
            'filename': filename,
            'original_filename': file.filename,
            'file_size': filepath.stat().st_size,
            'upload_time': datetime.now().isoformat()
        }
        
        # Create optimized version
        try:
            optimized_filename = optimize_image(filepath, upload_path)
            if optimized_filename:
                result['optimized_filename'] = optimized_filename
        except Exception as e:
            logger.error(f"Image optimization failed: {str(e)}")
        
        # Create thumbnail if requested
        if create_thumbnail:
            try:
                thumbnail_filename = create_thumbnail(filepath, upload_path)
                if thumbnail_filename:
                    result['thumbnail_filename'] = thumbnail_filename
            except Exception as e:
                logger.error(f"Thumbnail creation failed: {str(e)}")
        
        logger.info(f"File saved successfully: {filename}")
        return result
        
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        return None

def optimize_image(image_path: Path, output_dir: Path, 
                  max_size: Tuple[int, int] = (1920, 1080), 
                  quality: int = 85) -> Optional[str]:
    """Optimize image for web usage"""
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (for JPEG compatibility)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            # Resize if too large
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img = ImageOps.fit(img, max_size, Image.Resampling.LANCZOS)
            
            # Apply auto-orientation
            img = ImageOps.exif_transpose(img)
            
            # Generate optimized filename
            optimized_filename = f"opt_{image_path.name}"
            optimized_path = output_dir / optimized_filename
            
            # Save optimized image
            img.save(optimized_path, 'JPEG', quality=quality, optimize=True)
            
            return optimized_filename
            
    except Exception as e:
        logger.error(f"Image optimization failed: {str(e)}")
        return None

def create_thumbnail(image_path: Path, output_dir: Path, 
                    size: Tuple[int, int] = (200, 200)) -> Optional[str]:
    """Create thumbnail from image"""
    try:
        with Image.open(image_path) as img:
            # Apply auto-orientation
            img = ImageOps.exif_transpose(img)
            
            # Create thumbnail
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[-1])
                    img = background
            
            # Generate thumbnail filename
            thumbnail_filename = f"thumb_{image_path.stem}.jpg"
            thumbnail_path = output_dir / thumbnail_filename
            
            # Save thumbnail
            img.save(thumbnail_path, 'JPEG', quality=80, optimize=True)
            
            return thumbnail_filename
            
    except Exception as e:
        logger.error(f"Thumbnail creation failed: {str(e)}")
        return None

def save_base64_image(image_data: str, prefix: str = "", 
                     upload_folder: str = UPLOAD_FOLDER) -> Optional[str]:
    """Save base64 encoded image with validation"""
    try:
        if not image_data or not image_data.startswith('data:image'):
            logger.warning("Invalid base64 image data format")
            return None
        
        # Parse the data URL
        try:
            header, base64_str = image_data.split(';base64,')
            mime_type = header.split(':')[1]
        except (ValueError, IndexError):
            logger.warning("Invalid base64 image format")
            return None
        
        # Validate MIME type
        if mime_type not in ALLOWED_MIME_TYPES:
            logger.warning(f"MIME type '{mime_type}' not allowed")
            return None
        
        # Get file extension from MIME type
        ext_map = {
            'image/jpeg': 'jpg',
            'image/jpg': 'jpg',
            'image/png': 'png',
            'image/gif': 'gif',
            'image/webp': 'webp'
        }
        ext = ext_map.get(mime_type, 'jpg')
        
        # Decode base64 data
        try:
            binary_data = base64.b64decode(base64_str)
        except Exception as e:
            logger.error(f"Base64 decode failed: {str(e)}")
            return None
        
        # Validate size
        if len(binary_data) > MAX_FILE_SIZE:
            logger.warning("Base64 image too large")
            return None
        
        if len(binary_data) == 0:
            logger.warning("Empty base64 image data")
            return None
        
        # Create upload directory
        upload_path = Path(upload_folder)
        upload_path.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{prefix}_{timestamp}_{unique_id}.{ext}" if prefix else f"{timestamp}_{unique_id}.{ext}"
        filepath = upload_path / filename
        
        # Save file
        with open(filepath, 'wb') as f:
            f.write(binary_data)
        
        # Validate the saved image
        try:
            with Image.open(filepath) as img:
                img.verify()
                logger.info(f"Base64 image saved successfully: {filename}")
                return filename
        except Exception as e:
            # Clean up invalid file
            filepath.unlink(missing_ok=True)
            logger.error(f"Saved base64 image validation failed: {str(e)}")
            return None
            
    except Exception as e:
        logger.error(f"Error saving base64 image: {str(e)}")
        return None

def calculate_file_hash(file_path: Union[str, Path]) -> str:
    """Calculate SHA-256 hash of file for duplicate detection"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating file hash: {str(e)}")
        return ""

def cleanup_old_files(upload_folder: str = UPLOAD_FOLDER, days_old: int = 30) -> int:
    """Clean up files older than specified days"""
    try:
        upload_path = Path(upload_folder)
        if not upload_path.exists():
            return 0
        
        cutoff_time = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
        deleted_count = 0
        
        for file_path in upload_path.iterdir():
            if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old file: {file_path.name}")
                except Exception as e:
                    logger.error(f"Error deleting file {file_path.name}: {str(e)}")
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error during file cleanup: {str(e)}")
        return 0

# Define Dangote product list
DANGOTE_PRODUCTS = [
    "Table",
    "Chair",
    "Parasol",
    "Parasol Stand",
    "Tarpaulin",
    "Hawker Jacket",
    "Cups"
]

# Input validation utilities
def validate_string(value: str, min_length: int = 1, max_length: int = 255, 
                   field_name: str = "Field") -> Tuple[bool, str]:
    """Validate string input"""
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    
    value = value.strip()
    if len(value) < min_length:
        return False, f"{field_name} must be at least {min_length} characters"
    
    if len(value) > max_length:
        return False, f"{field_name} must be no more than {max_length} characters"
    
    return True, value

def validate_coordinates(lat: float, lng: float) -> Tuple[bool, str]:
    """Validate GPS coordinates"""
    try:
        lat = float(lat)
        lng = float(lng)
        
        if not (-90 <= lat <= 90):
            return False, "Latitude must be between -90 and 90"
        
        if not (-180 <= lng <= 180):
            return False, "Longitude must be between -180 and 180"
        
        return True, "Coordinates are valid"
        
    except (ValueError, TypeError):
        return False, "Invalid coordinate format"

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove potentially dangerous characters
    import re
    
    # Keep only alphanumeric, dots, hyphens, underscores
    sanitized = re.sub(r'[^\w\-_\.]', '_', filename)
    
    # Remove multiple consecutive dots or underscores
    sanitized = re.sub(r'[\._{2,}]', '_', sanitized)
    
    # Ensure it doesn't start with a dot
    sanitized = sanitized.lstrip('.')
    
    return sanitized or 'unnamed_file'
