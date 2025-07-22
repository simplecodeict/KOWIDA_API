from marshmallow import Schema, fields, validate, ValidationError

class UserRegistrationSchema(Schema):
    full_name = fields.Str(required=True, validate=validate.Length(min=2))
    phone = fields.Str(required=True, validate=validate.Length(min=9, max=10))
    password = fields.Str(required=True, validate=validate.Length(equal=4))
    promo_code = fields.Str(allow_none=True)
    role = fields.Str(allow_none=True, validate=validate.OneOf(['admin', 'user', 'referer']))
    paid_amount = fields.Decimal(places=2, required=False, allow_none=True, validate=validate.Range(min=0))
    # url field is removed since it will be populated from S3

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
        r'^[0-9]{9,10}$',
        error='Phone number must be 9 or 10 digits'
    ))

class UserFilterSchema(Schema):
    start_date = fields.Date(required=False, allow_none=True)
    end_date = fields.Date(required=False, allow_none=True)
    promo_code = fields.Str(required=False, allow_none=True)
    reference_code = fields.Str(required=False, allow_none=True)
    is_active = fields.Str(required=False, allow_none=True)
    phone = fields.Str(required=False, allow_none=True)
    payment_method = fields.Str(required=False, allow_none=True)
    page = fields.Int(required=False, load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(required=False, load_default=10, validate=validate.Range(min=1, max=100))

class ReferenceCodeSchema(Schema):
    reference_code = fields.Str(required=True)
    is_reference_paid = fields.Boolean(required=False, allow_none=True)
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