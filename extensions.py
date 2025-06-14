from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
import pytz
import os
from datetime import timedelta
import logging
import secrets
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError
import mimetypes
import uuid

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Initialize Flask extensions
db = SQLAlchemy()
bcrypt = Bcrypt()
jwt = JWTManager()

# Set Colombo timezone
colombo_tz = pytz.timezone('Asia/Colombo')

# Initialize AWS S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION', 'ap-south-1')
)

def generate_secure_key():
    """Generate a secure random key"""
    return secrets.token_urlsafe(64)  # 64 bytes = 512 bits

# JWT configuration function
def configure_jwt(app):
    # Use strong secret keys from environment or generate secure ones
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', generate_secure_key())
    app.config['JWT_PRIVATE_KEY'] = os.getenv('JWT_PRIVATE_KEY')
    app.config['JWT_PUBLIC_KEY'] = os.getenv('JWT_PUBLIC_KEY')
    
    # Use RS256 if keys are provided, fallback to HS512
    if app.config['JWT_PRIVATE_KEY'] and app.config['JWT_PUBLIC_KEY']:
        app.config['JWT_ALGORITHM'] = os.getenv('JWT_ALGORITHM', 'RS256')
    else:
        app.config['JWT_ALGORITHM'] = 'HS512'  # More secure than HS256
    
    # Token settings
    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    app.config['JWT_HEADER_NAME'] = 'Authorization'
    app.config['JWT_HEADER_TYPE'] = 'Bearer'
    
    # Token expiration (from environment or defaults)
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(
        seconds=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 3600))  # 1 hour default
    )
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(
        seconds=int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES', 604800))  # 1 week default
    )
    
    # Security settings
    app.config['JWT_ERROR_MESSAGE_KEY'] = 'message'
    app.config['JWT_IDENTITY_CLAIM'] = 'sub'
    app.config['JWT_USER_CLAIMS'] = 'user_claims'
    app.config['JWT_DECODE_ALGORITHMS'] = [app.config['JWT_ALGORITHM']]
    app.config['JWT_COOKIE_SECURE'] = True  # Only send cookies over HTTPS
    app.config['JWT_COOKIE_CSRF_PROTECT'] = True  # Enable CSRF protection
    app.config['JWT_CSRF_CHECK_FORM'] = True  # Check CSRF tokens in forms
    app.config['JWT_CSRF_IN_COOKIES'] = True  # Store CSRF tokens in cookies
    
    # Cookie settings (if using cookies in the future)
    app.config['JWT_COOKIE_SAMESITE'] = 'Strict'  # Strict same-site policy
    
    # Initialize JWT
    jwt.init_app(app)
    
    # Log non-sensitive configuration
    logger.info("JWT configured with:")
    logger.info(f"Algorithm: {app.config['JWT_ALGORITHM']}")
    logger.info(f"Token location: {app.config['JWT_TOKEN_LOCATION']}")
    logger.info(f"Access token expires in: {app.config['JWT_ACCESS_TOKEN_EXPIRES']}")
    logger.info(f"Refresh token expires in: {app.config['JWT_REFRESH_TOKEN_EXPIRES']}")
    logger.info(f"CSRF protection enabled: {app.config['JWT_COOKIE_CSRF_PROTECT']}")

def get_file_mime_type(file_name):
    """
    Get MIME type of file based on extension
    """
    mime_type, _ = mimetypes.guess_type(file_name)
    return mime_type or 'application/octet-stream'

def upload_file_to_s3(file_data, file_name, bucket_name=None):
    """
    Upload a file to S3 bucket and make it publicly accessible
    :param file_data: File data in bytes
    :param file_name: Name of the file
    :param bucket_name: Name of the S3 bucket (optional, uses default from env)
    :return: URL of the uploaded file
    """
    try:
        # Use default bucket if not specified
        bucket = bucket_name or os.getenv('AWS_S3_BUCKET')
        if not bucket:
            raise ValueError("S3 bucket name not provided")

        # Generate unique file name
        file_extension = file_name.split('.')[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"

        # Get file type
        file_type = get_file_mime_type(file_name)
        
        # Upload file to S3 with public-read ACL
        s3_client.put_object(
            Bucket=bucket,
            Key=unique_filename,
            Body=file_data,
            ContentType=file_type,
            ACL='public-read'  # Make the object publicly readable
        )

        # Generate URL for the uploaded file
        url = f"https://{bucket}.s3.amazonaws.com/{unique_filename}"
        return url

    except ClientError as e:
        logger.error(f"Error uploading file to S3: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error uploading file to S3: {str(e)}")
        raise 