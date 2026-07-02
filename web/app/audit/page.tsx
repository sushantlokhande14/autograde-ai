"use client";

import { gql, useLazyQuery } from "@apollo/client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

const GRADES = gql`
  query Grades($submissionId: String!) {
    grades(submissionId: $submissionId) {
      gradeId grader questionId score maxScore confidence reasoning breakdownJson
    }
  }
`;
const AUDIT = gql`
  query Audit($gradeId: String!) {
    audit(gradeId: $gradeId) {
      grade { grader questionId score maxScore confidence reasoning breakdownJson }
      model cacheHit prompt response citationsJson sandboxStdout sandboxStderr
    }
  }
`;

type G = { gradeId: string; grader: string; questionId: string; score: number;
           maxScore: number; confidence: number; reasoning: string; breakdownJson: string };

function AuditInner() {
  const params = useSearchParams();
  const [submission, setSubmission] = useState(params.get("submission") ?? "");
  const [loadGrades, gradesQ] = useLazyQuery(GRADES);
  const [loadAudit, auditQ] = useLazyQuery(AUDIT);

  useEffect(() => {
    if (submission) loadGrades({ variables: { submissionId: submission } });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const grades: G[] = gradesQ.data?.grades ?? [];
  const audit = auditQ.data?.audit;

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <p className="text-sm font-medium uppercase tracking-widest text-neutral-500">Grade audit</p>
      <div className="mt-2 flex gap-2">
        <input
          placeholder="submission id"
          value={submission}
          onChange={(e) => setSubmission(e.target.value)}
          className="w-96 rounded-lg border border-neutral-300 px-3 py-1.5 font-mono text-sm dark:border-neutral-700 dark:bg-neutral-800"
        />
        <button
          onClick={() => loadGrades({ variables: { submissionId: submission } })}
          className="rounded-lg bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white dark:bg-neutral-100 dark:text-neutral-900"
        >
          Load grades
        </button>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="space-y-2">
          {grades.map((g) => (
            <button
              key={g.gradeId}
              onClick={() => loadAudit({ variables: { gradeId: g.gradeId } })}
              className="block w-full rounded-xl border border-neutral-200 bg-white p-3 text-left hover:border-neutral-400 dark:border-neutral-800 dark:bg-neutral-900"
            >
              <div className="flex items-center gap-3 text-sm">
                <span className="font-medium">{g.grader}</span>
                <span className="font-mono">{g.questionId}</span>
                <span className="ml-auto tabular-nums">{g.score}/{g.maxScore}</span>
                <span className="tabular-nums text-neutral-500">conf {g.confidence.toFixed(2)}</span>
              </div>
              <p className="mt-1 line-clamp-2 text-xs text-neutral-500">{g.reasoning}</p>
            </button>
          ))}
        </section>

        {audit && (
          <section className="space-y-4 text-sm">
            <div className="rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
              <p className="font-medium">{audit.grade.grader} · {audit.grade.questionId} ·{" "}
                {audit.grade.score}/{audit.grade.maxScore}
                {audit.model && <span className="ml-2 text-neutral-500">{audit.model}{audit.cacheHit ? " · cache hit" : ""}</span>}
              </p>
              <p className="mt-2 whitespace-pre-wrap text-neutral-600 dark:text-neutral-400">{audit.grade.reasoning}</p>
              <Blob title="Criterion breakdown" body={pretty(audit.grade.breakdownJson)} />
              <Blob title="Retrieval citations" body={pretty(audit.citationsJson)} />
              {audit.prompt && <Blob title="LLM request payload" body={audit.prompt} />}
              {audit.response && <Blob title="LLM response payload" body={audit.response} />}
              {audit.sandboxStdout != null && <Blob title="Sandbox stdout" body={audit.sandboxStdout || "(empty)"} />}
              {audit.sandboxStderr != null && <Blob title="Sandbox stderr" body={audit.sandboxStderr || "(empty)"} />}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

export default function AuditPage() {
  return (
    <Suspense>
      <AuditInner />
    </Suspense>
  );
}

function pretty(s: string): string {
  try { return JSON.stringify(JSON.parse(s), null, 2); } catch { return s; }
}

function Blob({ title, body }: { title: string; body: string }) {
  return (
    <details className="mt-3">
      <summary className="cursor-pointer text-xs font-medium uppercase tracking-wide text-neutral-500">{title}</summary>
      <pre className="mt-2 max-h-72 overflow-auto rounded-lg bg-neutral-50 p-3 text-xs dark:bg-neutral-950">{body}</pre>
    </details>
  );
}
