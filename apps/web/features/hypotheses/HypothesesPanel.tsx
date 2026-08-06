"use client";

import { useMemo, useState } from "react";

import type { Evidence, Hypothesis } from "@/lib/incidents-api";

type HypothesesPanelProps = {
  hypotheses: Hypothesis[];
  evidence: Evidence[];
  onNavigateEvidence?: (evidenceId: string) => void;
};

function evidenceLabel(evidence: Evidence[]): Record<string, string> {
  return Object.fromEntries(evidence.map((item) => [item.id, item.title]));
}

function groundingClass(grounding: string | null | undefined): string {
  if (grounding === "knowledge_only") return "grounding-knowledge";
  if (grounding === "mixed") return "grounding-mixed";
  return "grounding-observed";
}

export function HypothesesPanel({
  hypotheses,
  evidence,
  onNavigateEvidence,
}: HypothesesPanelProps) {
  const [compareA, setCompareA] = useState<string>("");
  const [compareB, setCompareB] = useState<string>("");
  const labels = useMemo(() => evidenceLabel(evidence), [evidence]);

  const sorted = [...hypotheses].sort((a, b) => b.confidence - a.confidence);
  const active = sorted.filter((item) => item.status !== "rejected");
  const rejected = sorted.filter((item) => item.status === "rejected");

  const compareLeft = sorted.find((item) => item.id === compareA);
  const compareRight = sorted.find((item) => item.id === compareB);

  return (
    <div className="hypotheses-panel">
      <div className="hypothesis-compare-controls">
        <label>
          Compare A
          <select value={compareA} onChange={(event) => setCompareA(event.target.value)}>
            <option value="">Select hypothesis</option>
            {sorted.map((item) => (
              <option key={item.id} value={item.id}>
                {Math.round(item.confidence * 100)}% — {item.statement.slice(0, 60)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Compare B
          <select value={compareB} onChange={(event) => setCompareB(event.target.value)}>
            <option value="">Select hypothesis</option>
            {sorted.map((item) => (
              <option key={item.id} value={item.id}>
                {Math.round(item.confidence * 100)}% — {item.statement.slice(0, 60)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {compareLeft && compareRight ? (
        <div className="hypothesis-compare-grid">
          {[compareLeft, compareRight].map((item) => (
            <article key={item.id} className="card hypothesis-card">
              <HypothesisCardBody item={item} labels={labels} onNavigateEvidence={onNavigateEvidence} />
            </article>
          ))}
        </div>
      ) : null}

      {active.map((item) => (
        <article key={item.id} className={`card hypothesis-card ${groundingClass(item.grounding)}`}>
          <HypothesisCardBody item={item} labels={labels} onNavigateEvidence={onNavigateEvidence} />
        </article>
      ))}

      {rejected.length > 0 ? (
        <details className="rejected-hypotheses">
          <summary>{rejected.length} rejected hypotheses</summary>
          {rejected.map((item) => (
            <article key={item.id} className="card hypothesis-card rejected">
              <HypothesisCardBody item={item} labels={labels} onNavigateEvidence={onNavigateEvidence} />
            </article>
          ))}
        </details>
      ) : null}
    </div>
  );
}

function HypothesisCardBody({
  item,
  labels,
  onNavigateEvidence,
}: {
  item: Hypothesis;
  labels: Record<string, string>;
  onNavigateEvidence?: (evidenceId: string) => void;
}) {
  return (
    <>
      <header className="hypothesis-header">
        <strong>{Math.round(item.confidence * 100)}% confidence</strong>
        <span className="meta">
          {item.critic_verdict ?? "pending"} · {item.grounding ?? "unknown"}
        </span>
      </header>
      <p>{item.statement}</p>
      {item.rejection_reason ? <p className="rejection-reason">{item.rejection_reason}</p> : null}

      <section>
        <h4>Supporting evidence</h4>
        <EvidenceList ids={item.supporting_evidence} labels={labels} onNavigate={onNavigateEvidence} />
      </section>

      <section>
        <h4>Counter evidence</h4>
        <EvidenceList ids={item.contradicting_evidence} labels={labels} onNavigate={onNavigateEvidence} />
      </section>

      {item.assumptions.length > 0 ? (
        <section>
          <h4>Assumptions</h4>
          <ul>
            {item.assumptions.map((assumption) => (
              <li key={assumption}>{assumption}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {item.missing_evidence.length > 0 ? (
        <section>
          <h4>Missing evidence</h4>
          <ul>
            {item.missing_evidence.map((missing) => (
              <li key={missing}>{missing}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}

function EvidenceList({
  ids,
  labels,
  onNavigate,
}: {
  ids: string[];
  labels: Record<string, string>;
  onNavigate?: (evidenceId: string) => void;
}) {
  if (ids.length === 0) {
    return <p className="meta">None</p>;
  }
  return (
    <ul className="evidence-links">
      {ids.map((id) => (
        <li key={id}>
          {onNavigate ? (
            <button type="button" className="link-button" onClick={() => onNavigate(id)}>
              {labels[id] ?? id}
            </button>
          ) : (
            labels[id] ?? id
          )}
        </li>
      ))}
    </ul>
  );
}
