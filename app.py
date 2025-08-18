# app.py
from flask import Flask
from pykes.models import init_db
from pykes.routes import init_routes
from pykes.config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
init_db()

# Initialize routes BEFORE registering blueprints +tscQ#L4-+dSe%K
init_routes(app)

# Register blueprints
from app_reports import reports_bp
from app_admin import admin_bp
app.register_blueprint(reports_bp)
app.register_blueprint(admin_bp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)