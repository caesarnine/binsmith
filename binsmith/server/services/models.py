from __future__ import annotations

from functools import lru_cache
from typing import get_args

from pydantic_ai.models import KnownModelName, infer_model

from binsmith.runtime import get_default_model


@lru_cache(maxsize=1)
def list_known_models() -> tuple[str, ...]:
    literal = getattr(KnownModelName, "__value__", None)
    models: list[str] = []
    if literal is not None:
        try:
            models = list(get_args(literal))
        except TypeError:
            models = []

    default_model = get_default_model()
    if default_model:
        if default_model in models:
            models = [default_model, *[item for item in models if item != default_model]]
        else:
            models.insert(0, default_model)

    return tuple(models)


def is_known_model(model: str) -> bool:
    return model in list_known_models()


def get_default_model_name() -> str:
    return get_default_model()


def validate_model_credentials(model: str) -> None:
    """Raise UserError if the model cannot be instantiated due to missing credentials."""
    infer_model(model)
