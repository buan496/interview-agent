import type { Metadata } from "next";

import { AppHeader } from "@/components/app-header";
import { Providers } from "@/components/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "大厂面试训练 Agent",
  description: "AI 面试训练闭环系统",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <Providers>
          <div className="min-h-screen">
            <AppHeader />
            {children}
          </div>
        </Providers>
      </body>
    </html>
  );
}
