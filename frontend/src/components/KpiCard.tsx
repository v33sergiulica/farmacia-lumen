type Tone = "neutral" | "positive" | "warning" | "danger";

interface KpiCardProps {
  label: string;
  value: string;
  unit?: string;
  subtext?: string;
  delta?: string;
  tone?: Tone;
}

const TONE_CLASS: Record<Tone, string> = {
  neutral: "text-[#46544D]",
  positive: "text-[#146C43]",
  warning: "text-[#B54708]",
  danger: "text-[#B42318]",
};

export function KpiCard({
  label,
  value,
  unit,
  subtext,
  delta,
  tone = "neutral",
}: KpiCardProps) {
  return (
    <div className="rounded-lg border border-[#E2E7E4] bg-white p-4">
      <div className="text-xs font-medium text-[#5C6B63]">{label}</div>
      <div className="mt-2 flex items-baseline gap-1.5">
        <span className="tabular text-2xl font-semibold tracking-tight text-[#111A16]">
          {value}
        </span>
        {unit && (
          <span className="text-xs font-medium text-[#5C6B63]">{unit}</span>
        )}
      </div>
      {(delta || subtext) && (
        <div className="mt-1.5 flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-xs tabular">
          {delta && (
            <span className={`font-medium ${TONE_CLASS[tone]}`}>{delta}</span>
          )}
          {subtext && <span className="text-[#5C6B63]">{subtext}</span>}
        </div>
      )}
    </div>
  );
}
