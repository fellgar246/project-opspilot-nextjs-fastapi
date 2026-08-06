export type InvestigationEvent = {
  id?: string;
  incident_id: string;
  agent_run_id: string | null;
  seq: number;
  type: string;
  occurred_at: string;
  payload: Record<string, unknown>;
};

export type SseConnectionState = "connecting" | "connected" | "reconnecting" | "disconnected";

type InvestigationEventHandler = (event: InvestigationEvent) => void;
type ConnectionStateHandler = (state: SseConnectionState) => void;

const TERMINAL_EVENTS = new Set(["run_completed", "run_failed"]);

export class InvestigationEventSource {
  private source: EventSource | null = null;
  private lastEventId = 0;
  private reconnectAttempt = 0;
  private closed = false;
  private reloadRequested = false;

  constructor(
    private readonly url: string,
    private readonly onEvent: InvestigationEventHandler,
    private readonly onConnectionState: ConnectionStateHandler,
  ) {}

  connect(): void {
    this.closed = false;
    this.onConnectionState(this.reconnectAttempt > 0 ? "reconnecting" : "connecting");
    this.source = new EventSource(this.url, { withCredentials: true });

    this.source.onopen = () => {
      this.reconnectAttempt = 0;
      this.onConnectionState("connected");
    };

    this.source.onerror = () => {
      if (this.closed) {
        return;
      }
      this.source?.close();
      this.onConnectionState("reconnecting");
      const delay = Math.min(30_000, 1000 * 2 ** this.reconnectAttempt);
      this.reconnectAttempt += 1;
      window.setTimeout(() => this.connect(), delay);
    };

    const eventTypes = [
      "run_started",
      "node_started",
      "node_completed",
      "node_failed",
      "tool_called",
      "tool_result",
      "evidence_added",
      "hypothesis_added",
      "hypothesis_updated",
      "action_proposed",
      "approval_requested",
      "approval_decided",
      "run_paused",
      "run_resumed",
      "run_completed",
      "run_failed",
      "action_executed",
      "recovery_verified",
      "postmortem_generated",
      "retention_expired",
    ];

    for (const type of eventTypes) {
      this.source.addEventListener(type, (raw) => {
        const message = raw as MessageEvent<string>;
        if (message.lastEventId) {
          this.lastEventId = Math.max(this.lastEventId, Number.parseInt(message.lastEventId, 10));
        }
        if (type === "retention_expired") {
          this.reloadRequested = true;
          this.onConnectionState("disconnected");
          this.close();
          return;
        }
        try {
          const data = JSON.parse(message.data) as InvestigationEvent;
          if (data.seq > this.lastEventId) {
            this.lastEventId = data.seq;
          }
          this.onEvent(data);
          if (TERMINAL_EVENTS.has(data.type)) {
            this.close();
          }
        } catch {
          // ignore malformed payloads
        }
      });
    }
  }

  close(): void {
    this.closed = true;
    this.source?.close();
    this.source = null;
    this.onConnectionState("disconnected");
  }

  needsFullReload(): boolean {
    return this.reloadRequested;
  }

  getLastEventId(): number {
    return this.lastEventId;
  }
}
