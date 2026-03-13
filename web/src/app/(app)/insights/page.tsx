"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { listInsights } from "@/lib/api-client";

export default function InsightsPage() {
  const [active, setActive] = useState<number | null>(null);
  const { data = [], isLoading } = useQuery({ queryKey: ["insights"], queryFn: listInsights });

  if (isLoading) return <p>Loading insights…</p>;

  return (
    <div className="stack">
      <h2>Insights</h2>
      <div className="card">
        {(data ?? []).map((row, index) => (
          <div key={`${String(row.title)}-${index}`} style={{ marginBottom: 8 }}>
            <strong>#{index + 1}</strong> {String(row.title ?? "Untitled")} · confidence {Number(row.confidence ?? 0).toFixed(2)}
            <button onClick={() => setActive(active === index ? null : index)} style={{ marginLeft: 8 }}>Evidence</button>
            {active === index ? (
              <ul>
                {(row.source_refs ?? []).map((ref) => (
                  <li key={`${ref.type}-${ref.id}`}>{ref.label} ({ref.type}:{ref.id})</li>
                ))}
              </ul>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
