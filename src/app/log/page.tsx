import Link from "next/link";
import { getLogEntries } from "@/data/finance";

const moodColor: Record<string, string> = {
  "极佳": "bg-positive/10 text-positive",
  "不错": "bg-positive/10 text-positive",
  "平稳": "bg-bg text-text-muted",
  "有点难": "bg-accent/10 text-accent",
  "很艰难": "bg-negative/10 text-negative",
};

export default function LogPage() {
  const logEntries = getLogEntries();
  const entries = [...logEntries].reverse();

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 py-12">
      <h1 className="text-3xl font-bold">执行日志</h1>
      <p className="mt-2 text-text-secondary">
        每天做了什么、为什么做、结果如何 — 真实记录
      </p>

      <div className="mt-8 space-y-4">
        {entries.map((entry) => (
          <Link
            key={entry.slug}
            href={`/log/${entry.slug}`}
            className="block rounded-xl border border-border bg-bg-card p-6 transition-colors hover:bg-bg-card-hover"
          >
            <div className="flex items-center gap-3 mb-2">
              <span className="text-xs text-text-muted font-mono">
                {entry.date}
              </span>
              <span
                className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs ${moodColor[entry.mood] ?? "bg-bg text-text-muted"}`}
              >
                {entry.mood}
              </span>
            </div>
            <h2 className="text-lg font-semibold">{entry.title}</h2>
            <p className="mt-1 text-sm text-text-secondary">{entry.summary}</p>
            <div className="mt-3 flex gap-2">
              {entry.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-md bg-bg px-2 py-1 text-xs text-text-muted"
                >
                  #{tag}
                </span>
              ))}
            </div>
          </Link>
        ))}
      </div>

      {entries.length === 0 && (
        <div className="mt-16 text-center">
          <p className="text-text-muted">还没有日志，即将开始记录...</p>
        </div>
      )}
    </div>
  );
}
