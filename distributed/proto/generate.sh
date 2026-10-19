#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python -m grpc_tools.protoc \
  --proto_path=proto/v1 \
  --python_out=proto/v1 \
  --grpc_python_out=proto/v1 \
  --pyi_out=proto/v1 \
  proto/v1/worker.proto
sed -i '' 's/^import worker_pb2 as worker__pb2$/from . import worker_pb2 as worker__pb2/' proto/v1/worker_pb2_grpc.py 2>/dev/null || \
sed -i 's/^import worker_pb2 as worker__pb2$/from . import worker_pb2 as worker__pb2/' proto/v1/worker_pb2_grpc.py
