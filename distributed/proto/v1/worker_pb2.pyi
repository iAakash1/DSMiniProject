from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CapabilityRequest(_message.Message):
    __slots__ = ("request_id", "run_id", "ticker", "capability", "leader_epoch", "lamport_timestamp", "coordinator_id", "timeout_seconds")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    TICKER_FIELD_NUMBER: _ClassVar[int]
    CAPABILITY_FIELD_NUMBER: _ClassVar[int]
    LEADER_EPOCH_FIELD_NUMBER: _ClassVar[int]
    LAMPORT_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    COORDINATOR_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_SECONDS_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    run_id: str
    ticker: str
    capability: str
    leader_epoch: int
    lamport_timestamp: int
    coordinator_id: str
    timeout_seconds: float
    def __init__(self, request_id: _Optional[str] = ..., run_id: _Optional[str] = ..., ticker: _Optional[str] = ..., capability: _Optional[str] = ..., leader_epoch: _Optional[int] = ..., lamport_timestamp: _Optional[int] = ..., coordinator_id: _Optional[str] = ..., timeout_seconds: _Optional[float] = ...) -> None: ...

class EvidenceRecord(_message.Message):
    __slots__ = ("vendor", "capability", "status", "latency_ms", "observed_at", "data_json", "error")
    VENDOR_FIELD_NUMBER: _ClassVar[int]
    CAPABILITY_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    LATENCY_MS_FIELD_NUMBER: _ClassVar[int]
    OBSERVED_AT_FIELD_NUMBER: _ClassVar[int]
    DATA_JSON_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    vendor: str
    capability: str
    status: str
    latency_ms: float
    observed_at: str
    data_json: str
    error: str
    def __init__(self, vendor: _Optional[str] = ..., capability: _Optional[str] = ..., status: _Optional[str] = ..., latency_ms: _Optional[float] = ..., observed_at: _Optional[str] = ..., data_json: _Optional[str] = ..., error: _Optional[str] = ...) -> None: ...

class CapabilityResponse(_message.Message):
    __slots__ = ("request_id", "run_id", "worker_id", "worker_group", "capability", "status", "started_at", "completed_at", "latency_ms", "evidence", "error_json", "lamport_timestamp")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    WORKER_GROUP_FIELD_NUMBER: _ClassVar[int]
    CAPABILITY_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_AT_FIELD_NUMBER: _ClassVar[int]
    LATENCY_MS_FIELD_NUMBER: _ClassVar[int]
    EVIDENCE_FIELD_NUMBER: _ClassVar[int]
    ERROR_JSON_FIELD_NUMBER: _ClassVar[int]
    LAMPORT_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    run_id: str
    worker_id: str
    worker_group: str
    capability: str
    status: str
    started_at: str
    completed_at: str
    latency_ms: float
    evidence: _containers.RepeatedCompositeFieldContainer[EvidenceRecord]
    error_json: str
    lamport_timestamp: int
    def __init__(self, request_id: _Optional[str] = ..., run_id: _Optional[str] = ..., worker_id: _Optional[str] = ..., worker_group: _Optional[str] = ..., capability: _Optional[str] = ..., status: _Optional[str] = ..., started_at: _Optional[str] = ..., completed_at: _Optional[str] = ..., latency_ms: _Optional[float] = ..., evidence: _Optional[_Iterable[_Union[EvidenceRecord, _Mapping]]] = ..., error_json: _Optional[str] = ..., lamport_timestamp: _Optional[int] = ...) -> None: ...
