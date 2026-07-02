"use client";

import { gql, useSubscription } from "@apollo/client";
import { useState } from "react";

const PROGRESS_SUB = gql`
  subscription Progress($assignmentId: String!) {
    progress(assignmentId: $assignmentId) {
      assignmentId submissions gradedSubmissions pendingReviews autoApproved
      questions { questionId graded pendingReview }
    }
  }
`;

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900">
      <p className="text-sm text-neutral-500">{label}</p>
      <p className="mt-1 text-3xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}

export default function Overview() {
  const [assignment, setAssignment] = useState("cs152-hw3");
  const { data, error } = useSubscription(PROGRESS_SUB, {
    variables: { assignmentId: assignment },
  });
  const p = data?.progress;

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium uppercase tracking-widest text-neutral-500">
            Assignment overview · live
          </p>
          <input
            className="mt-2 rounded-lg border border-neutral-300 bg-transparent px-3 py-1.5 text-xl font-semibold dark:border-neutral-700"
            value={assignment}
            onChange={(e) => setAssignment(e.target.value)}
          />
        </div>
        <UploadPanel />
      </div>

      {error && (
        <p className="mt-6 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          API unreachable on :8000 — {String(error.message)}
        </p>
      )}

      {p && (
        <>
          <section className="mt-8 grid gap-4 sm:grid-cols-4">
            <Stat label="Submissions" value={p.submissions} />
            <Stat label="Graded" value={p.gradedSubmissions} />
            <Stat label="Pending review" value={p.pendingReviews} />
            <Stat label="Auto-approved" value={p.autoApproved} />
          </section>
          <section className="mt-8 rounded-xl border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
            <table className="w-full text-sm">
              <thead className="text-left text-neutral-500">
                <tr className="border-b border-neutral-200 dark:border-neutral-800">
                  <th className="px-5 py-3">Question</th>
                  <th className="px-5 py-3">Final grades</th>
                  <th className="px-5 py-3">Pending review</th>
                </tr>
              </thead>
              <tbody>
                {p.questions.map((q: { questionId: string; graded: number; pendingReview: number }) => (
                  <tr key={q.questionId} className="border-b border-neutral-100 last:border-0 dark:border-neutral-800">
                    <td className="px-5 py-2.5 font-mono">{q.questionId}</td>
                    <td className="px-5 py-2.5 tabular-nums">{q.graded}</td>
                    <td className="px-5 py-2.5 tabular-nums">{q.pendingReview}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}

function UploadPanel() {
  const [status, setStatus] = useState<string | null>(null);

  async function submit(form: FormData) {
    setStatus("uploading…");
    try {
      const res = await fetch("http://localhost:8000/upload", { method: "POST", body: form });
      const body = await res.json();
      setStatus(res.ok ? `ingested ${body.files_registered} files` : JSON.stringify(body));
    } catch (e) {
      setStatus(String(e));
    }
  }

  return (
    <form
      action={submit}
      className="flex items-center gap-2 rounded-xl border border-dashed border-neutral-300 p-3 text-xs dark:border-neutral-700"
    >
      <label>zip <input name="submissions" type="file" required className="w-36" /></label>
      <label>rubric <input name="rubric" type="file" required className="w-36" /></label>
      <label>roster <input name="roster" type="file" required className="w-36" /></label>
      <button className="rounded-lg bg-neutral-900 px-3 py-1.5 font-medium text-white dark:bg-neutral-100 dark:text-neutral-900">
        Upload
      </button>
      {status && <span className="text-neutral-500">{status}</span>}
    </form>
  );
}
