"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  BookOpenCheck,
  ChevronRight,
  Clock3,
  ExternalLink,
  Filter,
  Gauge,
  Loader2,
  RotateCcw,
  Search,
  Sparkles,
  Target,
} from "lucide-react";
import { useRouter } from "next/navigation";

import { AppButton, AppCard, Badge, BrandLogo, PageShell, cn } from "@/components/ui";
import { getTodayPracticePlan } from "@/lib/practice-plan-api";
import { getMetadata, getQuestions } from "@/lib/question-api";
import { createSession } from "@/lib/session-api";
import { getRadar, getReports } from "@/lib/stats-api";
import { getWrongBook } from "@/lib/wrong-book-api";
import type { PracticePlanTask } from "@/lib/types";

const difficultyOptions = [1, 2, 3, 4, 5];

type StartOverride = {
  mode?: "single" | "mock";
  question_id?: number;
  company_id?: number;
  position_id?: number;
  tag_ids?: number[];
  difficulty?: number;
};

export default function PracticePage() {
  const router = useRouter();
  const [companyId, setCompanyId] = useState("");
  const [positionId, setPositionId] = useState("");
  const [tagId, setTagId] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [page, setPage] = useState(1);

  const metadata = useQuery({ queryKey: ["metadata"], queryFn: getMetadata });
  const wrongBook = useQuery({ queryKey: ["wrong-book"], queryFn: getWrongBook });
  const radar = useQuery({ queryKey: ["radar"], queryFn: getRadar });
  const reports = useQuery({ queryKey: ["reports"], queryFn: getReports });
  const practicePlan = useQuery({ queryKey: ["practice-plan", "today"], queryFn: getTodayPracticePlan });

  const params = useMemo(() => {
    const value = new URLSearchParams({ page: String(page), page_size: "12" });
    if (companyId) value.set("company_id", companyId);
    if (positionId) value.set("position_id", positionId);
    if (tagId) value.append("tag_ids", tagId);
    if (difficulty) value.set("difficulty", difficulty);
    return value;
  }, [companyId, positionId, tagId, difficulty, page]);

  const questions = useQuery({ queryKey: ["questions", params.toString()], queryFn: () => getQuestions(params) });
  const startSession = useMutation({
    mutationFn: (override?: StartOverride) => {
      const fromPlanOrQuestion = override !== undefined;
      return createSession({
        mode: override?.mode ?? "single",
        question_id: override?.question_id,
        company_id: fromPlanOrQuestion ? override.company_id : companyId ? Number(companyId) : undefined,
        position_id: fromPlanOrQuestion ? override.position_id : positionId ? Number(positionId) : undefined,
        tag_ids: fromPlanOrQuestion ? override.tag_ids : tagId ? [Number(tagId)] : [],
        difficulty: fromPlanOrQuestion ? override.difficulty : difficulty ? Number(difficulty) : undefined,
      });
    },
    onSuccess: (data) => router.push(`/session/${data.session_id}`),
  });

  const reset = () => {
    setCompanyId("");
    setPositionId("");
    setTagId("");
    setDifficulty("");
    setPage(1);
  };

  const totalPages = Math.max(1, Math.ceil((questions.data?.total ?? 0) / 12));
  const weakRadar = useMemo(() => [...(radar.data ?? [])].sort((a, b) => Number(a.avg_score) - Number(b.avg_score))[0], [radar.data]);
  const latestReport = reports.data?.[0];
  const primaryTask = practicePlan.data?.recommended_tasks[0];
  const targetAbilities = practicePlan.data?.target_abilities ?? [];
  const weakTags = practicePlan.data?.weak_tags ?? [];

  function startPlanTask(task: PracticePlanTask) {
    if (task.entrypoint === "open_page" && task.payload.href) {
      router.push(task.payload.href);
      return;
    }
    startSession.mutate({
      question_id: task.payload.question_id ?? undefined,
      mode: task.payload.mode,
      company_id: task.payload.company_id ?? undefined,
      position_id: task.payload.position_id ?? undefined,
      tag_ids: task.payload.tag_ids ?? undefined,
      difficulty: task.payload.difficulty ?? undefined,
    });
  }

  function startTodayTraining() {
    if (primaryTask) {
      startPlanTask(primaryTask);
      return;
    }
    startSession.mutate(undefined);
  }

  return (
    <PageShell className="grid gap-8 pb-12">
      <section className="grid gap-6 lg:grid-cols-[1fr_380px] lg:items-stretch">
        <AppCard className="relative overflow-hidden p-6 sm:p-8 lg:p-10">
          <div className="absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-brandSoft to-transparent" />
          <div className="relative">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <BrandLogo variant="mark" className="h-11 w-11 rounded-2xl border border-line bg-white p-1.5 shadow-soft" priority />
                <div>
                  <p className="text-sm font-semibold text-brand">今日训练</p>
                  <p className="text-xs text-muted">Agent 工程师面试训练闭环</p>
                </div>
              </div>
              <Badge className="border-brand/20 bg-brandSoft text-brand">蓝白训练台</Badge>
            </div>

            <div className="mt-10 max-w-3xl">
              <h1 className="text-3xl font-semibold leading-tight text-ink sm:text-4xl lg:text-5xl">
                今天，从一次高质量模拟面试开始
              </h1>
              <p className="mt-5 max-w-2xl text-base leading-8 text-muted">
                系统会记录你的回答、追问表现、薄弱知识点和复盘报告，帮助你围绕 Agent 工程师岗位完成今日训练闭环。
              </p>
            </div>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <AppButton size="lg" onClick={startTodayTraining} disabled={startSession.isPending || practicePlan.isLoading}>
                {startSession.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                开始今日训练
              </AppButton>
              <AppButton
                size="lg"
                variant="secondary"
                onClick={() => (latestReport ? router.push(`/report/${latestReport.session_id}`) : router.push("/wrong-book"))}
              >
                查看最近报告
                <ChevronRight className="h-4 w-4" />
              </AppButton>
            </div>

            <div className="mt-9 grid gap-3 sm:grid-cols-3">
              <HeroNote title="真实 Session" description="从题目进入受控面试流程" />
              <HeroNote title="结构化复盘" description="把表现沉淀为能力报告" />
              <HeroNote title="下一轮计划" description="按薄弱点继续推进训练" />
            </div>
          </div>
        </AppCard>

        <AppCard className="p-6">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Gauge className="h-4 w-4 text-brand" />
            今日概览
          </div>
          <div className="mt-5 grid grid-cols-2 gap-3">
            <Metric value={`${practicePlan.data?.recommended_tasks.length ?? 0}`} label="今日训练" helper="推荐任务" />
            <Metric value={latestReport ? `${latestReport.overall_score}` : "--"} label="最近得分" helper="报告分数" />
            <Metric value={weakRadar ? weakRadar.tag : "--"} label="薄弱知识点" helper={weakRadar ? `${Number(weakRadar.avg_score).toFixed(0)} 分` : "等待训练"} />
            <Metric value={`${wrongBook.data?.length ?? 0}`} label="错题沉淀" helper="待复盘" />
          </div>
          <div className="mt-5 rounded-2xl border border-line bg-brandMist p-4">
            <p className="text-sm font-medium text-ink">下一步建议</p>
            <p className="mt-2 text-sm leading-6 text-muted">
              {practicePlan.data?.generated_reason ?? "完成一次训练后，系统会结合错题、薄弱标签和最近报告给出更明确的优先任务。"}
            </p>
          </div>
        </AppCard>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {practicePlan.data?.recommended_tasks.map((task) => (
          <TrainingTask key={task.id} task={task} onStart={() => startPlanTask(task)} disabled={startSession.isPending} />
        ))}
        {practicePlan.isLoading ? (
          <AppCard className="grid min-h-[220px] place-items-center p-5 text-sm text-muted">
            <Loader2 className="h-5 w-5 animate-spin text-brand" />
          </AppCard>
        ) : null}
      </section>

      <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="grid gap-5">
          <AppCard className="p-5 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-brand">推荐训练</p>
                <h2 className="mt-2 text-2xl font-semibold text-ink">今天该练什么</h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
                  优先完成系统推荐任务；题库筛选仍保留为辅助入口，用于按公司、岗位、标签和难度发起专项练习。
                </p>
              </div>
              <AppButton variant="secondary" onClick={() => startSession.mutate(undefined)} disabled={startSession.isPending}>
                {startSession.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                按筛选开始
              </AppButton>
            </div>

            <div className="mt-6 grid gap-4 lg:grid-cols-[280px_1fr]">
              <div className="rounded-3xl border border-line bg-white/80 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    <Filter className="h-4 w-4 text-brand" />
                    题库辅助筛选
                  </div>
                  <AppButton variant="ghost" className="h-9 px-2" onClick={reset} title="重置筛选">
                    <RotateCcw className="h-4 w-4" />
                  </AppButton>
                </div>

                <div className="grid gap-3">
                  <SelectField label="公司" value={companyId} onChange={setCompanyId} onResetPage={() => setPage(1)}>
                    <option value="">全部公司</option>
                    {metadata.data?.companies.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </SelectField>

                  <SelectField label="岗位" value={positionId} onChange={setPositionId} onResetPage={() => setPage(1)}>
                    <option value="">全部岗位</option>
                    {metadata.data?.positions.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </SelectField>

                  <SelectField label="标签" value={tagId} onChange={setTagId} onResetPage={() => setPage(1)}>
                    <option value="">全部标签</option>
                    {metadata.data?.tags.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </SelectField>

                  <SelectField label="难度" value={difficulty} onChange={setDifficulty} onResetPage={() => setPage(1)}>
                    <option value="">全部难度</option>
                    {difficultyOptions.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </SelectField>
                </div>
              </div>

              <div className="grid gap-3">
                <div className="flex items-end justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold text-ink">题库辅助入口</h3>
                    <p className="mt-1 text-sm text-muted">共 {questions.data?.total ?? 0} 题，选题后进入受控 Session。</p>
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  {questions.data?.items.map((item) => (
                    <AppCard key={item.id} className="flex min-h-[238px] flex-col rounded-3xl p-4 shadow-soft">
                      <div className="mb-3 flex flex-wrap gap-2">
                        <Badge>{item.company?.name ?? "通用"}</Badge>
                        <Badge>{item.position?.name ?? "岗位通用"}</Badge>
                        <Badge className="border-brand/20 bg-brandSoft text-brand">难度 {item.difficulty}</Badge>
                      </div>
                      <h4 className="line-clamp-3 text-base font-semibold leading-6 text-ink">{item.title}</h4>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {item.tags.slice(0, 4).map((tag) => (
                          <Badge key={tag.id}>{tag.name}</Badge>
                        ))}
                      </div>
                      {item.source_note?.startsWith("http") ? (
                        <a className="mt-3 inline-flex items-center gap-1 text-xs text-brand hover:underline" href={item.source_note} target="_blank" rel="noreferrer">
                          公开题源
                          <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      ) : null}
                      <AppButton
                        variant="secondary"
                        className="mt-auto w-full"
                        onClick={() => {
                          startSession.mutate({
                            question_id: item.id,
                            company_id: item.company?.id ?? undefined,
                            position_id: item.position?.id ?? undefined,
                          });
                        }}
                        disabled={startSession.isPending}
                      >
                        训练这道题
                        <ArrowRight className="h-4 w-4" />
                      </AppButton>
                    </AppCard>
                  ))}
                </div>

                {questions.data && questions.data.total > 12 ? (
                  <div className="flex flex-wrap items-center justify-center gap-3">
                    <AppButton variant="secondary" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1}>
                      <ArrowLeft className="h-4 w-4" />
                      上一页
                    </AppButton>
                    <span className="text-sm text-muted">
                      第 {page} / {totalPages} 页
                    </span>
                    <AppButton variant="secondary" onClick={() => setPage((value) => Math.min(totalPages, value + 1))} disabled={page >= totalPages}>
                      下一页
                      <ArrowRight className="h-4 w-4" />
                    </AppButton>
                  </div>
                ) : null}

                {!questions.isLoading && questions.data?.items.length === 0 ? (
                  <AppCard className="p-8 text-center text-sm text-muted">暂无匹配题目，请放宽筛选条件。</AppCard>
                ) : null}
              </div>
            </div>
          </AppCard>
        </div>

        <aside className="grid h-fit gap-5">
          <AppCard id="ability-diagnosis" className="p-5">
            <p className="text-sm font-semibold text-brand">最近薄弱点</p>
            <h2 className="mt-2 text-xl font-semibold text-ink">能力诊断</h2>
            <div className="mt-4 grid gap-3">
              {weakTags.slice(0, 3).map((item) => (
                <div key={item.tag_id} className="rounded-2xl border border-line bg-white p-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-ink">{item.tag}</span>
                    <span className="text-sm font-semibold text-brand">{Number(item.avg_score).toFixed(0)}</span>
                  </div>
                  <p className="mt-1 text-xs text-muted">已训练 {item.attempts} 次</p>
                </div>
              ))}
              {weakTags.length === 0 ? <p className="text-sm leading-6 text-muted">完成训练后，这里会展示最近薄弱知识点。</p> : null}
            </div>
          </AppCard>

          <AppCard className="p-5">
            <p className="text-sm font-semibold text-brand">最近复盘</p>
            <h2 className="mt-2 text-xl font-semibold text-ink">训练后的下一步</h2>
            <div className="mt-4 grid gap-3">
              <ReviewAction
                title="最近报告"
                description={latestReport ? `最近得分 ${latestReport.overall_score}` : "完成训练后生成报告"}
                onClick={() => (latestReport ? router.push(`/report/${latestReport.session_id}`) : router.push("/practice"))}
              />
              <ReviewAction title="错题本" description={`${wrongBook.data?.length ?? 0} 道题待沉淀`} onClick={() => router.push("/wrong-book")} />
              <ReviewAction
                title="能力诊断"
                description={weakRadar ? `${weakRadar.tag} 当前最低` : "等待更多训练数据"}
                onClick={() => document.getElementById("ability-diagnosis")?.scrollIntoView({ behavior: "smooth" })}
              />
            </div>
          </AppCard>

          <AppCard className="p-5">
            <p className="text-sm font-semibold text-brand">推荐知识点</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {targetAbilities.slice(0, 8).map((item) => (
                <Badge key={item} className="border-brand/20 bg-brandSoft text-brand">
                  {item}
                </Badge>
              ))}
              {targetAbilities.length === 0 ? <span className="text-sm text-muted">暂无推荐知识点，先完成一次训练。</span> : null}
            </div>
          </AppCard>
        </aside>
      </section>
    </PageShell>
  );
}

function HeroNote({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-2xl border border-line bg-white/80 p-4">
      <p className="text-sm font-semibold text-ink">{title}</p>
      <p className="mt-1 text-xs leading-5 text-muted">{description}</p>
    </div>
  );
}

function Metric({ value, label, helper }: { value: string; label: string; helper: string }) {
  return (
    <div className="rounded-2xl border border-line bg-white p-4">
      <div className="truncate text-xl font-semibold text-ink">{value}</div>
      <div className="mt-1 text-sm font-medium text-ink">{label}</div>
      <div className="mt-1 text-xs text-muted">{helper}</div>
    </div>
  );
}

function TrainingTask({
  task,
  onStart,
  disabled,
}: {
  task: PracticePlanTask;
  onStart: () => void;
  disabled?: boolean;
}) {
  const Icon = taskIcon(task.type);

  return (
    <AppCard className="flex min-h-[230px] flex-col p-5">
      <div className="flex items-center gap-2 text-sm font-semibold text-ink">
        <span className="grid h-9 w-9 place-items-center rounded-2xl bg-brandSoft text-brand">
          <Icon className="h-4 w-4" />
        </span>
        {task.title}
      </div>
      <p className="mt-4 text-sm leading-6 text-muted">{task.reason}</p>
      <p className="mt-3 text-sm leading-6 text-ink">{task.outcome}</p>
      <AppButton className="mt-auto" onClick={onStart} disabled={disabled}>
        {disabled ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
        {task.action_label}
      </AppButton>
    </AppCard>
  );
}

function ReviewAction({ title, description, onClick }: { title: string; description: string; onClick: () => void }) {
  return (
    <button
      className="group flex w-full items-center justify-between gap-3 rounded-2xl border border-line bg-white p-4 text-left transition hover:border-brand/30 hover:bg-brandMist"
      onClick={onClick}
      type="button"
    >
      <span>
        <span className="block text-sm font-semibold text-ink">{title}</span>
        <span className="mt-1 block text-xs text-muted">{description}</span>
      </span>
      <ChevronRight className="h-4 w-4 text-muted transition group-hover:text-brand" />
    </button>
  );
}

function taskIcon(type: PracticePlanTask["type"]) {
  if (type === "resume_session") return Clock3;
  if (type === "wrong_book_review") return BookOpenCheck;
  if (type === "weak_tag_training") return Target;
  if (type === "mock_interview") return Gauge;
  return Search;
}

function SelectField({
  label,
  value,
  onChange,
  onResetPage,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onResetPage: () => void;
  children: React.ReactNode;
}) {
  return (
    <label className="grid gap-2 text-sm">
      <span className="font-medium text-ink">{label}</span>
      <select
        className={cn(
          "h-11 rounded-control border border-line bg-white px-3 text-sm text-ink transition",
          "focus:border-brand focus:outline-none focus:ring-4 focus:ring-brand/10"
        )}
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
          onResetPage();
        }}
      >
        {children}
      </select>
    </label>
  );
}
