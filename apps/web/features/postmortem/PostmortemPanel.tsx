"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { getDefaultApiBaseUrl } from "@/lib/auth-api";
import {
  fetchPostmortem,
  generatePostmortem,
  postmortemExportUrl,
  savePostmortemEdit,
} from "@/lib/postmortem-api";

type PostmortemPanelProps = {
  incidentId: string;
};

export function PostmortemPanel({ incidentId }: PostmortemPanelProps) {
  const apiBaseUrl = getDefaultApiBaseUrl();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<string | null>(null);
  const [preview, setPreview] = useState(true);

  const postmortemQuery = useQuery({
    queryKey: ["postmortem", incidentId],
    queryFn: () => fetchPostmortem(apiBaseUrl, incidentId),
    retry: false,
  });

  const generateMutation = useMutation({
    mutationFn: () => generatePostmortem(apiBaseUrl, incidentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["postmortem", incidentId] }),
  });

  const saveMutation = useMutation({
    mutationFn: (content: string) => savePostmortemEdit(apiBaseUrl, incidentId, content),
    onSuccess: () => {
      setDraft(null);
      queryClient.invalidateQueries({ queryKey: ["postmortem", incidentId] });
    },
  });

  const content = draft ?? postmortemQuery.data?.content ?? "";

  if (postmortemQuery.isError && !draft) {
    return (
      <div>
        <p role="status">No postmortem generated yet.</p>
        <button type="button" onClick={() => generateMutation.mutate()} disabled={generateMutation.isPending}>
          {generateMutation.isPending ? "Generating…" : "Generate postmortem"}
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="toolbar">
        <button type="button" onClick={() => generateMutation.mutate()} disabled={generateMutation.isPending}>
          Regenerate
        </button>
        <button type="button" onClick={() => setPreview((value) => !value)}>
          {preview ? "Edit" : "Preview"}
        </button>
        <button type="button" onClick={() => saveMutation.mutate(content)} disabled={saveMutation.isPending}>
          Save edit
        </button>
        <a href={postmortemExportUrl(apiBaseUrl, incidentId, "md")} download>
          Export Markdown
        </a>
        <a href={postmortemExportUrl(apiBaseUrl, incidentId, "pdf")} download>
          Export PDF
        </a>
      </div>

      {postmortemQuery.data?.status === "draft_with_warnings" ? (
        <p className="warning" role="alert">
          Draft with warnings — invalid references:{" "}
          {postmortemQuery.data.invalid_references.join(", ")}
        </p>
      ) : null}

      <p className="meta">
        Version {postmortemQuery.data?.version ?? "—"} · {postmortemQuery.data?.status ?? "draft"}
      </p>

      {preview ? (
        <pre className="postmortem-preview">{content}</pre>
      ) : (
        <textarea
          className="postmortem-editor"
          value={content}
          onChange={(event) => setDraft(event.target.value)}
          rows={24}
        />
      )}
    </div>
  );
}
