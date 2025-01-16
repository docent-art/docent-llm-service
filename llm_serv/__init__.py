from llm_serv.registry import REGISTRY

# This ensures REGISTRY is initialized when the package is imported
_ = REGISTRY.models
