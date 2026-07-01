"use client";

import { useCallback, useEffect, useState } from "react";

const API = "http://localhost:8000";

type Pending = {
  artifact_id: string;
  source_file: string;
  artifact_type: string;
  question_id: string | null;
  confidence: number | null;
};

export default function ReviewPage() {
  const [rows, setRows] = useState<Pending[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [choices, setChoices] = useState<Record<string, string>>({});

  const load = useCallback(() => {
    fetch(`${API}/mappings/pending`)
      .then((r) => r.json())
      .then(setRows)
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(load, [load]);

  async function confirm(id: string) {
    const question_id = choices[id];
    if (!question_id) return;
    await fetch(`${API}/mappings/${id}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question_id }),
    });
    load();
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <p className="text-sm font-medium uppercase tracking-widest text-neutral-500">
        Review queue · question mappings
      </p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">
        Low-confidence mappings
      </h1>
      <p className="mt-2 text-sm text-neutral-600 dark:text-neutral-400">
        Artifacts the QuestionMapper was unsure about (confidence &lt; 0.6). Confirm
        the question each one answers; grading proceeds only after confirmation.
      </p>

      {error && (
        <p className="mt-6 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          Could not reach the API on :8000 — is it running? ({error})
        </p>
      )}

      {rows && rows.length === 0 && (
        <p className="mt-8 rounded-xl border border-neutral-200 bg-white p-6 text-neutral-500 dark:border-neutral-800 dark:bg-neutral-900">
          Nothing pending — every artifact cleared the confidence gate.
        </p>
      )}

      <ul className="mt-6 space-y-3">
        {rows?.map((r) => (
          <li
            key={r.artifact_id}
            className="flex flex-wrap items-center gap-3 rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate font-mono text-sm">{r.source_file}</p>
              <p className="mt-1 text-xs text-neutral-500">
                type: {r.artifact_type} · guess: {r.question_id ?? "—"} · confidence:{" "}
                {r.confidence?.toFixed(2) ?? "—"}
              </p>
            </div>
            <input
              className="w-24 rounded-lg border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-800"
              placeholder="q1"
              value={choices[r.artifact_id] ?? ""}
              onChange={(e) =>
                setChoices((c) => ({ ...c, [r.artifact_id]: e.target.value }))
              }
            />
            <button
              onClick={() => confirm(r.artifact_id)}
              className="rounded-lg bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-neutral-700 dark:bg-neutral-100 dark:text-neutral-900"
            >
              Confirm
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}
