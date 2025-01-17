# Providers

The base class for all providers is `LLMService`, in `base.py`.

The base class provides the following methods:

#### `_convert`

This method is implemented by each provider and converts the `LLMRequest` object to the format each provider requires. This means that the Conversation object is converted to the specific format (messages and system variables) as well as the configuration dictionary.

This method can raise the following exceptions:
> InternalConversionException(LLMServiceException)

#### `_service_call`

This method is implemented by each provider and calls the underlying provider directly, and handles failure cases like throttling with retries internally.

This method can raise the following exceptions:

> ServiceCallException(LLMServiceException)
Raised when there are connection issues or any other general error with the server

> ServiceCallThrottlingException(LLMServiceException)
Raised when the provider is throttling requests, after the maximum number of retries has been reached.

#### `__call__`

This method is called by the `LLMService` class and ties the ``_convert`` and ``_service_call`` methods together. It takes an `LLMRequest` object and returns an `LLMResponse` object.

This method return the following exceptions:

> ServiceCallException(LLMServiceException)
> ServiceCallThrottlingException(LLMServiceException)
> InternalConversionException(LLMServiceException)

> StructuredResponseException(LLMServiceException)
This exception is raised when there is a problem with the structured response conversion from the LLM output to the desired StructuredResponse class.