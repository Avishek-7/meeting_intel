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