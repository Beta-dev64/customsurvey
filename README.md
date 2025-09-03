# SurveyTray - POSM Retail Activation System

A comprehensive Flask-based web application for managing Point of Sale Material (POSM) retail activation campaigns, field agent execution tracking, and comprehensive reporting.

## 🚀 Features

### Core Functionality
- **User Management**: Role-based access control (Admin, Field Agents, Supervisors)
- **Outlet Management**: Complete retail outlet database with geographic organization
- **Execution Tracking**: Field visit monitoring with image capture and GPS coordinates
- **File Uploads**: Robust image processing with validation, optimization, and thumbnails
- **Comprehensive Reporting**: Export capabilities (CSV, Excel, PDF) with filtering
- **Dashboard Analytics**: Real-time statistics and performance metrics

### Technical Features
- **Enhanced Security**: Rate limiting, input validation, CSRF protection
- **Comprehensive Logging**: Structured logging with rotation and categorization
- **Error Handling**: Graceful error recovery with detailed logging
- **Database Optimization**: Indexed queries, connection pooling, transaction management
- **Image Processing**: Automatic optimization, thumbnail generation, format validation
- **Testing Framework**: Comprehensive unit and integration tests
- **Containerization**: Docker support for easy deployment

## 🏗️ Architecture

```
surveytray/
├── app.py                 # Main application with factory pattern
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container configuration
├── gunicorn.conf.py      # Production server configuration
├── .env.example          # Environment variables template
├── pytest.ini           # Test configuration
├── pykes/               # Core application package
│   ├── __init__.py
│   ├── config.py        # Environment-based configuration
│   ├── models.py        # Database models and operations
│   ├── routes.py        # Main route handlers (legacy)
│   ├── utils.py         # Utility functions and validation
│   └── logging_config.py # Comprehensive logging setup
├── tests/               # Test suite
│   ├── conftest.py      # Test fixtures and configuration
│   ├── test_models.py   # Model unit tests
│   └── test_uploads.py  # Upload integration tests
├── templates/           # Jinja2 HTML templates
├── static/             # CSS, JS, images
├── logs/               # Application logs (created at runtime)
└── uploads/            # File upload storage (created at runtime)
```

## 📋 Requirements

### System Requirements
- Python 3.11+
- SQLite (included with Python)
- 4GB+ RAM recommended
- 10GB+ storage for uploads and logs

### Python Dependencies
See `requirements.txt` for complete list. Key dependencies:
- Flask 3.0.0
- Pillow 10.2.0 (image processing)
- pandas 2.2.0 (data export)
- reportlab 4.0.9 (PDF generation)
- pytest 8.0.0 (testing)

## 🔧 Installation

### Development Setup

1. **Clone the Repository**
```bash
git clone <repository-url>
cd surveytray
```

2. **Create Virtual Environment**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
```

3. **Install Dependencies**
```bash
pip install -r requirements.txt
```

4. **Environment Configuration**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Initialize Database**
```bash
flask init-db
# or
python -c "from app import app; app.app_context().push(); from pykes.models import init_db; init_db()"
```

6. **Run Development Server**
```bash
python app.py
# or
flask run
```

The application will be available at `http://localhost:5000`

### Production Deployment

#### Option 1: Docker Deployment (Recommended)

```bash
# Build image
docker build -t surveytray .

# Run container
docker run -d \
  --name surveytray \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e FLASK_ENV=production \
  surveytray
```

#### Option 2: Traditional Server Deployment

```bash
# Install production dependencies
pip install gunicorn

# Run with Gunicorn
gunicorn --config gunicorn.conf.py app:app
```

#### Option 3: Systemd Service (Linux)

Create `/etc/systemd/system/surveytray.service`:
```ini
[Unit]
Description=SurveyTray POSM Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/surveytray
Environment=PATH=/path/to/surveytray/venv/bin
Environment=FLASK_ENV=production
ExecStart=/path/to/surveytray/venv/bin/gunicorn --config gunicorn.conf.py app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable surveytray
sudo systemctl start surveytray
```

