from datetime import datetime
from extensions import db, bcrypt, colombo_tz
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates
import re

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False, unique=True, index=True)
    _password = db.Column('password', db.String(128), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    promo_code = db.Column(db.String(255), nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=False)
    is_reference_paid = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz), onupdate=lambda: datetime.now(colombo_tz))
    
    # Relationships
    bank_details = db.relationship('BankDetails', backref='user', lazy=True, cascade='all, delete-orphan')
    references = db.relationship('Reference', 
                               primaryjoin="User.phone == Reference.phone",
                               backref=db.backref('referrer', lazy=True),
                               lazy=True)
    
    def __init__(self, full_name, phone, password, url, promo_code=None):
        self.full_name = full_name
        self.phone = phone
        self.password = password  # This will use the password.setter
        self.url = url
        self.promo_code = promo_code
        self.is_reference_paid = False
        self.is_active = False

    @hybrid_property
    def password(self):
        return self._password

    @password.setter
    def password(self, plain_text_password):
        if plain_text_password:
            # Password validation for 4 digits
            if not self._is_password_strong(plain_text_password):
                raise ValueError("Password must be exactly 4 digits (0-9)")
            self._password = bcrypt.generate_password_hash(plain_text_password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self._password, password)

    @validates('full_name')
    def validate_full_name(self, key, full_name):
        if not full_name or len(full_name.strip()) < 2:
            raise ValueError("Full name must be at least 2 characters long")
        return full_name.strip()

    @validates('phone')
    def validate_phone(self, key, phone):
        if not phone:
            raise ValueError("Phone number is required")
        
        # Remove any spaces or special characters
        phone = re.sub(r'[^0-9]', '', phone)
        
        # Validate Sri Lankan phone number format
        if not re.match(r'^[0-9]{9,10}$', phone):
            raise ValueError("Invalid phone number format. Must be 9-10 digits")
            
        return phone

    @validates('url')
    def validate_url(self, key, url):
        if not url:
            raise ValueError("URL is required")
        
        # Basic URL validation
        if not re.match(r'^https?:\/\/.+', url):
            raise ValueError("Invalid URL format")
            
        return url

    @staticmethod
    def _is_password_strong(password):
        """
        Validate password format
        - Must be exactly 4 digits (0-9)
        """
        # Check if password is exactly 4 digits
        return bool(re.match(r'^[0-9]{4}$', password)) 