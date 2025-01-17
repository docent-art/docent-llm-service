from pathlib import Path

import yaml
from pydantic import BaseModel


class ModelProvider(BaseModel):
    name: str
    config: dict = {}


class Model(BaseModel):
    provider: ModelProvider
    name: str
    id: str
    max_tokens: int
    max_output_tokens: int
    image_support: bool = False
    document_support: bool = False
    config: dict = {}


class Registry:
    _instance = None
    _initialized = False
    providers: list[ModelProvider] = []
    models: list[Model] = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Registry, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not Registry._initialized:
            self._initialize()
            Registry._initialized = True

    def _initialize(self):
        # Get the path to models.yaml
        yaml_path = Path(__file__).parent / "models.yaml"

        with open(yaml_path, "r") as file:
            data = yaml.safe_load(file)

        models = []
        models_data = data.get("MODELS", {})
        providers_data = data.get("PROVIDERS", {})

        for provider_name, provider_models in models_data.items():
            provider = ModelProvider(name=provider_name, config=providers_data[provider_name].get("config", {}))

            for model_name, model_data in provider_models.items():
                model = Model(
                    provider=provider,
                    name=model_name,
                    id=model_data["id"],
                    max_tokens=model_data["max_tokens"],
                    max_output_tokens=model_data["max_output_tokens"],
                    config=model_data.get("config", {}),
                )
                models.append(model)

        self.models = models

    def get_model(self, provider: str, name: str) -> Model:
        if not self.models:
            self._initialize()

        for model in self.models:
            if model.provider.name == provider and model.name == name:
                return model

        raise ValueError(f"No model found for provider '{provider}' with name '{name}'")


# Global instance
REGISTRY = Registry()
