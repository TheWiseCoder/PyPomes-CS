import pickle
from logging import Logger
from pathlib import Path
from pypomes_core import Mimetype
from typing import Any, BinaryIO

from .cs_common import (
    CS_ACCESS_DATA, CsEngine, CsParam, _assert_engine, _get_param, _except_msg
)


def cs_setup(*,
             engine: CsEngine | str,
             endpoint_url: str,
             bucket_name: str,
             access_key: str,
             secret_key: str,
             engine_type: CsEngine = None,
             region_name: str = None,
             secure_access: bool = None,
             logger: Logger = None,
             errors: list[str] = None) -> bool:
    """
    Establish the parameters for access to *engine* of type *AWS* or *MinIO*.

    To setup instances of *GCS*, use *gcs_setup()*. The meaning of some parameters may vary
    between different *CS* engines. All parameters are required, , with the exception of
    *region_name* and *secure_access*.

    :param engine: the *CS* engine identification
    :param endpoint_url: the access URL for the service
    :param bucket_name: the name of the default bucket
    :param access_key: the access key for the service
    :param secret_key: the access secret code
    :param engine_type: the *CS* engine type (one of [*aws*, *minio*])
    :param region_name: the name of the region where the engine is located
    :param secure_access: whether to use Transport Security Layer
    :param logger: the logger for the *CS* engine
    :param errors: incidental error messages (may be a non-empty list)
    :return: *True* if the parameters were accepted, *False* otherwise
    """
    # initialize the return variable
    result: bool = False

    if isinstance(engine, CsEngine):
        if not engine_type:
            engine_type = engine
        engine = engine.value

    # process the parameters
    if isinstance(engine_type, CsEngine) and engine_type != CsEngine.GCS and \
       endpoint_url and bucket_name and access_key and secret_key and not \
       (region_name and engine_type != CsEngine.AWS) and not \
       (secure_access and engine_type != CsEngine.MINIO):
        CS_ACCESS_DATA[engine] = {
            CsParam.ENGINE_ID: engine,
            CsParam.ENGINE_TYPE: engine_type,
            CsParam.BUCKET_NAME: bucket_name,
            CsParam.ENDPOINT_URL: endpoint_url,
            CsParam.ACCESS_KEY: access_key,
            CsParam.SECRET_KEY: secret_key,
            CsParam.VERSION: "",
            CsParam.LOGGER: logger
        }
        if engine_type == CsEngine.AWS:
            CS_ACCESS_DATA[engine][CsParam.REGION_NAME]: region_name
        elif engine_type == CsEngine.MINIO:
            CS_ACCESS_DATA[engine][CsParam.SECURE_ACCESS] = secure_access
        result = True
    else:
        err_msg = f"Cloud storage engine '{engine}' has missing or invalid setup data"
        if logger:
            logger.error(msg=err_msg)
        if isinstance(errors, list):
            errors.append(err_msg)

    return result


def cs_remove(*,
              engine: CsEngine | str) -> None:
    """
    Unconditionally remove *engine* from the list of configured *CS* engines.

    :param engine: the *CS* engine identification
    """
    # assert and remove the CS engine
    engine_id, _engine_type = _assert_engine(engine=engine)
    if engine_id:
        CS_ACCESS_DATA.pop(engine_id)


def cs_set_logger(engine: CsEngine | str = None,
                  logger: Logger = None) -> bool:
    """
    Establish the logger for logging operations involving *engine*.

    This operation must be invoked after *engine* has been configured. If specified,
    *engine* must be one of [*aws*, *minio*].

    :param engine: the *CS* engine to use (uses the default engine, if not provided)
    :param logger: the logger for the *CS* engine
    :return: *True* if the logger was estabished, *False* otherwise
    """
    # initialize the return variable
    result: bool = False

    # assert the CS engine
    engine_id, _engine_type = _assert_engine(engine=engine)
    if engine_id:
        CS_ACCESS_DATA[engine_id][CsParam.LOGGER] = logger
        result = True

    return result


def cs_get_engines() -> list[str]:
    """
    Retrieve the *list* of configured engines.

    This *list* may include any of the supported engines: *aws*, *minio*.
    Note that the values in the returned *list* are instances of *CsEngine*, not strings.

    :return: the *list* of configured *CS* engines
    """
    # SANITY-CHECK: return a cloned 'list'
    return list(CS_ACCESS_DATA)


