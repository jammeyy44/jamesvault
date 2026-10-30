import { brand } from "@/lib/brand";

/** Premium monogram badge with cursive S sweep glyph + brand wordmark for stakesweep.net */
export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <span className="relative grid h-10 w-10 place-items-center rounded-2xl bg-gradient-to-br from-[#7c3aed] via-[#6366f1] to-[#0284c7] shadow-[0_4px_20px_rgba(99,102,241,0.5)] border border-white/20">
        <svg viewBox="0 0 40 40" className="h-6 w-6" fill="none" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="stakeSweepGrad" x1="10" y1="8" x2="30" y2="34" gradientUnits="userSpaceOnUse">
              <stop stopColor="#ffffff" />
              <stop offset="0.5" stopColor="#e0e7ff" />
              <stop offset="1" stopColor="#38bdf8" />
            </linearGradient>
          </defs>
          {/* Elegant S Curve */}
          <path
            d="M26 13C24.5 9.5 21.5 8.5 17.5 8.5C13 8.5 10.5 11.5 10.5 15C10.5 20.5 18 21.5 22.5 23.5C27 25.5 28.5 28 28.5 31.5C28.5 35.5 24.5 37.5 20 37.5C15 37.5 12 34.5 11 31"
            stroke="url(#stakeSweepGrad)"
            strokeWidth="3.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {/* Sweep spark accent */}
          <path
            d="M27 7L28 9.5L30.5 10.5L28 11.5L27 14L26 11.5L23.5 10.5L26 9.5L27 7Z"
            fill="#38bdf8"
          />
        </svg>
      </span>
      <span className="text-xl font-black tracking-tight text-white hidden xs:inline sm:inline">
        <span>stakesweep</span>
        <span className="text-sky-400">.net</span>
      </span>
    </span>
  );
}
