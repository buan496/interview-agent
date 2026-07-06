"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Play, ShieldCheck, Target, Timer } from "lucide-react";
import { useRouter } from "next/navigation";

import { Badge, Button, Panel } from "@/components/ui";
import { getMetadata } from "@/lib/question-api";
import { createSession } from "@/lib/session-api";

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
        position_id: positionId ? Number(positionId) : undefined,
      }),
    onSuccess: (data) => router.push(`/session/${data.session_id}`),
  });

  return (
    <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <section className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge className="border-brand/30 bg-[#edf7f4] text-brand">模拟面试</Badge>
            <Badge>45 分钟</Badge>
            <Badge>6 道题</Badge>
          </div>
          <h1 className="mt-3 text-2xl font-semibold text-ink">用一次完整 Session 检验连续作答能力</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            系统会按题型比例安排多题训练，每题最多 3 轮追问。结束后生成结构化报告，并沉淀错题和能力画像。
          </p>

          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <FocusBlock icon={Target} value="15%" label="项目与行为" detail="表达结构、复盘能力、业务理解" />
            <FocusBlock icon={ShieldCheck} value="35%" label="基础知识" detail="概念准确性、边界条件、常见误区" />
            <FocusBlock icon={CheckCircle2} value="50%" label="编码与系统设计" detail="方案拆解、复杂度、工程取舍" />
          </div>

          <div className="mt-6 rounded border border-line bg-white p-4 shadow-soft">
            <div className="flex items-center gap-2 text-sm font-semibold text-ink">
              <Timer className="h-4 w-4 text-brand" />
              本轮流程
            </div>
            <div className="mt-4 grid gap-3 text-sm text-muted md:grid-cols-3">
              <Step index="1" title="抽题" detail="按目标公司、岗位和题型比例生成题组。" />
              <Step index="2" title="追问" detail="AI 根据回答深度决定是否继续追问。" />
              <Step index="3" title="报告" detail="输出评分、薄弱点、错题和下一步训练建议。" />
            </div>
          </div>
        </div>

        <Panel className="h-fit p-5">
          <h2 className="font-semibold text-ink">面试设置</h2>
          <p className="mt-1 text-sm leading-6 text-muted">不选择条件时，系统会从全量题库中随机抽题。</p>
          <div className="mt-4 grid gap-4">
            <label className="grid gap-1 text-sm">
              <span className="text-muted">目标公司</span>
              <select className="h-10 rounded border border-line bg-white px-3" value={companyId} onChange={(event) => setCompanyId(event.target.value)}>
                <option value="">随机公司</option>
                {metadata.data?.companies.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="grid gap-1 text-sm">
              <span className="text-muted">目标岗位</span>
              <select className="h-10 rounded border border-line bg-white px-3" value={positionId} onChange={(event) => setPositionId(event.target.value)}>
                <option value="">随机岗位</option>
                {metadata.data?.positions.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            {start.isError ? <p className="text-sm text-accent">当前筛选条件下题目不足，请放宽公司或岗位条件。</p> : null}
            <Button onClick={() => start.mutate()} disabled={start.isPending}>
              {start.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              开始模拟面试
            </Button>
          </div>
        </Panel>
      </section>
    </main>
  );
}

function FocusBlock({
  icon: Icon,
  value,
  label,
  detail,
}: {
  icon: React.ComponentType<{ className?: string }>;
  value: string;
  label: string;
  detail: string;
}) {
  return (
    <Panel className="p-5">
      <Icon className="h-5 w-5 text-brand" />
      <div className="mt-3 text-2xl font-semibold text-brand">{value}</div>
      <div className="mt-1 text-sm font-medium text-ink">{label}</div>
      <p className="mt-2 text-sm leading-6 text-muted">{detail}</p>
    </Panel>
  );
}

function Step({ index, title, detail }: { index: string; title: string; detail: string }) {
  return (
    <div>
      <div className="flex items-center gap-2 font-medium text-ink">
        <span className="grid h-6 w-6 place-items-center rounded bg-brand text-xs text-white">{index}</span>
        {title}
      </div>
      <p className="mt-2 leading-6">{detail}</p>
    </div>
  );
}
