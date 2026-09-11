"""Erreurs métier stables, partagées par REST et TCP."""


class XMLForgeError(Exception):
    status_code = 400
    code = "XMLFORGE_ERROR"

    def __init__(self, message, *, details=None):
        super().__init__(message)
        self.message = message
        self.details = details


class ValidationFailed(XMLForgeError):
    code = "VALIDATION_FAILED"


class XmlValidationError(ValidationFailed):
    code = "XML_INVALID"


class DataValidationError(ValidationFailed):
    code = "DATA_INVALID"


class ConstraintViolation(XMLForgeError):
    status_code = 409
    code = "CONSTRAINT_VIOLATION"


class ConflictError(XMLForgeError):
    status_code = 409
    code = "SYNC_CONFLICT"


class NotFoundError(XMLForgeError):
    status_code = 404
    code = "NOT_FOUND"


class PermissionDenied(XMLForgeError):
    status_code = 403
    code = "FORBIDDEN"


class StorageError(XMLForgeError):
    status_code = 500
    code = "STORAGE_ERROR"


class ControlPlaneIntegrityError(XMLForgeError):
    status_code = 409
    code = "CONTROL_PLANE_INTEGRITY"


class ControlPlaneNotFoundError(NotFoundError):
    code = "CONTROL_PLANE_NOT_FOUND"
