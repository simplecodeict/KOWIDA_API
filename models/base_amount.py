from extensions import db

class BaseAmount(db.Model):
    __tablename__ = 'base_amounts'
    
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False) 