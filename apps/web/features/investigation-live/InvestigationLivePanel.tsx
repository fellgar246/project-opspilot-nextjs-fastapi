"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "@/features/auth/AuthProvider";
import { getDefaultApiBaseUrl } from "@/lib/auth-api";
import {
  fetchAgentRuns,
  fetchEventHistory,
  fetchProposedActions,
  investigationEventsUrl,
  pauseInvestigation,
  resumeInvestigation,
  startInvestigation,
  type AgentRun,
} from "@/lib/investigation-api";
import { InvestigationEventSource, type InvestigationEvent, type SseConnectionState } from "@/lib/sse-client";

type NodeEntry = {
  node: string;
  status: "running" | "completed" | "failed";
  durationMs?: number | null;
  startedAt?: string;
};

type LiveHypothesis = {
  id: string;
  statement: string;
  confidence?: number;
  status?: string;
};

type LiveEvidence = {
  id: string;
  title?: string;
  summary?: string;
  sourceType?: string;
  toolName?: string;
};

type InvestigationLivePanelProps = {
  incidentId: string;
};

function readableError(payload: Record<string, unknown>): string {
  const code = String(payload.code ?? payload.error_type ?? "investigation_error");
  const message = String(payload.message ?? "An investigation step failed");
  return `${code.replace(/_/g, " ")}: ${message}`;
}

function applyEventToState(
  event: InvestigationEvent,
  handlers: {
    setEvents: React.Dispatch<React.SetStateAction<InvestigationEvent[]>>;
    setNodes: React.Dispatch<React.SetStateAction<Map<string, NodeEntry>>>;
    setToolCalls: React.Dispatch<React.SetStateAction<InvestigationEvent[]>>;
    setHypotheses: React.Dispatch<React.SetStateAction<Map<string, LiveHypothesis>>>;
    setEvidence: React.Dispatch<React.SetStateAction<Map<string, LiveEvidence>>>;
    invalidateActions: () => void;
    invalidateRuns: () => void;
  },
): void {
  handlers.setEvents((prev) => {
    if (prev.some((item) => item.seq === event.seq)) return prev;
    return [...prev, event].sort((a, b) => a.seq - b.seq);
  });

  const payload = event.payload ?? {};
  if (event.type === "node_started") {
    const node = String(payload.node ?? "unknown");
    handlers.setNodes((prev) =>
      new Map(prev).set(node, {
        node,
        status: "running",
        startedAt: event.occurred_at,
      }),
    );
  }
  if (event.type === "node_completed") {
    const node = String(payload.node ?? "unknown");
    handlers.setNodes((prev) =>
      new Map(prev).set(node, {
        node,
        status: "completed",
        durationMs: payload.duration_ms as number | null | undefined,
      }),
    );
  }
  if (event.type === "node_failed") {
    const node = String(payload.node ?? "unknown");
    handlers.setNodes((prev) => new Map(prev).set(node, { node, status: "failed" }));
  }
  if (event.type === "tool_called" || event.type === "tool_result") {
    handlers.setToolCalls((prev) => [...prev, event]);
  }
  if (event.type === "evidence_added") {
    const evidenceId = String(payload.evidence_id ?? "");
    if (evidenceId) {
      handlers.setEvidence((prev) =>
        new Map(prev).set(evidenceId, {
          id: evidenceId,
          title: payload.title as string | undefined,
          summary: payload.summary as string | undefined,
          sourceType: payload.source_type as string | undefined,
          toolName: payload.tool_name as string | undefined,
        }),
      );
    }
  }
  if (event.type === "hypothesis_added" || event.type === "hypothesis_updated") {
    const hypothesisId = String(payload.hypothesis_id ?? "");
    if (hypothesisId) {
      handlers.setHypotheses((prev) =>
        new Map(prev).set(hypothesisId, {
          id: hypothesisId,
          statement: String(payload.statement ?? prev.get(hypothesisId)?.statement ?? ""),
          confidence: payload.confidence as number | undefined,
          status: payload.status as string | undefined,
        }),
      );
    }
  }
  if (event.type === "approval_requested" || event.type === "action_proposed") {
    handlers.invalidateActions();
  }
  if (event.type === "run_completed" || event.type === "run_failed") {
    handlers.invalidateRuns();
  }
}

