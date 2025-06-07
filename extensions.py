from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
import pytz
import os
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

# Initialize Flask extensions
db = SQLAlchemy()
bcrypt = Bcrypt()
jwt = JWTManager()

# Set Colombo timezone
colombo_tz = pytz.timezone('Asia/Colombo')

# JWT configuration function
def configure_jwt(app):
    # Use environment variable for secret key with fallback
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'dev-jwt-secret-key')
    
    # Basic JWT settings
    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    app.config['JWT_HEADER_NAME'] = 'Authorization'
    app.config['JWT_HEADER_TYPE'] = 'Bearer'
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
    
    # Additional JWT settings for better compatibility
    app.config['JWT_ERROR_MESSAGE_KEY'] = 'message'
    app.config['JWT_IDENTITY_CLAIM'] = 'sub'
    app.config['JWT_USER_CLAIMS'] = 'user_claims'
    app.config['JWT_DECODE_ALGORITHMS'] = ['HS256']
    
    # Initialize JWT
    jwt.init_app(app)
    
    logger.debug("JWT configured with:")
    logger.debug(f"JWT_TOKEN_LOCATION: {app.config['JWT_TOKEN_LOCATION']}")
    logger.debug(f"JWT_HEADER_NAME: {app.config['JWT_HEADER_NAME']}")
    logger.debug(f"JWT_HEADER_TYPE: {app.config['JWT_HEADER_TYPE']}")
    logger.debug(f"JWT_ACCESS_TOKEN_EXPIRES: {app.config['JWT_ACCESS_TOKEN_EXPIRES']}")
    logger.debug(f"JWT_IDENTITY_CLAIM: {app.config['JWT_IDENTITY_CLAIM']}")
    logger.debug(f"JWT_DECODE_ALGORITHMS: {app.config['JWT_DECODE_ALGORITHMS']}") 