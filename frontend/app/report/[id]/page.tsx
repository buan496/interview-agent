"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BookOpen, CheckCircle2, ClipboardList, Loader2, Target, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Bar, BarChart, CartesianGrid, PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Badge, Panel, cn } from "@/components/ui";
import { getReport } from "@/lib/report-api";
import type { SessionReport } from "@/lib/types";

type ReportQuestion = SessionReport["questions"][number];

export default function ReportPage() {
  const params = useParams<{ id: string }>();
  const report = useQuery({ queryKey: ["report", params.id], queryFn: () => getReport(params.id) });

  if (report.isLoading) {
    return (
      <main className="grid min-h-[60vh] place-items-center">
        <Loader2 className="h-6 w-6 animate-spin text-brand" />
      </main>
    );
  }

  if (!report.data) {
    return <main className="p-6 text-sm text-muted">报告还没有准备好。</main>;
  }

  const data = report.data;
  const focusItems = buildFocusItems(data);
  const strongest = [...data.questions].sort((a, b) => b.score - a.score)[0];
  const weakest = [...data.questions].sort((a, b) => a.score - b.score)[0];

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-3xl">
          <Badge>{data.mode === "mock" ? "模拟面试" : "单题训练"}</Badge>
          <h1 className="mt-3 text-2xl font-semibold">复盘工作台</h1>
          <p className="mt-2 text-sm leading-6 text-muted">{data.summary}</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-4xl font-semibold text-brand">{data.overall_score}</div>
            <div className="text-xs text-muted">总分</div>
          </div>
          <Link
            className="inline-flex h-10 items-center justify-center gap-2 rounded bg-brand px-4 text-sm font-medium text-white hover:bg-[#17675c]"
            href="/practice"
          >
            <ArrowRight className="h-4 w-4" />
            去今日训练
          </Link>
        </div>
      </header>

      <section className="mt-5 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <Panel className="p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold">下一轮优先补齐</h2>
              <p className="mt-1 text-xs text-muted">今日训练会优先从这些薄弱点继续推进。</p>
            </div>
            <Badge>{focusItems.length} 项行动</Badge>
          </div>
          <div className="mt-4 grid gap-3">
            {focusItems.length > 0 ? (
              focusItems.map((item) => (
                <div key={`${item.questionTitle}-${item.text}`} className="grid gap-2 rounded border border-line bg-panel p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge className={cn(item.kind === "gap" && "border-[#d69e2e] text-[#7a4f01]", item.kind === "action" && "border-brand text-brand")}>
                      {item.kind === "gap" ? "缺口" : "行动"}
                    </Badge>
                    <span className="text-xs text-muted">{item.questionTitle}</span>
                  </div>
                  <p className="text-sm leading-6">{item.text}</p>
                </div>
              ))
            ) : (
              <p className="rounded border border-line bg-panel p-3 text-sm text-muted">本次报告没有发现明确薄弱点，可以继续做一组模拟面试校准能力画像。</p>
            )}
          </div>
        </Panel>

        <Panel className="p-4">
          <h2 className="text-sm font-semibold">本轮概览</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
            <Metric label="题目数" value={data.questions.length.toString()} icon={ClipboardList} />
            <Metric label="最高分" value={strongest ? `${strongest.score}` : "-"} detail={strongest?.title} icon={CheckCircle2} />
            <Metric label="最低分" value={weakest ? `${weakest.score}` : "-"} detail={weakest?.title} icon={TriangleAlert} />
          </div>
        </Panel>
      </section>

      <section className="mt-5 grid gap-4 lg:grid-cols-2">
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
          <h2 className="text-sm font-semibold">单题得分</h2>
          <ResponsiveContainer width="100%" height="90%">
            <BarChart data={data.questions.map((item, index) => ({ ...item, label: `Q${index + 1}` }))}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" />
              <YAxis domain={[0, 100]} />
              <Tooltip />
              <Bar dataKey="score" fill="#3b5f7a" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </section>

      <section className="mt-5 grid gap-3">
        {data.questions.map((item, index) => (
          <QuestionReview key={item.sq_id} index={index} item={item} />
        ))}
      </section>
    </main>
  );
}

