"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { supabase } from "../../../lib/supabase";
import GrowthModal from "../GrowthModal";
import {
  resolveDoiOrFindByTitle,
  fetchCitationsWithDates,
  aggregateByYear,
  computeYoY,
} from "../citationUtils";

export default function PaperDetailPage() {
  const params = useParams();
  const id = params?.id;

  const [paper, setPaper] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [modalOpen, setModalOpen] = useState(false);
  const [series, setSeries] = useState([]);
  const [yoy, setYoy] = useState([]);
  const [usedDoi, setUsedDoi] = useState("");
  const [seriesMonthly, setSeriesMonthly] = useState([]);
  const [sectorCounts, setSectorCounts] = useState({ industry: 0, academia: 0, mixed: 0, unknown: 0 });
  const [busy, setBusy] = useState(false);
  const [affBusy, setAffBusy] = useState(false);
  const [affCounts, setAffCounts] = useState(null);

  useEffect(() => {
    async function fetchPaper() {
      if (!id) return;
  const { data, error } = await supabase.from("papers").select("*").eq("id", id).single();
      if (error) {
        setError("Paper not found.");
      } else {
        setPaper(data);
      }
      setLoading(false);
    }
    fetchPaper();
  }, [id]);

  if (loading) return <div className="text-center text-lg text-blue-700 mt-10">Loading...</div>;
  if (error) return (
    <div className="max-w-4xl mx-auto p-4">
      <div className="text-red-700 mb-4">{error}</div>
      <Link className="text-blue-700 underline" href="/papers">Back to Papers</Link>
    </div>
  );
  if (!paper) return null;

  const handleGrowth = async () => {
    setBusy(true);
    try {
  const resolved = await resolveDoiOrFindByTitle({ doi: paper.doi, title: paper.title, arxivId: paper.arxiv_id || paper.arxivId });
      const doi = resolved.doi;
      // Prefer server route to avoid CORS/rate limits and keep logic in one place
      const year = (paper.publication_date && String(paper.publication_date).slice(0,4)) || "";
      const authors = paper.author || "";
      const params = new URLSearchParams({
        ...(doi ? { doi } : {}),
        title: paper.title || "",
        authors,
        year
      });
      const url = `/api/citations?${params.toString()}`;
  const resp = await fetch(url, { cache: 'no-store' });
  const payload = resp.ok ? await resp.json() : { series: [] };
  const s = payload.series || [];
  const sm = payload.seriesMonthly || [];
  const used = payload.doi || "";
  const sc = payload.sectorCounts || { industry: 0, academia: 0, mixed: 0, unknown: 0 };
      const y = computeYoY(s);
      setSeries(s);
  setSeriesMonthly(sm);
      setYoy(y);
  setUsedDoi(used);
  setSectorCounts(sc);
      setModalOpen(true);
    } catch (e) {
      console.error(e);
      alert("Failed to compute growth.");
    } finally {
      setBusy(false);
    }
  };

  const handleAffiliations = async () => {
    setAffBusy(true);
    try {
      const year = (paper.publication_date && String(paper.publication_date).slice(0, 4)) || "";
      const params = new URLSearchParams({
        ...(paper.doi ? { doi: paper.doi } : {}),
        title: paper.title || "",
        authors: paper.author || "",
        year
      });
      const url = `/api/citing-affiliations?${params.toString()}`;
      const r = await fetch(url, { cache: 'no-store' });
      const payload = r.ok ? await r.json() : { counts: null };
      setAffCounts(payload.counts || { academia: 0, industry: 0, government: 0, mixed: 0, unknown: 0 });
    } catch (e) {
      console.error(e);
      setAffCounts({ academia: 0, industry: 0, government: 0, mixed: 0, unknown: 0 });
    } finally {
      setAffBusy(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto p-4 space-y-6">
      <div className="flex items-center justify-between">
        <Link className="text-blue-700 underline" href="/papers">
          ← Back to Papers
        </Link>
      </div>

      <div className="bg-white rounded-2xl shadow p-5">
        <h1 className="text-2xl sm:text-3xl font-bold text-blue-900 mb-3 break-words">{paper.title}</h1>
        <div className="grid sm:grid-cols-2 gap-3 text-sm text-gray-800">
          <div><span className="font-semibold text-blue-900">Author:</span> {paper.author || "N/A"}</div>
          <div><span className="font-semibold text-blue-900">Publication Date:</span> {paper.publication_date || "N/A"}</div>
          <div><span className="font-semibold text-blue-900">Conference:</span> {paper.conference_name || "N/A"}</div>
          <div><span className="font-semibold text-blue-900">Citations:</span> {paper.citation_number ?? "N/A"}</div>
          {paper.doi && (
            <div className="sm:col-span-2">
              <span className="font-semibold text-blue-900">DOI:</span>{" "}
              <a
                className="text-blue-700 underline break-all"
                href={`https://doi.org/${paper.doi}`}
                target="_blank"
                rel="noreferrer"
              >
                {paper.doi}
              </a>
            </div>
          )}
        </div>

        {paper.abstract && (
          <div className="mt-5">
            <h2 className="text-lg font-semibold text-blue-900 mb-2">Abstract</h2>
            <p className="text-gray-800 whitespace-pre-line leading-relaxed">{paper.abstract}</p>
          </div>
        )}

        <div className="mt-6">
          <button
            className="rounded bg-emerald-600 text-white px-4 py-2 text-sm hover:bg-emerald-700 disabled:opacity-50"
            disabled={busy}
            onClick={handleGrowth}
          >
            {busy ? "Working…" : "Generate Growth Rate"}
          </button>
          <button
            className="ml-3 rounded bg-indigo-600 text-white px-4 py-2 text-sm hover:bg-indigo-700 disabled:opacity-50"
            disabled={affBusy}
            onClick={handleAffiliations}
          >
            {affBusy ? "Classifying…" : "Citing Affiliations"}
          </button>
        </div>
      </div>

      {affCounts && (
        <div className="bg-white rounded-2xl shadow p-5">
          <h2 className="text-lg font-semibold text-blue-900 mb-2">Citing papers by affiliation</h2>
          <div className="text-sm text-gray-800 space-y-1">
            <div>Academic: <span className="font-semibold text-gray-900">{affCounts.academia || 0}</span></div>
            <div>Industry: <span className="font-semibold text-gray-900">{affCounts.industry || 0}</span></div>
            <div>Government: <span className="font-semibold text-gray-900">{affCounts.government || 0}</span></div>
            <div>Mixed: <span className="font-semibold text-gray-900">{affCounts.mixed || 0}</span></div>
            <div>Unknown: <span className="font-semibold text-gray-900">{affCounts.unknown || 0}</span></div>
          </div>
        </div>
      )}

      <GrowthModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={paper.title}
        series={series}
  seriesMonthly={seriesMonthly}
        yoy={yoy}
        usedDoi={usedDoi}
  sectorCounts={sectorCounts}
      />
    </div>
  );
}
