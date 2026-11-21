
import Link from "next/link"
import SahayakApp from "@/src/components/sahayak-app"

export default function HomePage() {
  return (
    <>
      <SahayakApp />

      <Link
        href="/offline"
        className="fixed bottom-20 right-5 z-50 rounded-xl bg-teal-700 px-5 py-3 text-sm font-semibold text-white shadow-lg transition hover:bg-teal-800"
      >
        🎤 Real Gnani Recording
      </Link>
    </>
  )
}
