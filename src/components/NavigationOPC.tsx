"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/opc", label: "首页" },
  { href: "/opc/dashboard", label: "财务看板" },
  { href: "/opc/log", label: "执行日志" },
  { href: "/opc/business", label: "业务线" },
  { href: "/opc/about", label: "关于" },
];

export default function NavigationOPC() {
  const pathname = usePathname();

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-[#1e1e2e] bg-[#08080c]/80 backdrop-blur-md">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="flex h-16 items-center justify-between">
          <Link href="/opc" className="flex items-center gap-3">
            <span className="text-xs font-bold tracking-[3px] text-[#818cf8] border border-[#818cf8]/30 bg-[#818cf8]/10 rounded-full px-3 py-1">OPC</span>
            <span className="text-sm text-text-secondary">一人公司 × AI → 年赚千万</span>
          </Link>

          <div className="flex items-center gap-1">
            {navItems.map((item) => {
              const isActive =
                item.href === "/opc"
                  ? pathname === "/opc"
                  : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`rounded-lg px-3 py-2 text-sm transition-colors ${
                    isActive
                      ? "bg-[#818cf8]/10 text-[#818cf8] font-medium"
                      : "text-text-secondary hover:text-text hover:bg-bg-card"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
}
