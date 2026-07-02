"use client";

export default function HealthPage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <p className="text-sm font-medium uppercase tracking-widest text-neutral-500">System health</p>
      <p className="mt-2 text-sm text-neutral-500">
        Grader latency, throughput, and pipeline liveness — embedded from Grafana
        (anonymous viewer access). Open{" "}
        <a className="underline underline-offset-4" href="http://localhost:3001/d/autograde-graders" target="_blank">
          the full dashboard
        </a>{" "}
        for exploration, or{" "}
        <a className="underline underline-offset-4" href="http://localhost:8233" target="_blank">
          Temporal UI
        </a>{" "}
        for workflow state.
      </p>
      <iframe
        src="http://localhost:3001/d/autograde-graders?kiosk&refresh=30s"
        className="mt-6 h-[70vh] w-full rounded-xl border border-neutral-200 dark:border-neutral-800"
      />
    </div>
  );
}
