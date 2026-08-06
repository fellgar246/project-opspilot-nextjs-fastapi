# Postmortem generation prompt (v1)

Generate a postmortem document using ONLY persisted investigation data.

Rules:
- Every factual claim MUST cite evidence with `[[evidence:UUID]]`, hypotheses with `[[hypothesis:UUID]]`, actions with `[[action:UUID]]`, or timeline entries with `[[timeline:UUID]]`.
- Do NOT invent events, metrics, or actions not present in the provided context.
- If no conclusive root cause exists, state that explicitly.
- Preventive actions MUST be labeled as recommendations.

Sections required:
1. Executive summary
2. Impact
3. Timeline (from persisted timeline only)
4. Root cause (or explicit absence)
5. Contributing factors
6. Detection
7. Mitigation applied
8. Verification
9. Learnings
10. Preventive actions (recommendations)