def cs_get_param(key: CsParam,
                 engine: CsEngine | str = None) -> str | None:
    """
    Return the connection parameter value for *key*.

    The *key* should be one of *endpoint-url*, *bucket-name*, *access-key*, *secret-key*,
    and *secure-access*. For *aws*, the extra key *region-name* may be used.

    :param key: the connection parameter
    :param engine: the reference *CS* engine (the default engine, if not provided)
    :return: the current value of the connection parameter, or *None* if not found
    """
    # initialize the return variable
    result: Any = None

    # assert the CS engine
    engine_id, engine_type = _assert_engine(engine=engine)

    # retrieve the connection parameter
    if engine_id:
        result = _get_param(engine_id=engine_id,
                            param=key)
    return result


def cs_get_params(engine: CsEngine | str = None) -> dict[CsParam, Any] | None:
    """
    Return the current access parameters as a serializeable *dict*.

    :param engine: the database engine (the default engine, if not provided)
    :return: the current connection parameters for the engine, or *None* if not found
    """
    # initialize the return variable
    result: dict[CsParam, Any] | None = None

    # assert the CS engine
    engine_id, engine_type = _assert_engine(engine=engine)
    # retrieve the connection parameters
    if engine_id:
        result = CS_ACCESS_DATA[engine_id].copy()
        result.pop(CsParam.CREDENTIALS, None)
        result.pop(CsParam.LOGGER, None)

    return result


def cs_get_type(engine: CsEngine | str = None) -> CsEngine:
    """
    Return the current value for the type of the *CS* engine for the instance identified by *engine*.

    :param engine: the reference *CS* engine (the default engine, if not provided)
    :return: the engine type for instance *engine*, or *None* if not found
    """
    return _assert_engine(engine=engine)[1]


def cs_startup(engine: CsEngine | str = None,
               bucket: str = None,
               errors: list[str] = None) -> bool:
    """
    Prepare the *CS* client for operations.

    This function should be called just once, at startup,
    to make sure the interaction with the *CS* service is fully functional.

    :param engine: the *CS* engine to use (uses the default engine, if not provided)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if service is fully functional, *False* otherwise
    """
    # initialize the return variable
    result: bool = False

    # make sure to have an errors list
    if not isinstance(errors, list):
        errors = []

    # assert the CS engine
    engine_id, engine_type = _assert_engine(engine=engine,
                                            errors=errors)
    if engine_id:
        # determine whether 'engine_id' has been prepared for operations
        version: str = CS_ACCESS_DATA[engine_id].get(CsParam.VERSION)
        if version:
            result = True
        else:
            # make sure to have a bucket
            bucket = bucket or _get_param(engine_id=engine_id,
                                          param=CsParam.BUCKET_NAME)
            if engine_type == CsEngine.AWS:
                from . import aws_pomes
                result = aws_pomes.startup(engine_id=engine_id,
                                           bucket=bucket,
                                           errors=errors)
            elif engine_type == CsEngine.MINIO:
                from . import minio_pomes
                result = minio_pomes.startup(engine_id=engine_id,
                                             bucket=bucket,
                                             errors=errors)
            elif engine_type == CsEngine.GCS:
                from . import gcs_pomes
                result = gcs_pomes.startup(engine_id=engine_id,
                                           bucket=bucket,
                                           errors=errors)
            if result:
                CS_ACCESS_DATA[engine_id][CsParam.VERSION] = __get_version(engine=engine)

    return result


def cs_get_client(engine: CsEngine | str = None,
                  errors: list[str] = None) -> Any:
    """
    Obtain and return a client to *engine*, or *None* if the client cannot be obtained.

    The target *CS* engine, default or specified, must have been previously configured.

    :param engine: the *CS* engine to use (uses the default engine, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: the client to the *CS* engine, or *None* if the client cannot be obtained
    """
    # initialize the return variable
    result: Any = None

    # assert the CS engine
    engine_id, engine_type = _assert_engine(engine=engine,
                                            errors=errors)
    if engine_type == CsEngine.AWS:
        from . import aws_pomes
        result = aws_pomes.get_client(engine_id=engine_id,
                                      errors=errors)
    elif engine_type == CsEngine.MINIO:
        from . import minio_pomes
        result = minio_pomes.get_client(engine_id=engine_id,
                                        errors=errors)
    elif engine_type == CsEngine.GCS:
        from . import gcs_pomes
        result = gcs_pomes.get_client(engine_id=engine_id,
                                      errors=errors)

    return result


