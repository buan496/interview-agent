"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, ClipboardCheck, FileText, Loader2, MessageSquareText, Play, RotateCcw, ShieldCheck, Sparkles, Target, Timer } from "lucide-react";
import { useRouter } from "next/navigation";

import { AppButton, AppCard, Badge, BrandLogo, PageShell, cn } from "@/components/ui";
import { getMetadata } from "@/lib/question-api";
import { createSession } from "@/lib/session-api";

const interviewFacts = [
  { label: "题目数量", value: "6 道题" },
  { label: "预计时长", value: "45 分钟" },
  { label: "AI 追问", value: "最多 3 轮" },
  { label: "结束产物", value: "结构化报告" },
];

const focusAreas = [
  {
    icon: Target,
    value: "15%",
    label: "项目与行为",
    detail: "检验项目表达、复盘能力和业务理解是否能支撑真实面试追问。",
  },
  {
    icon: ShieldCheck,
    value: "35%",
    label: "基础知识",
    detail: "校准概念准确性、边界条件、常见误区和知识点掌握程度。",
  },
  {
    icon: CheckCircle2,
    value: "50%",
    label: "编码与系统设计",
    detail: "覆盖方案拆解、复杂度判断、工程取舍和系统设计表达。",
  },
];

const flowSteps = [
  { index: "1", title: "抽题", detail: "按目标公司、岗位和题型比例生成一组模拟面试题。" },
  { index: "2", title: "作答与追问", detail: "AI 根据回答深度决定是否继续追问，尽量还原连续作答压力。" },
  { index: "3", title: "评分报告", detail: "输出综合评分、薄弱点、错题沉淀和下一轮训练建议。" },
];

