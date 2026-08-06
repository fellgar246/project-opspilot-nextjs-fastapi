"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useAuth } from "@/features/auth/AuthProvider";
import { getDefaultApiBaseUrl } from "@/lib/auth-api";
import {
  compareEvaluationRuns,
  fetchEvaluationCases,
  fetchEvaluationRuns,
  runEvaluation,
  type EvaluationRun,
} from "@/lib/evaluations-api";

function MetricTable({ metrics }: { metrics: Record<string, number> }) {
  const entries = Object.entries(metrics).filter(([, v]) => typeof v === "number");
  return (
    <table>
      <thead>
        <tr>
          <th>Metric</th>
          <th>Value</th>
        </tr>
      </thead>
      <tbody>
        {entries.map(([key, value]) => (
          <tr key={key}>
            <td>{key}</td>
            <td>{typeof value === "number" && value < 1 ? `${(value * 100).toFixed(1)}%` : value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function RunDetails({ run }: { run: EvaluationRun }) {
  const failedCases = run.case_results.filter((c) => c.status !== "passed");
  return (
    <section className="card">
      <h3>
        Run {run.id.slice(0, 8)} — {run.gate_passed ? "GATE PASSED" : "GATE FAILED"}
      </h3>
      <p>
        Agent: {run.model_provider} / {run.prompt_version} @ {run.git_sha}
      </p>
      {!run.gate_passed ? (
        <ul>
          {run.gate_failures.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      ) : null}
      <MetricTable metrics={run.metrics} />
      <h4>Cases ({run.case_results.length})</h4>
      <table>
        <thead>
          <tr>
            <th>Case</th>
            <th>Status</th>
            <th>Trace</th>
            <th>Failed evaluators</th>
          </tr>
        </thead>
        <tbody>
          {run.case_results.map((c) => (
            <tr key={c.case_id}>
              <td>{c.case_id}</td>
              <td>{c.status}</td>
              <td>{c.trace_reference ?? "—"}</td>
              <td>
                {c.evaluator_results
                  .filter((e) => !e.passed)
                  .map((e) => `${e.name}: ${e.details}`)
                  .join("; ") || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {failedCases.length > 0 ? (
        <details>
          <summary>Inspect failed cases ({failedCases.length})</summary>
          {failedCases.map((c) => (
            <div key={c.case_id}>
              <strong>{c.case_id}</strong>
              <ul>
                {c.evaluator_results
                  .filter((e) => !e.passed)
                  .map((e) => (
                    <li key={e.name}>
                      {e.name}: {e.details}
                    </li>
                  ))}
              </ul>
            </div>
          ))}
        </details>
      ) : null}
    </section>
  );
}

export function EvaluationLab() {
  const { can } = useAuth();
  const apiBaseUrl = getDefaultApiBaseUrl();
  const queryClient = useQueryClient();
  const [baselineId, setBaselineId] = useState("");
  const [candidateId, setCandidateId] = useState("");
  const [compareResult, setCompareResult] = useState<Record<string, unknown> | null>(null);

  const casesQuery = useQuery({
    queryKey: ["evaluation-cases"],
    queryFn: () => fetchEvaluationCases(apiBaseUrl),
    enabled: can("run_evaluations"),
  });

  const runsQuery = useQuery({
    queryKey: ["evaluation-runs"],
    queryFn: () => fetchEvaluationRuns(apiBaseUrl),
    enabled: can("run_evaluations"),
  });

  const runMutation = useMutation({
    mutationFn: (smoke: boolean) => runEvaluation(apiBaseUrl, { smoke }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["evaluation-runs"] }),
  });

  if (!can("run_evaluations")) {
    return <p>Evaluation Lab is restricted to admin users.</p>;
  }

  return (
    <div>
      <header className="dashboard-header">
        <div>
          <h1>Evaluation Lab</h1>
          <p>Dataset-driven agent quality measurement and regression comparison.</p>
        </div>
        <div>
          <button type="button" onClick={() => runMutation.mutate(true)} disabled={runMutation.isPending}>
            Run smoke (5 cases)
          </button>{" "}
          <button type="button" onClick={() => runMutation.mutate(false)} disabled={runMutation.isPending}>
            Run full eval
          </button>
        </div>
      </header>

      <section>
        <h2>Dataset</h2>
        <p>{casesQuery.data?.length ?? 0} cases versioned in Git</p>
      </section>

      <section>
        <h2>Recent runs</h2>
        {runsQuery.data?.map((run) => (
          <RunDetails key={run.id} run={run} />
        ))}
      </section>

      <section>
        <h2>Compare runs</h2>
        <label>
          Baseline{" "}
          <input value={baselineId} onChange={(e) => setBaselineId(e.target.value)} placeholder="run uuid" />
        </label>{" "}
        <label>
          Candidate{" "}
          <input value={candidateId} onChange={(e) => setCandidateId(e.target.value)} placeholder="run uuid" />
        </label>{" "}
        <button
          type="button"
          onClick={() =>
            void compareEvaluationRuns(apiBaseUrl, baselineId, candidateId).then(setCompareResult)
          }
        >
          Compare
        </button>
        {compareResult ? <pre>{JSON.stringify(compareResult, null, 2)}</pre> : null}
      </section>
    </div>
  );
}