def cs_data_retrieve(identifier: str,
                     prefix: str | Path = None,
                     data_range: tuple[int, int] = None,
                     bucket: str = None,
                     engine: CsEngine | str = None,
                     client: Any = None,
                     errors: list[str] = None) -> bytes | None:
    """
    Retrieve data from the *CS* store.

    :param identifier: the data identifier
    :param prefix: optional path prefixing the item to be retrieved
    :param data_range: the begin-end positions within the data (in bytes, defaults to *None* - all bytes)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the *CS* engine to use (uses the default engine, if not provided)
    :param client: optional *CS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: the bytes retrieved, or *None* if error or data not found
    """
    # initialize the return variable
    result: bytes | None = None

    # assert the CS engine
    engine_id, engine_type = _assert_engine(engine=engine,
                                            errors=errors)
    if engine_type == CsEngine.AWS:
        from . import aws_pomes
        result = aws_pomes.data_retrieve(engine_id=engine_id,
                                         identifier=identifier,
                                         prefix=prefix,
                                         bucket=bucket,
                                         data_range=data_range,
                                         client=client,
                                         errors=errors)
    elif engine_type == CsEngine.MINIO:
        from . import minio_pomes
        result = minio_pomes.data_retrieve(engine_id=engine_id,
                                           identifier=identifier,
                                           prefix=prefix,
                                           bucket=bucket,
                                           data_range=data_range,
                                           client=client,
                                           errors=errors)
    elif engine_type == CsEngine.GCS:
        from . import gcs_pomes
        result = gcs_pomes.data_retrieve(engine_id=engine_id,
                                         identifier=identifier,
                                         prefix=prefix,
                                         bucket=bucket,
                                         data_range=data_range,
                                         client=client,
                                         errors=errors)
    return result


def cs_data_store(identifier: str,
                  data: bytes | str | BinaryIO,
                  length: int,
                  prefix: str | Path = None,
                  mimetype: Mimetype | str = Mimetype.BINARY,
                  tags: dict = None,
                  bucket: str = None,
                  engine: CsEngine | str = None,
                  client: Any = None,
                  errors: list[str] = None) -> dict[str, str] | None:
    """
    Store data at the *CS* store.

    In case *length* cannot be determined, it should be set to *-1* (*MinIO*), or to *None* (*AWS*, *GCS*).
    Note that *length* is the number of bytes of *data* to be stored. This might lead to error when storing
    strings. In Python, a standard string is a sequence of Unicode code points, not bytes, and thus:
      - *len(string)*: returns the number of characters (Unicode code points)
      - *len(string.encode('utf-8'))*: returns the number of bytes the string occupies when encoded

    This operation returns *None* for *GCS*, and in case of success, a *dict* with information related to
    the stored item for *MinIO* or *AWS*. Unfortunately, it is not possible to detail the information returned,
    as there is no consistency in the responses. In fact, the responses vary wildly with the different *CS*
    implementations. It should also be noted that those responses are not guaranteed to be serializable.

    :param identifier: the data identifier
    :param data: the data to store
    :param length: the length of the data
    :param prefix: optional destination path prefixing the item holding the data
    :param mimetype: the data mimetype, defaults to *BINARY*
    :param tags: optional metadata tags describing the data
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the *CS* engine to use (uses the default engine, if not provided)
    :param client: optional *CS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: stored item's properties, or *None* if error
    """
    # initialize the return variable
    result: dict[str, str] | None = None

    # assert the CS engine
    engine_id, engine_type = _assert_engine(engine=engine,
                                            errors=errors)
    if engine_type == CsEngine.AWS:
        from . import aws_pomes
        result = aws_pomes.data_store(engine_id=engine_id,
                                      identifier=identifier,
                                      data=data,
                                      bucket=bucket,
                                      prefix=prefix,
                                      length=length,
                                      mimetype=mimetype,
                                      tags=tags,
                                      client=client,
                                      errors=errors)
    elif engine_type == CsEngine.MINIO:
        from . import minio_pomes
        result = minio_pomes.data_store(engine_id=engine_id,
                                        identifier=identifier,
                                        data=data,
                                        bucket=bucket,
                                        prefix=prefix,
                                        length=length,
                                        mimetype=mimetype,
                                        tags=tags,
                                        client=client,
                                        errors=errors)
    elif engine_type == CsEngine.GCS:
        from . import gcs_pomes
        gcs_pomes.data_store(engine_id=engine_id,
                             identifier=identifier,
                             data=data,
                             bucket=bucket,
                             prefix=prefix,
                             length=length,
                             mimetype=mimetype,
                             tags=tags,
                             client=client,
                             errors=errors)
    return result


