class LLMServiceException(Exception):
    """Base exception class for LLM Service errors"""
    pass

class InternalConversionException(LLMServiceException):
    """Raised when there are issues with the internal conversion of the request"""
    pass

class ServiceConnectionException(LLMServiceException):
    """Raised when there are connection issues or any other general error with the server"""
    pass

class ThrottlingException(LLMServiceException):
    """Raised when the provider is throttling requests, after the maximum number of retries has been reached"""
    pass

class StructuredResponseException(LLMServiceException):
    """Raised when there is a problem with the structured response conversion from the LLM output to the desired StructuredResponse class"""
    pass