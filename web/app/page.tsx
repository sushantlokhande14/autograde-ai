const views = [
  {
    title: "Assignment overview",
    body: "Live grading progress per assignment via GraphQL subscriptions.",
    phase: "Phase 5",
  },
  {
    title: "Rubric authoring",
    body: "Author rubric JSON with a preview-grade-on-sample button.",
    phase: "Phase 5",
  },
  {
    title: "Review queue",
    body: "Least-confident grades first, with approve / edit / regrade.",
    phase: "Phase 5",
  },
  {
    title: "Grade audit",
    body: "Three-click trail from a grade to prompt, retrieval, and sandbox run.",
    phase: "Phase 5",
  },
  {
    title: "System health",
    body: "Embedded Grafana: grader latency, cost, calibration.",
    phase: "Phase 5",
  },
];

export default function Home() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <header className="mb-12">
        <p className="text-sm font-medium uppercase tracking-widest text-neutral-500">
          Phase 0 · Foundation
        </p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">Autograde AI</h1>
        <p className="mt-3 max-w-2xl text-neutral-600 dark:text-neutral-400">
          A local-first, agent-orchestrated grading pipeline for CS coursework.
          The dashboard scaffold is live; the views below come online in Phase 5.
        </p>
      </header>

      <section className="grid gap-4 sm:grid-cols-2">
        {views.map((v) => (
          <article
            key={v.title}
            className="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm dark:border-neutral-800 dark:bg-neutral-900"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-medium">{v.title}</h2>
              <span className="rounded-full bg-neutral-100 px-2.5 py-0.5 text-xs font-medium text-neutral-500 dark:bg-neutral-800">
                {v.phase}
              </span>
            </div>
            <p className="mt-2 text-sm text-neutral-600 dark:text-neutral-400">{v.body}</p>
          </article>
        ))}
      </section>

      <footer className="mt-12 text-sm text-neutral-500">
        Health check:{" "}
        <a className="underline underline-offset-4" href="/api/healthz">
          /api/healthz
        </a>
      </footer>
    </main>
  );
}