def cs_file_retrieve(identifier: str,
                     filepath: Path | str,
                     bucket: str = None,
                     prefix: str | Path = None,
                     engine: CsEngine | str = None,
                     client: Any = None,
                     errors: list[str] = None) -> bool | None:
    """
    Retrieve a file from the *CS* store.

    :param identifier: the file identifier, tipically a file name
    :param filepath: the path to save the retrieved file at
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path prefixing the item to retrieve as a file
    :param engine: the *CS* engine to use (uses the default engine, if not provided)
    :param client: optional *CS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if the file was retrieved, *False* otherwise, or *None* if error
    """
    # initialize the return variable
    result: bool | None = None

    # assert the CS engine
    engine_id, engine_type = _assert_engine(engine=engine,
                                            errors=errors)
    if engine_type == CsEngine.AWS:
        from . import aws_pomes
        result = aws_pomes.file_retrieve(engine_id=engine_id,
                                         identifier=identifier,
                                         filepath=filepath,
                                         bucket=bucket,
                                         prefix=prefix,
                                         client=client,
                                         errors=errors)
    elif engine_type == CsEngine.MINIO:
        from . import minio_pomes
        result = minio_pomes.file_retrieve(engine_id=engine_id,
                                           identifier=identifier,
                                           filepath=filepath,
                                           bucket=bucket,
                                           prefix=prefix,
                                           client=client,
                                           errors=errors)
    elif engine_type == CsEngine.GCS:
        from . import gcs_pomes
        result = gcs_pomes.file_retrieve(engine_id=engine_id,
                                         identifier=identifier,
                                         filepath=filepath,
                                         bucket=bucket,
                                         prefix=prefix,
                                         client=client,
                                         errors=errors)
    return result


def cs_file_store(identifier: str,
                  filepath: Path | str,
                  mimetype: Mimetype | str,
                  tags: dict = None,
                  bucket: str = None,
                  prefix: str | Path = None,
                  engine: CsEngine | str = None,
                  client: Any = None,
                  errors: list[str] = None) -> bool:
    """
    Store a file at the *CS* store.

    :param identifier: the file identifier, tipically a file name
    :param filepath: optional path specifying where the file is
    :param mimetype: the file mimetype
    :param tags: optional metadata tags describing the file
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional destination path prefixing the item holding the file data
    :param engine: the *CS* engine to use (uses the default engine, if not provided)
    :param client: optional *CS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if the file was successfully stored, *False* if error
    """
    # initialize the return variable
    result: bool = False

    # assert the CS engine
    engine_id, engine_type = _assert_engine(engine=engine,
                                            errors=errors)
    if engine_type == CsEngine.AWS:
        from . import aws_pomes
        result = aws_pomes.file_store(engine_id=engine_id,
                                      identifier=identifier,
                                      filepath=filepath,
                                      mimetype=mimetype,
                                      bucket=bucket,
                                      prefix=prefix,
                                      tags=tags,
                                      client=client,
                                      errors=errors)
    elif engine_type == CsEngine.MINIO:
        from . import minio_pomes
        result = minio_pomes.file_store(engine_id=engine_id,
                                        identifier=identifier,
                                        filepath=filepath,
                                        mimetype=mimetype,
                                        bucket=bucket,
                                        prefix=prefix,
                                        tags=tags,
                                        client=client,
                                        errors=errors)
    elif engine_type == CsEngine.GCS:
        from . import gcs_pomes
        result = gcs_pomes.file_store(engine_id=engine_id,
                                      identifier=identifier,
                                      filepath=filepath,
                                      mimetype=mimetype,
                                      bucket=bucket,
                                      prefix=prefix,
                                      tags=tags,
                                      client=client,
                                      errors=errors)
    return result


def cs_object_retrieve(identifier: str,
                       bucket: str = None,
                       prefix: str | Path = None,
                       engine: CsEngine | str = None,
                       client: Any = None,
                       errors: list[str] = None) -> Any:
    """
    Retrieve an object from the *CS* store.

    :param identifier: the object identifier
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional path prefixing the item to retrieve as object
    :param engine: the *CS* engine to use (uses the default engine, if not provided)
    :param client: optional *CS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: the object retrieved, or *None* if error or object not found
    """
    # initialize the return variable
    result: Any = None

    # retrieve the data
    data: bytes = cs_data_retrieve(identifier=identifier,
                                   bucket=bucket,
                                   prefix=prefix,
                                   engine=engine,
                                   client=client,
                                   errors=errors)
    if data:
        # umarshall the corresponding object
        try:
            result = pickle.loads(data)
        except Exception as e:
            if isinstance(errors, list):
                errors.append(_except_msg(exception=e,
                                          engine_id=engine))
    return result


