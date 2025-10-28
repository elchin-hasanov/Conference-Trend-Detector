"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function NavBar() {
  const pathname = usePathname();

  const linkCls = (href) =>
    `px-3 py-2 rounded-md text-sm font-medium ${
      pathname === href ? "bg-blue-700 text-white" : "text-white hover:bg-blue-600"
    }`;

  return (
    <nav className="bg-blue-800 text-white shadow sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-12 items-center justify-between">
          <div className="flex items-center gap-2">
            <Link href="/" className="text-white font-bold tracking-wide">TrendScraper</Link>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/" className={linkCls("/")}>Home</Link>
            <Link href="/papers" className={linkCls("/papers")}>Papers</Link>
            <Link href="/clusters" className={linkCls("/clusters")}>Clusters</Link>
          </div>
        </div>
      </div>
    </nav>
  );
}
