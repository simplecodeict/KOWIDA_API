from datetime import datetime
from extensions import db, colombo_tz

class SharedTransaction(db.Model):
    __tablename__ = 'shared_transactions'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_count = db.Column(db.Integer, nullable=False)
    full_amount = db.Column(db.Numeric(10, 2), nullable=False)
    kowida_fund = db.Column(db.Numeric(10, 2), nullable=False)
    randyll_fund = db.Column(db.Numeric(10, 2), nullable=False)
    receipt_url = db.Column(db.String(500), nullable=True)
    status = db.Column(db.Boolean, default=False, nullable=False)
    remark = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz).replace(tzinfo=None))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(colombo_tz).replace(tzinfo=None), onupdate=lambda: datetime.now(colombo_tz).replace(tzinfo=None))
    
    def __init__(self, user_count, full_amount, kowida_fund, randyll_fund, receipt_url=None, status=False, remark=None):
        self.user_count = user_count
        self.full_amount = full_amount
        self.kowida_fund = kowida_fund
        self.randyll_fund = randyll_fund
        self.receipt_url = receipt_url
        self.status = status
        self.remark = remark
