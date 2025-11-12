from datetime import datetime
from extensions import db, colombo_tz

class UserToken(db.Model):
    __tablename__ = 'user_tokens'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    expo_push_token = db.Column(db.Text, nullable=True)
    
    # Relationship
    user = db.relationship('User', backref='user_tokens')

