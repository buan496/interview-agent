"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BarChart3, Brain, Clock3, Loader2, PlayCircle, RotateCcw, Target, TrendingUp, type LucideIcon } from "lucide-react";

import { AppButton, AppCard, Badge, BrandLogo, PageShell, cn } from "@/components/ui";
import { getAbilityProfile } from "@/lib/ability-profile-api";
import type { AbilityMasteryLevel, AbilityTagProfile } from "@/lib/types";

const masteryMeta: Record<AbilityMasteryLevel, { label: string; className: string; hint: string }> = {
  strong: { label: "优势", className: "border-emerald-200 bg-emerald-50 text-emerald-700", hint: "保持输出稳定性，可尝试更高难度追问。" },
  stable: { label: "稳定", className: "border-brand/20 bg-brandSoft text-brand", hint: "基础较稳，建议通过项目表达继续强化。" },
  weak: { label: "薄弱", className: "border-accent/20 bg-[#fff7ed] text-accent", hint: "建议优先进入错题复盘或专项训练。" },
};

export default function AbilityPage() {
  const profile = useQuery({ queryKey: ["ability-profile"], queryFn: getAbilityProfile });
  const data = profile.data;
  const hasProfile = Boolean(data && (data.total_sessions > 0 || data.tag_profiles.length > 0));

  return (
    <PageShell className="grid gap-8 pb-12">
      <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-stretch">
        <AppCard className="relative overflow-hidden p-6 sm:p-8 lg:p-10">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_14%_12%,rgba(30,119,255,0.16),transparent_32%),linear-gradient(135deg,rgba(246,251,255,0.95),rgba(255,255,255,0.58))]" />
          <div className="relative">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <BrandLogo variant="mark" className="h-11 w-11 rounded-2xl border border-line bg-white p-1.5 shadow-soft" priority />
                <div>
                  <p className="text-sm font-semibold text-brand">能力画像</p>
                  <p className="text-xs text-muted">只展示当前登录用户的长期训练表现</p>
                </div>
              </div>
              <Badge className="border-brand/20 bg-brandSoft text-brand">Ability Profile v1</Badge>
            </div>

            <div className="mt-10 max-w-3xl">
              <h1 className="text-3xl font-semibold leading-tight text-ink sm:text-4xl lg:text-5xl">看清自己的优势和薄弱项，再决定下一轮训练</h1>
              <p className="mt-5 max-w-2xl text-base leading-8 text-muted">
                系统基于历史 Session、标签得分和错题沉淀，生成当前用户的能力画像。v1 采用规则聚合，不引入复杂预测或 Agent Memory。
              </p>
            </div>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <LinkButton href="/practice" variant="primary">
                <PlayCircle className="h-4 w-4" />
                去今日训练
              </LinkButton>
              <LinkButton href="/wrong-book" variant="secondary">
                <RotateCcw className="h-4 w-4" />
                复盘错题
              </LinkButton>
            </div>
          </div>
        </AppCard>

        <AppCard className="p-6">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink">
            <BarChart3 className="h-4 w-4 text-brand" />
            总体能力概览
          </div>
          {profile.isLoading ? (
            <div className="mt-8 grid min-h-40 place-items-center text-sm text-muted">
              <Loader2 className="h-6 w-6 animate-spin text-brand" />
            </div>
          ) : (
            <div className="mt-5 grid grid-cols-2 gap-3">
              <SummaryMetric value={formatScore(data?.overall_score)} label="综合得分" helper="已完成训练" />
              <SummaryMetric value={`${data?.completed_sessions ?? 0}`} label="完成轮次" helper={`共 ${data?.total_sessions ?? 0} 轮`} />
              <SummaryMetric value={`${data?.total_questions ?? 0}`} label="累计题量" helper="Session 题数" />
              <SummaryMetric value={`${data?.tag_profiles.length ?? 0}`} label="标签维度" helper="已形成画像" />
            </div>
          )}
          {data?.updated_at ? (
            <p className="mt-4 inline-flex items-center gap-1 text-xs text-muted">
              <Clock3 className="h-3.5 w-3.5 text-brand" />
              最近更新：{formatDateTime(data.updated_at)}
            </p>
          ) : null}
        </AppCard>
      </section>

      <AppCard className="p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-brand">Ability Workbench</p>
            <h2 className="mt-2 text-2xl font-semibold text-ink">能力画像工作台</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">优势项用于维持稳定输出；薄弱项会指导下一轮错题复盘和专项训练。</p>
          </div>
          <AppButton variant="secondary" onClick={() => profile.refetch()} disabled={profile.isFetching}>
            {profile.isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
            刷新
          </AppButton>
        </div>

        {profile.isLoading ? (
          <div className="grid min-h-[280px] place-items-center text-sm text-muted">
            <Loader2 className="h-6 w-6 animate-spin text-brand" />
          </div>
        ) : null}

        {profile.isError ? (
          <div className="mt-6 rounded-3xl border border-line bg-brandMist p-8 text-center">
            <p className="text-base font-semibold text-ink">能力画像加载失败</p>
            <p className="mt-2 text-sm text-muted">可以先返回今日训练，稍后再查看能力维度。</p>
            <div className="mt-5">
              <LinkButton href="/practice" variant="primary">返回今日训练</LinkButton>
            </div>
          </div>
        ) : null}

        {!profile.isLoading && !profile.isError && !hasProfile ? <EmptyAbility /> : null}

        {!profile.isLoading && !profile.isError && hasProfile && data ? (
          <div className="mt-6 grid gap-6">
            <section className="grid gap-4 lg:grid-cols-2">
              <ProfileGroup title="优势能力" icon={TrendingUp} items={data.strengths} empty="还没有稳定优势项，继续训练后会自动形成。" />
              <ProfileGroup title="薄弱能力" icon={Target} items={data.weaknesses} empty="当前没有明显薄弱项，建议通过模拟面试继续校准。" />
            </section>

            <section className="grid gap-4">
              <div>
                <h3 className="text-xl font-semibold text-ink">标签维度表现</h3>
                <p className="mt-2 text-sm leading-6 text-muted">按知识标签和面试能力维度聚合平均分、训练次数、错题次数和最近训练时间。</p>
              </div>
              <div className="grid gap-3">
                {data.tag_profiles.map((item) => (
                  <TagProfileCard key={item.tag_id} item={item} />
                ))}
              </div>
            </section>
          </div>
        ) : null}
      </AppCard>
    </PageShell>
  );
}

