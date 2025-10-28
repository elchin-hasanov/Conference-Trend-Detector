

"use client";
import { supabase } from '../../lib/supabase';
import { useEffect, useState } from 'react';
import Link from 'next/link';

export default function PapersPage() {
  const [papers, setPapers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sectorCounts, setSectorCounts] = useState({ industry: 0, academia: 0, mixed: 0, unknown: 0 });
  // Detail interactions moved to /papers/[id]

  useEffect(() => {
    async function fetchPapers() {
      const { data, error } = await supabase
        .from('papers')
        .select('*')
        .order('publication_date', { ascending: false });
      if (!error) setPapers(data);
      setLoading(false);
    }
    fetchPapers();
  }, []);

  // After papers load, classify each via /api/sector and aggregate counts
  useEffect(() => {
    let abort = false;
    async function classifyAll() {
      if (!papers?.length) {
        setSectorCounts({ industry: 0, academia: 0, mixed: 0, unknown: 0 });
        return;
      }
      const counts = { industry: 0, academia: 0, mixed: 0, unknown: 0 };
      // Limit concurrency to avoid rate limits
      const chunk = async (items, size) => {
        for (let i = 0; i < items.length; i += size) {
          const slice = items.slice(i, i + size);
          const res = await Promise.all(
            slice.map(async (p) => {
              try {
                const year = (p.publication_date || '').slice(0, 4) || undefined;
                const url = new URL('/api/sector', window.location.origin);
                if (p.doi) url.searchParams.set('doi', p.doi);
                url.searchParams.set('title', p.title || '');
                url.searchParams.set('authors', p.author || '');
                if (year) url.searchParams.set('year', year);
                const r = await fetch(url.toString());
                if (!r.ok) return { sector: 'unknown' };
                return await r.json();
              } catch {
                return { sector: 'unknown' };
              }
            })
          );
          for (const s of res) {
            const key = s?.sector || 'unknown';
            if (counts[key] === undefined) counts[key] = 0;
            counts[key] += 1;
          }
          if (abort) return;
        }
      };
      await chunk(papers, 6);
      if (!abort) setSectorCounts(counts);
    }
    classifyAll();
    return () => {
      abort = true;
    };
  }, [papers]);

  if (loading) return <div className="text-center text-lg text-blue-700 mt-10">Loading...</div>;

  // Sort papers by citation_number descending
  const sortedPapers = [...papers].sort((a, b) => (b.citation_number || 0) - (a.citation_number || 0));
  const totalCount = sortedPapers.length;

  return (
    <div className="max-w-6xl mx-auto px-4">
      <div className="bg-white rounded-2xl shadow-lg p-3 sm:p-5">
        <h1 className="text-3xl font-bold text-blue-900 mb-2 text-center">Papers</h1>
        <div className="text-center text-blue-700 mb-6 text-lg font-medium">
          Total papers: {totalCount}
          <div className="mt-2 text-sm text-gray-700">
            Industry: <span className="font-semibold text-gray-900">{sectorCounts.industry}</span>
            {' '}· Academia: <span className="font-semibold text-gray-900">{sectorCounts.academia}</span>
            {' '}· Mixed: <span className="font-semibold text-gray-900">{sectorCounts.mixed}</span>
            {' '}· Unknown: <span className="font-semibold text-gray-900">{sectorCounts.unknown}</span>
          </div>
        </div>
        <div className="rounded-lg w-full">
          <table className="w-full bg-white border border-gray-200 text-sm sm:text-base table-auto">
            <thead className="bg-blue-50">
              <tr>
                <th className="py-3 px-4 border-b border-gray-200 text-left font-semibold text-blue-900">Title</th>
                {/* Hidden columns moved to detail page */}
                <th className="py-3 px-4 border-b border-gray-200 text-left font-semibold text-blue-900">Publication Date</th>
                <th className="py-3 px-4 border-b border-gray-200 text-left font-semibold text-blue-900">Citation Number</th>
                <th className="py-3 px-4 border-b border-gray-200 text-left font-semibold text-blue-900">Conference Name</th>
              </tr>
            </thead>
            <tbody>
              {sortedPapers.map((paper) => (
                <tr key={paper.id} className="hover:bg-blue-100 transition-colors">
                  <td className="py-2 px-4 border-b border-gray-100 align-top font-semibold text-gray-900 break-words">
                    <Link className="text-blue-700 hover:underline" href={`/papers/${paper.id}`}>
                      {paper.title}
                    </Link>
                  </td>
                  <td className="py-2 px-4 border-b border-gray-100 align-top text-gray-800 whitespace-nowrap">{paper.publication_date}</td>
                  <td className="py-2 px-4 border-b border-gray-100 align-top text-center text-gray-900 font-semibold whitespace-nowrap">{paper.citation_number}</td>
                  <td className="py-2 px-4 border-b border-gray-100 align-top text-gray-700 max-w-[280px] break-words">{paper.conference_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
