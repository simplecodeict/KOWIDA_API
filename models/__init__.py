from extensions import db

# Import all models
from .user import User
from .bank_details import BankDetails
from .reference import Reference

__all__ = ['User', 'BankDetails', 'Reference']
