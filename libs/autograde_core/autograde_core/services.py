"""Registry of application services and their dev /healthz ports.

Single source of truth for the port map documented in
docs/phases/phase-0-foundation.md. Scripts (healthcheck, dev runner) iterate
this instead of hard-coding ports.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceSpec:
    name: str          # logical service name, e.g. "grader:theory"
    module: str        # import path to the ASGI app, e.g. "services.graders.theory.main:app"
    port: int


SERVICES: tuple[ServiceSpec, ...] = (
    ServiceSpec("api", "services.api.main:app", 8000),
    ServiceSpec("router", "services.router.main:app", 8010),
    ServiceSpec("parser:pdf", "services.parsers.pdf.main:app", 8021),
    ServiceSpec("parser:notebook", "services.parsers.notebook.main:app", 8022),
    ServiceSpec("parser:code", "services.parsers.code.main:app", 8023),
    ServiceSpec("parser:image", "services.parsers.image.main:app", 8024),
    ServiceSpec("parser:fallback", "services.parsers.fallback.main:app", 8025),
    ServiceSpec("question_mapper", "services.question_mapper.main:app", 8030),
    ServiceSpec("grader:theory", "services.graders.theory.main:app", 8041),
    ServiceSpec("grader:code_execution", "services.graders.code_execution.main:app", 8042),
    ServiceSpec("grader:code_style", "services.graders.code_style.main:app", 8043),
    ServiceSpec("grader:derivation", "services.graders.derivation.main:app", 8044),
    ServiceSpec("grader:figure", "services.graders.figure.main:app", 8045),
    ServiceSpec("grader:plagiarism", "services.graders.plagiarism.main:app", 8046),
    ServiceSpec("feedback_synth", "services.graders.feedback_synth.main:app", 8047),
    ServiceSpec("cross_check", "services.graders.cross_check.main:app", 8048),
    ServiceSpec("retrieval", "services.retrieval.main:app", 8050),
    ServiceSpec("orchestrator", "services.orchestrator.main:app", 8060),
    ServiceSpec("export", "services.export.main:app", 8070),
)

SERVICE_PORTS: dict[str, int] = {s.name: s.port for s in SERVICES}


def iter_services() -> tuple[ServiceSpec, ...]:
    return SERVICES
