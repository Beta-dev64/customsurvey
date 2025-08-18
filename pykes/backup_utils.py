import os
import shutil
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'instance', 'app.db')
BACKUP_DIR = os.path.join(os.path.dirname(__file__), '..', 'db_backup')

def create_backup():
    # Create backup directory if it doesn't exist
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # Create timestamped backup filename
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    backup_path = os.path.join(BACKUP_DIR, f'app_db_{timestamp}.db')
    
    # Copy the database file
    shutil.copy2(DB_PATH, backup_path)
    return backup_path

def send_notification(backup_path, recipient_email):
    # Email configuration (update with your SMTP details)
    smtp_server = 'smtp.example.com'
    smtp_port = 587
    smtp_username = 'your_email@example.com'
    smtp_password = 'your_password'
    
    # Create email message
    msg = MIMEMultipart()
    msg['From'] = smtp_username
    msg['To'] = recipient_email
    msg['Subject'] = 'Database Backup Notification'
    
    body = f"""
    Database backup completed successfully.
    
    Backup file: {backup_path}
    Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    msg.attach(MIMEText(body, 'plain'))
    
    # Send email
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)

def perform_scheduled_backup():
    recipient_email = 'admin@example.com'  # Change to your admin email
    try:
        backup_path = create_backup()
        send_notification(backup_path, recipient_email)
        print(f"Backup completed: {backup_path}")
    except Exception as e:
        print(f"Backup failed: {str(e)}")