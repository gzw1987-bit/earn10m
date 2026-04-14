import Link from "next/link";
import { notFound } from "next/navigation";
import { getLogEntries } from "@/data/finance";

export function generateStaticParams() {
  return getLogEntries().map((entry) => ({ slug: entry.slug }));
}

export default async function LogDetailPage(
  props: PageProps<"/log/[slug]">
) {
  const { slug } = await props.params;
  const logEntries = getLogEntries();
  const entry = logEntries.find((e) => e.slug === slug);

  if (!entry) {
    notFound();
  }

  const renderContent = (content: string) => {
    return content.split("\n").map((line, i) => {
      if (line.startsWith("# ")) {
        return (
          <h1 key={i} className="text-3xl font-bold mt-8 mb-4">
            {line.slice(2)}
          </h1>
        );
      }
      if (line.startsWith("## ")) {
        return (
          <h2 key={i} className="text-xl font-semibold mt-6 mb-3">
            {line.slice(3)}
          </h2>
        );
      }
      if (line.startsWith("- ")) {
        return (
          <li key={i} className="ml-4 text-text-secondary">
            {line.slice(2)}
          </li>
        );
      }
      if (/^\d+\.\s/.test(line)) {
        return (
          <li key={i} className="ml-4 text-text-secondary list-decimal">
            {line.replace(/^\d+\.\s/, "")}
          </li>
        );
      }
      if (line.startsWith("---")) {
        return <hr key={i} className="my-6 border-border" />;
      }
      if (line.trim() === "") {
        return <div key={i} className="h-2" />;
      }
      const parts = line.split(/(\*\*[^*]+\*\*)/);
      return (
        <p key={i} className="text-text-secondary leading-relaxed">
          {parts.map((part, j) =>
            part.startsWith("**") && part.endsWith("**") ? (
              <strong key={j} className="text-text font-semibold">
                {part.slice(2, -2)}
              </strong>
            ) : (
              part
            )
          )}
        </p>
      );
    });
  };

  return (
    <div className="mx-auto max-w-3xl px-4 sm:px-6 py-12">
      <Link
        href="/log"
        className="text-sm text-text-muted hover:text-text transition-colors"
      >
        ← 返回日志列表
      </Link>

      <div className="mt-6 flex items-center gap-3">
        <span className="text-sm text-text-muted font-mono">{entry.date}</span>
        <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">
          {entry.mood}
        </span>
      </div>

      <div className="mt-4 flex gap-2">
        {entry.tags.map((tag) => (
          <span
            key={tag}
            className="rounded-md bg-bg-card px-2 py-1 text-xs text-text-muted"
          >
            #{tag}
          </span>
        ))}
      </div>

      <article className="mt-8">{renderContent(entry.content)}</article>
    </div>
  );
}
