# pykes/utils.py
import os
import uuid
import base64
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


UPLOAD_FOLDER = 'static/uploads'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_base64_image(image_data, prefix):
    # Check if the image data is a Data URL
    if image_data and image_data.startswith('data:image'):
        # Extract the base64 data
        format, base64_str = image_data.split(';base64,')

        # Get the file extension
        ext = format.split('/')[-1]

        # Generate a unique filename
        filename = f"{prefix}_{uuid.uuid4()}.{ext}"

        # Convert base64 to binary
        try:
            binary_data = base64.b64decode(base64_str)

            # Save the file
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            with open(filepath, 'wb') as f:
                f.write(binary_data)

            return filename
        except Exception as e:
            print(f"Error saving base64 image: {e}")
            return None

    return None

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