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
      className={`rounded-xl border p-6 transition-colors ${
        highlight
          ? "border-primary/30 bg-primary/5"
          : "border-border bg-bg-card hover:bg-bg-card-hover"
      }`}
    >
      <p className="text-sm text-text-muted">{label}</p>
      <p className={`mt-2 text-3xl font-bold ${trendColor}`}>{value}</p>
      {subtext && (
        <p className="mt-1 text-sm text-text-secondary">{subtext}</p>
      )}
    </div>
  );
}
