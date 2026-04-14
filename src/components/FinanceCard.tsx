interface FinanceCardProps {
  label: string;
  value: string;
  subtext?: string;
  trend?: "up" | "down" | "neutral";
  highlight?: boolean;
}

export default function FinanceCard({
  label,
  value,
  subtext,
  trend,
  highlight,
}: FinanceCardProps) {
  const trendColor =
    trend === "up"
      ? "text-positive"
      : trend === "down"
        ? "text-negative"
        : "text-text-secondary";

  return (
    <div
      className={`rounded-xl border p-4 sm:p-6 transition-colors ${
        highlight
          ? "border-primary/30 bg-primary/5"
          : "border-[#1e1e2e] bg-[#0d0d14] hover:bg-[#111118]"
      }`}
    >
      <p className="text-xs sm:text-sm text-text-muted">{label}</p>
      <p className={`mt-1 sm:mt-2 text-xl sm:text-3xl font-bold ${trendColor}`}>{value}</p>
      {subtext && (
        <p className="mt-1 text-xs sm:text-sm text-text-secondary">{subtext}</p>
      )}
    </div>
  );
}
