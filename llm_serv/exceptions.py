class BaseException(Exception):
    """Base exception class for all LLM service exceptions."""
    pass

class CredentialsException(BaseException):
    """Exception raised when credentials are not set."""
    pass

class TimeoutException(BaseException):
    """Exception raised when a request times out."""
    pass

class StructuredResponseException(BaseException):
    """Exception raised when structured response parsing fails."""
    def __init__(self, message: str, xml: str = "", return_class: type = None):
        self.xml = xml
        self.return_class = return_class
        super().__init__(message)

class ServiceCallException(BaseException):
    """Exception raised when a service call fails."""
    pass

class ServiceCallThrottlingException(BaseException):
    """Exception raised when a service call is throttled."""
    pass

class InternalConversionException(BaseException):
    """Exception raised when internal conversion fails."""
    pass

class ModelNotFoundException(BaseException):
    """Exception raised when the model is not found on the backend."""
    pass
