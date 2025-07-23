from extensions import db

# Import all models
from .user import User
from .bank_details import BankDetails
from .reference import Reference
from .transaction import Transaction
from .transaction_details import TransactionDetails

__all__ = ['User', 'BankDetails', 'Reference', 'Transaction', 'TransactionDetails']
