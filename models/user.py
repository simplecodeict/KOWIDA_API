from datetime import datetime
from extensions import db, bcrypt, colombo_tz
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates
from sqlalchemy import Enum
import re

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False, unique=True, index=True)
    _password = db.Column('password', db.String(128), nullable=False)
    url = db.Column(db.String(255), nullable=True)
    payment_method = db.Column(db.String(50), nullable=False, default='card_payment')
    promo_code = db.Column(db.String(255), nullable=True, index=True)
    role = db.Column(Enum('admin', 'user', 'referer', name='user_roles'), default='user', nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    is_reference_paid = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)
    
    # Relationships
    bank_details = db.relationship('BankDetails', backref='user', lazy=True, cascade='all, delete-orphan')
    references = db.relationship('Reference', 
                               primaryjoin="User.phone == Reference.phone",
                               backref=db.backref('referrer', lazy=True),
                               lazy=True)
    
    def __init__(self, full_name, phone, password, url, payment_method='card_payment', promo_code=None, role=None):
        self.full_name = full_name
        self.phone = phone
        self.password = password  # This will use the password.setter
        self.url = url
        self.payment_method = payment_method
        self.promo_code = promo_code
        self.role = role  # Will be validated and defaulted to 'user' if None
        self.is_reference_paid = False
        self.is_active = False
        # Explicitly set the created_at time to ensure correct timezone
        # Store local time without timezone info to avoid UTC conversion
        self.created_at = datetime.now(colombo_tz).replace(tzinfo=None)
        self.updated_at = datetime.now(colombo_tz).replace(tzinfo=None)

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
            return None  # Allow null/empty URLs
        
        # Basic URL validation
        if not re.match(r'^https?:\/\/.+', url):
            raise ValueError("Invalid URL format")
            
        return url

    @validates('payment_method')
    def validate_payment_method(self, key, payment_method):
        if not payment_method:
            return 'card_payment'  # Default to card_payment if not provided
        
        # Validate payment method (allow common payment methods)
        allowed_methods = ['card_payment', 'bank_deposit', 'bank_transfer', 'cash', 'online_payment']
        if payment_method.lower() not in allowed_methods:
            raise ValueError(f"Invalid payment method. Allowed methods: {', '.join(allowed_methods)}")
            
        return payment_method.lower()

    @validates('role')
    def validate_role(self, key, role):
        if not role:
            return 'user'  # Default to user if not provided
        
        # Validate role (allow only specified roles)
        allowed_roles = ['admin', 'user', 'referer']
        if role.lower() not in allowed_roles:
            raise ValueError(f"Invalid role. Allowed roles: {', '.join(allowed_roles)}")
            
        return role.lower()

    @staticmethod
    def _is_password_strong(password):
        """
        Validate password format
        - Must be exactly 4 digits (0-9)
        """
        # Check if password is exactly 4 digits
        return bool(re.match(r'^[0-9]{4}$', password)) 