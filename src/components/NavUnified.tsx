"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const navItems = [
  { href: "/", label: "首页" },
  { href: "/dashboard", label: "财务看板" },
  { href: "/log", label: "执行日志" },
  { href: "/business", label: "业务线" },
  { href: "/about", label: "关于" },
];

export default function NavUnified() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-[#1e1e2e] bg-[#08080c]/80 backdrop-blur-md">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="flex h-14 sm:h-16 items-center justify-between">
          <Link href="/" className="flex items-center gap-2 sm:gap-3">
            <span className="text-xs font-bold tracking-[2px] text-[#818cf8] border border-[#818cf8]/30 bg-[#818cf8]/10 rounded-full px-2.5 py-0.5">OPC</span>
            <span className="text-sm font-bold">
              <span className="text-negative">-360万</span>
              <span className="text-text-muted mx-1">→</span>
              <span className="text-accent">千万</span>
            </span>
          </Link>

          {/* 桌面导航 */}
          <div className="hidden sm:flex items-center gap-1">
            {navItems.map((item) => {
              const isActive =
                item.href === "/"
                  ? pathname === "/"
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

          {/* 手机汉堡按钮 */}
          <button
            onClick={() => setOpen(!open)}
            className="sm:hidden flex flex-col gap-1.5 p-2"
            aria-label="菜单"
          >
            <span className={`block w-5 h-0.5 bg-text-secondary transition-transform ${open ? "rotate-45 translate-y-2" : ""}`} />
            <span className={`block w-5 h-0.5 bg-text-secondary transition-opacity ${open ? "opacity-0" : ""}`} />
            <span className={`block w-5 h-0.5 bg-text-secondary transition-transform ${open ? "-rotate-45 -translate-y-2" : ""}`} />
          </button>
        </div>
      </div>

      {/* 手机下拉菜单 */}
      {open && (
        <div className="sm:hidden border-t border-[#1e1e2e] bg-[#08080c]/95 backdrop-blur-md">
          <div className="px-4 py-3 space-y-1">
            {navItems.map((item) => {
              const isActive =
                item.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className={`block rounded-lg px-4 py-3 text-base transition-colors ${
                    isActive
                      ? "bg-[#818cf8]/10 text-[#818cf8] font-medium"
                      : "text-text-secondary hover:text-text hover:bg-[#0d0d14]"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </nav>
  );
}