def cs_object_store(identifier: str,
                    obj: Any,
                    tags: dict = None,
                    bucket: str = None,
                    prefix: str | Path = None,
                    engine: CsEngine | str = None,
                    client: Any = None,
                    errors: list[str] = None) -> dict[str, str] | None:
    """
    Store an object at the *CS* store.

    On success, this operation returns a *dict* with the following properties related to the stored item:
      - *object_name*: The name of the object that was uploaded
      - *version_id*: The version ID of the object, if versioning is enabled on the bucket
      - *etag*: The entity tag (ETag) of the object, which is a unique identifier for the object's content

    :param identifier: the object identifier
    :param obj: object to be stored
    :param tags: optional metadata tags describing the object
    :param engine: the *CS* engine to use (uses the default engine, if not provided)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param prefix: optional destination path prefixing the item holding the object
    :param client: optional *CS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: the stored item's properties listed above, or *None* if error
    """
    # initialize the return variable
    result: dict[str, str] | None = None

    # serialize the object
    data: bytes | None = None
    try:
        data = pickle.dumps(obj=obj)
    except Exception as e:
        if isinstance(errors, list):
            errors.append(_except_msg(exception=e,
                                      engine_id=engine))
    if data:
        # store the serialized object
        result = cs_data_store(identifier=identifier,
                               data=data,
                               length=len(data),
                               mimetype=Mimetype.BINARY,
                               tags=tags,
                               bucket=bucket,
                               prefix=prefix,
                               engine=engine,
                               client=client,
                               errors=errors)
    return result


def cs_item_exists(identifier: str,
                   prefix: str | Path = None,
                   bucket: str = None,
                   engine: CsEngine | str = None,
                   client: Any = None,
                   errors: list[str] = None) -> bool | None:
    """
    Determine if a given item exists in the *CS* store.

    :param identifier: the item identifier
    :param prefix: optional path prefixing the item to be located
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the *CS* engine to use (uses the default engine, if not provided)
    :param client: optional *CS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if the item was found, *False* otherwise, *None* if error
    """
    # initialize the return variable
    result: bool | None = None

    # necessary, as errors are verified after function invocation
    curr_errors: list[str] = []

    # get info about this object
    item_info: dict[str, Any] = cs_item_get_tags(identifier=identifier,
                                                 prefix=prefix,
                                                 bucket=bucket,
                                                 engine=engine,
                                                 client=client,
                                                 errors=curr_errors)
    if not curr_errors:
        result = item_info is not None
    elif isinstance(errors, list):
        errors.extend(curr_errors)

    return result


def cs_item_get_info(identifier: str,
                     attributes: list[str],
                     prefix: str | Path = None,
                     bucket: str = None,
                     engine: CsEngine | str = None,
                     client: Any = None,
                     errors: list[str] = None) -> Any:
    """
    Retrieve the information about an item in the *CS* store.

    The information returned depends on the *engine* in question, and can be viewed at the
    native invocation's *docstring*.

    :param identifier: the item identifier
    :param attributes: the item's attributes to be returned
    :param prefix: optional path prefixing the item
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the *CS* engine to use (uses the default engine, if not provided)
    :param client: optional *CS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: information about the item, or *None* if error or item not found
    """
    # initialize the return variable
    result: Any | None = None

    # assert the CS engine
    engine_id, engine_type = _assert_engine(engine=engine,
                                            errors=errors)
    if engine_type == CsEngine.AWS:
        from . import aws_pomes
        result = aws_pomes.item_get_info(engine_id=engine_id,
                                         identifier=identifier,
                                         attributes=attributes,
                                         prefix=prefix,
                                         bucket=bucket,
                                         client=client,
                                         errors=errors)
    elif engine_type == CsEngine.MINIO:
        from . import minio_pomes
        result = minio_pomes.item_get_info(engine_id=engine_id,
                                           identifier=identifier,
                                           attributes=attributes,
                                           prefix=prefix,
                                           bucket=bucket,
                                           client=client,
                                           errors=errors)
    elif engine_type == CsEngine.GCS:
        from . import gcs_pomes
        result = gcs_pomes.item_get_info(engine_id=engine_id,
                                         identifier=identifier,
                                         attributes=attributes,
                                         prefix=prefix,
                                         bucket=bucket,
                                         client=client,
                                         errors=errors)
    return result


