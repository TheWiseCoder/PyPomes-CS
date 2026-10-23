from .cs_common import (
    CsEngine, CsParam
)
from .cs_pomes import (
    cs_setup, cs_remove, cs_set_logger, cs_get_engines,
    cs_get_param, cs_get_params, cs_get_type,
    cs_startup, cs_get_client,
    cs_data_store, cs_data_retrieve,
    cs_file_store, cs_file_retrieve,
    cs_object_store, cs_object_retrieve,
    cs_item_exists, cs_item_get_info,
    cs_item_get_tags, cs_item_remove,
    cs_items_count, cs_items_get_info,
    cs_items_get_names, cs_items_remove, cs_generate_presigned_url
)
from .gcs_pomes import gcs_setup

__all__ = [
    # cs_common
    "CsEngine", "CsParam",
    # cs_pomes
    "cs_setup", "cs_remove", "cs_set_logger", "cs_get_engines",
    "cs_get_param", "cs_get_params", "cs_get_type",
    "cs_startup", "cs_get_client",
    "cs_data_store", "cs_data_retrieve",
    "cs_file_store", "cs_file_retrieve",
    "cs_object_store", "cs_object_retrieve",
    "cs_item_exists", "cs_item_get_info",
    "cs_item_get_tags", "cs_item_remove",
    "cs_items_count", "cs_items_get_info",
    "cs_items_get_names", "cs_items_remove", "cs_generate_presigned_url",
    # gcs_pomes
    "gcs_setup"
]

from importlib.metadata import version
__version__ = version("pypomes_cs")
__version_info__ = tuple(int(i) for i in __version__.split(".") if i.isdigit())
