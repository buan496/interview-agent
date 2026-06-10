"use client";

import { useRouter } from "next/navigation";
import { LogIn } from "lucide-react";

import { Button, Panel } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  return (
    <main className="grid min-h-[calc(100vh-3.5rem)] place-items-center px-4">
      <Panel className="w-full max-w-sm p-6">
        <h1 className="text-xl font-semibold">登录</h1>
        <Button className="mt-5 w-full" onClick={() => router.push("/practice")}>
          <LogIn className="h-4 w-4" />
          进入练习
        </Button>
      </Panel>
    </main>
  );
}

