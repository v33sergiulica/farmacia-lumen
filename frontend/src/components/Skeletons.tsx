export function KpiStripSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="rounded-lg border border-[#E2E7E4] bg-white p-4"
        >
          <div className="h-3 w-20 animate-pulse rounded bg-[#EAEFED]" />
          <div className="mt-3 h-7 w-28 animate-pulse rounded bg-[#EAEFED]" />
          <div className="mt-2.5 h-3 w-24 animate-pulse rounded bg-[#EAEFED]" />
        </div>
      ))}
    </div>
  );
}

export function ChartCardSkeleton({ heightClass = "h-80" }: { heightClass?: string }) {
  return (
    <div className="rounded-lg border border-[#E2E7E4] bg-white p-5">
      <div className="flex items-center justify-between">
        <div className="h-4 w-56 animate-pulse rounded bg-[#EAEFED]" />
        <div className="h-7 w-32 animate-pulse rounded bg-[#EAEFED]" />
      </div>
      <div className={`mt-4 w-full animate-pulse rounded bg-[#F2F5F3] ${heightClass}`} />
    </div>
  );
}

export function TableCardSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="rounded-lg border border-[#E2E7E4] bg-white p-5">
      <div className="h-4 w-48 animate-pulse rounded bg-[#EAEFED]" />
      <div className="mt-4 space-y-2.5">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="h-8 w-full animate-pulse rounded bg-[#F2F5F3]" />
        ))}
      </div>
    </div>
  );
}
