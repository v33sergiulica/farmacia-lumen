import { RotateCw } from "lucide-react";

interface PanelErrorProps {
  title?: string;
  message: string;
  onRetry: () => void;
}

export function PanelError({
  title = "Failed to load data",
  message,
  onRetry,
}: PanelErrorProps) {
  return (
    <div className="flex flex-col items-start justify-between gap-3 rounded-lg border border-[#FECDCA] bg-[#FEF3F2] p-4 sm:flex-row sm:items-center">
      <div>
        <p className="text-sm font-medium text-[#B42318]">{title}</p>
        <p className="mt-0.5 text-xs text-[#46544D]">{message}</p>
      </div>
      <button
        type="button"
        onClick={onRetry}
        className="inline-flex items-center gap-1.5 rounded border border-[#E2E7E4] bg-white px-3 py-1.5 text-xs font-medium text-[#111A16] hover:bg-[#F6F7F6]"
      >
        <RotateCw size={14} strokeWidth={1.5} />
        Retry
      </button>
    </div>
  );
}
