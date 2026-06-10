"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, Play, Timer } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button, Panel } from "@/components/ui";
import { createSession, getMetadata } from "@/lib/api";

export default function MockPage() {
  const router = useRouter();
  const metadata = useQuery({ queryKey: ["metadata"], queryFn: getMetadata });
  const [companyId, setCompanyId] = useState("");
  const [positionId, setPositionId] = useState("");
  const start = useMutation({
    mutationFn: () =>
      createSession({
        mode: "mock",
        company_id: companyId ? Number(companyId) : undefined,
        position_id: positionId ? Number(positionId) : undefined
      }),
    onSuccess: (data) => router.push(`/session/${data.session_id}`)
  });

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <section>
          <div className="flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded bg-brand text-white">
              <Timer className="h-5 w-5" />
            </span>
            <div>
              <h1 className="text-2xl font-semibold">45 分钟模拟面试</h1>
              <p className="mt-1 text-sm text-muted">系统按题型配比安排 6 题，每题最多追问 3 层，结束后生成能力报告。</p>
            </div>
          </div>
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            {[
              ["15%", "项目与行为"],
              ["35%", "基础知识"],
              ["50%", "编码与系统设计"]
            ].map(([value, label]) => (
              <Panel key={label} className="p-5">
                <div className="text-2xl font-semibold text-brand">{value}</div>
                <div className="mt-1 text-sm text-muted">{label}</div>
              </Panel>
            ))}
          </div>
        </section>

        <Panel className="p-5">
          <h2 className="font-semibold">面试设置</h2>
          <div className="mt-4 grid gap-4">
            <label className="grid gap-1 text-sm">
              <span className="text-muted">目标公司</span>
              <select className="h-10 rounded border border-line bg-white px-3" value={companyId} onChange={(event) => setCompanyId(event.target.value)}>
                <option value="">随机公司</option>
                {metadata.data?.companies.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <label className="grid gap-1 text-sm">
              <span className="text-muted">目标岗位</span>
              <select className="h-10 rounded border border-line bg-white px-3" value={positionId} onChange={(event) => setPositionId(event.target.value)}>
                <option value="">随机岗位</option>
                {metadata.data?.positions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            {start.isError ? <p className="text-sm text-accent">当前筛选的题目不足，请放宽公司或岗位条件。</p> : null}
            <Button onClick={() => start.mutate()} disabled={start.isPending}>
              {start.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              开始模拟面试
            </Button>
          </div>
        </Panel>
      </div>
    </main>
  );
}
