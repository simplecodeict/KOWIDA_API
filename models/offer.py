from datetime import datetime
from extensions import db, colombo_tz

class Offer(db.Model):
    __tablename__ = 'offers'
    
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(500), nullable=False)
    base_value = db.Column(db.Numeric(10, 2), nullable=False)
    discount = db.Column(db.Numeric(10, 2), nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz).replace(tzinfo=None))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz).replace(tzinfo=None), onupdate=lambda: datetime.now(colombo_tz).replace(tzinfo=None))

