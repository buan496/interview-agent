"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BarChart3, BookOpenCheck, Clock3, History, Loader2, PlayCircle, RotateCcw } from "lucide-react";

import { AppButton, AppCard, Badge, BrandLogo, PageShell, cn } from "@/components/ui";
import { getTrainingHistory } from "@/lib/training-history-api";
import type { TrainingHistoryItem } from "@/lib/types";

const modeLabel: Record<string, string> = {
  single: "单题训练",
  mock: "模拟面试",
};

const statusLabel: Record<string, string> = {
  created: "已创建",
  ongoing: "进行中",
  paused: "已暂停",
  finished: "已完成",
  expired: "已超时",
  cancelled: "已取消",
};

export default function HistoryPage() {
  const history = useQuery({ queryKey: ["training-history"], queryFn: () => getTrainingHistory({ limit: 50 }) });
  const items = history.data ?? [];
  const completedCount = items.filter((item) => item.status === "finished").length;
  const activeCount = items.filter((item) => item.next_action === "continue").length;
  const averageScore = averageCompletedScore(items);

  return (
    <PageShell className="grid gap-8 pb-12">
      <section className="grid gap-6 lg:grid-cols-[1fr_360px] lg:items-stretch">
        <AppCard className="relative overflow-hidden p-6 sm:p-8 lg:p-10">
          <div className="absolute inset-x-0 top-0 h-44 bg-gradient-to-b from-brandSoft to-transparent" />
          <div className="relative">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <BrandLogo variant="mark" className="h-11 w-11 rounded-2xl border border-line bg-white p-1.5 shadow-soft" priority />
                <div>
                  <p className="text-sm font-semibold text-brand">训练历史</p>
                  <p className="text-xs text-muted">只展示当前登录用户的训练记录</p>
                </div>
              </div>
              <Badge className="border-brand/20 bg-brandSoft text-brand">user_id 隔离</Badge>
            </div>

            <div className="mt-10 max-w-3xl">
              <h1 className="text-3xl font-semibold leading-tight text-ink sm:text-4xl lg:text-5xl">回看每一轮训练，把复盘沉淀成下一步行动</h1>
              <p className="mt-5 max-w-2xl text-base leading-8 text-muted">
                历史中心按时间倒序汇总你的 Session、报告入口、训练状态、分数摘要和薄弱标签，帮助你从单次训练走向连续提升。
              </p>
            </div>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <LinkButton href="/practice" variant="primary">
                <PlayCircle className="h-4 w-4" />
                去今日训练
              </LinkButton>
              <LinkButton href="/mock" variant="secondary">
                <BookOpenCheck className="h-4 w-4" />
                开始模拟面试
              </LinkButton>
            </div>
          </div>
        </AppCard>

        <AppCard className="p-6">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink">
            <BarChart3 className="h-4 w-4 text-brand" />
            历史概览
          </div>
          <div className="mt-5 grid grid-cols-2 gap-3">
            <SummaryMetric value={`${items.length}`} label="训练记录" helper="当前用户" />
            <SummaryMetric value={`${completedCount}`} label="已完成" helper="可查看报告" />
            <SummaryMetric value={`${activeCount}`} label="进行中" helper="可继续训练" />
            <SummaryMetric value={averageScore ?? "--"} label="平均得分" helper="已完成记录" />
          </div>
        </AppCard>
      </section>

      <AppCard className="p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-brand">Training Timeline</p>
            <h2 className="mt-2 text-2xl font-semibold text-ink">历史训练记录</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">已完成训练进入报告复盘；未完成训练可以从原 Session 继续。</p>
          </div>
          <AppButton variant="secondary" onClick={() => history.refetch()} disabled={history.isFetching}>
            {history.isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
            刷新
          </AppButton>
        </div>

        {history.isLoading ? (
          <div className="grid min-h-[280px] place-items-center text-sm text-muted">
            <Loader2 className="h-6 w-6 animate-spin text-brand" />
          </div>
        ) : null}

        {history.isError ? (
          <div className="mt-6 rounded-3xl border border-line bg-brandMist p-8 text-center">
            <p className="text-base font-semibold text-ink">训练历史加载失败</p>
            <p className="mt-2 text-sm text-muted">可以先返回今日训练，稍后再查看历史记录。</p>
            <div className="mt-5">
              <LinkButton href="/practice" variant="primary">返回今日训练</LinkButton>
            </div>
          </div>
        ) : null}

        {!history.isLoading && !history.isError && items.length === 0 ? (
          <EmptyHistory />
        ) : (
          <div className="mt-6 grid gap-4">
            {items.map((item) => (
              <HistoryItemCard key={item.session_id} item={item} />
            ))}
          </div>
        )}
      </AppCard>
    </PageShell>
  );
}

function HistoryItemCard({ item }: { item: TrainingHistoryItem }) {
  const isFinished = item.next_action === "view_report";
  const actionHref = isFinished && item.report_id ? `/report/${item.report_id}` : `/session/${item.session_id}`;
  const actionLabel = isFinished ? "查看报告" : "继续训练";

  return (
    <article className="rounded-3xl border border-line bg-white p-4 shadow-soft sm:p-5">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px] lg:items-center">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge className="border-brand/20 bg-brandSoft text-brand">{modeLabel[item.mode] ?? item.mode}</Badge>
            <Badge>{statusLabel[item.status] ?? item.status}</Badge>
            <Badge>{item.question_count} 题</Badge>
            {item.overall_score !== null && item.overall_score !== undefined ? (
              <Badge className="border-brand/20 bg-white text-brand">{item.overall_score} 分</Badge>
            ) : null}
          </div>
          <h3 className="mt-3 line-clamp-2 text-lg font-semibold leading-7 text-ink">{item.title}</h3>
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted">
            <span className="inline-flex items-center gap-1">
              <Clock3 className="h-3.5 w-3.5 text-brand" />
              开始：{formatDateTime(item.started_at)}
            </span>
            {item.completed_at ? <span>完成：{formatDateTime(item.completed_at)}</span> : null}
          </div>
          {item.weak_tags.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {item.weak_tags.map((tag) => (
                <Badge key={tag} className="border-accent/20 bg-[#fff7ed] text-accent">
                  {tag}
                </Badge>
              ))}
            </div>
          ) : null}
        </div>

        <div className="flex flex-col gap-3 lg:items-end">
          <p className="text-sm text-muted">{nextActionHint(item)}</p>
          <LinkButton href={actionHref} variant={isFinished ? "primary" : "secondary"} className="w-full lg:w-auto">
            {actionLabel}
            <ArrowRight className="h-4 w-4" />
          </LinkButton>
        </div>
      </div>
    </article>
  );
}

