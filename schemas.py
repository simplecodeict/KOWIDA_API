from marshmallow import Schema, fields, validate, ValidationError

class UserRegistrationSchema(Schema):
    full_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    phone = fields.Str(required=True, validate=validate.Regexp(
        r'^[0-9]{9,10}$',
        error='Phone number must be 9 or 10 digits'
    ))
    password = fields.Str(required=True, validate=validate.Length(min=6))
    promo_code = fields.Str(required=False)
    url = fields.Url(required=True, validate=validate.Length(max=255))

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