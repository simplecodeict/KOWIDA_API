from datetime import datetime
from extensions import db, colombo_tz
from sqlalchemy import func
import re

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.String(20), primary_key=True)
    total_reference_count = db.Column(db.Integer, nullable=False)
    total_reference_amount = db.Column(db.Numeric(10, 2), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reference_code = db.Column(db.String(50), nullable=False)
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False)
    received_amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz), onupdate=lambda: datetime.now(colombo_tz))
    
    # Relationships
    user = db.relationship('User', backref='transactions')
    transaction_details = db.relationship('TransactionDetails', backref='parent_transaction', cascade='all, delete-orphan')
    
    def __init__(self, total_reference_count, total_reference_amount, user_id, reference_code, discount_amount, received_amount, status=False):
        self.id = self._generate_transaction_id()
        self.total_reference_count = total_reference_count
        self.total_reference_amount = total_reference_amount
        self.user_id = user_id
        self.reference_code = reference_code
        self.discount_amount = discount_amount
        self.received_amount = received_amount
        self.status = status
    
    @staticmethod
    def _generate_transaction_id():
        """Generate unique transaction ID like TR001, TR002, etc."""
        # Get the last transaction ID
        last_transaction = Transaction.query.order_by(Transaction.id.desc()).first()
        
        if last_transaction:
            # Extract the number from the last ID
            match = re.search(r'TR(\d+)', last_transaction.id)
            if match:
                last_number = int(match.group(1))
                new_number = last_number + 1
            else:
                new_number = 1
        else:
            new_number = 1
        
        # Format with leading zeros (e.g., TR001, TR002, TR010, TR100)
        return f"TR{new_number:03d}"
    
    def to_dict(self):
        return {
            'id': self.id,
            'total_reference_count': self.total_reference_count,
            'total_reference_amount': float(self.total_reference_amount),
            'user_id': self.user_id,
            'reference_code': self.reference_code,
            'discount_amount': float(self.discount_amount),
            'received_amount': float(self.received_amount),
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        } 