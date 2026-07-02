"use client";

import { gql, useMutation } from "@apollo/client";
import { useState } from "react";

const VALIDATE = gql`
  mutation Validate($rubricJson: String!) {
    validateRubric(rubricJson: $rubricJson) { valid errors }
  }
`;
const PREVIEW = gql`
  mutation Preview($rubricJson: String!, $questionId: String!, $sampleAnswer: String!) {
    previewGrade(rubricJson: $rubricJson, questionId: $questionId, sampleAnswer: $sampleAnswer) {
      score maxScore confidence reasoning
    }
  }
`;

const STARTER = `{
  "assignment_id": "cs101-hw1",
  "title": "New assignment",
  "grading_backend": "local",
  "questions": [
    {
      "question_id": "q1",
      "type": "theory",
      "weight": 10,
      "prompt": "Explain ...",
      "rubric_criteria": [
        {"criterion": "definition", "points": 5},
        {"criterion": "example", "points": 5}
      ]
    }
  ]
}`;

export default function RubricPage() {
  const [rubric, setRubric] = useState(STARTER);
  const [questionId, setQuestionId] = useState("q1");
  const [sample, setSample] = useState("");
  const [validate, v] = useMutation(VALIDATE);
  const [preview, p] = useMutation(PREVIEW);
  const check = v.data?.validateRubric;
  const grade = p.data?.previewGrade;

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <p className="text-sm font-medium uppercase tracking-widest text-neutral-500">Rubric authoring</p>
      <div className="mt-4 grid gap-6 lg:grid-cols-2">
        <section>
          <textarea
            value={rubric}
            onChange={(e) => setRubric(e.target.value)}
            spellCheck={false}
            className="h-[28rem] w-full rounded-xl border border-neutral-300 bg-white p-4 font-mono text-xs dark:border-neutral-700 dark:bg-neutral-900"
          />
          <button
            onClick={() => validate({ variables: { rubricJson: rubric } })}
            className="mt-3 rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white dark:bg-neutral-100 dark:text-neutral-900"
          >
            Validate
          </button>
          {check && (
            <div className={`mt-3 rounded-lg p-3 text-sm ${check.valid ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" : "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300"}`}>
              {check.valid ? "Rubric is valid." : (
                <ul className="list-disc pl-4">{check.errors.map((e: string) => <li key={e}>{e}</li>)}</ul>
              )}
            </div>
          )}
        </section>

        <section>
          <p className="text-sm font-medium">Preview grade on a sample answer</p>
          <div className="mt-2 flex gap-2">
            <input
              value={questionId}
              onChange={(e) => setQuestionId(e.target.value)}
              className="w-24 rounded-lg border border-neutral-300 px-2 py-1.5 font-mono text-sm dark:border-neutral-700 dark:bg-neutral-800"
            />
            <button
              onClick={() => preview({ variables: { rubricJson: rubric, questionId, sampleAnswer: sample } })}
              disabled={p.loading || !sample}
              className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm disabled:opacity-40 dark:border-neutral-700"
            >
              {p.loading ? "Grading…" : "Preview grade"}
            </button>
          </div>
          <textarea
            placeholder="Paste a sample student answer…"
            value={sample}
            onChange={(e) => setSample(e.target.value)}
            className="mt-3 h-56 w-full rounded-xl border border-neutral-300 bg-white p-4 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          />
          {grade && (
            <div className="mt-3 rounded-xl border border-neutral-200 bg-white p-4 text-sm dark:border-neutral-800 dark:bg-neutral-900">
              <p className="font-medium tabular-nums">
                {grade.score}/{grade.maxScore} · confidence {grade.confidence.toFixed(2)}
              </p>
              <p className="mt-2 text-neutral-600 dark:text-neutral-400">{grade.reasoning}</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
