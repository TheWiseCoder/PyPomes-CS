import json
import sys
from pypomes_core import (
    APP_PREFIX,
    env_get_bool, env_get_str, env_get_strs,
    env_get_enum, env_get_path, file_get_data
)
from pathlib import Path

from .cs_common import CS_ACCESS_DATA, CsEngine, CsParam


def cs_init_from_environment() -> None:
    """
    Establish the access data for select *CS* engines, from environment variables.

    If authentication is done through credential key/value pairs, spscifying *CS* parameters dynamically
    with *gcs_setup()* is the required way for *GCS* engines, whereas specifying *CS* parameters
    dynamically with *cs_setup()* is the preferred way for AWS and MinIO engines.
    To make sure defined environment variables are processed, this function is invoked once,
    at module *cs_pomes* load time. The environment variables can be setup in two ways:

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

      - 2. for multiple *CS* engines, or if engine id named variables are preferred, specify a
           comma-separated list of engines identifications in *<APP_PREFIX>_CS_ENGINES, and for each one,
           specify the set above, respectively replacing *_CS_* with that unique identification.

    :return: the access data for the selected *CS* engines
    """
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
        # HAZARD: prevent re-establishing access data for engine
        if engine_id not in CS_ACCESS_DATA:
            prefix = f"{APP_PREFIX}_{prefix}"
            cs_type: CsEngine = env_get_enum(key=f"{prefix}_ENGINE_TYPE",
                                             enum_class=CsEngine)
            if not cs_type:
                err_msg: str = f"Unable to establish type for CS engine '{engine_id}'"
                sys.stderr.write(err_msg)
                raise ValueError(err_msg)

            CS_ACCESS_DATA[engine_id] = {
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
                CS_ACCESS_DATA[engine_id].update({
                    CsParam.CREDENTIALS: credentials,
                    CsParam.PROJECT_ID: env_get_str(key=f"{prefix}_PROJECT_ID"),
                })
            elif cs_type in [CsEngine.AWS, CsEngine.MINIO]:
                CS_ACCESS_DATA[engine_id].update({
                    CsParam.ENDPOINT_URL: env_get_str(key=f"{prefix}_ENDPOINT_URL"),
                    CsParam.ACCESS_KEY: env_get_str(key=f"{prefix}_ACCESS_KEY"),
                    CsParam.SECRET_KEY: env_get_str(key=f"{prefix}_SECRET_KEY"),
                    CsParam.REGION_NAME: env_get_str(key=f"{prefix}_REGION_NAME")
                })
                if cs_type == CsEngine.MINIO:
                    CS_ACCESS_DATA[engine_id][CsParam.SECURE_ACCESS] = env_get_bool(key=f"{prefix}_SECURE_ACCESS")
