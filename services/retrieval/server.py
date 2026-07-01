"""Retrieval gRPC server.

Wraps ``autograde_rag.retrieve`` for out-of-process callers; graders running
in-process import the library directly. Run:

    uv run python -m services.retrieval.server --port 50051
"""

from __future__ import annotations

import argparse
from concurrent import futures

import grpc
import structlog

from autograde_core.pb import retrieval_pb2, retrieval_pb2_grpc
from autograde_rag.retrieve import retrieve

log = structlog.get_logger()


class RetrievalServicer(retrieval_pb2_grpc.RetrievalServiceServicer):
    def Retrieve(self, request, context):  # noqa: N802 (grpc naming)
        try:
            result = retrieve(
                request.assignment_id,
                request.question_id,
                request.artifact_type,
                top_k=request.top_k or 3,
                query_hint=request.query_hint,
                include_reference=request.include_reference,
            )
        except LookupError as exc:
            context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
            return None
        return retrieval_pb2.RetrieveResponse(
            chunks=[
                retrieval_pb2.Chunk(
                    chunk_id=c.chunk_id,
                    source=c.source,
                    text=c.text,
                    score=c.score,
                    reference_answer=c.reference_answer,
                )
                for c in result.chunks
            ],
            cache_hit=result.cache_hit,
            latency_ms=result.latency_ms,
        )


def serve(port: int = 50051) -> grpc.Server:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    retrieval_pb2_grpc.add_RetrievalServiceServicer_to_server(RetrievalServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    log.info("retrieval_grpc_listening", port=port)
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=50051)
    args = parser.parse_args()
    serve(args.port).wait_for_termination()