def cs_item_get_tags(identifier: str,
                     prefix: str | Path = None,
                     bucket: str = None,
                     engine: CsEngine | str = None,
                     client: Any = None,
                     errors: list[str] = None) -> dict[str, Any] | None:
    """
    Retrieve the existing metadata tags for an item in the *CS* store.

    If item has no associated metadata tags, an empty *dict* is returned. The information returned depends
    on the *engine* in question, and can be viewed at the native invocation's *docstring*.

    :param identifier: the item identifier
    :param prefix: optional path prefixing the item
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the CS engine to use (uses the default engine, if not provided)
    :param client: optional CS client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: the metadata tags associated with the item, or *None* if error or item not found
    """
    # initialize the return variable
    result: dict[str, Any] | None = None

    # assert the CS engine
    engine_id, engine_type = _assert_engine(engine=engine,
                                            errors=errors)
    if engine_type == CsEngine.AWS:
        from . import aws_pomes
        result = aws_pomes.item_get_tags(engine_id=engine_id,
                                         identifier=identifier,
                                         prefix=prefix,
                                         bucket=bucket,
                                         client=client,
                                         errors=errors)
    elif engine_type == CsEngine.MINIO:
        from . import minio_pomes
        result = minio_pomes.item_get_tags(engine_id=engine_id,
                                           identifier=identifier,
                                           prefix=prefix,
                                           bucket=bucket,
                                           client=client,
                                           errors=errors)
    elif engine_type == CsEngine.GCS:
        from . import gcs_pomes
        result = gcs_pomes.item_get_tags(engine_id=engine_id,
                                         identifier=identifier,
                                         prefix=prefix,
                                         bucket=bucket,
                                         client=client,
                                         errors=errors)
    return result


def cs_item_remove(identifier: str,
                   prefix: str | Path = None,
                   version: str = None,
                   bucket: str = None,
                   engine: CsEngine | str = None,
                   client: Any = None,
                   errors: list[str] = None) -> int | None:
    """
    Remove an item from the *CS* store.

    If *version* is not specified, then only the item's current (latest) version is removed.

    :param identifier: the item identifier
    :param prefix: optional path prefixing the items to be removed
    :param version: optional version of the item to be removed (defaults to the its current version)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the *CS* engine to use (uses the default engine, if not provided)
    :param client: optional *CS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if the item was successfully removed, *False* otherwise, *None* if error
    """
    # initialize the return variable
    result: bool | None = None

    # assert the CS engine
    engine_id, engine_type = _assert_engine(engine=engine,
                                            errors=errors)
    if engine_type == CsEngine.AWS:
        from . import aws_pomes
        result = aws_pomes.item_remove(engine_id=engine_id,
                                       identifier=identifier,
                                       prefix=prefix,
                                       version=version,
                                       bucket=bucket,
                                       client=client,
                                       errors=errors)
    elif engine_type == CsEngine.MINIO:
        from . import minio_pomes
        result = minio_pomes.item_remove(engine_id=engine_id,
                                         identifier=identifier,
                                         prefix=prefix,
                                         version=version,
                                         bucket=bucket,
                                         client=client,
                                         errors=errors)
    elif engine_type == CsEngine.GCS:
        from . import gcs_pomes
        result = gcs_pomes.item_remove(engine_id=engine_id,
                                       identifier=identifier,
                                       prefix=prefix,
                                       version=version,
                                       bucket=bucket,
                                       client=client,
                                       errors=errors)
    return result


def cs_items_count(prefix: str | Path | None,
                   bucket: str = None,
                   engine: CsEngine | str = None,
                   client: Any = None,
                   errors: list[str] = None) -> int | None:
    """
    Retrieve the number of items prefixed with *prefix*, in the *CS* store.

    If *prefix* is not specified, then the bucket's root is used. A count operation on the contents
    of a *prefix* may be time-consuming, in *AWS* storages, and extremely so, in *MinIO* storages.

    :param prefix: path prefixing the items to be counted
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the *CS* engine to use (uses the default engine, if not provided)
    :param client: optional *CS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: the number of items in *prefix*, 0 if *prefix* not found, or *None* if error
    """
    # initialize the return variable
    result: int | None = None

    # assert the CS engine
    engine_id, engine_type = _assert_engine(engine=engine,
                                            errors=errors)
    if engine_type == CsEngine.AWS:
        from . import aws_pomes
        result = aws_pomes.items_count(engine_id=engine_id,
                                       bucket=bucket,
                                       prefix=prefix,
                                       client=client,
                                       errors=errors)
    elif engine_type == CsEngine.MINIO:
        from . import minio_pomes
        result = minio_pomes.items_count(engine_id=engine_id,
                                         bucket=bucket,
                                         prefix=prefix,
                                         client=client,
                                         errors=errors)
    elif engine_type == CsEngine.GCS:
        from . import gcs_pomes
        result = gcs_pomes.items_count(engine_id=engine_id,
                                       bucket=bucket,
                                       prefix=prefix,
                                       client=client,
                                       errors=errors)
    return result


