"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpenCheck, Brain, Gauge, History, Home, Timer } from "lucide-react";

import { Badge, BrandLogo, cn } from "@/components/ui";

const navItems = [
  { href: "/history", label: "训练历史", icon: History },
  { href: "/ability", label: "能力画像", icon: Brain },
  { href: "/practice", label: "今日训练", icon: Home },
  { href: "/wrong-book", label: "错题本", icon: Gauge },
  { href: "/mock", label: "模拟面试", icon: Timer },
];

export function AppHeader() {
  const pathname = usePathname();
  const isPractice = pathname === "/" || pathname.startsWith("/practice");

  return (
    <header className="sticky top-0 z-40 border-b border-line/80 bg-white/90 backdrop-blur">
      <div className="mx-auto flex min-h-16 max-w-7xl flex-col gap-3 px-4 py-3 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:gap-4 lg:py-0">
        <div className="flex items-center justify-between gap-3">
          <Link href="/practice" className="flex min-w-0 items-center gap-3">
            <BrandLogo variant="mark" className="h-9 w-9 shrink-0 rounded-2xl border border-line bg-white p-1.5 shadow-soft" priority />
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold text-ink">大厂面试训练 Agent</span>
              <span className="hidden text-xs text-muted sm:block">AI 面试训练闭环系统</span>
            </span>
          </Link>
          <Badge className="shrink-0 border-brand/20 bg-brandSoft text-brand lg:hidden">AI 面试训练</Badge>
        </div>

        <nav className="flex items-center gap-2 overflow-x-auto pb-1 lg:pb-0" aria-label="主导航">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || (item.href !== "/practice" && pathname.startsWith(item.href)) || (item.href === "/practice" && isPractice);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "inline-flex h-10 shrink-0 items-center gap-2 rounded-control px-3 text-sm font-semibold transition",
                  active ? "bg-brand text-white shadow-button" : "border border-line bg-white text-muted hover:border-brand/30 hover:bg-brandMist hover:text-ink"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="hidden items-center gap-3 lg:flex">
          <Badge className="border-brand/20 bg-brandSoft text-brand">AI 面试训练</Badge>
          {!isPractice ? (
            <Link
              href="/practice"
              className="inline-flex h-10 items-center justify-center gap-2 rounded-control border border-line bg-white px-3 text-sm font-semibold text-ink shadow-soft transition hover:border-brand/30 hover:bg-brandMist"
            >
              <BookOpenCheck className="h-4 w-4 text-brand" />
              返回今日训练
            </Link>
          ) : null}
        </div>
      </div>
    </header>
  );
}
