"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function NavBar() {
  const pathname = usePathname();
  const linkCls = (href) =>
    `px-4 py-2 rounded-md text-sm font-medium ${
      pathname === href
        ? "bg-blue-700 text-white"
        : "text-blue-900 hover:bg-blue-100"
    }`;

  return (
    <header className="w-full border-b bg-white sticky top-0 z-40">
      <nav className="max-w-6xl mx-auto flex items-center justify-between px-4 py-3">
        <Link href="/" className="text-xl font-bold text-blue-900">
          TrendScraper
        </Link>
        <div className="flex gap-2">
          <Link href="/" className={linkCls("/")}>Home</Link>
          <Link href="/papers" className={linkCls("/papers")}>Papers</Link>
          <Link href="/clusters" className={linkCls("/clusters")}>Clusters</Link>
        </div>
      </nav>
    </header>
  );
}
