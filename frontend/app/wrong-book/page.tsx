"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, BookOpenCheck, CheckCircle2, Filter, Gauge, Loader2, RotateCcw, Search, Target, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { AppButton, AppCard, Badge, BrandLogo, PageShell, cn } from "@/components/ui";
import { createSession } from "@/lib/session-api";
import { getWrongBook } from "@/lib/wrong-book-api";
import type { WrongBookItem } from "@/lib/types";

type PriorityFilter = "all" | "due" | "low-score" | "repeated";

const priorityOptions: Array<{ value: PriorityFilter; label: string }> = [
  { value: "all", label: "全部错题" },
  { value: "due", label: "待复习" },
  { value: "low-score", label: "低分题" },
  { value: "repeated", label: "反复出错" },
];

const emptyWrongBookItems: WrongBookItem[] = [];

export default function WrongBookPage() {
  const router = useRouter();
  const query = useQuery({ queryKey: ["wrong-book"], queryFn: getWrongBook });
  const [tagFilter, setTagFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>("all");
  const [activeQuestionId, setActiveQuestionId] = useState<number | null>(null);

  const retry = useMutation({
    mutationFn: (questionId: number) => createSession({ mode: "single", question_id: questionId }),
    onMutate: (questionId) => setActiveQuestionId(questionId),
    onSuccess: (data) => router.push(`/session/${data.session_id}`),
    onSettled: () => setActiveQuestionId(null),
  });

  const items = query.data ?? emptyWrongBookItems;
  const tags = useMemo(() => {
    const values = new Map<number, string>();
    items.forEach((item) => item.tags.forEach((tag) => values.set(tag.id, tag.name)));
    return [...values.entries()].map(([id, name]) => ({ id, name }));
  }, [items]);

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      const matchesTag = tagFilter ? item.tags.some((tag) => String(tag.id) === tagFilter) : true;
      const matchesPriority =
        priorityFilter === "all" ||
        (priorityFilter === "due" && Boolean(item.next_review)) ||
        (priorityFilter === "low-score" && (item.last_score ?? 0) < 70) ||
        (priorityFilter === "repeated" && item.fail_count >= 2);
      return matchesTag && matchesPriority;
    });
  }, [items, priorityFilter, tagFilter]);

  const recommendedItem = useMemo(() => pickRecommended(items), [items]);
  const lowScoreCount = items.filter((item) => (item.last_score ?? 0) < 70).length;
  const repeatedCount = items.filter((item) => item.fail_count >= 2).length;
  const dueCount = items.filter((item) => Boolean(item.next_review)).length;

  function resetFilters() {
    setTagFilter("");
    setPriorityFilter("all");
  }

  function startRecommended() {
    if (recommendedItem) {
      retry.mutate(recommendedItem.question_id);
      return;
    }
    router.push("/practice");
  }

  return (
    <PageShell className="grid gap-6 pb-12">
      <AppCard className="relative overflow-hidden p-6 sm:p-8">
        <div className="absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-brandSoft to-transparent" />
        <div className="relative grid gap-6 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <BrandLogo variant="mark" className="h-11 w-11 rounded-2xl border border-line bg-white p-1.5 shadow-soft" priority />
              <Badge className="border-brand/20 bg-brandSoft text-brand">错题复盘</Badge>
              <Badge>{items.length} 道错题</Badge>
            </div>
            <h1 className="mt-7 text-3xl font-semibold leading-tight text-ink sm:text-4xl">把低分题重新拉回训练闭环</h1>
            <p className="mt-4 max-w-3xl text-base leading-8 text-muted">
              围绕 Agent 工程师岗位，把低分题、反复出错题和待复习知识点整理成下一轮训练入口。
            </p>
          </div>

          <div className="grid gap-3 sm:min-w-[340px]">
            <AppButton size="lg" onClick={startRecommended} disabled={retry.isPending || query.isLoading}>
              {retry.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Target className="h-4 w-4" />}
              开始推荐训练
            </AppButton>
            <LinkButton href="/practice" variant="secondary">
              <ArrowLeft className="h-4 w-4" />
              返回今日训练
            </LinkButton>
          </div>
        </div>
      </AppCard>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={BookOpenCheck} label="错题数量" value={`${items.length}`} helper="已沉淀题目" />
        <MetricCard icon={TriangleAlert} label="低分题" value={`${lowScoreCount}`} helper="最近得分低于 70" />
        <MetricCard icon={RotateCcw} label="反复出错" value={`${repeatedCount}`} helper="失败次数不少于 2" />
        <MetricCard icon={Gauge} label="薄弱知识点" value={`${tags.length}`} helper="来自错题标签" />
      </section>

      <section className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <AppCard className="h-fit p-5">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-ink">
              <Filter className="h-4 w-4 text-brand" />
              复盘筛选
            </div>
            <AppButton variant="ghost" className="h-9 px-2" onClick={resetFilters} title="重置筛选">
              <RotateCcw className="h-4 w-4" />
            </AppButton>
          </div>

          <div className="mt-5 grid gap-4">
            <label className="grid gap-2 text-sm">
              <span className="font-medium text-ink">掌握状态</span>
              <select
                className="h-11 rounded-control border border-line bg-white px-3 text-sm text-ink transition focus:border-brand focus:outline-none focus:ring-4 focus:ring-brand/10"
                value={priorityFilter}
                onChange={(event) => setPriorityFilter(event.target.value as PriorityFilter)}
              >
                {priorityOptions.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="grid gap-2 text-sm">
              <span className="font-medium text-ink">知识点</span>
              <select
                className="h-11 rounded-control border border-line bg-white px-3 text-sm text-ink transition focus:border-brand focus:outline-none focus:ring-4 focus:ring-brand/10"
                value={tagFilter}
                onChange={(event) => setTagFilter(event.target.value)}
              >
                <option value="">全部知识点</option>
                {tags.map((tag) => (
                  <option key={tag.id} value={tag.id}>
                    {tag.name}
                  </option>
                ))}
              </select>
            </label>

            <div className="rounded-3xl border border-line bg-brandMist p-4">
              <p className="text-sm font-semibold text-ink">当前筛选</p>
              <p className="mt-2 text-sm leading-6 text-muted">
                共匹配 {filteredItems.length} 道错题。优先重练低分、反复失败或已到复习时间的题目。
              </p>
            </div>
          </div>
        </AppCard>

        <section className="grid gap-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-brand">错题列表</p>
              <h2 className="mt-2 text-2xl font-semibold text-ink">下一轮该复盘哪些题</h2>
            </div>
            <Badge>{filteredItems.length} 道匹配</Badge>
          </div>

          {query.isLoading ? (
            <AppCard className="grid min-h-56 place-items-center p-8 text-sm text-muted">
              <Loader2 className="h-6 w-6 animate-spin text-brand" />
              <span className="mt-3">正在读取错题本...</span>
            </AppCard>
          ) : null}

          {query.isError ? (
            <AppCard className="p-8 text-center">
              <TriangleAlert className="mx-auto h-8 w-8 text-accent" />
              <h3 className="mt-4 text-xl font-semibold text-ink">错题本暂时无法读取</h3>
              <p className="mt-2 text-sm leading-6 text-muted">可以先返回今日训练继续推进，稍后再回来复盘。</p>
              <div className="mt-5 flex justify-center">
                <LinkButton href="/practice" variant="primary">
                  <ArrowRight className="h-4 w-4" />
                  返回今日训练
                </LinkButton>
              </div>
            </AppCard>
          ) : null}

          {!query.isLoading && !query.isError && filteredItems.length > 0 ? (
            <div className="grid gap-4 lg:grid-cols-2">
              {filteredItems.map((item) => (
                <WrongBookCard
                  key={item.question_id}
                  item={item}
                  loading={retry.isPending && activeQuestionId === item.question_id}
                  disabled={retry.isPending}
                  onRetry={() => retry.mutate(item.question_id)}
                />
              ))}
            </div>
          ) : null}

          {!query.isLoading && !query.isError && items.length === 0 ? (
            <EmptyState
              title="暂无错题"
              description="完成训练后，低分题会自动进入这里。你可以先回到今日训练，让系统生成第一批复盘材料。"
              actionLabel="去今日训练"
              href="/practice"
            />
          ) : null}

          {!query.isLoading && !query.isError && items.length > 0 && filteredItems.length === 0 ? (
            <EmptyState
              title="没有匹配的错题"
              description="当前筛选条件下没有错题。放宽知识点或掌握状态后再继续复盘。"
              actionLabel="重置筛选"
              onAction={resetFilters}
            />
          ) : null}
        </section>
      </section>
    </PageShell>
  );
}