const valueCards = [
  { icon: Timer, title: "真实面试节奏", detail: "一次完整 Session 连续推进，训练时间管理和表达稳定性。" },
  { icon: MessageSquareText, title: "AI 追问与评分", detail: "围绕回答深度继续追问，并沉淀可复盘的评分反馈。" },
  { icon: FileText, title: "复盘报告", detail: "结束后进入报告工作台，查看总体表现、题目复盘和参考答案。" },
  { icon: RotateCcw, title: "错题沉淀", detail: "低分题和薄弱知识点会进入后续训练闭环，支持持续提升。" },
];

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

  const companyName = metadata.data?.companies.find((item) => String(item.id) === companyId)?.name ?? "随机公司";
  const positionName = metadata.data?.positions.find((item) => String(item.id) === positionId)?.name ?? "随机岗位";

  return (
    <PageShell className="grid gap-6 pb-12">
      <AppCard className="relative overflow-hidden p-6 sm:p-8 lg:p-10">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_10%,rgba(30,119,255,0.14),transparent_34%),linear-gradient(135deg,rgba(246,251,255,0.95),rgba(255,255,255,0.5))]" />
        <div className="relative grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-2">
              <BrandLogo variant="mark" className="h-11 w-11 rounded-2xl border border-line bg-white p-1.5 shadow-soft" priority />
              <Badge className="border-brand/20 bg-brandSoft text-brand">模拟面试</Badge>
              <Badge>Agent 工程师</Badge>
            </div>
            <h1 className="mt-6 text-3xl font-semibold leading-tight text-ink sm:text-4xl lg:text-5xl">模拟面试</h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-muted sm:text-lg">
              围绕 Agent 工程师岗位，完成一轮接近真实面试的结构化训练。系统会记录连续作答、AI 追问、评分报告和后续复盘建议。
            </p>
            <div className="mt-7 flex flex-col gap-3 sm:flex-row">
              <AppButton size="lg" onClick={() => start.mutate()} disabled={start.isPending}>
                {start.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                {start.isPending ? "正在创建面试" : "开始模拟面试"}
              </AppButton>
              <AppButton size="lg" variant="secondary" onClick={() => router.push("/practice")}>
                <ArrowLeft className="h-4 w-4" />
                返回今日训练
              </AppButton>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {interviewFacts.map((item) => (
              <AppCard key={item.label} className="rounded-3xl p-5 shadow-soft">
                <p className="text-sm text-muted">{item.label}</p>
                <p className="mt-2 text-xl font-semibold text-ink">{item.value}</p>
              </AppCard>
            ))}
          </div>
        </div>
      </AppCard>

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="grid gap-6">
          <AppCard className="p-5 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <Badge className="border-brand/20 bg-brandSoft text-brand">面试模式</Badge>
                <h2 className="mt-3 text-2xl font-semibold text-ink">标准模拟面试</h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
                  当前后端能力提供一轮标准模拟面试：按公司、岗位和题型比例抽题，并在结束后生成结构化报告。
                </p>
              </div>
              <Badge className="border-[#88b5ff] bg-[#f1f7ff] text-brand">已接入训练闭环</Badge>
            </div>

            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              {focusAreas.map((item) => (
                <FocusBlock key={item.label} {...item} />
              ))}
            </div>
          </AppCard>

          <AppCard className="p-5 sm:p-6">
            <div className="flex items-center gap-2 text-sm font-semibold text-ink">
              <ClipboardCheck className="h-4 w-4 text-brand" />
              本轮流程
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-3">
              {flowSteps.map((item) => (
                <Step key={item.index} {...item} />
              ))}
            </div>
          </AppCard>

          <section className="grid gap-4 md:grid-cols-2">
            {valueCards.map((item) => (
              <ValueCard key={item.title} {...item} />
            ))}
          </section>
        </div>

        <AppCard className="h-fit p-5 sm:p-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold text-ink">面试设置</h2>
              <p className="mt-2 text-sm leading-6 text-muted">不选择条件时，系统会从全量题库中随机抽题。</p>
            </div>
            <Sparkles className="h-5 w-5 text-brand" />
          </div>

          <div className="mt-5 grid gap-4">
            <SelectField label="目标公司" value={companyId} onChange={setCompanyId} disabled={metadata.isLoading}>
              <option value="">随机公司</option>
              {metadata.data?.companies.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </SelectField>

            <SelectField label="目标岗位" value={positionId} onChange={setPositionId} disabled={metadata.isLoading}>
              <option value="">随机岗位</option>
              {metadata.data?.positions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </SelectField>

            <div className="rounded-3xl border border-line bg-brandMist p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand">当前配置</p>
              <p className="mt-2 text-sm leading-6 text-muted">
                {companyName} · {positionName} · 6 道题 · 最多 3 轮追问
              </p>
            </div>

            {metadata.isLoading ? <p className="text-sm text-muted">正在加载公司和岗位选项...</p> : null}
            {metadata.isError ? <p className="text-sm text-accent">选项加载失败，仍可使用随机公司和随机岗位启动模拟面试。</p> : null}
            {start.isError ? <p className="text-sm text-accent">当前筛选条件下题目不足，请放宽公司或岗位条件。</p> : null}

            <AppButton onClick={() => start.mutate()} disabled={start.isPending}>
              {start.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {start.isPending ? "正在创建面试" : "开始模拟面试"}
            </AppButton>
          </div>
        </AppCard>
      </section>
    </PageShell>
  );
}

function SelectField({
  label,
  value,
  onChange,
  disabled,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="grid gap-2 text-sm">
      <span className="font-medium text-ink">{label}</span>
      <select
        className={cn(
          "h-12 rounded-control border border-line bg-white px-4 text-sm text-ink shadow-[0_1px_0_rgba(15,23,42,0.02)] transition",
          "focus:border-brand focus:outline-none focus:ring-4 focus:ring-brand/10",
          disabled && "cursor-not-allowed opacity-60"
        )}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
      >
        {children}
      </select>
    </label>
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
    <AppCard className="rounded-3xl p-5 shadow-soft">
      <Icon className="h-5 w-5 text-brand" />
      <div className="mt-3 text-2xl font-semibold text-brand">{value}</div>
      <div className="mt-1 text-sm font-semibold text-ink">{label}</div>
      <p className="mt-2 text-sm leading-6 text-muted">{detail}</p>
    </AppCard>
  );
}

function Step({ index, title, detail }: { index: string; title: string; detail: string }) {
  return (
    <div className="rounded-3xl border border-line bg-white p-4">
      <div className="flex items-center gap-2 font-semibold text-ink">
        <span className="grid h-7 w-7 place-items-center rounded-2xl bg-brand text-xs text-white">{index}</span>
        {title}
      </div>
      <p className="mt-3 text-sm leading-6 text-muted">{detail}</p>
    </div>
  );
}

function ValueCard({
  icon: Icon,
  title,
  detail,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  detail: string;
}) {
  return (
    <AppCard className="p-5">
      <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brandSoft text-brand">
        <Icon className="h-5 w-5" />
      </div>
      <h3 className="mt-4 text-lg font-semibold text-ink">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-muted">{detail}</p>
    </AppCard>
  );
}
