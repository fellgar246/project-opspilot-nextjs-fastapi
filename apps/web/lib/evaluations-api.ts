import { fetchWithAuth } from "@/lib/api-client";

export type EvaluatorResult = {
  name: string;
  passed: boolean;
  score: number | null;
  details: string;
  deterministic: boolean;
};

export type EvaluationCaseResult = {
  case_id: string;
  status: string;
  trace_reference: string | null;
  duration_seconds: number;
  error: string | null;
  evaluator_results: EvaluatorResult[];
};

export type EvaluationRun = {
  id: string;
  status: string;
  model_provider: string;
  prompt_version: string;
  git_sha: string;
  tags_filter: string[];
  metrics: Record<string, number>;
  gate_passed: boolean;
  gate_failures: string[];
  report_json_path: string | null;
  report_html_path: string | null;
  started_at: string;
  completed_at: string | null;
  case_results: EvaluationCaseResult[];
};

export type EvaluationCase = {
  id: string;
  scenario_id: string;
  tags: string[];
  expected_root_cause: string | null;
  seed: number;
};

export async function fetchEvaluationRuns(apiBaseUrl: string): Promise<EvaluationRun[]> {
  const response = await fetchWithAuth<{ items: EvaluationRun[] }>(
    apiBaseUrl,
    "/api/v1/evaluations/runs",
  );
  return response.items;
}

export async function fetchEvaluationCases(apiBaseUrl: string): Promise<EvaluationCase[]> {
  return fetchWithAuth<EvaluationCase[]>(apiBaseUrl, "/api/v1/evaluations/cases");
}

export async function runEvaluation(
  apiBaseUrl: string,
  options: { smoke?: boolean; tags?: string[] } = {},
): Promise<EvaluationRun> {
  return fetchWithAuth<EvaluationRun>(apiBaseUrl, "/api/v1/evaluations/run", {
    method: "POST",
    body: JSON.stringify({
      smoke: options.smoke ?? false,
      tags: options.tags ?? [],
      concurrency: 4,
    }),
  });
}

export async function compareEvaluationRuns(
  apiBaseUrl: string,
  baselineRunId: string,
  candidateRunId: string,
): Promise<Record<string, unknown>> {
  return fetchWithAuth(apiBaseUrl, "/api/v1/evaluations/compare", {
    method: "POST",
    body: JSON.stringify({
      baseline_run_id: baselineRunId,
      candidate_run_id: candidateRunId,
    }),
  });
}
