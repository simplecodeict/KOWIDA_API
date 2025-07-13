from datetime import datetime
from extensions import db, colombo_tz

class Reference(db.Model):
    __tablename__ = 'references'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False, unique=True)
    discount_amount = db.Column(db.Numeric(10, 2), nullable=True)
    received_amount = db.Column(db.Numeric(10, 2), nullable=True)
    phone = db.Column(db.ForeignKey('users.phone'), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz), onupdate=lambda: datetime.now(colombo_tz))
    
    # Remove the backref from here since it's defined in the User model
    user = db.relationship('User', foreign_keys=[phone]) 