def cs_items_get_info(attrs: list[str],
                      prefix: str | Path,
                      max_count: int = None,
                      start_after: str = None,
                      bucket: str = None,
                      engine: CsEngine | str = None,
                      client: Any = None,
                      errors: list[str] = None) -> list[dict[str, Any]] | None:
    """
    Recursively retrieve and return information on a list of items prefixed with *prefix*, in the *CS* store.

    If *prefix* is not specified, then the bucket's root is used. If *max_count* is a positive integer,
    the number of items returned may be less, but not more, than its value, otherwise it is ignored, and
    all existing items in *prefix* are returned. Optionally, *start_after* identifies the item after which
    the listing must start, thus allowing for paginating the items retrieval operation.

    The information returned depends on the *engine* in question, and can be viewed at the native
    invocation's *docstring*. The parameter *attrs* must contain one or more of the attributes relevant
    to the *engine*. For the *GCS* engine, attributes named *metadata.<custom_metadata_i* are the
    custom metadata associated with the data.

    :param attrs: the items' attributes to be returned
    :param prefix: path prefixing the items to be listed
    :param max_count: the maximum number of items to return (defaults to all items)
    :param start_after: optionally identifies the item after which to start the listing (defaults to first item)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the *CS* engine to use (uses the default engine, if not provided)
    :param client: optional *CS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: information on a list of items in *prefix*, or *None* if error or *prefix* not found
    """
    # initialize the return variable
    result: list[dict[str, Any]] | None = None

    # assert the CS engine
    engine_id, engine_type = _assert_engine(engine=engine,
                                            errors=errors)
    if engine_type == CsEngine.AWS:
        from . import aws_pomes
        result = aws_pomes.items_get_info(engine_id=engine_id,
                                          attrs=attrs,
                                          prefix=prefix,
                                          max_count=max_count,
                                          start_after=start_after,
                                          bucket=bucket,
                                          client=client,
                                          errors=errors)
    elif engine_type == CsEngine.MINIO:
        from . import minio_pomes
        result = minio_pomes.items_get_info(engine_id=engine_id,
                                            attrs=attrs,
                                            prefix=prefix,
                                            max_count=max_count,
                                            start_after=start_after,
                                            bucket=bucket,
                                            client=client,
                                            errors=errors)
    if engine_type == CsEngine.GCS:
        from . import gcs_pomes
        result = gcs_pomes.items_get_info(engine_id=engine_id,
                                          attrs=attrs,
                                          prefix=prefix,
                                          max_count=max_count,
                                          start_after=start_after,
                                          bucket=bucket,
                                          client=client,
                                          errors=errors)
    return result


def cs_items_get_names(prefix: str | Path,
                       max_count: int = None,
                       start_after: str = None,
                       bucket: str = None,
                       engine: CsEngine | str = None,
                       client: Any = None,
                       errors: list[str] = None) -> list[str] | None:
    """
    Recursively retrieve and return the names of items prefixed with *prefix*, in the *CS* store.

    If *prefix* is not specified, then the bucket's root is used. If *max_count* is a positive integer,
    the number of items returned may be less, but not more, than its value, otherwise it is ignored, and
    all existing items in *prefix* are returned. Optionally, *start_after* identifies the item after which
    the listing must start, thus allowing for paginating the items retrieval operation.

    :param prefix: path prefixing the items to be listed
    :param max_count: the maximum number of items to return (defaults to all items)
    :param start_after: optionally identifies the item after which to start the listing (defaults to first item)
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the *CS* engine to use (uses the default engine, if not provided)
    :param client: optional *CS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: names of items in *prefix*, or *None* if error or *prefix* not found
    """
    # initialize the return variable
    result: list[dict[str, Any]] | None = None

    # assert the CS engine
    engine_id, engine_type = _assert_engine(engine=engine,
                                            errors=errors)
    if engine_type == CsEngine.AWS:
        from . import aws_pomes
        result = aws_pomes.items_get_names(engine_id=engine_id,
                                           prefix=prefix,
                                           max_count=max_count,
                                           start_after=start_after,
                                           bucket=bucket,
                                           client=client,
                                           errors=errors)
    elif engine_type == CsEngine.MINIO:
        from . import minio_pomes
        result = minio_pomes.items_get_names(engine_id=engine_id,
                                             prefix=prefix,
                                             max_count=max_count,
                                             start_after=start_after,
                                             bucket=bucket,
                                             client=client,
                                             errors=errors)
    if engine_type == CsEngine.GCS:
        from . import gcs_pomes
        result = gcs_pomes.items_get_names(engine_id=engine_id,
                                           prefix=prefix,
                                           max_count=max_count,
                                           start_after=start_after,
                                           bucket=bucket,
                                           client=client,
                                           errors=errors)
    return result


