-- Autograde AI — Postgres bootstrap.
-- Runs once on first container init against the primary database.
-- Two schemas: `grading` (hashed IDs only, pipeline reads/writes) and
-- `identity` (real names, gated behind row-level security). See PROJECT_PLAN §7.

-- ---------------------------------------------------------------------------
-- Roles
-- ---------------------------------------------------------------------------
-- The export service is the only principal allowed to read identity data.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'export_service') THEN
        CREATE ROLE export_service LOGIN PASSWORD 'change_me_locally';
    END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- grading schema — never contains real names
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS grading;

CREATE TABLE IF NOT EXISTS grading.assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_code TEXT NOT NULL,
    title TEXT NOT NULL,
    rubric JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    grading_config JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS grading.submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID REFERENCES grading.assignments(id),
    student_hash TEXT NOT NULL,              -- HMAC(assignment_id, canvas_id, secret)
    ingested_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (assignment_id, student_hash)
);

CREATE TABLE IF NOT EXISTS grading.artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID REFERENCES grading.submissions(id),
    source_file TEXT NOT NULL,
    artifact_type TEXT NOT NULL,             -- "theory", "code", "figure", "derivation"
    question_id TEXT,
    question_mapping_confidence FLOAT,
    content_ref TEXT NOT NULL,               -- MinIO key for normalized content
    metadata JSONB,
    parsed_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS grading.grades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID REFERENCES grading.submissions(id),
    question_id TEXT NOT NULL,
    grader TEXT NOT NULL,
    score FLOAT NOT NULL,
    max_score FLOAT NOT NULL,
    confidence FLOAT NOT NULL,
    reasoning TEXT NOT NULL,
    rubric_breakdown JSONB NOT NULL,
    retrieval_citations JSONB,
    sandbox_run_id UUID,
    llm_call_id UUID,
    graded_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS grading.reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID REFERENCES grading.submissions(id),
    question_id TEXT NOT NULL,
    status TEXT NOT NULL,                     -- "pending","approved","edited","regraded"
    original_score FLOAT NOT NULL,
    final_score FLOAT,
    reviewer_notes TEXT,
    reviewed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS grading.llm_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grader TEXT NOT NULL,
    model TEXT NOT NULL,
    backend TEXT NOT NULL,                    -- "local","anthropic","openai"
    input_tokens INT NOT NULL,
    output_tokens INT NOT NULL,
    cache_hit BOOLEAN NOT NULL,
    latency_ms INT NOT NULL,
    cost_usd DECIMAL(10, 6) NOT NULL,
    request_payload_ref TEXT,
    response_payload_ref TEXT,
    called_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS grading.sandbox_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID REFERENCES grading.submissions(id),
    test_case_id TEXT NOT NULL,
    exit_code INT,
    stdout_ref TEXT,
    stderr_ref TEXT,
    duration_ms INT,
    timed_out BOOLEAN NOT NULL DEFAULT false,
    ran_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- identity schema — real names, RLS-gated
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS identity;

CREATE TABLE IF NOT EXISTS identity.student_lookup (
    student_hash TEXT PRIMARY KEY,
    assignment_id UUID NOT NULL,
    display_name TEXT NOT NULL,
    canvas_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE identity.student_lookup ENABLE ROW LEVEL SECURITY;
ALTER TABLE identity.student_lookup FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS export_only_read ON identity.student_lookup;
CREATE POLICY export_only_read ON identity.student_lookup
    FOR SELECT USING (current_user = 'export_service');

-- Only the export service may read identity; the pipeline role never sees names.
GRANT USAGE ON SCHEMA identity TO export_service;
GRANT SELECT ON identity.student_lookup TO export_service;
