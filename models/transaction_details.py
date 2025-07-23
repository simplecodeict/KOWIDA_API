from datetime import datetime
from extensions import db, colombo_tz

class TransactionDetails(db.Model):
    __tablename__ = 'transaction_details'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    transaction_id = db.Column(db.String(20), db.ForeignKey('transactions.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz).replace(tzinfo=None))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz).replace(tzinfo=None), onupdate=lambda: datetime.now(colombo_tz).replace(tzinfo=None))
    
    # Relationships
    user = db.relationship('User', backref='transaction_details')
    transaction = db.relationship('Transaction')
    
    def __init__(self, user_id, transaction_id):
        self.user_id = user_id
        self.transaction_id = transaction_id
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'transaction_id': self.transaction_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        } 