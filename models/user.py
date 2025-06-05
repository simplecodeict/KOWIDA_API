from datetime import datetime
from extensions import db, bcrypt, colombo_tz

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False, unique=True)
    password = db.Column(db.String(128), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    promo_code = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz), onupdate=lambda: datetime.now(colombo_tz))
    
    # Relationships
    bank_details = db.relationship('BankDetails', backref='user', lazy=True)
    references = db.relationship('Reference', 
                               primaryjoin="User.phone == Reference.phone",
                               backref=db.backref('referrer', lazy=True),
                               lazy=True)
    
    def __init__(self, full_name, phone, password, url, promo_code=None):
        self.full_name = full_name
        self.phone = phone
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')
        self.url = url
        self.promo_code = promo_code

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password, password) 