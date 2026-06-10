import type { Metadata } from "next";
import Link from "next/link";
import { BookOpenCheck, Gauge, Settings2 } from "lucide-react";

import { Providers } from "@/components/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "大厂面试练习 Agent",
  description: "AI 模拟面试练习平台"
};

const navItems = [
  { href: "/practice", label: "练习", icon: BookOpenCheck },
  { href: "/wrong-book", label: "错题本", icon: Gauge },
  { href: "/admin", label: "审核", icon: Settings2 }
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <Providers>
          <div className="min-h-screen">
            <header className="border-b border-line bg-white/86 backdrop-blur">
              <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
                <Link href="/practice" className="flex items-center gap-2 text-sm font-semibold text-ink">
                  <span className="grid h-8 w-8 place-items-center rounded bg-brand text-white">面</span>
                  <span>大厂面试练习 Agent</span>
                </Link>
                <nav className="flex items-center gap-1">
                  {navItems.map((item) => {
                    const Icon = item.icon;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className="inline-flex h-9 items-center gap-2 rounded px-3 text-sm text-muted transition hover:bg-panel hover:text-ink"
                      >
                        <Icon className="h-4 w-4" />
                        <span className="hidden sm:inline">{item.label}</span>
                      </Link>
                    );
                  })}
                </nav>
              </div>
            </header>
            {children}
          </div>
        </Providers>
      </body>
    </html>
  );
}

