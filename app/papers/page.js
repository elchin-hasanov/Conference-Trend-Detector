

"use client";
import { supabase } from '../../lib/supabase';
import { useEffect, useState } from 'react';

export default function PapersPage() {
  const [papers, setPapers] = useState([]);
  const [loading, setLoading] = useState(true);

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

  if (loading) return <div className="text-center text-lg text-blue-700 mt-10">Loading...</div>;

  // Sort papers by citation_number descending
  const sortedPapers = [...papers].sort((a, b) => (b.citation_number || 0) - (a.citation_number || 0));
  const totalCount = sortedPapers.length;

  return (
    <div className="w-screen px-0 sm:px-0">
      <div className="bg-white rounded-2xl shadow-lg p-2 sm:p-4">
        <h1 className="text-3xl font-bold text-blue-900 mb-2 text-center">Papers</h1>
        <div className="text-center text-blue-700 mb-6 text-lg font-medium">Total papers: {totalCount}</div>
        <div className="overflow-x-auto rounded-lg w-full">
          <table className="w-full bg-white border border-gray-200 text-sm sm:text-base table-fixed">
            <thead className="bg-blue-50">
              <tr>
                <th className="py-3 px-4 border-b border-gray-200 text-left font-semibold text-blue-900 w-1/4 min-w-[200px]">Title</th>
                <th className="py-3 px-4 border-b border-gray-200 text-left font-semibold text-blue-900 w-1/7 min-w-[100px]">Author</th>
                <th className="py-3 px-4 border-b border-gray-200 text-left font-semibold text-blue-900 w-2/5 min-w-[300px]">Abstract</th>
                <th className="py-3 px-4 border-b border-gray-200 text-left font-semibold text-blue-900">Publication Date</th>
                <th className="py-3 px-4 border-b border-gray-200 text-left font-semibold text-blue-900">Citation Number</th>
                <th className="py-3 px-4 border-b border-gray-200 text-left font-semibold text-blue-900">Conference Name</th>
              </tr>
            </thead>
            <tbody>
              {sortedPapers.map((paper) => (
                <tr key={paper.id} className="hover:bg-blue-100 transition-colors">
                  <td className="py-2 px-4 border-b border-gray-100 align-top font-semibold text-gray-900 w-1/4 min-w-[200px] break-words">{paper.title}</td>
                  <td className="py-2 px-4 border-b border-gray-100 align-top text-gray-800 w-1/5 min-w-[160px] break-words">{paper.author}</td>
                  <td className="py-2 px-4 border-b border-gray-100 align-top text-gray-700 w-2/5 min-w-[300px] whitespace-pre-line break-words" title={paper.abstract}>{paper.abstract}</td>
                  <td className="py-2 px-4 border-b border-gray-100 align-top text-gray-800">{paper.publication_date}</td>
                  <td className="py-2 px-4 border-b border-gray-100 align-top text-center text-gray-900 font-semibold">{paper.citation_number}</td>
                  <td className="py-2 px-4 border-b border-gray-100 align-top text-gray-700 max-w-xs break-words">{paper.conference_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
