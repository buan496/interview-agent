"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  BookOpenCheck,
  Clock3,
  ExternalLink,
  Filter,
  Gauge,
  Loader2,
  RotateCcw,
  Search,
  Target,
} from "lucide-react";
import { useRouter } from "next/navigation";

import { Badge, Button, Panel } from "@/components/ui";
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

  return (
    <main className="mx-auto grid max-w-7xl gap-5 px-4 py-5 sm:px-6">
      <section className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge className="border-brand/30 bg-[#edf7f4] text-brand">今日训练台</Badge>
            <Badge>训练闭环入口</Badge>
          </div>
          <h1 className="mt-3 text-2xl font-semibold text-ink">今天先完成一组有目标的面试训练</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            {practicePlan.data?.generated_reason ?? "系统会根据错题、薄弱标签和最近训练记录给出优先任务。题库仍然可用，但它是辅助入口，不再要求你自己乱找题。"}
          </p>
        </div>

        <Panel className="p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Gauge className="h-4 w-4 text-brand" />
            训练概览
          </div>
          <div className="mt-4 grid grid-cols-3 gap-3 text-center">
            <Metric value={`${wrongBook.data?.length ?? 0}`} label="错题" />
            <Metric value={weakRadar ? `${Number(weakRadar.avg_score).toFixed(0)}` : "--"} label="最低标签分" />
            <Metric value={`${reports.data?.length ?? 0}`} label="报告" />
          </div>
          {latestReport ? (
            <p className="mt-3 text-sm leading-6 text-muted">
              最近一次{latestReport.mode === "mock" ? "模拟面试" : "单题训练"}得分 {latestReport.overall_score}，建议继续补齐薄弱标签。
            </p>
          ) : (
            <p className="mt-3 text-sm leading-6 text-muted">完成第一轮训练后，这里会显示最近报告和能力变化。</p>
          )}
        </Panel>
      </section>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {practicePlan.data?.recommended_tasks.map((task) => (
          <TrainingTask key={task.id} task={task} onStart={() => startPlanTask(task)} disabled={startSession.isPending} />
        ))}
        {practicePlan.isLoading ? (
          <Panel className="grid min-h-[210px] place-items-center p-4 text-sm text-muted">
            <Loader2 className="h-5 w-5 animate-spin text-brand" />
          </Panel>
        ) : null}
      </section>

      <section className="grid gap-5 lg:grid-cols-[320px_1fr]">
        <Panel className="h-fit p-4">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Filter className="h-4 w-4 text-brand" />
              题库辅助筛选
            </div>
            <Button variant="ghost" className="h-8 px-2" onClick={reset} title="重置筛选">
              <RotateCcw className="h-4 w-4" />
            </Button>
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

            <Button className="mt-2" onClick={() => startSession.mutate(undefined)} disabled={startSession.isPending}>
              {startSession.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              按筛选开始训练
            </Button>
          </div>
        </Panel>

        <section className="grid gap-4">
          <div className="flex items-end justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold text-ink">题库辅助入口</h2>
              <p className="mt-1 text-sm text-muted">共 {questions.data?.total ?? 0} 题，选题后会进入受控 Session。</p>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {questions.data?.items.map((item) => (
              <Panel key={item.id} className="flex min-h-[230px] flex-col p-4">
                <div className="mb-3 flex flex-wrap gap-2">
                  <Badge>{item.company?.name ?? "通用"}</Badge>
                  <Badge>{item.position?.name ?? "岗位通用"}</Badge>
                  <Badge className="border-[#f0d2c6] bg-[#fff6f2] text-accent">难度 {item.difficulty}</Badge>
                </div>
                <h3 className="line-clamp-3 text-base font-semibold leading-6 text-ink">{item.title}</h3>
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
                <Button
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
                </Button>
              </Panel>
            ))}
          </div>

          {questions.data && questions.data.total > 12 ? (
            <div className="flex items-center justify-center gap-3">
              <Button variant="secondary" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1}>
                <ArrowLeft className="h-4 w-4" />
                上一页
              </Button>
              <span className="text-sm text-muted">
                第 {page} / {totalPages} 页
              </span>
              <Button variant="secondary" onClick={() => setPage((value) => Math.min(totalPages, value + 1))} disabled={page >= totalPages}>
                下一页
                <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          ) : null}

          {!questions.isLoading && questions.data?.items.length === 0 ? <Panel className="p-8 text-center text-sm text-muted">暂无匹配题目，请放宽筛选条件。</Panel> : null}
        </section>
      </section>
    </main>
  );
}

function Metric({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="text-lg font-semibold text-ink">{value}</div>
      <div className="mt-1 text-xs text-muted">{label}</div>
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
    <Panel className="flex min-h-[210px] flex-col p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-ink">
        <Icon className="h-4 w-4 text-brand" />
        {task.title}
      </div>
      <p className="mt-3 text-sm leading-6 text-muted">{task.reason}</p>
      <p className="mt-2 text-sm leading-6 text-ink">{task.outcome}</p>
      <Button className="mt-auto" onClick={onStart} disabled={disabled}>
        {disabled ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
        {task.action_label}
      </Button>
    </Panel>
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
    <label className="grid gap-1 text-sm">
      <span className="text-muted">{label}</span>
      <select
        className="h-10 rounded border border-line bg-white px-3"
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
