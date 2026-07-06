"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ClipboardList,
  FileText,
  Gauge,
  Loader2,
  RotateCcw,
  Target,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Bar, BarChart, CartesianGrid, PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { AppButton, AppCard, Badge, BrandLogo, PageShell, cn } from "@/components/ui";
import { getReport } from "@/lib/report-api";
import type { SessionReport } from "@/lib/types";

type ReportQuestion = SessionReport["questions"][number];

export default function ReportPage() {
  const params = useParams<{ id: string }>();
  const report = useQuery({ queryKey: ["report", params.id], queryFn: () => getReport(params.id) });

  if (report.isLoading) {
    return (
      <PageShell className="grid place-items-center">
        <AppCard className="grid min-h-48 min-w-72 place-items-center p-8 text-sm text-muted">
          <Loader2 className="h-6 w-6 animate-spin text-brand" />
          <span className="mt-3">正在生成复盘报告...</span>
        </AppCard>
      </PageShell>
    );
  }

  if (report.isError) {
    return (
      <PageShell className="grid place-items-center">
        <AppCard className="max-w-xl p-8 text-center">
          <TriangleAlert className="mx-auto h-8 w-8 text-accent" />
          <h1 className="mt-4 text-2xl font-semibold text-ink">报告暂时无法读取</h1>
          <p className="mt-3 text-sm leading-6 text-muted">可能是报告还在生成，或当前训练记录不可用。你可以先返回今日训练继续推进。</p>
          <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
            <AppButton type="button" variant="secondary" onClick={() => window.location.reload()}>
              <RotateCcw className="h-4 w-4" />
              重新加载
            </AppButton>
            <LinkButton href="/practice" variant="primary">
              <ArrowRight className="h-4 w-4" />
              去今日训练
            </LinkButton>
          </div>
        </AppCard>
      </PageShell>
    );
  }

  if (!report.data) {
    return (
      <PageShell className="grid place-items-center">
        <AppCard className="max-w-xl p-8 text-center">
          <FileText className="mx-auto h-8 w-8 text-brand" />
          <h1 className="mt-4 text-2xl font-semibold text-ink">报告还没有准备好</h1>
          <p className="mt-3 text-sm leading-6 text-muted">完成训练评分后，这里会展示整体表现、能力短板、题目复盘和下一步建议。</p>
          <div className="mt-6 flex justify-center">
            <LinkButton href="/practice" variant="primary">
              <ArrowRight className="h-4 w-4" />
              去今日训练
            </LinkButton>
          </div>
        </AppCard>
      </PageShell>
    );
  }

  const data = report.data;
  return <ReportWorkbench data={data} sessionId={params.id} />;
}