## ⚙️ Configuration

### Environment Variables

Create `.env` file with the following variables:

```bash
# Application
FLASK_ENV=development  # development, production, testing
FLASK_DEBUG=True
SECRET_KEY=your-secret-key-here

# Database
DB_PATH=maindatabase.db
DATABASE_URL=sqlite:///maindatabase.db

# File Uploads
UPLOAD_FOLDER=static/uploads
MAX_CONTENT_LENGTH=16777216  # 16MB

# Security
SESSION_COOKIE_SECURE=False  # True for HTTPS
WTF_CSRF_ENABLED=True

# Logging
LOG_LEVEL=INFO
ENABLE_JSON_LOGGING=False

# Performance
PAGINATION_PER_PAGE=20
CACHE_TYPE=simple
RATELIMIT_ENABLED=True
```

### Database Schema

The application uses SQLite with the following main tables:

- **users**: User accounts with role-based access
- **outlets**: Retail outlet information
- **executions**: Field visit tracking with images
- **profile**: Application branding configuration

## 🔐 Default Credentials

**Admin Account:**
- Username: `admin`
- Password: `admin123`

**Test Field Agent:**
- Username: `agent1`
- Password: `agent123`

⚠️ **Change default passwords in production!**

## 🧪 Testing

### Run All Tests
```bash
pytest
```

### Run Specific Test Categories
```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Upload functionality tests
pytest -m upload

# Database tests
pytest -m database

# Skip slow tests
pytest -m "not slow"
```

### Test Coverage
```bash
pytest --cov=pykes --cov-report=html
# Open htmlcov/index.html in browser
```

## 📊 Usage

### Admin Functions
- **User Management**: Create, edit, delete users
- **Outlet Management**: Import outlets via CSV/Excel
- **Report Generation**: Export execution data
- **System Configuration**: Customize branding and settings

### Field Agent Functions
- **Visit Execution**: Record retail visits with images
- **GPS Tracking**: Automatic location capture
- **Product Verification**: Track available POSM products
- **Notes and Documentation**: Detailed visit recording

### Reporting Features
- **Data Export**: CSV, Excel, PDF formats
- **Filtering**: By date, region, agent, status
- **Analytics**: Performance dashboards
- **Image Reports**: Include before/after photos

## 🔧 Maintenance

### Database Maintenance
```bash
# Database statistics
flask db-stats

# Optimize database
python -c "from pykes.models import optimize_database; optimize_database()"
```

### File Cleanup
```bash
# Clean old uploaded files (30+ days)
flask cleanup-files
```

### Log Management
Logs are automatically rotated. Manual cleanup:
```bash
# Remove logs older than 30 days
find logs/ -name "*.log*" -mtime +30 -delete
```

### Backup
```bash
# Backup database
cp maindatabase.db backups/db_$(date +%Y%m%d_%H%M%S).db

# Backup uploads
tar -czf backups/uploads_$(date +%Y%m%d_%H%M%S).tar.gz static/uploads/
```

## 🚨 Troubleshooting

### Common Issues

**Database Locked Error**
```bash
# Check for active connections
lsof maindatabase.db
# Restart application if needed
```

**File Upload Issues**
```bash
# Check permissions
chmod 755 static/uploads
chown -R www-data:www-data static/uploads
```

**Memory Issues**
```bash
# Monitor memory usage
python -c "from pykes.models import get_database_stats; print(get_database_stats())"
```

