import json
from pypomes_core import (
    APP_PREFIX,
    env_get_bool, env_get_str, env_get_strs,
    env_get_enum, env_get_path, str_sanitize, file_get_data
)
from enum import StrEnum, auto
from pathlib import Path
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


def __get_access_data() -> dict[str, dict[CsParam, Any]]:
    """
    Establish the access data for select *CS* engines, from environment variables.

    If authentication is done through credential key/value pairs, spscifying *CS* parameters dynamically
    with *gcs_setup()* is the required way for *GCS* engines, whereas specifying *CS* parameters
    dynamically with *cs_setup()* is the preferred way for AWS and MinIO engines. With environment variables,
    it can be done in two ways:

      - 1. for a single *CS* engine, specify the set
           - *<APP_PREFIX>_CS_ENGINE_ID*
           - *<APP_PREFIX>_CS_ENGINE_TYPE* (one of *aws*, *minio*, *gcs*)
           - *<APP_PREFIX>_CS_BUCKET_NAME*
           - *<APP_PREFIX>_CS_CREDENTIALS* (GCS - must be a path to a file)
           - *<APP_PREFIX>_CS_PROJECT_ID* (GCS)
           - *<APP_PREFIX>_CS_ENDPOINT_URL* (AWS, MinIO)
           - *<APP_PREFIX>_CS_ACCESS_KEY* (AWS, MinIO)
           - *<APP_PREFIX>_CS_SECRET_KEY* (AWS, MinIO)
           - *<APP_PREFIX>_CS_SECURE_ACCESS* (AWS, MinIO)
           - *<APP_PREFIX>_CS_REGION_NAME* (AWS, MinIO)

      - 2. for multiple *CS* engines, specify a comma-separated list of  engines in
           *<APP_PREFIX>_CS_ENGINES, and, for each engine, specify the set above,
           respectively replacing *_CS_* with that unique identification.

    :return: the access data for the selected *CS* engines
    """
    # initialize the return variable
    result: dict[str, dict[CsParam, Any]] = {}

    prefixes: list[str] = []
    single_engine: str = env_get_str(key=f"{APP_PREFIX}_CS_ENGINE_ID")
    if single_engine:
        prefixes.append("CS")
    else:
        multi_engines: list[str] = env_get_strs(key=f"{APP_PREFIX}_CS_ENGINES")
        if multi_engines:
            prefixes.extend(multi_engines)

    for prefix in prefixes:
        engine_id = single_engine or prefix
        prefix = f"{APP_PREFIX}_{prefix}"
        cs_type: CsEngine = env_get_enum(key=f"{prefix}_ENGINE_TYPE",
                                         enum_class=CsEngine)
        if not cs_type:
            raise ValueError(f"Unable to establish type for CS engine '{engine_id}'")

        result[engine_id] = {
            CsParam.BUCKET_NAME: env_get_str(key=f"{prefix}_BUCKET_NAME"),
            CsParam.ENGINE_TYPE: cs_type,
            CsParam.VERSION: "",
            CsParam.LOGGER: None
        }
        if cs_type == CsEngine.GCS:
            credentials: Path = env_get_path(key=f"{prefix}_CREDENTIALS")
            if credentials:
                credentials_bytes: bytes = file_get_data(credentials)
                credentials = json.loads(s=credentials_bytes)
            result[engine_id].update({
                CsParam.CREDENTIALS: credentials,
                CsParam.PROJECT_ID: env_get_str(key=f"{prefix}_PROJECT_ID"),
            })
        elif cs_type in [CsEngine.AWS, CsEngine.MINIO]:
            result[engine_id].update({
                CsParam.ENDPOINT_URL: env_get_str(key=f"{prefix}_ENDPOINT_URL"),
                CsParam.ACCESS_KEY: env_get_str(key=f"{prefix}_ACCESS_KEY"),
                CsParam.SECRET_KEY: env_get_str(key=f"{prefix}_SECRET_KEY"),
                CsParam.REGION_NAME: env_get_str(key=f"{prefix}_REGION_NAME")
            })
            if cs_type == CsEngine.MINIO:
                result[engine_id][CsParam.SECURE_ACCESS] = env_get_bool(key=f"{prefix}_SECURE_ACCESS")

    return result


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


# access data for the configured CS engines
CS_ACCESS_DATA: Final[dict[str, dict[CsParam, Any]]] = __get_access_data()
