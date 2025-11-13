from datetime import datetime
from extensions import db, colombo_tz

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    type = db.Column(db.String(50), nullable=True)
    header = db.Column(db.String(255), nullable=True)
    sub_header = db.Column(db.String(255), nullable=True)
    body = db.Column(db.Text, nullable=True)
    restriction_area = db.Column(db.String(255), nullable=True)
    url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz).replace(tzinfo=None))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz).replace(tzinfo=None), onupdate=lambda: datetime.now(colombo_tz).replace(tzinfo=None))