function EmptyHistory() {
  return (
    <div className="mt-6 rounded-3xl border border-line bg-brandMist p-8 text-center">
      <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-white text-brand shadow-soft">
        <History className="h-5 w-5" />
      </div>
      <h3 className="mt-4 text-lg font-semibold text-ink">还没有训练历史</h3>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-muted">先完成一次今日训练或模拟面试，系统会自动把 Session、报告和下一步建议沉淀到这里。</p>
      <div className="mt-5 flex flex-col justify-center gap-3 sm:flex-row">
        <LinkButton href="/practice" variant="primary">去今日训练</LinkButton>
        <LinkButton href="/mock" variant="secondary">开始模拟面试</LinkButton>
      </div>
    </div>
  );
}

function SummaryMetric({ value, label, helper }: { value: string; label: string; helper: string }) {
  return (
    <div className="rounded-2xl border border-line bg-white p-4">
      <div className="truncate text-xl font-semibold text-ink">{value}</div>
      <div className="mt-1 text-sm font-medium text-ink">{label}</div>
      <div className="mt-1 text-xs text-muted">{helper}</div>
    </div>
  );
}

function LinkButton({
  href,
  variant,
  className,
  children,
}: {
  href: string;
  variant: "primary" | "secondary";
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "inline-flex h-11 items-center justify-center gap-2 rounded-control px-4 text-sm font-semibold transition duration-200",
        variant === "primary" && "bg-brand text-white shadow-button hover:-translate-y-0.5 hover:bg-brandDeep",
        variant === "secondary" && "border border-line bg-surface text-ink shadow-soft hover:-translate-y-0.5 hover:border-brand/30 hover:bg-brandMist",
        className
      )}
    >
      {children}
    </Link>
  );
}

function averageCompletedScore(items: TrainingHistoryItem[]) {
  const scores = items.map((item) => item.overall_score).filter((score): score is number => typeof score === "number");
  if (scores.length === 0) return null;
  return String(Math.round(scores.reduce((total, score) => total + score, 0) / scores.length));
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function nextActionHint(item: TrainingHistoryItem) {
  if (item.next_action === "view_report") return "本轮已完成，可进入报告复盘。";
  if (item.next_action === "continue") return "训练仍在进行，可以继续作答。";
  return "建议回到错题本复盘薄弱点。";
}