**Log File Issues**
```bash
# Check log directory permissions
ls -la logs/
mkdir -p logs
chmod 755 logs
```

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
export FLASK_DEBUG=True
```

### Health Checks

The application provides health check endpoints:
- `GET /health` - Application health status
- `GET /health/ready` - Readiness probe for load balancers

## 🔒 Security Considerations

### Production Security Checklist

- [ ] Change default passwords
- [ ] Use strong SECRET_KEY
- [ ] Enable HTTPS (set SESSION_COOKIE_SECURE=True)
- [ ] Configure firewall rules
- [ ] Regular security updates
- [ ] Monitor logs for suspicious activity
- [ ] Backup data regularly
- [ ] Use environment variables for secrets

### Rate Limiting

Default rate limits:
- 1000 requests per hour per IP
- Configurable via `RATELIMIT_DEFAULT`

### File Upload Security

- File type validation (images only)
- File size limits (16MB default)
- Virus scanning recommended for production
- Automatic image optimization and thumbnail generation

## 📈 Performance Optimization

### Database Optimization
- Indexed queries for common searches
- Connection pooling
- Query optimization with EXPLAIN QUERY PLAN

### File Handling
- Automatic image compression
- Thumbnail generation
- Old file cleanup

### Caching
- Simple in-memory caching (default)
- Redis support available
- Template caching

### Monitoring
- Comprehensive logging
- Database statistics
- Performance metrics via health endpoints

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guide
- Write comprehensive tests
- Update documentation
- Use meaningful commit messages
- Ensure backward compatibility

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Flask and the Python community
- Pillow for image processing
- Bootstrap for UI framework
- All contributors and testers

## 📞 Support

For support and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review the logs in the `logs/` directory

---

**Built with ❤️ for efficient retail activation management**

# Dangote Cement Execution Tracker

A web application prototype for tracking outlet execution activities for Dangote Cement in Nigeria.

## Features

1. **Pre-populated Outlet Database** - The system comes with an existing database of Dangote Cement outlets across Nigeria.

2. **Execution Capture** - Field agents can:
   - Login to the system
   - Select outlets to perform executions
   - Capture before and after images
   - Automatically record geolocation data
   - Document product availability
   - Add notes and observations

3. **Dashboard** - Interactive dashboard with:
   - Key metrics and statistics
   - Execution over time visualization
   - Regional breakdown of outlets
   - Outlet type distribution
   - Agent performance metrics

4. **Reporting** - Generate detailed reports:
   - Product availability analysis
   - Execution coverage statistics
   - Before and after image comparison
   - Regional performance analysis

5. **Responsive Design** - Works on both desktop and mobile devices for field agents

## Technical Details

### Technologies Used

- **Backend**: Flask (Python)
- **Database**: SQLite (for prototype; would be migrated to a more robust solution for production)
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
- **Visualization**: Chart.js
- **Geolocation**: HTML5 Geolocation API
- **Camera Access**: MediaDevices API

### Database Schema

1. **Outlets Table**
   - Contains outlet information (URN, name, address, type, location, etc.)
   - Pre-populated with sample data

2. **Users Table**
   - Stores user credentials and roles
   - Supports different user types (admin, field agent)

3. **Executions Table**
   - Records execution details
   - Links to before/after images
   - Stores geolocation data
   - Contains product availability information

## Getting Started

### Demo Credentials

- **Admin**: 
  - Username: admin
  - Password: admin123

- **Field Agent**: 
  - Username: agent1
  - Password: agent123

### Running the Application

1. Install dependencies:
   ```
   pip install flask pandas
   ```

2. Run the application:
   ```
   python app.py
   ```

3. Access the application at `http://localhost:5000`

## Future Enhancements

1. **AI Image Analysis** - Implement AI/ML to automatically compare before/after images for compliance

2. **Advanced Analytics** - More sophisticated reporting and predictive analytics

3. **Offline Mode** - Allow field agents to capture executions offline and sync when connectivity is available

4. **Mobile App** - Native mobile applications for Android and iOS

5. **Integration** - Connect with other Dangote systems for seamless data flow

## Screenshots

(Screenshots would be added here in a real README)

## License

This is a prototype application. All rights reserved.

## Contact

For more information, please contact the development team.