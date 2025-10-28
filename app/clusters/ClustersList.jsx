"use client";

import React from "react";

function formatAvg(val) {
  if (val === null || val === undefined) return "N/A";
  const n = Number(val);
  if (Number.isNaN(n)) return "N/A";
  return n.toFixed(2);
}

export default function ClustersList({ clusters }) {
  const [sortField, setSortField] = React.useState("count"); // "count" | "avg_citation"
  const [sortDir, setSortDir] = React.useState("desc"); // "asc" | "desc"

  const sorted = React.useMemo(() => {
    const arr = Array.isArray(clusters) ? [...clusters] : [];
    const dir = sortDir === "asc" ? 1 : -1;
    return arr.sort((a, b) => {
      const va = sortField === "count" ? a.count : a.avg_citation;
      const vb = sortField === "count" ? b.count : b.avg_citation;
      // Nulls last
      const aNull = va === null || va === undefined;
      const bNull = vb === null || vb === undefined;
      if (aNull && bNull) return 0;
      if (aNull) return 1;
      if (bNull) return -1;
      const na = Number(va);
      const nb = Number(vb);
      if (na === nb) return 0;
      return na > nb ? dir : -dir;
    });
  }, [clusters, sortField, sortDir]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3 mb-2">
        <label className="text-sm text-gray-700">Sort by</label>
        <select
          className="border rounded px-2 py-1 text-sm"
          value={sortField}
          onChange={(e) => setSortField(e.target.value)}
        >
          <option value="count">Number of papers</option>
          <option value="avg_citation">Average citations</option>
        </select>
        <select
          className="border rounded px-2 py-1 text-sm"
          value={sortDir}
          onChange={(e) => setSortDir(e.target.value)}
        >
          <option value="asc">Ascending</option>
          <option value="desc">Descending</option>
        </select>
      </div>

      {sorted.map((cl) => (
        <div key={cl.id} className="border rounded-lg p-4 shadow-sm">
          <div className="flex items-baseline justify-between gap-4">
            <h2 className="text-xl font-semibold text-blue-800">[{cl.id}] {cl.label}</h2>
            <div className="text-gray-600">
              <span className="mr-3">Papers: {cl.count}</span>
              <span>Avg citations: {formatAvg(cl.avg_citation)}</span>
            </div>
          </div>
          <ul className="mt-3 list-disc pl-6 space-y-1">
            {cl.papers.map((p, idx) => (
              <li key={idx} className="text-gray-900">
                <span className="font-medium">{p.title}</span>
                <span className="text-gray-600">{` (citations: ${p.citation_number ?? "N/A"})`}</span>
              </li>
            ))}
          </ul>
          {cl.created_at && (
            <div className="text-xs text-gray-500 mt-2">Created: {new Date(cl.created_at).toLocaleString()}</div>
          )}
        </div>
      ))}
    </div>
  );
}
