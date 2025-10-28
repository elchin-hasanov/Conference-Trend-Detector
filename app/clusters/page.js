import React from "react";
import { supabase } from "@/lib/supabase";
import ClustersList from "./ClustersList";

async function fetchClustersFromDB() {
  const { data, error } = await supabase
    .from("paper_clusters")
    .select("cluster_id, keywords, avg_citation, num_papers, papers, created_at")
    .order("cluster_id", { ascending: true });
  if (error) {
    return { ok: false, error };
  }
  // Normalize to UI shape used previously
  const clusters = (data || []).map((row) => ({
    id: row.cluster_id,
    label: row.keywords,
    avg_citation: row.avg_citation,
    count: row.num_papers,
    papers: Array.isArray(row.papers) ? row.papers : [],
    created_at: row.created_at,
  }));
  return { ok: true, clusters };
}

export default async function ClustersPage() {
  const res = await fetchClustersFromDB();

  return (
    <div className="min-h-screen bg-white p-6">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold text-blue-900 mb-6">Clusters</h1>
        {!res.ok && (
          <div className="text-red-700">
            Failed to load clusters from Supabase. Ensure NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY are set.
          </div>
        )}
        {res.ok && res.clusters.length === 0 && (
          <div className="text-gray-600">No clusters found. Run the clustering export to populate paper_clusters.</div>
        )}
        {res.ok && res.clusters.length > 0 && <ClustersList clusters={res.clusters} />}
      </div>
    </div>
  );
}
