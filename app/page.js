import Link from "next/link";

export default function Home() {
  return (
    <div className="font-sans min-h-screen bg-white p-8 flex flex-col items-center justify-center">
      <main className="flex flex-col gap-10 items-center w-full max-w-2xl">
        <div className="text-center text-3xl text-blue-900 font-bold mb-4">
          Welcome to TrendScraper!
        </div>
        <div className="text-center text-lg text-blue-800 mb-8">
          Explore trending research papers and more.
        </div>
        <div className="flex gap-6 mt-6">
          <Link href="/papers">
            <span className="inline-block rounded-lg bg-blue-600 text-white px-6 py-3 font-semibold shadow hover:bg-blue-700 transition-colors cursor-pointer">View Papers</span>
          </Link>
        </div>
      </main>
    </div>
  );
}
