"use client";

import React from "react";
import dynamic from "next/dynamic";
import "chart.js/auto";

// Dynamically import react-chartjs-2 to avoid SSR issues
const Line = dynamic(
  () => import("react-chartjs-2").then((mod) => mod.Line),
  { ssr: false }
);

export default function GrowthModal({ open, onClose, title, series, seriesMonthly, yoy, usedDoi }) {
  if (!open) return null;

  const monthly = Array.isArray(seriesMonthly) && seriesMonthly.length > 0;
  const labels = monthly ? seriesMonthly.map((d) => d.month) : series.map((d) => d.year);
  const counts = monthly ? seriesMonthly.map((d) => d.count) : series.map((d) => d.count);
  const yoyLabels = yoy.map((d) => d.year);
  const yoyVals = yoy.map((d) => d.growth);

  const data = {
    labels,
    datasets: [
      {
        label: monthly ? "Citations per Month" : "Citations per Year",
        data: counts,
        borderColor: "#2563eb",
        backgroundColor: "rgba(37, 99, 235, 0.2)",
        tension: 0.2,
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: { legend: { display: true, labels: { color: "#000" } } },
    scales: {
      x: {
        ticks: { autoSkip: true, maxTicksLimit: monthly ? 12 : 10, color: "#000" },
      },
      y: { beginAtZero: true, ticks: { color: "#000" } },
    },
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
  <div className="bg-white text-black rounded-lg shadow-xl w-[95%] max-w-3xl p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold text-blue-900">Growth: {title}</h3>
          <button className="text-gray-600 hover:text-gray-900" onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="space-y-4">
          {usedDoi && (
            <div className="text-sm text-gray-700">DOI used: <a className="text-blue-700 underline" href={`https://doi.org/${usedDoi}`} target="_blank" rel="noreferrer">{usedDoi}</a></div>
          )}
          {series.length === 0 ? (
            <div className="text-center text-gray-700 py-10">No citation time series available.</div>
          ) : (
            <Line data={data} options={options} />
          )}
          {yoy.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold mb-1 text-blue-800">YoY Growth (%)</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-blue-50">
                    <tr>
                      <th className="text-left p-2">Year</th>
                      <th className="text-left p-2">Growth %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {yoyLabels.map((y, i) => (
                      <tr key={y} className="border-b">
                        <td className="p-2">{y}</td>
                        <td className="p-2">{yoyVals[i].toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
