from flask import Flask, jsonify
from extensions import db, bcrypt, jwt, colombo_tz
from datetime import timedelta
from flask_jwt_extended import exceptions as jwt_exceptions
from jwt.exceptions import InvalidTokenError, DecodeError

def create_app():
    app = Flask(__name__)
    
    # Database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:lahiru12@localhost/postgres'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'dev-key-change-in-production'
    
    # JWT Configuration
    app.config['JWT_SECRET_KEY'] = 'jwt-secret-key-change-in-production'  # Change this in production!
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)  # Token expires in 1 hour
    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    app.config['JWT_HEADER_NAME'] = 'Authorization'
    app.config['JWT_HEADER_TYPE'] = 'Bearer'
    
    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    
    # Import models
    from models import User, BankDetails, Reference
    
    # Register blueprints
    from routes import auth_bp
    from routes.bank import bank_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(bank_bp, url_prefix='/api')
    
    # JWT error handlers
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({
            'status': 'error',
            'message': 'Invalid token'
        }), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({
            'status': 'error',
            'message': 'Authorization token is missing'
        }), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_data):
        return jsonify({
            'status': 'error',
            'message': 'Token has expired'
        }), 401

    @jwt.token_verification_failed_loader
    def verification_failed_callback(jwt_header, jwt_data):
        return jsonify({
            'status': 'error',
            'message': 'Token verification failed'
        }), 401

    @app.errorhandler(jwt_exceptions.JWTDecodeError)
    def handle_jwt_decode_error(e):
        return jsonify({
            'status': 'error',
            'message': 'Invalid token format'
        }), 401

    @app.errorhandler(Exception)
    def handle_generic_jwt_error(e):
        if isinstance(e, (InvalidTokenError, DecodeError)):
            return jsonify({
                'status': 'error',
                'message': 'Invalid token format'
            }), 401
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True) 