from marshmallow import Schema, fields, validate, ValidationError
from datetime import datetime

def validate_password_if_provided(value):
    """Validate password only if it's provided"""
    if value is not None and value != '':
        if not (len(value) == 4 and value.isdigit()):
            raise ValidationError("Password must be exactly 4 digits (0-9)")
    return value

class UserRegistrationSchema(Schema):
    full_name = fields.Str(required=True, validate=validate.Length(min=2))
    phone = fields.Str(required=True, validate=validate.Length(min=9, max=15))
    password = fields.Str(required=True, validate=validate.Length(equal=4))
    promo_code = fields.Str(allow_none=True)
    role = fields.Str(allow_none=True, validate=validate.OneOf(['admin', 'user', 'referer']))
    paid_amount = fields.Decimal(places=2, required=False, allow_none=True, validate=validate.Range(min=0))
    referal_coin = fields.Decimal(places=2, required=False, allow_none=True, validate=validate.Range(min=0))
    # url field is removed since it will be populated from S3

class PreRegisterSchema(Schema):
    full_name = fields.Str(required=True, validate=validate.Length(min=2))
    phone = fields.Str(required=True, validate=validate.Length(min=9, max=10))
    password = fields.Str(required=False, allow_none=True, load_default=None, validate=validate_password_if_provided)

class LoginSchema(Schema):
    phone = fields.Str(required=True, validate=validate.Regexp(
        r'^[0-9]{9,10}$',
        error='Phone number must be 9 or 10 digits'
    ))
    password = fields.Str(required=True)

class BankDetailsSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    bank_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    branch = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    account_number = fields.Str(required=True, validate=validate.Length(min=5, max=20))

class ReferenceCreateSchema(Schema):
    phone = fields.Str(required=True, validate=validate.Regexp(
        r'^[0-9]{9,10}$',
        error='Phone number must be 9 or 10 digits'
    ))
    promo_code = fields.Str(required=True)
    discount_amount = fields.Decimal(places=2, required=True, validate=validate.Range(min=0))
    received_amount = fields.Decimal(places=2, required=True, validate=validate.Range(min=0))

class AdminBankDetailsSchema(Schema):
    phone = fields.Str(required=True, validate=validate.Regexp(
        r'^[0-9]{9,10}$',
        error='Phone number must be 9 or 10 digits'
    ))
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    bank_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    branch = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    account_number = fields.Str(required=True, validate=validate.Length(min=5, max=20))

class UserPhoneSchema(Schema):
    phone = fields.Str(required=True, validate=validate.Regexp(
        r'^[0-9]{9,15}$',
        error='Phone number must be 9 or 10 digits'
    ))

class UserFilterSchema(Schema):
    start_date = fields.Date(required=False, allow_none=True)
    end_date = fields.Date(required=False, allow_none=True)
    promo_code = fields.Str(required=False, allow_none=True)
    reference_code = fields.Str(required=False, allow_none=True)
    is_active = fields.Str(required=False, allow_none=True)
    is_reference_paid = fields.Boolean(required=False, allow_none=True)
    phone = fields.Str(required=False, allow_none=True)
    payment_method = fields.Str(required=False, allow_none=True)
    page = fields.Int(required=False, load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(required=False, load_default=10, validate=validate.Range(min=1, max=100))

class ReferenceCodeSchema(Schema):
    reference_code = fields.Str(required=True)
    is_reference_paid = fields.Boolean(required=False, allow_none=True)
    is_active = fields.Boolean(required=False, allow_none=True)
    page = fields.Int(required=False, load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(required=False, load_default=10, validate=validate.Range(min=1, max=100))

class AdminUserDataSchema(Schema):
    full_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    phone = fields.Str(required=True, validate=validate.Regexp(
        r'^[0-9]{9,10}$',
        error='Phone number must be 9 or 10 digits'
    ))
    password = fields.Str(required=True)
    role = fields.Str(allow_none=True, validate=validate.OneOf(['admin', 'user', 'referer']))
    paid_amount = fields.Decimal(places=2, required=False, allow_none=True, validate=validate.Range(min=0))

class AdminReferenceDataSchema(Schema):
    code = fields.Str(required=True)
    discount_amount = fields.Decimal(places=2, required=True, validate=validate.Range(min=0))
    received_amount = fields.Decimal(places=2, required=True, validate=validate.Range(min=0))

class AdminRegistrationSchema(Schema):
    user_data = fields.Nested(AdminUserDataSchema, required=True)
    bank_details = fields.Nested(BankDetailsSchema, required=True)
    reference_data = fields.Nested(AdminReferenceDataSchema, required=True)

class MakeTransactionSchema(Schema):
    reference_code = fields.Str(required=True)
    user_id = fields.Int(required=True)
    total_reference_amount = fields.Decimal(places=2, required=True, validate=validate.Range(min=0))
    # receipt will be handled as file upload, not in JSON schema

class TransactionFilterSchema(Schema):
    reference_code = fields.Str(required=False, allow_none=True)
    user_id = fields.Int(required=False, allow_none=True)
    page = fields.Int(required=False, load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(required=False, load_default=10, validate=validate.Range(min=1, max=100))

class ReferrerStatisticsSchema(Schema):
    user_id = fields.Int(required=True)

class DateOrDateTimeField(fields.DateTime):
    """Custom field that accepts both date and datetime strings, converting dates to datetime at midnight"""
    
    def _deserialize(self, value, attr, data, **kwargs):
        # If it's already a datetime object, return as is
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            # Check if it's just a date string (YYYY-MM-DD format, exactly 10 characters)
            if len(value.strip()) == 10 and value.count('-') == 2:
                try:
                    # Parse as date and set time to midnight (00:00:00)
                    date_obj = datetime.strptime(value.strip(), '%Y-%m-%d')
                    return date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
                except ValueError:
                    # If parsing fails, fall through to datetime parsing
                    pass
            
            # Try parsing as datetime using parent's deserialization
            try:
                return super()._deserialize(value, attr, data, **kwargs)
            except ValidationError:
                raise ValidationError("Not a valid date or datetime. Expected format: YYYY-MM-DD or ISO datetime format.")
        
        # For other types, use parent's deserialization
        return super()._deserialize(value, attr, data, **kwargs)

class OfferSchema(Schema):
    message = fields.Str(required=True, validate=validate.Length(min=1, max=500))
    base_value = fields.Decimal(places=2, required=True, validate=validate.Range(min=0))
    discount = fields.Decimal(places=2, required=True, validate=validate.Range(min=0))
    end_date = DateOrDateTimeField(required=True)
    is_active = fields.Boolean(required=False, load_default=True)

class VersionCreateSchema(Schema):
    version = fields.Str(required=True, validate=validate.Length(min=1, max=50))

class VersionUpdateSchema(Schema):
    version = fields.Str(required=True, validate=validate.Length(min=1, max=50)) 