function WrongBookCard({
  item,
  loading,
  disabled,
  onRetry,
}: {
  item: WrongBookItem;
  loading: boolean;
  disabled: boolean;
  onRetry: () => void;
}) {
  const score = item.last_score ?? 0;
  const priority = getPriority(item);
  return (
    <AppCard className="flex min-h-[260px] flex-col p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge className={scoreBadgeClass(score)}>{score} 分</Badge>
        <Badge>失败 {item.fail_count} 次</Badge>
        <Badge className={priority.className}>{priority.label}</Badge>
        {item.next_review ? <Badge>下次复习 {item.next_review}</Badge> : null}
      </div>

      <h3 className="mt-4 text-lg font-semibold leading-7 text-ink">{item.title}</h3>

      <div className="mt-4 flex flex-wrap gap-2">
        {item.tags.length > 0 ? (
          item.tags.map((tag) => (
            <Badge key={tag.id} className="border-brand/20 bg-brandSoft text-brand">
              {tag.name}
            </Badge>
          ))
        ) : (
          <Badge>通用知识点</Badge>
        )}
      </div>

      <div className="mt-5 grid gap-3 rounded-3xl border border-line bg-brandMist p-4 text-sm leading-6 text-muted">
        <p>
          {item.fail_count >= 2
            ? "这道题已经多次答错，建议优先重新训练，重点补齐核心概念和表达结构。"
            : "建议重新做一轮单题训练，把反馈继续沉淀到能力画像。"}
        </p>
        <p>参考答案和 AI 反馈会在完成重练后进入报告页查看。</p>
      </div>

      <div className="mt-auto flex flex-col gap-3 pt-5 sm:flex-row">
        <AppButton className="flex-1" onClick={onRetry} disabled={disabled}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
          重新训练
        </AppButton>
      </div>
    </AppCard>
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
      <div className="mt-3 text-3xl font-semibold text-ink">{value}</div>
      <p className="mt-2 text-sm leading-6 text-muted">{helper}</p>
    </AppCard>
  );
}

