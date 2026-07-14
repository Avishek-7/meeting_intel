class MeetingIntelError(Exception):
    """Base exception for all MeetingIntel errors."""
    pass

class ValidationError(MeetingIntelError):
    """Raised when client input is invalid."""
    pass

class AIServiceError(MeetingIntelError):
    """Raised when AI processing fails."""
    pass

class DatabaseError(MeetingIntelError):
    """Raised for database-related issues."""
    pass

class ConflictError(DatabaseError):
    """Raised when a request conflicts with current database state."""
    pass

class NotFoundError(MeetingIntelError):
    """Raised when a requested resource is not found or access is denied."""
    pass