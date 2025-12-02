from datetime import datetime
from extensions import db, colombo_tz
from sqlalchemy import Enum

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    type = db.Column(Enum('announcement', 'quotes', 'news', 'boost_knowledge', name='notification_types'), nullable=True)
    header = db.Column(db.String(255), nullable=True)
    sub_header = db.Column(db.String(255), nullable=True)
    body = db.Column(db.Text, nullable=True)
    restriction_area = db.Column(db.String(255), nullable=True)
    url = db.Column(db.String(500), nullable=True)
    who_see = db.Column(db.String(255), nullable=False, default='all')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz).replace(tzinfo=None))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz).replace(tzinfo=None), onupdate=lambda: datetime.now(colombo_tz).replace(tzinfo=None))