function ReportWorkbench({ data, sessionId }: { data: SessionReport; sessionId: string }) {
  const focusItems = useMemo(() => buildFocusItems(data), [data]);
  const strongest = useMemo(() => [...data.questions].sort((a, b) => b.score - a.score)[0], [data.questions]);
  const weakest = useMemo(() => [...data.questions].sort((a, b) => a.score - b.score)[0], [data.questions]);
  const weakQuestions = data.questions.filter((item) => item.score < 80 || item.mastery !== "pass");
  const completionRate = data.questions.length ? Math.round((data.questions.filter((item) => item.score != null).length / data.questions.length) * 100) : 0;
  const endedText = formatDateTime(data.ended_at ?? data.started_at);

  return (
    <PageShell className="grid gap-6 pb-12">
      <AppCard className="relative overflow-hidden p-6 sm:p-8">
        <div className="absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-brandSoft to-transparent" />
        <div className="relative grid gap-6 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <BrandLogo variant="mark" className="h-11 w-11 rounded-2xl border border-line bg-white p-1.5 shadow-soft" priority />
              <Badge className="border-brand/20 bg-brandSoft text-brand">{data.mode === "mock" ? "模拟面试" : "单题训练"}</Badge>
              <Badge>{endedText}</Badge>
            </div>
            <h1 className="mt-7 text-3xl font-semibold leading-tight text-ink sm:text-4xl">本轮面试报告</h1>
            <p className="mt-4 max-w-3xl text-base leading-8 text-muted">{data.summary}</p>
          </div>

          <div className="grid gap-4 rounded-3xl border border-line bg-white/85 p-5 shadow-soft sm:min-w-[320px]">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-brand">综合得分</p>
                <div className="mt-1 text-5xl font-semibold text-ink">{data.overall_score}</div>
              </div>
              <Badge className={scoreBadgeClass(data.overall_score)}>{scoreLevel(data.overall_score)}</Badge>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <LinkButton href="/practice" variant="primary">
                <ArrowRight className="h-4 w-4" />
                去今日训练
              </LinkButton>
              <LinkButton href={`/session/${sessionId}`} variant="secondary">
                <ArrowLeft className="h-4 w-4" />
                返回答题页
              </LinkButton>
            </div>
          </div>
        </div>
      </AppCard>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={Gauge} label="综合得分" value={`${data.overall_score}`} helper={scoreLevel(data.overall_score)} />
        <MetricCard icon={CheckCircle2} label="答题完成度" value={`${completionRate}%`} helper={`${data.questions.length} 道题已复盘`} />
        <MetricCard icon={TriangleAlert} label="薄弱知识点" value={`${weakQuestions.length}`} helper={weakest ? weakest.title : "暂无明显短板"} />
        <MetricCard icon={ClipboardList} label="下一步训练" value={`${focusItems.length}`} helper="缺口与行动项" />
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="grid gap-5">
          <AppCard className="p-5 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-brand">能力诊断</p>
                <h2 className="mt-2 text-2xl font-semibold text-ink">这轮训练暴露了什么</h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">结合雷达分、题目得分和行动项判断下一轮训练优先级。</p>
              </div>
              <Badge className="border-brand/20 bg-brandSoft text-brand">{data.radar.length} 个能力维度</Badge>
            </div>

            <div className="mt-6 grid gap-5 lg:grid-cols-2">
              <div className="h-80 rounded-3xl border border-line bg-white p-4">
                <h3 className="text-sm font-semibold text-ink">能力雷达</h3>
                <ResponsiveContainer width="100%" height="90%">
                  <RadarChart data={data.radar}>
                    <PolarGrid stroke="#d7e4f7" />
                    <PolarAngleAxis dataKey="tag" tick={{ fontSize: 11, fill: "#667085" }} />
                    <Radar dataKey="avg_score" stroke="#2563eb" fill="#2563eb" fillOpacity={0.18} />
                    <Tooltip />
                  </RadarChart>
                </ResponsiveContainer>
              </div>

              <div className="h-80 rounded-3xl border border-line bg-white p-4">
                <h3 className="text-sm font-semibold text-ink">单题得分</h3>
                <ResponsiveContainer width="100%" height="90%">
                  <BarChart data={data.questions.map((item, index) => ({ ...item, label: `Q${index + 1}` }))}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#d7e4f7" />
                    <XAxis dataKey="label" tick={{ fill: "#667085" }} />
                    <YAxis domain={[0, 100]} tick={{ fill: "#667085" }} />
                    <Tooltip />
                    <Bar dataKey="score" fill="#2563eb" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {buildAbilityNotes(data).map((item) => (
                <AbilityNote key={item.title} title={item.title} score={item.score} description={item.description} />
              ))}
            </div>
          </AppCard>

          <section className="grid gap-4">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-brand">题目复盘</p>
                <h2 className="mt-2 text-2xl font-semibold text-ink">逐题拆解表现</h2>
              </div>
              <Badge>{data.questions.length} 道题</Badge>
            </div>
            {data.questions.length > 0 ? (
              data.questions.map((item, index) => <QuestionReview key={item.sq_id} index={index} item={item} />)
            ) : (
              <AppCard className="p-8 text-center text-sm text-muted">本次报告没有题目明细。</AppCard>
            )}
          </section>
        </div>

        <aside className="grid h-fit gap-5">
          <AppCard className="p-5">
            <p className="text-sm font-semibold text-brand">下一轮优先补齐</p>
            <h2 className="mt-2 text-xl font-semibold text-ink">训练建议</h2>
            <p className="mt-2 text-sm leading-6 text-muted">今日训练会优先从这些薄弱点继续推进。</p>
            <div className="mt-5 grid gap-3">
              {focusItems.length > 0 ? (
                focusItems.slice(0, 6).map((item) => (
                  <FocusItem key={`${item.questionTitle}-${item.text}`} kind={item.kind} text={item.text} questionTitle={item.questionTitle} />
                ))
              ) : (
                <p className="rounded-2xl border border-line bg-brandMist p-4 text-sm leading-6 text-muted">本次报告没有发现明确薄弱点，可以继续做一组模拟面试校准能力画像。</p>
              )}
            </div>
          </AppCard>

          <AppCard className="p-5">
            <p className="text-sm font-semibold text-brand">本轮概览</p>
            <div className="mt-5 grid gap-3">
              <SideMetric label="最高分" value={strongest ? `${strongest.score}` : "-"} detail={strongest?.title} />
              <SideMetric label="最低分" value={weakest ? `${weakest.score}` : "-"} detail={weakest?.title} />
              <SideMetric label="薄弱题目" value={`${weakQuestions.length}`} detail="建议纳入错题复盘" />
            </div>
          </AppCard>

          <AppCard className="p-5">
            <p className="text-sm font-semibold text-brand">接下来做什么</p>
            <div className="mt-5 grid gap-3">
              <NextAction title="继续今日训练" description="回到训练台，按系统推荐继续补齐短板。" href="/practice" primary />
              <NextAction title="复盘错题" description="集中处理低分题和缺失要点。" href="/wrong-book" />
              <NextAction title="再做一轮模拟面试" description="用完整流程校准表达和追问应对。" href="/mock" />
            </div>
          </AppCard>
        </aside>
      </section>
    </PageShell>
  );
}

