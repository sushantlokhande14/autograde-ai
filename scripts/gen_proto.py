"""Generate gRPC Python stubs from proto/*.proto into autograde_core.pb.

Generated files are gitignored; run this after a fresh checkout or whenever a
.proto changes:

    uv run python scripts/gen_proto.py

grpc_tools emits top-level `import xxx_pb2` statements in the *_pb2_grpc modules,
which do not resolve inside a package. We rewrite them to package-relative
imports so `autograde_core.pb` is importable as a normal package.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PROTO_DIR = REPO / "proto"
OUT_DIR = REPO / "libs" / "autograde_core" / "autograde_core" / "pb"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "__init__.py").write_text(
        '"""Generated gRPC stubs (contents gitignored). Run scripts/gen_proto.py."""\n'
    )

    protos = sorted(PROTO_DIR.glob("*.proto"))
    if not protos:
        print("no .proto files found in", PROTO_DIR)
        return 1

    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"-I{PROTO_DIR}",
        f"--python_out={OUT_DIR}",
        f"--grpc_python_out={OUT_DIR}",
        f"--pyi_out={OUT_DIR}",
        *[str(p) for p in protos],
    ]
    print("running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=REPO)
    if result.returncode != 0:
        return result.returncode

    for grpc_file in OUT_DIR.glob("*_pb2_grpc.py"):
        text = grpc_file.read_text()
        text = re.sub(
            r"^import (\w+_pb2)( as \w+)?$", r"from . import \1\2", text, flags=re.M
        )
        grpc_file.write_text(text)

    names = sorted(p.name for p in OUT_DIR.glob("*_pb2*.py"))
    print(f"generated into {OUT_DIR.relative_to(REPO)}: {', '.join(names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
