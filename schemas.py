from marshmallow import Schema, fields, validate, ValidationError

class UserRegistrationSchema(Schema):
    full_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    phone = fields.Str(required=True, validate=validate.Regexp(
        r'^(\+94|0)[0-9]{9}$',
        error='Phone number must be in format +94XXXXXXXXX or 0XXXXXXXXX'
    ))
    password = fields.Str(required=True, validate=validate.Length(min=6))
    url = fields.Url(required=True, validate=validate.Length(max=255))

class LoginSchema(Schema):
    phone = fields.Str(required=True, validate=validate.Regexp(
        r'^[0-9]{9}$',
        error='Phone number must be in format +94XXXXXXXXX or 0XXXXXXXXX'
    ))
    password = fields.Str(required=True)

class BankDetailsSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    bank_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    branch = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    account_number = fields.Str(required=True, validate=validate.Length(min=5, max=20)) 