function QuestionReview({ item, index }: { item: ReportQuestion; index: number }) {
  return (
    <Panel className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge>Q{index + 1}</Badge>
          <Badge>{qtypeLabel(item.qtype)}</Badge>
          <Badge className={scoreBadgeClass(item.score)}>{item.score}</Badge>
          <Badge>{masteryLabel(item.mastery)}</Badge>
        </div>
        <div className="flex flex-wrap gap-1">
          {item.tags.map((tag) => (
            <Badge key={tag.id}>{tag.name}</Badge>
          ))}
        </div>
      </div>

      <h2 className="mt-3 text-base font-semibold">{item.title}</h2>
      <p className="mt-3 text-sm leading-6 text-muted">{item.feedback}</p>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <DiagnosticList title="做得好的点" icon={CheckCircle2} items={item.strengths} empty="本题暂未提取明确优势。" />
        <DiagnosticList title="缺失要点" icon={Target} items={item.missing_points} empty="本题暂未提取缺失要点。" tone="warning" />
        <DiagnosticList title="表达问题" icon={TriangleAlert} items={item.expression_issues} empty="本题暂未提取表达问题。" tone="warning" />
        <DiagnosticList title="下一步动作" icon={ClipboardList} items={item.action_items} empty="本题暂未生成行动项。" />
      </div>

      <details className="mt-4 rounded border border-line bg-panel p-3 text-sm">
        <summary className="cursor-pointer font-medium">
          <BookOpen className="mr-2 inline h-4 w-4 align-[-3px]" />
          参考答案
        </summary>
        <p className="mt-2 whitespace-pre-wrap leading-6 text-muted">{item.ideal_answer}</p>
      </details>
    </Panel>
  );
}

function DiagnosticList({
  title,
  icon: Icon,
  items,
  empty,
  tone = "default",
}: {
  title: string;
  icon: typeof CheckCircle2;
  items: string[];
  empty: string;
  tone?: "default" | "warning";
}) {
  return (
    <div className="rounded border border-line bg-panel p-3">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Icon className={cn("h-4 w-4", tone === "warning" ? "text-[#a16207]" : "text-brand")} />
        {title}
      </div>
      {items.length > 0 ? (
        <ul className="mt-2 grid gap-2 text-sm leading-6 text-muted">
          {items.map((item) => (
            <li key={item} className="flex gap-2">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-muted">{empty}</p>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  detail,
  icon: Icon,
}: {
  label: string;
  value: string;
  detail?: string;
  icon: typeof ClipboardList;
}) {
  return (
    <div className="rounded border border-line bg-panel p-3">
      <div className="flex items-center gap-2 text-xs text-muted">
        <Icon className="h-4 w-4 text-brand" />
        {label}
      </div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
      {detail ? <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">{detail}</p> : null}
    </div>
  );
}

function buildFocusItems(data: SessionReport) {
  return data.questions.flatMap((question) => [
    ...question.missing_points.slice(0, 2).map((text) => ({ kind: "gap" as const, text, questionTitle: question.title })),
    ...question.action_items.slice(0, 2).map((text) => ({ kind: "action" as const, text, questionTitle: question.title })),
  ]);
}

function qtypeLabel(value: string) {
  const labels: Record<string, string> = {
    knowledge: "知识题",
    coding: "编码题",
    system_design: "系统设计",
    behavioral: "行为题",
  };
  return labels[value] ?? value;
}

function masteryLabel(value: string) {
  const labels: Record<string, string> = {
    pass: "通过",
    weak: "薄弱",
    fail: "未通过",
  };
  return labels[value] ?? value;
}

function scoreBadgeClass(score: number) {
  if (score >= 80) return "border-brand text-brand";
  if (score >= 60) return "border-[#d69e2e] text-[#7a4f01]";
  return "border-[#dc2626] text-[#991b1b]";
}
