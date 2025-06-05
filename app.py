from flask import Flask
from extensions import db, bcrypt, jwt, colombo_tz
from datetime import timedelta

def create_app():
    app = Flask(__name__)
    
    # Database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:lahiru12@localhost/postgres'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'dev-key-change-in-production'
    
    # JWT Configuration
    app.config['JWT_SECRET_KEY'] = 'jwt-secret-key-change-in-production'  # Change this in production!
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)  # Token expires in 1 hour
    
    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    
    # Import models
    from models import User, BankDetails, Reference
    
    # Register blueprints
    from routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True) 