"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useParams } from "next/navigation";
import { Bar, BarChart, CartesianGrid, PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Badge, Panel } from "@/components/ui";
import { getReport } from "@/lib/api";

export default function ReportPage() {
  const params = useParams<{ id: string }>();
  const report = useQuery({ queryKey: ["report", params.id], queryFn: () => getReport(params.id) });
  if (report.isLoading) {
    return <main className="grid min-h-[60vh] place-items-center"><Loader2 className="h-6 w-6 animate-spin text-brand" /></main>;
  }
  if (!report.data) {
    return <main className="p-6 text-sm text-muted">报告尚未生成</main>;
  }
  const data = report.data;
  return (
    <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Badge>{data.mode === "mock" ? "模拟面试" : "单题练习"}</Badge>
          <h1 className="mt-3 text-2xl font-semibold">面试报告</h1>
          <p className="mt-1 text-sm text-muted">{data.summary}</p>
        </div>
        <div className="text-right">
          <div className="text-4xl font-semibold text-brand">{data.overall_score}</div>
          <div className="text-xs text-muted">综合得分</div>
        </div>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <Panel className="h-80 p-4">
          <h2 className="text-sm font-semibold">能力雷达</h2>
          <ResponsiveContainer width="100%" height="90%">
            <RadarChart data={data.radar}>
              <PolarGrid />
              <PolarAngleAxis dataKey="tag" tick={{ fontSize: 11 }} />
              <Radar dataKey="avg_score" stroke="#1f7a6d" fill="#1f7a6d" fillOpacity={0.25} />
              <Tooltip />
            </RadarChart>
          </ResponsiveContainer>
        </Panel>
        <Panel className="h-80 p-4">
          <h2 className="text-sm font-semibold">逐题得分</h2>
          <ResponsiveContainer width="100%" height="90%">
            <BarChart data={data.questions.map((item, index) => ({ ...item, label: `第${index + 1}题` }))}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" />
              <YAxis domain={[0, 100]} />
              <Tooltip />
              <Bar dataKey="score" fill="#3b5f7a" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <section className="mt-5 grid gap-3">
        {data.questions.map((item, index) => (
          <Panel key={item.sq_id} className="p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2"><Badge>第 {index + 1} 题</Badge><Badge>{item.qtype}</Badge><Badge>{item.score} 分</Badge></div>
              <span className="text-sm text-muted">{item.mastery}</span>
            </div>
            <h2 className="mt-3 font-semibold">{item.title}</h2>
            <p className="mt-3 text-sm leading-6 text-muted">{item.feedback}</p>
            <details className="mt-3 rounded border border-line bg-panel p-3 text-sm">
              <summary className="cursor-pointer font-medium">查看参考答案</summary>
              <p className="mt-2 whitespace-pre-wrap leading-6 text-muted">{item.ideal_answer}</p>
            </details>
          </Panel>
        ))}
      </section>
    </main>
  );
}
