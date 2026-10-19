from pypomes_core import (
    APP_PREFIX,
    env_get_bool, env_get_str, env_get_strs,
    env_get_enum, str_sanitize, obj_positional
)
from enum import StrEnum, auto
from logging import Logger
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

    # AWS and MinIO
    ENDPOINT_URL = "endpoint-url"
    ACCESS_KEY = "access-key"
    SECRET_KEY = "secret-key"
    SECURE_ACCESS = "secure-access"
    REGION_NAME = "region-name"

    # GCS
    CREDENTIALS = "credentials"
    PROJECT_ID = "project-id"


# CS loggers
_CS_LOGGERS: Final[dict[str, Logger | None]] = {}


def __get_access_data() -> dict[str, dict[CsParam, Any]]:
    """
    Establish the access data for select *CS* engines, from environment variables.

    Sepcifying *CS* parameters dynamically with 'gcs_setup()' is the required way for *GCS* engines,
    if authentication is done through credential key/value pairs, whereas specifying *CS* parameters
    dynamically with 'cs_setup()' is the preferred way for AWS and MinIO engines. Specifying *CS*
    parameters with environment variables can be done in two ways:
      - 1. for a single *CS* engine, specify the set
           - *<APP_PREFIX>_CS_ENGINE_ID*
           - *<APP_PREFIX>_CS_ENGINE_TYPE* (one of *aws*, *minio*, *gcs*)
           - *<APP_PREFIX>_CS_BUCKET_NAME*
           - *<APP_PREFIX>_CS_CREDENTIALS* (GCS)
           - *<APP_PREFIX>_CS_PROJECT_ID* (GCS)
           - *<APP_PREFIX>_CS_ENDPOINT_URL* (AWS, MinIO)
           - *<APP_PREFIX>_CS_ACCESS_KEY* (AWS, MinIO)
           - *<APP_PREFIX>_CS_SECRET_KEY* (AWS, MinIO)
           - *<APP_PREFIX>_CS_SECURE_ACCESS* (AWS, MinIO)
           - *<APP_PREFIX>_CS_REGION_NAME* (AWS, MinIO)
      - 2. for multiple *CS* engines, specify a comma-separated list of engines in
           *<APP_PREFIX>_CS_ENGINES, and, for each engine, specify the set above, respectively replacing
           *_CS_* with *_AWS_*, *_MINIO_*, and *_GCS_*, for the engines listed

    :return: the access data for the selected *CS* engines
    """
    # initialize the return variable
    result: dict[str, dict[CsParam, Any]] = {}

    engines: list[str] = []
    single_engine: str = env_get_str(key=f"{APP_PREFIX}_CS_ENGINE_ID")
    if single_engine:
        default_setup: bool = True
        engines.append(single_engine)
    else:
        default_setup: bool = False
        multi_engines: list[str] = env_get_strs(key=f"{APP_PREFIX}_CS_ENGINES")
        if multi_engines:
            engines.extend(multi_engines)

    for engine in engines:
        if default_setup:
            prefix: str = "CS"
            default_setup = False
        else:
            prefix: str = engine
        cs_type: CsEngine = env_get_enum(key=f"{APP_PREFIX}_{prefix}_ENGINE_TYPE",
                                         enum_class=CsEngine,
                                         values=[CsEngine.AWS, CsEngine.MINIO])
        if not cs_type:
            cs_type = obj_positional(engine,
                                     keys=("AWS", "MINIO"),
                                     values=(CsEngine.AWS, CsEngine.MINIO))
        if not cs_type:
            raise ValueError(f"Unable to establish type for CS engine '{engine}'")
        result[engine] = {
            CsParam.BUCKET_NAME: env_get_str(key=f"{APP_PREFIX}_{prefix}_BUCKET_NAME"),
            CsParam.ENGINE_TYPE: cs_type,
            CsParam.VERSION: ""
        }
        if cs_type in [CsEngine.AWS, CsEngine.MINIO]:
            result[engine].update({
                CsParam.ENDPOINT_URL: env_get_str(key=f"{APP_PREFIX}_{prefix}_ENDPOINT_URL"),
                CsParam.BUCKET_NAME: env_get_str(key=f"{APP_PREFIX}_{prefix}_BUCKET_NAME"),
                CsParam.ACCESS_KEY: env_get_str(key=f"{APP_PREFIX}_{prefix}_ACCESS_KEY"),
                CsParam.SECRET_KEY: env_get_str(key=f"{APP_PREFIX}_{prefix}_SECRET_KEY"),
                CsParam.REGION_NAME: env_get_str(key=f"{APP_PREFIX}_{prefix}_REGION_NAME")
            })
            if cs_type == CsEngine.MINIO:
                result[engine][CsParam.SECURE_ACCESS] = env_get_bool(key=f"{APP_PREFIX}_{prefix}_SECURE_ACCESS")
        elif cs_type == CsEngine.GCS:
            result[engine][CsParam.PROJECT_ID] = env_get_str(key=f"{APP_PREFIX}_{prefix}_PROJECT_ID")
        _CS_LOGGERS[engine] = None

    return result


# access data for the configured CS engines
_CS_ACCESS_DATA: Final[dict[str, dict[CsParam, Any]]] = __get_access_data()


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

    for key, value in _CS_ACCESS_DATA.items():
        if not engine or engine == key:
            result = (key, value.get(CsParam.ENGINE_TYPE))
            break
    if not result:
        for key, value in _CS_ACCESS_DATA.items():
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
    return (_CS_ACCESS_DATA.get(engine_id) or {}).get(param)


def _get_params(engine_id: str) -> dict[CsParam, Any]:
    """
    Return the current parameters being used for *engine*.

    :param engine_id: the reference database engine
    :return: the current parameters for the engine
    """
    return _CS_ACCESS_DATA.get(engine_id)


def _except_msg(exception: Exception,
                engine_id: str) -> str:
    """
    Format and return the error message corresponding to the exception raised while accessing the *CS* store.

    :param exception: the exception raised
    :param engine_id: the reference database engine
    :return: the formatted error message
    """
    endpoint: str = (_CS_ACCESS_DATA.get(engine_id) or {}).get(CsParam.ENDPOINT_URL)
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
