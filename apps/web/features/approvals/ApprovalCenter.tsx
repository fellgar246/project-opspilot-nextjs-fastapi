"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/features/auth/AuthProvider";
import { getDefaultApiBaseUrl } from "@/lib/auth-api";
import {
  approveAction,
  fetchPendingApprovals,
  rejectAction,
  type Approval,
} from "@/lib/investigation-api";
import { InvestigationEventSource, type InvestigationEvent } from "@/lib/sse-client";

function formatCountdown(expiresAt: string): string {
  const remainingMs = new Date(expiresAt).getTime() - Date.now();
  if (remainingMs <= 0) return "Expired";
  const minutes = Math.floor(remainingMs / 60_000);
  const seconds = Math.floor((remainingMs % 60_000) / 1000);
  return `${minutes}m ${seconds}s`;
}

type ApprovalCardProps = {
  approval: Approval;
  canDecide: boolean;
  onDecided: () => void;
};

function ApprovalCard({ approval, canDecide, onDecided }: ApprovalCardProps) {
  const apiBaseUrl = getDefaultApiBaseUrl();
  const [rejectReason, setRejectReason] = useState("");
  const [confirmHigh, setConfirmHigh] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(formatCountdown(approval.expires_at));

  useEffect(() => {
    const timer = window.setInterval(() => {
      setCountdown(formatCountdown(approval.expires_at));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [approval.expires_at]);

  const approveMutation = useMutation({
    mutationFn: () => approveAction(apiBaseUrl, approval.id),
    onSuccess: onDecided,
    onError: (err: Error) => setError(err.message),
  });

  const rejectMutation = useMutation({
    mutationFn: () => rejectAction(apiBaseUrl, approval.id, rejectReason.trim()),
    onSuccess: onDecided,
    onError: (err: Error) => setError(err.message),
  });

  const isHighRisk = approval.action.risk_level === "high";

  return (
    <article className="card approval-card">
      <header>
        <h3>
          <Link href={`/incidents/${approval.incident_id}`}>{approval.incident_title}</Link>
        </h3>
        <p className="meta">
          {approval.incident_severity.toUpperCase()} · expires in {countdown}
        </p>
      </header>
      <p>{approval.action.description}</p>
      <dl className="approval-details">
        <div>
          <dt>Action</dt>
          <dd>{approval.action.action_type}</dd>
        </div>
        <div>
          <dt>Target</dt>
          <dd>{approval.action.target}</dd>
        </div>
        <div>
          <dt>Risk</dt>
          <dd>
            {approval.action.risk_level} — {approval.action.risk_rationale}
          </dd>
        </div>
        <div>
          <dt>Expected result</dt>
          <dd>{approval.action.expected_result}</dd>
        </div>
        <div>
          <dt>Rollback plan</dt>
          <dd>{approval.action.rollback_plan}</dd>
        </div>
        <div>
          <dt>Parameters</dt>
          <dd>
            <pre>{JSON.stringify(approval.action.parameters, null, 2)}</pre>
          </dd>
        </div>
      </dl>

      {canDecide ? (
        <div className="approval-actions">
          {isHighRisk ? (
            <label>
              <input
                type="checkbox"
                checked={confirmHigh}
                onChange={(event) => setConfirmHigh(event.target.checked)}
              />
              I confirm the exact parameters above for this high-risk action
            </label>
          ) : null}
          <button
            type="button"
            disabled={approveMutation.isPending || (isHighRisk && !confirmHigh)}
            onClick={() => approveMutation.mutate()}
          >
            Approve
          </button>
          <textarea
            rows={2}
            placeholder="Rejection reason (required)"
            value={rejectReason}
            onChange={(event) => setRejectReason(event.target.value)}
          />
          <button
            type="button"
            className="danger"
            disabled={rejectMutation.isPending || !rejectReason.trim()}
            onClick={() => rejectMutation.mutate()}
          >
            Reject
          </button>
        </div>
      ) : (
        <p className="meta">Approval decisions require approver or admin role.</p>
      )}
      {error ? <p role="alert">{error}</p> : null}
    </article>
  );
}

export function ApprovalCenter() {
  const { can } = useAuth();
  const apiBaseUrl = getDefaultApiBaseUrl();
  const queryClient = useQueryClient();
  const [liveApprovals, setLiveApprovals] = useState<Approval[]>([]);
  const [connectionState, setConnectionState] = useState<string>("disconnected");

  const pendingQuery = useQuery({
    queryKey: ["approvals", "pending"],
    queryFn: () => fetchPendingApprovals(apiBaseUrl),
    refetchInterval: 30_000,
  });

  useEffect(() => {
    if (pendingQuery.data?.items) {
      setLiveApprovals(pendingQuery.data.items);
    }
  }, [pendingQuery.data]);

  const incidentIds = useMemo(
    () => [...new Set(liveApprovals.map((item) => item.incident_id))],
    [liveApprovals],
  );

  useEffect(() => {
    const sources: InvestigationEventSource[] = [];
    for (const incidentId of incidentIds) {
      const source = new InvestigationEventSource(
        `${apiBaseUrl}/api/v1/incidents/${incidentId}/events`,
        (event: InvestigationEvent) => {
          if (event.type === "approval_requested") {
            void queryClient.invalidateQueries({ queryKey: ["approvals", "pending"] });
          }
        },
        setConnectionState,
      );
      source.connect();
      sources.push(source);
    }
    return () => {
      for (const source of sources) source.close();
    };
  }, [apiBaseUrl, incidentIds, queryClient]);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["approvals", "pending"] });
  };

  return (
    <section>
      <header className="page-header">
        <div>
          <h1>Approval Center</h1>
          <p className="meta">Connection: {connectionState}</p>
        </div>
        <Link href="/incidents">← Incidents</Link>
      </header>
      {pendingQuery.isLoading ? <p role="status">Loading pending approvals…</p> : null}
      {liveApprovals.length === 0 ? (
        <p role="status">No pending approvals.</p>
      ) : (
        liveApprovals.map((approval) => (
          <ApprovalCard
            key={approval.id}
            approval={approval}
            canDecide={can("approve_action")}
            onDecided={refresh}
          />
        ))
      )}
    </section>
  );
}