function EmptyState({
  title,
  description,
  actionLabel,
  href,
  onAction,
}: {
  title: string;
  description: string;
  actionLabel: string;
  href?: string;
  onAction?: () => void;
}) {
  return (
    <AppCard className="p-8 text-center">
      <Search className="mx-auto h-8 w-8 text-brand" />
      <h3 className="mt-4 text-xl font-semibold text-ink">{title}</h3>
      <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted">{description}</p>
      <div className="mt-5 flex justify-center">
        {href ? (
          <LinkButton href={href} variant="primary">
            <ArrowRight className="h-4 w-4" />
            {actionLabel}
          </LinkButton>
        ) : (
          <AppButton onClick={onAction}>
            <RotateCcw className="h-4 w-4" />
            {actionLabel}
          </AppButton>
        )}
      </div>
    </AppCard>
  );
}

function LinkButton({ href, variant, children }: { href: string; variant: "primary" | "secondary"; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className={cn(
        "inline-flex h-11 items-center justify-center gap-2 rounded-control px-4 text-sm font-semibold transition",
        variant === "primary" && "bg-brand text-white shadow-button hover:bg-brandDeep",
        variant === "secondary" && "border border-line bg-white text-ink shadow-soft hover:border-brand/30 hover:bg-brandMist"
      )}
    >
      {children}
    </Link>
  );
}

function pickRecommended(items: WrongBookItem[]) {
  return [...items].sort((a, b) => getPriorityScore(b) - getPriorityScore(a))[0];
}

function getPriorityScore(item: WrongBookItem) {
  return (item.fail_count >= 2 ? 40 : 0) + ((item.last_score ?? 0) < 70 ? 30 : 0) + (item.next_review ? 20 : 0) + Math.max(0, 10 - (item.last_score ?? 0) / 10);
}

function getPriority(item: WrongBookItem) {
  if (item.fail_count >= 2) return { label: "反复出错", className: "border-[#dc2626]/20 bg-[#fff6f2] text-[#991b1b]" };
  if ((item.last_score ?? 0) < 70) return { label: "低分优先", className: "border-[#d69e2e] bg-[#fff8e5] text-[#7a4f01]" };
  if (item.next_review) return { label: "待复习", className: "border-brand/20 bg-brandSoft text-brand" };
  return { label: "巩固复盘", className: "border-line bg-panel text-muted" };
}

function scoreBadgeClass(score: number) {
  if (score >= 80) return "border-brand/20 bg-brandSoft text-brand";
  if (score >= 60) return "border-[#d69e2e] bg-[#fff8e5] text-[#7a4f01]";
  return "border-[#dc2626]/20 bg-[#fff6f2] text-[#991b1b]";
}
