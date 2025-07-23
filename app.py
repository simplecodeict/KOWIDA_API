from flask import Flask, jsonify, request
from extensions import db, bcrypt, jwt, colombo_tz, configure_jwt
from datetime import timedelta
from flask_jwt_extended import exceptions as jwt_exceptions
from jwt.exceptions import InvalidTokenError, DecodeError
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
import os
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Print environment variables for debugging (remove in production)
logging.debug(f"DATABASE_URL: {os.getenv('DATABASE_URL')}")
logging.debug(f"SECRET_KEY set: {'Yes' if os.getenv('SECRET_KEY') else 'No'}")
logging.debug(f"JWT_SECRET_KEY set: {'Yes' if os.getenv('JWT_SECRET_KEY') else 'No'}")

def create_app():
    app = Flask(__name__)
    
    # Enable CORS with proper configuration
    CORS(app, resources={
        r"/api/*": {
            "origins": os.getenv('ALLOWED_ORIGINS', '*').split(','),
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # Database configuration
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logging.error("DATABASE_URL environment variable is not set!")
        database_url = 'postgresql://postgres:lahiru12@localhost/postgres'  # Fallback for development
        
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Check if required environment variables are set
    if not os.getenv('SECRET_KEY'):
        logging.error("SECRET_KEY environment variable is not set!")
        app.config['SECRET_KEY'] = 'dev-key-change-in-production'  # Fallback for development
    else:
        app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
        
    if not os.getenv('JWT_SECRET_KEY'):
        logging.error("JWT_SECRET_KEY environment variable is not set!")
        app.config['JWT_SECRET_KEY'] = 'jwt-secret-key-change-in-production'  # Fallback for development
    else:
        app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')

    # Configure JWT
    configure_jwt(app)
    
    # Rate limiting configuration
    app.config['RATELIMIT_DEFAULT'] = os.getenv('RATELIMIT_DEFAULT', '100 per minute')
    app.config['RATELIMIT_STORAGE_URL'] = os.getenv('RATELIMIT_STORAGE_URL', 'memory://')
    
    # Security headers
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response
    
    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    
    # Import models
    from models import User, BankDetails, Reference, Transaction, TransactionDetails
    from models.base_amount import BaseAmount
    
    # Register blueprints
    from routes import auth_bp
    from routes.bank import bank_bp
    from routes.reference import reference_bp
    from routes.admin import admin_bp
    from routes.base_amount import base_amount_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(bank_bp, url_prefix='/api')
    app.register_blueprint(reference_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(base_amount_bp, url_prefix='/api')
    
    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_data):
        logger.debug(f"Token expired. Header: {jwt_header}, Data: {jwt_data}")
        return jsonify({
            'status': 'error',
            'message': 'Token has expired',
            'error_code': 'TOKEN_EXPIRED'
        }), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        logger.debug(f"Invalid token error: {error}")
        return jsonify({
            'status': 'error',
            'message': 'Invalid token',
            'error_code': 'INVALID_TOKEN'
        }), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        logger.debug(f"Missing token error: {error}")
        return jsonify({
            'status': 'error',
            'message': 'Authorization token is missing',
            'error_code': 'MISSING_TOKEN'
        }), 401

    @jwt.token_verification_failed_loader
    def verification_failed_callback(jwt_header, jwt_data):
        logger.debug(f"Token verification failed. Header: {jwt_header}, Data: {jwt_data}")
        return jsonify({
            'status': 'error',
            'message': 'Token verification failed',
            'error_code': 'TOKEN_VERIFICATION_FAILED'
        }), 401

    # Generic error handlers
    @app.errorhandler(HTTPException)
    def handle_http_error(e):
        logger.error(f"HTTP error: {e}")
        return jsonify({
            'status': 'error',
            'message': e.description,
            'error_code': e.name.upper().replace(' ', '_'),
            'status_code': e.code
        }), e.code

    @app.errorhandler(Exception)
    def handle_generic_error(e):
        if isinstance(e, (InvalidTokenError, DecodeError)):
            logger.error(f"JWT decode error: {e}")
            return jsonify({
                'status': 'error',
                'message': 'Invalid token format',
                'error_code': 'INVALID_TOKEN_FORMAT'
            }), 401
            
        # Log the error here (you should set up proper logging)
        logger.error(f"Unhandled error: {str(e)}")
        
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred',
            'error_code': 'INTERNAL_SERVER_ERROR'
        }), 500
    
    # Database connection health check endpoint
    @app.route('/api/health', methods=['GET'])
    def health_check():
        try:
            # Check database connection
            db.session.execute('SELECT 1')
            return jsonify({
                'status': 'success',
                'message': 'Service is healthy',
                'database': 'connected'
            }), 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({
                'status': 'error',
                'message': 'Service is unhealthy',
                'database': 'disconnected',
                'error': str(e)
            }), 500
    
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
    
    return app

app = create_app()

if __name__ == '__main__':
    # Only enable debug mode in development
    debug_mode = os.getenv('FLASK_ENV', 'development') == 'development'
    app.run(
        host=os.getenv('FLASK_HOST', '0.0.0.0'),
        port=int(os.getenv('FLASK_PORT', 5000)),
        debug=debug_mode
    ) 