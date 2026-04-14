import Navigation from "./Navigation";

export default function OriginalShell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Navigation />
      <main className="flex-1 pt-16">{children}</main>
      <footer className="border-t border-border py-8 text-center text-sm text-text-muted">
        <div className="mx-auto max-w-6xl px-4">
          <p>从负债360万到年赚千万 — 真实记录，不加滤镜</p>
          <p className="mt-1">Started: 2026.04.13</p>
        </div>
      </footer>
    </>
  );
}