function QuestionReview({ item, index }: { item: ReportQuestion; index: number }) {
  const shouldReview = item.score < 80 || item.mastery !== "pass" || item.missing_points.length > 0;
  return (
    <AppCard className="p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge>Q{index + 1}</Badge>
          <Badge>{qtypeLabel(item.qtype)}</Badge>
          <Badge>难度 {item.difficulty}</Badge>
          <Badge className={scoreBadgeClass(item.score)}>{item.score}</Badge>
          <Badge>{masteryLabel(item.mastery)}</Badge>
        </div>
        <div className="flex flex-wrap gap-2">
          {item.tags.map((tag) => (
            <Badge key={tag.id} className="border-brand/20 bg-brandSoft text-brand">
              {tag.name}
            </Badge>
          ))}
        </div>
      </div>

      <h3 className="mt-5 text-xl font-semibold leading-8 text-ink">{item.title}</h3>

      <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="grid gap-4">
          <ReviewBlock title="AI 评价">
            <p className="whitespace-pre-wrap">{item.feedback}</p>
          </ReviewBlock>
          <div className="grid gap-4 md:grid-cols-2">
            <DiagnosticList title="做得好的点" icon={CheckCircle2} items={item.strengths} empty="本题暂未提取明确优势。" />
            <DiagnosticList title="缺失要点" icon={Target} items={item.missing_points} empty="本题暂未提取缺失要点。" tone="warning" />
            <DiagnosticList title="表达问题" icon={TriangleAlert} items={item.expression_issues} empty="本题暂未提取表达问题。" tone="warning" />
            <DiagnosticList title="下一步动作" icon={ClipboardList} items={item.action_items} empty="本题暂未生成行动项。" />
          </div>
          <details className="rounded-3xl border border-line bg-brandMist p-4 text-sm">
            <summary className="cursor-pointer font-semibold text-ink">
              <BookOpen className="mr-2 inline h-4 w-4 align-[-3px] text-brand" />
              参考答案
            </summary>
            <p className="mt-3 whitespace-pre-wrap leading-6 text-muted">{item.ideal_answer}</p>
          </details>
        </div>

        <div className="grid content-start gap-3">
          <ScorePanel label="得分" value={`${item.score}`} />
          <ScorePanel label="掌握度" value={masteryLabel(item.mastery)} />
          <div className={cn("rounded-3xl border p-4", shouldReview ? "border-[#f0d2c6] bg-[#fff6f2]" : "border-line bg-brandMist")}>
            <p className="text-sm font-semibold text-ink">{shouldReview ? "建议加入错题复盘" : "保持当前掌握度"}</p>
            <p className="mt-2 text-sm leading-6 text-muted">
              {shouldReview ? "本题存在低分、薄弱掌握或缺失要点，建议在下一轮训练中继续追问。" : "本题表现稳定，可把训练资源优先放到更薄弱题目。"}
            </p>
          </div>
        </div>
      </div>
    </AppCard>
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
    <div className="rounded-3xl border border-line bg-white p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-ink">
        <Icon className={cn("h-4 w-4", tone === "warning" ? "text-[#a16207]" : "text-brand")} />
        {title}
      </div>
      {items.length > 0 ? (
        <ul className="mt-3 grid gap-2 text-sm leading-6 text-muted">
          {items.map((item) => (
            <li key={item} className="flex gap-2">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm leading-6 text-muted">{empty}</p>
      )}
    </div>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  helper,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  helper: string;
}) {
  return (
    <AppCard className="p-5">
      <div className="flex items-center gap-2 text-sm font-semibold text-muted">
        <Icon className="h-4 w-4 text-brand" />
        {label}
      </div>
      <div className="mt-3 truncate text-3xl font-semibold text-ink">{value}</div>
      <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted">{helper}</p>
    </AppCard>
  );
}

function AbilityNote({ title, score, description }: { title: string; score: number | null; description: string }) {
  return (
    <div className="rounded-3xl border border-line bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-ink">{title}</p>
        <span className="text-sm font-semibold text-brand">{score == null ? "--" : Math.round(score)}</span>
      </div>
      <p className="mt-2 text-sm leading-6 text-muted">{description}</p>
    </div>
  );
}

function FocusItem({ kind, text, questionTitle }: { kind: "gap" | "action"; text: string; questionTitle: string }) {
  return (
    <div className="rounded-3xl border border-line bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge className={cn(kind === "gap" && "border-[#d69e2e] bg-[#fff8e5] text-[#7a4f01]", kind === "action" && "border-brand/20 bg-brandSoft text-brand")}>
          {kind === "gap" ? "缺口" : "行动"}
        </Badge>
        <span className="line-clamp-1 text-xs text-muted">{questionTitle}</span>
      </div>
      <p className="mt-3 text-sm leading-6 text-ink">{text}</p>
    </div>
  );
}

function ReviewBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-3xl border border-line bg-white p-4">
      <h4 className="text-sm font-semibold text-ink">{title}</h4>
      <div className="mt-2 text-sm leading-6 text-muted">{children}</div>
    </section>
  );
}

function ScorePanel({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-3xl border border-line bg-brandMist p-4">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-ink">{value}</p>
    </div>
  );
}

function SideMetric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-3xl border border-line bg-white p-4">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-ink">{value}</p>
      {detail ? <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted">{detail}</p> : null}
    </div>
  );
}

function NextAction({ title, description, href, primary }: { title: string; description: string; href: string; primary?: boolean }) {
  return (
    <Link
      href={href}
      className={cn(
        "group flex items-center justify-between gap-3 rounded-3xl border p-4 transition",
        primary ? "border-brand/20 bg-brand text-white shadow-button hover:bg-brandDeep" : "border-line bg-white text-ink hover:border-brand/30 hover:bg-brandMist"
      )}
    >
      <span>
        <span className="block text-sm font-semibold">{title}</span>
        <span className={cn("mt-1 block text-xs leading-5", primary ? "text-white/80" : "text-muted")}>{description}</span>
      </span>
      <ArrowRight className={cn("h-4 w-4 shrink-0 transition group-hover:translate-x-0.5", primary ? "text-white" : "text-muted")} />
    </Link>
  );
}

function LinkButton({ href, variant, children }: { href: string; variant: "primary" | "secondary"; children: React.ReactNode }) {
  const classes =
    variant === "primary"
      ? "bg-brand text-white shadow-button hover:bg-brandDeep"
      : "border border-line bg-white text-ink shadow-soft hover:border-brand/30 hover:bg-brandMist";
  return (
    <Link href={href} className={cn("inline-flex h-11 items-center justify-center gap-2 rounded-control px-4 text-sm font-semibold transition", classes)}>
      {children}
    </Link>
  );
}

function buildFocusItems(data: SessionReport) {
  return data.questions.flatMap((question) => [
    ...question.missing_points.slice(0, 2).map((text) => ({ kind: "gap" as const, text, questionTitle: question.title })),
    ...question.action_items.slice(0, 2).map((text) => ({ kind: "action" as const, text, questionTitle: question.title })),
  ]);
}

function buildAbilityNotes(data: SessionReport) {
  const radar = new Map(data.radar.map((item) => [item.tag, item.avg_score]));
  const fallbackAvg = data.questions.length ? data.questions.reduce((sum, item) => sum + item.score, 0) / data.questions.length : null;
  const findScore = (keywords: string[]) => {
    const found = [...radar.entries()].find(([tag]) => keywords.some((keyword) => tag.toLowerCase().includes(keyword.toLowerCase())));
    return found?.[1] ?? fallbackAvg;
  };
  return [
    { title: "基础概念", score: findScore(["基础", "knowledge", "redis", "概念"]), description: "看核心原理、边界条件和常见误区是否讲清楚。" },
    { title: "项目表达", score: findScore(["项目", "表达", "behavioral"]), description: "看回答是否有背景、动作、结果和复盘，而不是泛泛描述。" },
    { title: "系统设计", score: findScore(["系统", "design"]), description: "看需求拆解、链路设计、瓶颈和演进方案是否完整。" },
    { title: "Agent / RAG / Tool Use", score: findScore(["agent", "rag", "tool"]), description: "看是否能把 AI 工程关键链路、检索和工具调用讲成体系。" },
    { title: "追问应对", score: fallbackAvg, description: "看面对追问时是否能补齐缺失点，而不是重复原答案。" },
  ];
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

function scoreLevel(score: number) {
  if (score >= 85) return "表现优秀";
  if (score >= 70) return "基础稳定";
  if (score >= 60) return "需要补齐";
  return "优先复盘";
}

function scoreBadgeClass(score: number) {
  if (score >= 80) return "border-brand/20 bg-brandSoft text-brand";
  if (score >= 60) return "border-[#d69e2e] bg-[#fff8e5] text-[#7a4f01]";
  return "border-[#dc2626]/20 bg-[#fff6f2] text-[#991b1b]";
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "完成时间待同步";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
