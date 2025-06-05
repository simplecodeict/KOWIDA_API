from flask import Flask
from extensions import db
from models.reference import Reference
from models.user import User

def migrate_references():
    # Create a temporary table
    db.engine.execute("""
        CREATE TABLE references_new (
            id SERIAL PRIMARY KEY,
            code VARCHAR(50) UNIQUE NOT NULL,
            discount_amount NUMERIC(10,2),
            received_amount NUMERIC(10,2),
            phone VARCHAR(9) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE,
            FOREIGN KEY (phone) REFERENCES users(phone)
        )
    """)
    
    # Copy data from old table to new table
    db.engine.execute("""
        INSERT INTO references_new (id, code, discount_amount, received_amount, phone, created_at, updated_at)
        SELECT r.id, r.code, r.discount_amount, r.received_amount, u.phone, r.created_at, r.updated_at
        FROM references r
        JOIN users u ON r.user_id = u.id
    """)
    
    # Drop old table
    db.engine.execute("DROP TABLE references")
    
    # Rename new table
    db.engine.execute("ALTER TABLE references_new RENAME TO references")
    
    # Create index on phone
    db.engine.execute("CREATE INDEX idx_references_phone ON references(phone)")

if __name__ == '__main__':
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:lahiru12@localhost/postgres'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        migrate_references() 