function ProfileGroup({
  title,
  icon: Icon,
  items,
  empty,
}: {
  title: string;
  icon: LucideIcon;
  items: AbilityTagProfile[];
  empty: string;
}) {
  return (
    <AppCard className="rounded-3xl p-5 shadow-soft">
      <div className="flex items-center gap-2 text-sm font-semibold text-ink">
        <Icon className="h-4 w-4 text-brand" />
        {title}
      </div>
      {items.length === 0 ? <p className="mt-5 text-sm leading-6 text-muted">{empty}</p> : null}
      <div className="mt-5 grid gap-3">
        {items.map((item) => (
          <CompactTag key={item.tag_id} item={item} />
        ))}
      </div>
    </AppCard>
  );
}

function CompactTag({ item }: { item: AbilityTagProfile }) {
  const meta = masteryMeta[item.mastery_level];
  return (
    <div className="rounded-2xl border border-line bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-base font-semibold text-ink">{item.tag}</p>
          <p className="mt-1 text-xs text-muted">{item.category ?? "未分类"} · {item.practice_count} 次训练 · {item.wrong_count} 次错题</p>
        </div>
        <Badge className={meta.className}>{meta.label}</Badge>
      </div>
      <div className="mt-3">
        <ScoreBar score={toScore(item.average_score)} />
      </div>
    </div>
  );
}

function TagProfileCard({ item }: { item: AbilityTagProfile }) {
  const meta = masteryMeta[item.mastery_level];
  const score = toScore(item.average_score);
  return (
    <article className="rounded-3xl border border-line bg-white p-4 shadow-soft sm:p-5">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px] lg:items-center">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge className={meta.className}>{meta.label}</Badge>
            <Badge>{item.category ?? "未分类"}</Badge>
            <Badge>{item.practice_count} 次训练</Badge>
            {item.wrong_count > 0 ? <Badge className="border-accent/20 bg-[#fff7ed] text-accent">{item.wrong_count} 次错题</Badge> : null}
          </div>
          <h3 className="mt-3 text-lg font-semibold text-ink">{item.tag}</h3>
          <p className="mt-2 text-sm leading-6 text-muted">{meta.hint}</p>
          {item.last_practiced_at ? <p className="mt-2 text-xs text-muted">最近训练：{formatDateTime(item.last_practiced_at)}</p> : null}
        </div>

        <div className="rounded-2xl border border-line bg-brandMist p-4">
          <p className="text-sm text-muted">平均得分</p>
          <p className="mt-1 text-3xl font-semibold text-ink">{formatScore(score)}</p>
          <div className="mt-3">
            <ScoreBar score={score} />
          </div>
        </div>
      </div>
    </article>
  );
}

function EmptyAbility() {
  return (
    <div className="mt-6 rounded-3xl border border-line bg-brandMist p-8 text-center">
      <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-white text-brand shadow-soft">
        <Brain className="h-5 w-5" />
      </div>
      <h3 className="mt-4 text-lg font-semibold text-ink">还没有能力画像</h3>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-muted">完成一次今日训练或模拟面试后，系统会根据得分、标签和错题沉淀生成长期能力画像。</p>
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

function ScoreBar({ score }: { score: number }) {
  const width = Math.max(0, Math.min(100, score));
  return (
    <div className="h-2 overflow-hidden rounded-full bg-[#dbeafe]">
      <div className="h-full rounded-full bg-brand transition-all" style={{ width: `${width}%` }} />
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
      {variant === "primary" ? <ArrowRight className="h-4 w-4" /> : null}
    </Link>
  );
}

function toScore(value: number | string | null | undefined) {
  const numeric = Number(value ?? 0);
  return Number.isFinite(numeric) ? numeric : 0;
}

function formatScore(value: number | string | null | undefined) {
  if (value === null || value === undefined) return "--";
  return String(Math.round(toScore(value)));
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