def cs_items_remove(identifiers: list[str | tuple[str, str]] = None,
                    prefix: str | Path = None,
                    bucket: str = None,
                    engine: CsEngine | str = None,
                    client: Any = None,
                    errors: list[str] = None) -> int:
    """
    Remove the items listed in *identifiers* from the *CS* store.

    The items to be removed are listed in *identifiers*, either with a simple *name*, or with
    a *name,version* pair. If the version is not provided for a given item, then only its
    current (latest) version is removed. Items in *identifiers* are ignored, if not found.
    If *identifiers* is not provided, then all items prefixed with *prefix* are removed.

    The removal operation will attempt to continue if errors occur. Thus, make sure to check *errors*,
    besides inspecting the returned value.

    :param identifiers: identifiers for the items to be removed (defaults to all items in *prefix*)
    :param prefix: optional path prefixing the items to be removed
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the *CS* engine to use (uses the default engine, if not provided)
    :param client: optional *CS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: The number of items successfully removed
    """
    # initialize the return variable
    result: int = 0

    # assert the CS engine
    engine_id, engine_type = _assert_engine(engine=engine,
                                            errors=errors)
    if engine_type == CsEngine.AWS:
        from . import aws_pomes
        result = aws_pomes.items_remove(engine_id=engine_id,
                                        identifiers=identifiers,
                                        bucket=bucket,
                                        prefix=prefix,
                                        client=client,
                                        errors=errors)
    elif engine_type == CsEngine.MINIO:
        from . import minio_pomes
        result = minio_pomes.items_remove(engine_id=engine_id,
                                          identifiers=identifiers,
                                          bucket=bucket,
                                          prefix=prefix,
                                          client=client,
                                          errors=errors)
    elif engine_type == CsEngine.GCS:
        from . import gcs_pomes
        result = gcs_pomes.items_remove(engine_id=engine_id,
                                        identifiers=identifiers,
                                        bucket=bucket,
                                        prefix=prefix,
                                        client=client,
                                        errors=errors)
    return result


def cs_generate_presigned_url(identifier: str,
                              prefix: str | Path = None,
                              expires_in: int = None,
                              bucket: str = None,
                              engine: CsEngine | str = None,
                              client: Any = None,
                              errors: list[str] = None) -> str:
    """
    Generate a presigned URL that grants time-limited, no credentials required, access to a private *CS* object.

    :param identifier: the data identifier
    :param expires_in: time until expiration (in seconds, defaults to 3600)
    :param prefix: optional path prefixing the item to be retrieved
    :param bucket: the bucket to use (uses the default bucket, if not provided)
    :param engine: the *CS* engine to use (uses the default engine, if not provided)
    :param client: optional *CS* client (obtains a new one, if not provided)
    :param errors: incidental error messages (might be a non-empty list)
    :return: the URL generated, or *None* if error or data not found
    """
    # initialize the return variable
    result: str | None = None

    # assert the CS engine
    engine_id, engine_type = _assert_engine(engine=engine,
                                            errors=errors)
    if engine_type == CsEngine.AWS:
        from . import aws_pomes
        result = aws_pomes.generate_presigned_url(engine_id=engine_id,
                                                  identifier=identifier,
                                                  prefix=prefix,
                                                  expires_in=expires_in,
                                                  bucket=bucket,
                                                  client=client,
                                                  errors=errors)
    elif engine_type == CsEngine.MINIO:
        from . import minio_pomes
        result = minio_pomes.generate_presigned_url(engine_id=engine_id,
                                                    identifier=identifier,
                                                    prefix=prefix,
                                                    expires_in=expires_in,
                                                    bucket=bucket,
                                                    client=client,
                                                    errors=errors)
    if engine_type == CsEngine.GCS:
        from . import gcs_pomes
        result = gcs_pomes.generate_presigned_url(engine_id=engine_id,
                                                  identifier=identifier,
                                                  prefix=prefix,
                                                  expires_in=expires_in,
                                                  bucket=bucket,
                                                  client=client,
                                                  errors=errors)
    return result


def __get_version(engine: CsEngine | str = None) -> str | None:
    """
    Obtain and return the current version of *engine*.

    :param engine: the reference *CS* engine (the default engine, if not provided)
    :return: the engine's current version, or *None* if not found
    """
    # initialize the return variable
    result: str | None = None

    # assert the CS engine
    _engine_id, engine_type = _assert_engine(engine=engine)
    match engine_type:
        case CsEngine.MINIO:
            import minio
            result = minio.__version__
        case CsEngine.AWS:
            import boto3
            result = boto3.__version__
        case CsEngine.GCS:
            import google.cloud.storage
            result = google.cloud.storage.__version__

    return result
