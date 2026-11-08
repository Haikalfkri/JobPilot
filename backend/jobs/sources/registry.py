from .arbeitnow import ArbeitnowAdapter
from .base import SourceError
from .jobicy import JobicyAdapter

REGISTRY = {cls.source_key: cls for cls in (JobicyAdapter, ArbeitnowAdapter)}


def get_adapter(source_key: str, **kwargs):
    try:
        return REGISTRY[source_key](**kwargs)
    except KeyError:
        raise SourceError("UNKNOWN_SOURCE", f"No adapter is registered for '{source_key}'.") from None