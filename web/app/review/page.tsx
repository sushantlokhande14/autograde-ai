"use client";

import { gql, useMutation, useQuery } from "@apollo/client";
import Link from "next/link";
import { useState } from "react";

const PENDING = gql`
  query Pending {
    pendingReviews(limit: 100) {
      reviewId submissionId studentHash questionId status
      originalScore finalScore confidence flags
    }
  }
`;
const APPROVE = gql`
  mutation Approve($reviewId: String!, $finalScore: Float, $notes: String) {
    approveReview(reviewId: $reviewId, finalScore: $finalScore, notes: $notes) { reviewId status }
  }
`;
const REGRADE = gql`
  mutation Regrade($submissionId: String!) { regradeSubmission(submissionId: $submissionId) }
`;

type Row = {
  reviewId: string; submissionId: string; studentHash: string; questionId: string;
  status: string; originalScore: number; finalScore: number | null;
  confidence: number | null; flags: string;
};

export default function ReviewQueue() {
  const { data, refetch, error } = useQuery(PENDING, { fetchPolicy: "network-only" });
  const [approve] = useMutation(APPROVE);
  const [regrade] = useMutation(REGRADE);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const rows: Row[] = data?.pendingReviews ?? [];

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <p className="text-sm font-medium uppercase tracking-widest text-neutral-500">Review queue</p>
      <h1 className="mt-1 text-2xl font-semibold">
        {rows.length} pending · least confident first
      </h1>
      {error && <p className="mt-4 text-sm text-red-600">{String(error.message)}</p>}

      <ul className="mt-6 space-y-3">
        {rows.map((r) => (
          <li key={r.reviewId} className="rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-full bg-neutral-100 px-2.5 py-0.5 font-mono text-xs dark:bg-neutral-800">
                {r.studentHash}…
              </span>
              <span className="font-mono text-sm">{r.questionId}</span>
              <span className="text-sm tabular-nums">score {r.originalScore}</span>
              <span className={`text-sm tabular-nums ${(r.confidence ?? 0) < 0.4 ? "text-red-600" : "text-amber-600"}`}>
                conf {(r.confidence ?? 0).toFixed(2)}
              </span>
              <Link className="ml-auto text-sm underline underline-offset-4" href={`/audit?submission=${r.submissionId}`}>
                audit
              </Link>
            </div>
            {r.flags && r.flags !== "no inconsistencies detected" && (
              <p className="mt-2 text-xs text-amber-700 dark:text-amber-400">⚑ {r.flags}</p>
            )}
            <div className="mt-3 flex items-center gap-2">
              <button
                onClick={() => approve({ variables: { reviewId: r.reviewId } }).then(() => refetch())}
                className="rounded-lg bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white dark:bg-neutral-100 dark:text-neutral-900"
              >
                Approve
              </button>
              <input
                placeholder="new score"
                value={edits[r.reviewId] ?? ""}
                onChange={(e) => setEdits((s) => ({ ...s, [r.reviewId]: e.target.value }))}
                className="w-24 rounded-lg border border-neutral-300 px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-800"
              />
              <button
                onClick={() =>
                  approve({
                    variables: { reviewId: r.reviewId, finalScore: parseFloat(edits[r.reviewId]) },
                  }).then(() => refetch())
                }
                disabled={!edits[r.reviewId]}
                className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm disabled:opacity-40 dark:border-neutral-700"
              >
                Save edit
              </button>
              <button
                onClick={() => regrade({ variables: { submissionId: r.submissionId } })}
                className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm dark:border-neutral-700"
              >
                Regrade
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
