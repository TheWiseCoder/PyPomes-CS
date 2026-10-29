from pypomes_core import str_sanitize
from enum import StrEnum, auto
from typing import Any, Final
from unidecode import unidecode


class CsEngine(StrEnum):
    """
    Supported *CS* engines.
    """
    AWS = auto()
    GCS = auto()
    MINIO = auto()


class CsParam(StrEnum):
    """
    Parameters for connecting to *CS* engines.
    """
    # all engines
    ENGINE_ID = "engine-id"
    ENGINE_TYPE = "engine-type"
    BUCKET_NAME = "bucket-name"
    VERSION = "version"
    LOGGER = "logger"

    # AWS and MinIO
    ENDPOINT_URL = "endpoint-url"
    ACCESS_KEY = "access-key"
    SECRET_KEY = "secret-key"
    SECURE_ACCESS = "secure-access"
    REGION_NAME = "region-name"

    # GCS
    CREDENTIALS = "credentials"
    PROJECT_ID = "project-id"


# access data for the configured CS engines
CS_ACCESS_DATA: Final[dict[str, dict[CsParam, Any]]] = {}


def _assert_engine(engine: CsEngine | str,
                   errors: list[str] = None) -> tuple[str, CsEngine]:
    """
    Verify if *engine* is in the list of supported engines.

    If *engine* is a supported engine, it is returned. If its value is *None*,
    the first engine in the list of supported engines (the default engine) is returned.

    :param engine: the reference database engine
    :param errors: incidental errors
    :return: the validated or the default engine
    """
    # initialize the return valiable
    result: tuple[str | None, CsEngine | None] | None = None

    for key, value in CS_ACCESS_DATA.items():
        if not engine or engine == key:
            result = (key, value.get(CsParam.ENGINE_TYPE))
            break
    if not result:
        for key, value in CS_ACCESS_DATA.items():
            if engine == value.get(CsParam.ENGINE_TYPE):
                result = (key, value[CsParam.ENGINE_TYPE])
                break

    if not result:
        if isinstance(errors, list):
            errors.append(f"CS engine '{engine}' unknown or not configured")
        result = (None, None)

    return result


def _get_param(engine_id: str,
               param: CsParam) -> Any:
    """
    Return the current value of *param* being used by *engine*.

    :param engine_id: the reference CS engine
    :param param: the reference parameter
    :return: the parameter's current value
    """
    return (CS_ACCESS_DATA.get(engine_id) or {}).get(param)


def _get_params(engine_id: str) -> dict[CsParam, Any]:
    """
    Return the current parameters being used for *engine*.

    :param engine_id: the reference database engine
    :return: the current parameters for the engine
    """
    return CS_ACCESS_DATA.get(engine_id)


def _except_msg(exception: Exception,
                engine_id: str) -> str:
    """
    Format and return the error message corresponding to the exception raised while accessing the *CS* store.

    :param exception: the exception raised
    :param engine_id: the reference database engine
    :return: the formatted error message
    """
    endpoint: str = (CS_ACCESS_DATA.get(engine_id) or {}).get(CsParam.ENDPOINT_URL)
    return f"Error accessing '{engine_id}' at '{endpoint}': {str_sanitize(f'{exception}')}"


def _normalize_tags(tags: dict[str, str]) -> dict[str, str]:

    # initialize the return variable
    result: dict[str, str] | None = None

    # have tags been defined ?
    if tags:
        # yes, process them
        result = {}
        for key, value in tags.items():
            # normalize 'key' and 'value', by removing all diacritics
            result[unidecode(string=key).lower()] = unidecode(string=value)

    return result
