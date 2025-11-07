from extensions import db

class Version(db.Model):
    __tablename__ = 'versions'
    
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(50), nullable=False)

