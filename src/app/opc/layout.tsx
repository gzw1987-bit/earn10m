import NavigationOPC from "@/components/NavigationOPC";

export default function OPCLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <NavigationOPC />
      <main className="flex-1 pt-16">{children}</main>
      <footer className="border-t border-[#1e1e2e] py-8 text-center text-sm text-text-muted">
        <div className="mx-auto max-w-6xl px-4">
          <p>OPC 一人公司 × AI — 从负债360万到年赚千万</p>
          <p className="mt-1">Started: 2026.04.13 | 0 员工 · N 个 AI Agent</p>
        </div>
      </footer>
    </>
  );
}
