"""
Schémas Marshmallow pour validation des entrées V3 - XML source de vérité
Supporte nouveaux attributs : comment, status, archived, protected, file_identifier, etc.
"""
from marshmallow import Schema, fields, validate, INCLUDE

class BaseSchema(Schema):
    class Meta:
        unknown = INCLUDE  # Permet key_identifier, comment, file_identifier, etc. sans erreur

class RegisterSchema(BaseSchema):
    full_name = fields.Str(required=True, validate=validate.Length(min=2, max=120))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=6, max=128))

class LoginSchema(BaseSchema):
    email = fields.Email(required=True)
    password = fields.Str(required=True)

class DatabaseCreateSchema(BaseSchema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    description = fields.Str(required=False, load_default="")
    comment = fields.Str(required=False, load_default="")
    scope = fields.Str(required=False, load_default="PERSONAL", validate=validate.OneOf(["PERSONAL", "COMMON", "personal", "common"]))
    common_permission = fields.Str(required=False, allow_none=True, validate=validate.OneOf(["VIEW", "EDIT", "MANAGE"]))

class DatabaseUpdateSchema(BaseSchema):
    name = fields.Str(required=False, validate=validate.Length(min=1, max=120))
    description = fields.Str(required=False)
    comment = fields.Str(required=False)
    status = fields.Str(required=False, validate=validate.OneOf(["ACTIVE","ARCHIVED","active","archived"]))
    scope = fields.Str(required=False, validate=validate.OneOf(["PERSONAL", "COMMON", "personal", "common"]))
    common_permission = fields.Str(required=False, allow_none=True, validate=validate.OneOf(["VIEW", "EDIT", "MANAGE"]))
    expected_version = fields.Int(required=False)

class TableCreateSchema(BaseSchema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    description = fields.Str(required=False, load_default="")
    database_id = fields.Int(required=True)
    is_protected = fields.Bool(required=False, load_default=False)
    protected = fields.Bool(required=False, load_default=False)  # alias XML
    file_identifier = fields.Str(required=False, load_default=None)
    fileIdentifier = fields.Str(required=False, load_default=None)  # alias camelCase
    comment = fields.Str(required=False, load_default="")
    status = fields.Str(required=False, load_default="ACTIVE")
    archived = fields.Bool(required=False)
    expected_version = fields.Int(required=False)

class TableUpdateSchema(BaseSchema):
    name = fields.Str(required=False, validate=validate.Length(min=1, max=120))
    description = fields.Str(required=False)
    is_protected = fields.Bool(required=False)
    protected = fields.Bool(required=False)
    file_identifier = fields.Str(required=False, allow_none=True)
    fileIdentifier = fields.Str(required=False, allow_none=True)
    comment = fields.Str(required=False)
    status = fields.Str(required=False, validate=validate.OneOf(["ACTIVE","ARCHIVED","active","archived"]))
    archived = fields.Bool(required=False)
    # clé pour débloquer table protégée
    key_identifier = fields.Str(required=False)
    expected_version = fields.Int(required=False)

class ColumnCreateSchema(BaseSchema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    type = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    length = fields.Str(required=False, load_default="-")
    nullable = fields.Bool(required=False, load_default=True)
    primary_key = fields.Bool(required=False, load_default=False)
    primaryKey = fields.Bool(required=False, load_default=False)
    foreign_key = fields.Bool(required=False, load_default=False)
    foreignKey = fields.Bool(required=False, load_default=False)
    unique = fields.Bool(required=False, load_default=False, data_key="unique")
    auto_increment = fields.Bool(required=False, load_default=False)
    autoIncrement = fields.Bool(required=False, load_default=False)
    default = fields.Str(required=False, allow_none=True, load_default=None, data_key="default")
    comment = fields.Str(required=False, load_default="")
    status = fields.Str(required=False, load_default="ACTIVE")
    archived = fields.Bool(required=False)
    references = fields.Str(required=False, allow_none=True)
    index = fields.Bool(required=False, load_default=False)
    on_delete = fields.Str(required=False, load_default="NO ACTION")
    on_update = fields.Str(required=False, load_default="NO ACTION")
    table_id = fields.Int(required=True)
    key_identifier = fields.Str(required=False)
    expected_version = fields.Int(required=False)

class ColumnUpdateSchema(BaseSchema):
    name = fields.Str(required=False)
    type = fields.Str(required=False)
    length = fields.Str(required=False)
    nullable = fields.Bool(required=False)
    primary_key = fields.Bool(required=False)
    primaryKey = fields.Bool(required=False)
    foreign_key = fields.Bool(required=False)
    foreignKey = fields.Bool(required=False)
    unique = fields.Bool(required=False)
    auto_increment = fields.Bool(required=False)
    autoIncrement = fields.Bool(required=False)
    default = fields.Str(required=False, allow_none=True)
    comment = fields.Str(required=False)
    status = fields.Str(required=False)
    archived = fields.Bool(required=False)
    references = fields.Str(required=False, allow_none=True)
    index = fields.Bool(required=False)
    on_delete = fields.Str(required=False)
    on_update = fields.Str(required=False)
    key_identifier = fields.Str(required=False)
    expected_version = fields.Int(required=False)

class UnlockTableSchema(BaseSchema):
    table_id = fields.Int(required=True)
    key_identifier = fields.Str(required=True)

class ConvertXmlToSqlSchema(BaseSchema):
    xml = fields.Str(required=True)

class ConvertSqlToXmlSchema(BaseSchema):
    sql = fields.Str(required=True)

class SyncXmlSchema(BaseSchema):
    xml = fields.Str(required=True)
    key_identifier = fields.Str(required=False)