export function InvestigationLivePanel({ incidentId }: InvestigationLivePanelProps) {
  const { can } = useAuth();
  const apiBaseUrl = getDefaultApiBaseUrl();
  const queryClient = useQueryClient();
  const [connectionState, setConnectionState] = useState<SseConnectionState>("disconnected");
  const [events, setEvents] = useState<InvestigationEvent[]>([]);
  const [nodes, setNodes] = useState<Map<string, NodeEntry>>(new Map());
  const [toolCalls, setToolCalls] = useState<InvestigationEvent[]>([]);
  const [hypotheses, setHypotheses] = useState<Map<string, LiveHypothesis>>(new Map());
  const [evidence, setEvidence] = useState<Map<string, LiveEvidence>>(new Map());
  const sseRef = useRef<InvestigationEventSource | null>(null);
  const bootstrappedRef = useRef(false);

  const runsQuery = useQuery({
    queryKey: ["agent-runs", incidentId],
    queryFn: () => fetchAgentRuns(apiBaseUrl, incidentId),
  });

  const actionsQuery = useQuery({
    queryKey: ["proposed-actions", incidentId],
    queryFn: () => fetchProposedActions(apiBaseUrl, incidentId),
  });

  const activeRun: AgentRun | undefined = runsQuery.data?.items.find((run) =>
    ["pending", "running", "paused", "awaiting_approval"].includes(run.status),
  );

  const eventHandlers = useMemo(
    () => ({
      setEvents,
      setNodes,
      setToolCalls,
      setHypotheses,
      setEvidence,
      invalidateActions: () =>
        void queryClient.invalidateQueries({ queryKey: ["proposed-actions", incidentId] }),
      invalidateRuns: () =>
        void queryClient.invalidateQueries({ queryKey: ["agent-runs", incidentId] }),
    }),
    [incidentId, queryClient],
  );

  const bootstrapFromHistory = useCallback(async () => {
    const history = await fetchEventHistory(apiBaseUrl, incidentId);
    for (const event of history.items) {
      applyEventToState(event, eventHandlers);
    }
    bootstrappedRef.current = true;
  }, [apiBaseUrl, incidentId, eventHandlers]);

  const startMutation = useMutation({
    mutationFn: () => startInvestigation(apiBaseUrl, incidentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["agent-runs", incidentId] });
      setEvents([]);
      setNodes(new Map());
      setToolCalls([]);
      setHypotheses(new Map());
      setEvidence(new Map());
      bootstrappedRef.current = false;
    },
  });

  const pauseMutation = useMutation({
    mutationFn: () => pauseInvestigation(apiBaseUrl, incidentId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["agent-runs", incidentId] }),
  });

  const resumeMutation = useMutation({
    mutationFn: () => resumeInvestigation(apiBaseUrl, incidentId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["agent-runs", incidentId] }),
  });

  useEffect(() => {
    if (!activeRun) return;
    const progress = activeRun.node_progress ?? {};
    const completed = (progress.completed_nodes as string[] | undefined) ?? [];
    const seeded = new Map<string, NodeEntry>();
    for (const node of completed) {
      seeded.set(node, { node, status: "completed" });
    }
    if (progress.current_node) {
      seeded.set(String(progress.current_node), {
        node: String(progress.current_node),
        status: "running",
      });
    }
    setNodes((prev) => (prev.size === 0 ? seeded : prev));
  }, [activeRun]);

  useEffect(() => {
    let cancelled = false;

    async function connect() {
      if (!bootstrappedRef.current) {
        try {
          await bootstrapFromHistory();
        } catch {
          // history bootstrap is best-effort; SSE will still connect
        }
      }
      if (cancelled) return;

      const source = new InvestigationEventSource(
        investigationEventsUrl(apiBaseUrl, incidentId),
        (event) => applyEventToState(event, eventHandlers),
        (state) => {
          setConnectionState(state);
          if (source.needsFullReload()) {
            void bootstrapFromHistory();
          }
        },
      );
      sseRef.current = source;
      source.connect();
    }

    void connect();
    return () => {
      cancelled = true;
      sseRef.current?.close();
    };
  }, [apiBaseUrl, incidentId, bootstrapFromHistory, eventHandlers]);

  const timeline = useMemo(() => events.slice(-50), [events]);
  const failedEvents = events.filter((event) => event.type === "node_failed");

  return (
    <div className="investigation-live">
      <header className="investigation-toolbar">
        <p className="meta">
          Connection: {connectionState}
          {activeRun ? ` · Run ${activeRun.status}` : " · No active run"}
        </p>
        {can("manage_investigation") ? (
          <div className="button-row">
            {!activeRun ? (
              <button type="button" disabled={startMutation.isPending} onClick={() => startMutation.mutate()}>
                Start investigation
              </button>
            ) : null}
            {activeRun?.status === "running" ? (
              <button type="button" disabled={pauseMutation.isPending} onClick={() => pauseMutation.mutate()}>
                Pause
              </button>
            ) : null}
            {activeRun?.status === "paused" ? (
              <button type="button" disabled={resumeMutation.isPending} onClick={() => resumeMutation.mutate()}>
                Resume
              </button>
            ) : null}
          </div>
        ) : null}
      </header>

      <section>
        <h3>Nodes</h3>
        {nodes.size === 0 ? <p role="status">No node progress yet.</p> : null}
        {[...nodes.values()].map((entry) => (
          <article key={entry.node} className={`node-entry status-${entry.status}`}>
            <strong>{entry.node}</strong>
            <span>{entry.status}</span>
            {entry.durationMs != null ? <span>{entry.durationMs} ms</span> : null}
          </article>
        ))}
      </section>

      <section>
        <h3>Tool calls</h3>
        {toolCalls.length === 0 ? <p role="status">No tool calls yet.</p> : null}
        {toolCalls.map((event) => (
          <article key={event.seq} className="timeline-entry">
            <time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleTimeString()}</time>
            <strong>{event.type}</strong>
            <pre>{JSON.stringify(event.payload, null, 2)}</pre>
          </article>
        ))}
      </section>

      <section>
        <h3>Evidence</h3>
        {evidence.size === 0 ? <p role="status">No evidence collected yet.</p> : null}
        {[...evidence.values()].map((item) => (
          <article key={item.id} className="card">
            <strong>{item.title ?? item.id}</strong>
            <p className="meta">{item.sourceType ?? item.toolName}</p>
            {item.summary ? <p>{item.summary}</p> : null}
          </article>
        ))}
      </section>

      <section>
        <h3>Hypotheses</h3>
        {hypotheses.size === 0 ? <p role="status">No hypotheses yet.</p> : null}
        {[...hypotheses.values()].map((item) => (
          <article key={item.id} className="card">
            <p>{item.statement || item.id}</p>
            <p className="meta">
              {item.confidence != null ? `confidence ${item.confidence.toFixed(2)}` : null}
              {item.status ? ` · ${item.status}` : null}
            </p>
          </article>
        ))}
      </section>

      <section>
        <h3>Live timeline</h3>
        {timeline.map((event) => (
          <article key={event.seq} className="timeline-entry">
            <time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleTimeString()}</time>
            <strong>{event.type}</strong>
          </article>
        ))}
      </section>

      {failedEvents.length > 0 ? (
        <section role="alert">
          <h3>Errors</h3>
          {failedEvents.map((event) => (
            <p key={event.seq}>{readableError(event.payload)}</p>
          ))}
        </section>
      ) : null}

      <section>
        <h3>Proposed actions</h3>
        {actionsQuery.data?.items.length === 0 ? (
          <p role="status">No proposed actions yet.</p>
        ) : (
          actionsQuery.data?.items.map((action) => (
            <article key={action.id} className="card">
              <strong>{action.action_type}</strong>
              <p>{action.description}</p>
              <p className="meta">
                {action.risk_level} · {action.status}
              </p>
            </article>
          ))
        )}
      </section>
    </div>
  );
}
