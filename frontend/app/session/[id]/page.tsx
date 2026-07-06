"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BookOpenCheck,
  CheckCircle2,
  Circle,
  Clock3,
  FileText,
  Gauge,
  Loader2,
  MessageSquareText,
  Mic,
  Send,
  ShieldCheck,
  Square,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { AppButton, AppCard, Badge, BrandLogo, PageShell, cn } from "@/components/ui";
import { getSession, submitAnswer, transcribeAudio } from "@/lib/session-api";
import { readSse } from "@/lib/sse";
import type { Message, SessionDetail, SseDonePayload, Verdict } from "@/lib/types";

type SessionQuestion = SessionDetail["questions"][number];

const terminalStatuses = new Set(["finished", "expired", "cancelled"]);

const sessionStatusCopy: Record<string, string> = {
  created: "已创建",
  ongoing: "训练中",
  paused: "已暂停",
  finished: "已结束",
  expired: "已超时",
  cancelled: "已取消",
};

const questionStatusCopy: Record<string, string> = {
  pending: "等待中",
  answering: "答题中",
  scored: "已评分",
  skipped: "已跳过",
  timeout: "已超时",
};

const qtypeCopy: Record<string, string> = {
  behavioral: "项目与行为",
  knowledge: "基础知识",
  coding: "编码能力",
  system_design: "系统设计",
};

const masteryCopy: Record<string, string> = {
  pass: "通过",
  weak: "薄弱",
  fail: "未通过",
};

export default function SessionPage() {
  const params = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const session = useQuery({ queryKey: ["session", params.id], queryFn: () => getSession(params.id) });
  const [answer, setAnswer] = useState("");
  const [streamingText, setStreamingText] = useState("");
  const [pending, setPending] = useState(false);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [audioError, setAudioError] = useState("");
  const [actionError, setActionError] = useState("");
  const [secondsLeft, setSecondsLeft] = useState(0);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const questions = useMemo(() => session.data?.questions ?? [], [session.data?.questions]);
  const current = useMemo(() => pickCurrentQuestion(session.data), [session.data]);
  const currentIndex = current ? questions.findIndex((item) => item.sq_id === current.sq_id) : -1;
  const messages = useMemo<Message[]>(() => current?.messages ?? [], [current]);
  const latestFollowup = useMemo(() => [...messages].reverse().find((message) => message.msg_type === "followup" || message.msg_type === "hint"), [messages]);
  const persistedVerdict = useMemo(() => getVerdictFromMessage([...messages].reverse().find((message) => message.msg_type === "verdict")), [messages]);
  const visibleVerdict = verdict ?? persistedVerdict;
  const isTerminal = terminalStatuses.has(session.data?.status ?? "");
  const canAnswer = Boolean(current && current.status === "answering" && !pending && !isTerminal);
  const phase = getPhase(session.data?.status, current, pending, latestFollowup, Boolean(answer.trim()));
  const progressPercent = getProgressPercent(session.data, current);

  useEffect(() => {
    if (typeof session.data?.remaining_seconds === "number") {
      setSecondsLeft(session.data.remaining_seconds);
    }
  }, [session.data?.remaining_seconds]);

  useEffect(() => {
    if (!session.data?.deadline_at || isTerminal) return;
    const timer = window.setInterval(() => setSecondsLeft((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [session.data?.deadline_at, isTerminal]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!current || !answer.trim() || !canAnswer) return;
    setPending(true);
    setStreamingText("");
    setVerdict(null);
    setActionError("");
    const content = answer.trim();
    setAnswer("");
    try {
      const response = await submitAnswer(params.id, { sq_id: current.sq_id, content });
      await readSse(response, (item) => {
        if (item.event === "token") {
          const payload = JSON.parse(item.data) as { text: string };
          setStreamingText((value) => value + payload.text);
        }
        if (item.event === "done") {
          const payload = JSON.parse(item.data) as SseDonePayload;
          setVerdict(payload.next_question ? null : payload.verdict ?? null);
        }
        if (item.event === "error") {
          const payload = JSON.parse(item.data) as { message: string };
          setActionError(payload.message);
        }
      });
      await queryClient.invalidateQueries({ queryKey: ["session", params.id] });
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "提交失败，请稍后重试。");
      setAnswer(content);
    } finally {
      setPending(false);
    }
  }

  async function toggleRecording() {
    setAudioError("");
    if (recording) {
      recorderRef.current?.stop();
      setRecording(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        setTranscribing(true);
        try {
          const payload = await transcribeAudio(blob);
          setAnswer((value) => `${value}${value ? "\n" : ""}${payload.text}`);
        } catch (error) {
          setAudioError(error instanceof Error ? error.message : "语音转写失败");
        } finally {
          setTranscribing(false);
        }
      };
      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setAudioError("无法访问麦克风，请检查浏览器权限。");
    }
  }

  if (session.isLoading) {
    return (
      <PageShell className="grid place-items-center">
        <Loader2 className="h-6 w-6 animate-spin text-brand" />
      </PageShell>
    );
  }

  if (!current || !session.data) {
    return (
      <PageShell>
        <AppCard className="p-8 text-sm text-muted">会话不存在或已无法读取。</AppCard>
      </PageShell>
    );
  }

  const timeText = formatSeconds(secondsLeft);
  const statusText = sessionStatusCopy[session.data.status] ?? session.data.status;
  const nextAction = getNextAction(session.data.status, current, visibleVerdict, pending);
  const answerStructure = getAnswerStructure(current.question.qtype);
  const answerGoal = getAnswerGoal(current.question.qtype);
  const totalQuestions = Math.max(questions.length, session.data.total_questions);
  const PhaseIcon = phase.icon;
  const questionNumber = Math.max(1, currentIndex + 1);

  return (
    <PageShell className="grid gap-6 pb-12">
      <AppCard className="overflow-hidden">
        <div className="grid gap-5 p-5 sm:p-6 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <BrandLogo variant="mark" className="h-10 w-10 rounded-2xl border border-line bg-white p-1.5 shadow-soft" />
              <div>
                <p className="text-sm font-semibold text-brand">{session.data.mode === "mock" ? "模拟面试 Session" : "单题训练 Session"}</p>
                <h1 className="mt-1 text-2xl font-semibold text-ink">第 {questionNumber} / {totalQuestions} 题</h1>
              </div>
              <Badge className={cn("ml-0 border-brand/20 bg-brandSoft text-brand lg:ml-2", phase.tone === "danger" && "border-accent/20 bg-[#fff6f2] text-accent")}>
                <PhaseIcon className={cn("mr-1 h-3.5 w-3.5", pending && "animate-spin")} />
                {phase.label}
              </Badge>
              <Badge>{statusText}</Badge>
            </div>
            <div className="mt-5 h-2 overflow-hidden rounded-full bg-brandSoft">
              <div className="h-full rounded-full bg-brand transition-all" style={{ width: `${progressPercent}%` }} />
            </div>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">{nextAction}</p>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:min-w-[560px]">
            <Metric icon={Clock3} label="剩余时间" value={timeText} tone={secondsLeft <= 180 && !isTerminal ? "danger" : "default"} />
            <Metric icon={MessageSquareText} label="追问轮次" value={`${current.followup_count}/${session.data.max_followups}`} />
            <Metric icon={Gauge} label="当前状态" value={phase.label} />
            <Metric icon={ShieldCheck} label="本题评分" value={current.final_score == null ? "--" : `${current.final_score}`} />
          </div>
        </div>
      </AppCard>

      {isTerminal ? <FinishedSessionCard status={session.data.status} sessionId={params.id} /> : null}

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="grid gap-5">
          <AppCard className="p-5 sm:p-6">
            <div className="flex flex-wrap items-center gap-2">
              <Badge>{qtypeCopy[current.question.qtype] ?? current.question.qtype}</Badge>
              <Badge>难度 {current.question.difficulty}</Badge>
              <Badge>{questionStatusCopy[current.status] ?? current.status}</Badge>
              {current.question.tags.slice(0, 5).map((tag) => (
                <Badge key={tag.id} className="border-brand/20 bg-brandSoft text-brand">
                  {tag.name}
                </Badge>
              ))}
            </div>
            <h2 className="mt-5 text-2xl font-semibold leading-9 text-ink">{current.question.title}</h2>
            {current.question.body ? <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-muted">{current.question.body}</p> : null}
          </AppCard>

          <AppCard className="overflow-hidden">
            <div className="border-b border-line bg-white/80 px-5 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                  <PhaseIcon className={cn("h-4 w-4 text-brand", pending && "animate-spin")} />
                  答题工作区
                </div>
                <span className="text-sm text-muted">{canAnswer ? "组织回答后提交给 AI 面试官评分。" : "当前状态不可提交回答。"}</span>
              </div>
            </div>

            <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_300px]">
              <div className="grid gap-4">
                <section className="max-h-[420px] min-h-[260px] overflow-y-auto rounded-3xl border border-line bg-brandMist p-4">
                  <div className="grid gap-3">
                    {messages.map((message) => (
                      <MessageBubble key={message.id} message={message} />
                    ))}
                    {streamingText ? <MessageBubble message={{ id: -1, role: "interviewer", content: streamingText, msg_type: "followup" }} /> : null}
                    {!messages.length && !streamingText ? <EmptyTrace /> : null}
                  </div>
                </section>

                <form onSubmit={submit} className="grid gap-3">
                  {actionError ? (
                    <div className="flex items-center gap-2 rounded-2xl border border-[#f0d2c6] bg-[#fff6f2] px-4 py-3 text-sm text-accent">
                      <AlertCircle className="h-4 w-4" />
                      {actionError}
                    </div>
                  ) : null}
                  <textarea
                    className="min-h-36 w-full resize-none rounded-3xl border border-line bg-white p-4 text-sm leading-6 text-ink shadow-[0_1px_0_rgba(15,23,42,0.02)] transition placeholder:text-[#98a2b3] focus:border-brand focus:outline-none focus:ring-4 focus:ring-brand/10 disabled:bg-panel"
                    value={answer}
                    onChange={(event) => setAnswer(event.target.value)}
                    placeholder="输入你的回答，建议先给结论，再解释关键依据和取舍。也可以使用语音作答。"
                    disabled={!canAnswer}
                  />
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-xs leading-5 text-muted">
                      {!answer.trim() && canAnswer ? "请先填写回答内容，提交按钮会自动启用。" : pending ? "AI 正在评分，请不要重复提交。" : "回答会进入本轮 Session 记录，并用于生成报告。"}
                    </p>
                    <div className="flex flex-col gap-3 sm:flex-row">
                      <AppButton type="button" variant="secondary" onClick={toggleRecording} disabled={!canAnswer || transcribing}>
                        {transcribing ? <Loader2 className="h-4 w-4 animate-spin" /> : recording ? <Square className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                        {transcribing ? "转写中" : recording ? "停止录音" : "语音作答"}
                      </AppButton>
                      <AppButton type="submit" disabled={!canAnswer || !answer.trim()}>
                        {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                        {pending ? "评分中" : "提交回答"}
                      </AppButton>
                    </div>
                  </div>
                  {audioError ? <p className="text-xs text-accent">{audioError}</p> : null}
                </form>
              </div>

              <div className="grid content-start gap-4">
                <InfoPanel title="答题目标" icon={Target}>
                  <p>{answerGoal}</p>
                </InfoPanel>
                <InfoPanel title="推荐结构" icon={BookOpenCheck}>
                  <ol className="list-decimal space-y-1 pl-4">
                    {answerStructure.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ol>
                </InfoPanel>
                <InfoPanel title="下一步" icon={ArrowRight}>
                  <p>{nextAction}</p>
                </InfoPanel>
              </div>
            </div>
          </AppCard>
        </div>

        <aside className="grid h-fit gap-5">
          <AppCard className="p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-ink">
              <ShieldCheck className="h-4 w-4 text-brand" />
              AI 反馈
            </div>

            <div className="mt-5 grid gap-4">
              <FeedbackSection title="追问内容">
                {latestFollowup && current.status === "answering" ? (
                  <p className="whitespace-pre-wrap">{latestFollowup.content}</p>
                ) : (
                  <p>{current.followup_count > 0 ? "本题已有追问，继续围绕反馈补全回答。" : "当前暂无追问，提交后 AI 会判断是否需要继续深挖。"}</p>
                )}
              </FeedbackSection>

              <FeedbackSection title="总体评价">
                {visibleVerdict ? (
                  <div className="grid gap-3">
                    <div className="grid grid-cols-2 gap-3">
                      <ScoreTile label="得分" value={`${visibleVerdict.score}`} />
                      <ScoreTile label="掌握度" value={masteryCopy[visibleVerdict.mastery] ?? visibleVerdict.mastery} />
                    </div>
                    <p className="whitespace-pre-wrap">{visibleVerdict.feedback}</p>
                  </div>
                ) : (
                  <p>完成作答后，这里会展示即时评分、掌握度和总体反馈。</p>
                )}
              </FeedbackSection>

              <FeedbackSection title="优点 / 问题 / 改进建议">
                <p>
                  即时反馈会先给总体评价；训练结束后，完整报告会按优点、缺失点、表达问题和行动项拆开展示。
                </p>
              </FeedbackSection>

              {visibleVerdict?.ideal_answer ? (
                <FeedbackSection title="参考答案">
                  <details className="rounded-2xl border border-line bg-white p-3">
                    <summary className="cursor-pointer text-sm font-semibold text-ink">展开参考答案</summary>
                    <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-muted">{visibleVerdict.ideal_answer}</p>
                  </details>
                </FeedbackSection>
              ) : null}

              <FeedbackSection title="页面入口">
                <div className="grid gap-3">
                  {session.data.status === "finished" ? (
                    <LinkButton href={`/report/${params.id}`} variant="primary">
                      <FileText className="h-4 w-4" />
                      查看报告
                    </LinkButton>
                  ) : null}
                  <LinkButton href="/practice" variant="secondary">
                    <ArrowLeft className="h-4 w-4" />
                    返回今日训练
                  </LinkButton>
                </div>
              </FeedbackSection>
            </div>
          </AppCard>
        </aside>
      </section>
    </PageShell>
  );
}

function pickCurrentQuestion(session: SessionDetail | undefined): SessionQuestion | undefined {
  if (!session) return undefined;
  const byBackendIndex = session.questions[session.current_question_index - 1];
  if (byBackendIndex && byBackendIndex.status !== "pending") return byBackendIndex;
  return session.questions.find((item) => item.status === "answering") ?? session.questions.find((item) => item.final_score == null) ?? session.questions.at(-1);
}

function getProgressPercent(session: SessionDetail | undefined, current: SessionQuestion | undefined) {
  if (!session || !current) return 0;
  const total = Math.max(1, session.total_questions || session.questions.length);
  const completed = session.questions.filter((item) => item.final_score != null || ["scored", "skipped", "timeout"].includes(item.status)).length;
  const activeOffset = current.status === "answering" ? 0.35 : 0;
  return Math.min(100, Math.max(6, ((completed + activeOffset) / total) * 100));
}

function getPhase(status: string | undefined, current: SessionQuestion | undefined, pending: boolean, latestFollowup: Message | undefined, hasDraft: boolean) {
  if (pending) return { label: "评分中", icon: Loader2, tone: "default" as const };
  if (status === "finished") return { label: "已结束", icon: CheckCircle2, tone: "default" as const };
  if (status === "expired") return { label: "已超时", icon: AlertCircle, tone: "danger" as const };
  if (status === "cancelled") return { label: "已取消", icon: AlertCircle, tone: "danger" as const };
  if (!current) return { label: "读取题目", icon: Circle, tone: "default" as const };
  if (current.status === "scored") return { label: "已评分", icon: ShieldCheck, tone: "default" as const };
  if (latestFollowup && current.status === "answering") return { label: "追问作答", icon: MessageSquareText, tone: "default" as const };
  if (current.status === "answering") return { label: hasDraft ? "答题中" : "准备答题", icon: Target, tone: "default" as const };
  return { label: questionStatusCopy[current.status] ?? current.status, icon: Circle, tone: "default" as const };
}

function getNextAction(status: string, current: SessionQuestion, verdict: Verdict | null, pending: boolean) {
  if (pending) return "AI 正在评估本轮回答，请等待评分或追问结果。";
  if (status === "finished") return "本轮训练已完成，可以查看完整报告或返回今日训练。";
  if (status === "expired") return "会话已超时，本轮不能继续提交。";
  if (status === "cancelled") return "会话已取消，请返回今日训练重新开始。";
  if (current.status === "scored" || verdict) return "本题已评分，系统会进入下一题或生成报告。";
  if (current.followup_count > 0) return "回答追问，补齐缺失点后再次提交。";
  return "先组织结构化回答，再提交给 AI 面试官评估。";
}

function getAnswerGoal(qtype: string) {
  if (qtype === "coding") return "讲清思路、复杂度、边界条件，并解释关键实现取舍。";
  if (qtype === "system_design") return "从需求、约束、核心模型、关键链路和扩展性逐层展开。";
  if (qtype === "behavioral") return "用具体场景说明背景、行动、结果和复盘，避免空泛描述。";
  return "准确覆盖核心概念、原理、适用场景和常见误区。";
}

function getAnswerStructure(qtype: string) {
  if (qtype === "coding") return ["确认输入输出与边界", "说明算法思路和复杂度", "补充异常场景与优化点"];
  if (qtype === "system_design") return ["澄清目标和规模", "设计核心数据模型与链路", "说明瓶颈、容错和演进方案"];
  if (qtype === "behavioral") return ["交代背景和目标", "说明你的关键行动", "量化结果并给出复盘"];
  return ["先给结论", "解释底层原理", "结合场景说明取舍"];
}

function getVerdictFromMessage(message: Message | undefined): Verdict | null {
  const raw = message?.eval_json?.verdict;
  if (!raw || typeof raw !== "object") return null;
  const data = raw as Partial<Verdict>;
  const mastery = data.mastery === "pass" || data.mastery === "weak" || data.mastery === "fail" ? data.mastery : "weak";
  return {
    score: typeof data.score === "number" ? data.score : 0,
    mastery,
    feedback: typeof data.feedback === "string" ? data.feedback : message?.content ?? "",
    ideal_answer: typeof data.ideal_answer === "string" ? data.ideal_answer : "",
  };
}

function formatSeconds(total: number) {
  const minutes = Math.floor(total / 60).toString().padStart(2, "0");
  const seconds = (total % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function Metric({
  icon: Icon,
  label,
  value,
  tone = "default",
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  tone?: "default" | "danger";
}) {
  return (
    <div className="rounded-2xl border border-line bg-white px-3 py-2 shadow-soft">
      <div className="flex items-center gap-1.5 text-xs text-muted">
        <Icon className={tone === "danger" ? "h-3.5 w-3.5 text-accent" : "h-3.5 w-3.5 text-brand"} />
        {label}
      </div>
      <div className={tone === "danger" ? "mt-1 truncate text-base font-semibold text-accent" : "mt-1 truncate text-base font-semibold text-ink"}>{value}</div>
    </div>
  );
}

function InfoPanel({ title, icon: Icon, children }: { title: string; icon: React.ComponentType<{ className?: string }>; children: React.ReactNode }) {
  return (
    <section className="rounded-3xl border border-line bg-white p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-ink">
        <Icon className="h-4 w-4 text-brand" />
        {title}
      </div>
      <div className="mt-3 text-sm leading-6 text-muted">{children}</div>
    </section>
  );
}

function FeedbackSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      <div className="mt-2 text-sm leading-6 text-muted">{children}</div>
    </section>
  );
}

function ScoreTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-line bg-brandMist p-3">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 text-lg font-semibold text-ink">{value}</p>
    </div>
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

function FinishedSessionCard({ status, sessionId }: { status: string; sessionId: string }) {
  const isFinished = status === "finished";
  return (
    <AppCard className="border-brand/20 bg-white p-5 sm:p-6">
      <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-center">
        <div>
          <p className="text-sm font-semibold text-brand">{isFinished ? "本轮训练已完成" : "本轮训练已停止"}</p>
          <h2 className="mt-2 text-2xl font-semibold text-ink">{isFinished ? "查看报告，把反馈转成下一轮计划" : "返回今日训练，重新选择下一步"}</h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            {isFinished ? "报告会整理得分、薄弱点、参考答案和后续行动项。" : "当前会话不能继续提交，可以回到今日训练重新开始。"}
          </p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          {isFinished ? (
            <LinkButton href={`/report/${sessionId}`} variant="primary">
              <FileText className="h-4 w-4" />
              查看报告
            </LinkButton>
          ) : null}
          <LinkButton href="/practice" variant="secondary">
            <ArrowLeft className="h-4 w-4" />
            返回今日训练
          </LinkButton>
          <LinkButton href="/practice" variant="secondary">
            <ArrowRight className="h-4 w-4" />
            再练一轮
          </LinkButton>
        </div>
      </div>
    </AppCard>
  );
}

function MessageBubble({ message }: { message: Pick<Message, "id" | "role" | "content" | "msg_type"> }) {
  const isCandidate = message.role === "candidate";
  const label = isCandidate ? "候选人" : message.msg_type === "question" ? "题目" : message.msg_type === "verdict" ? "评分反馈" : "AI 面试官";
  return (
    <div className={isCandidate ? "flex justify-end" : "flex justify-start"}>
      <div
        className={
          isCandidate
            ? "max-w-[88%] rounded-3xl bg-brand px-4 py-3 text-sm leading-6 text-white shadow-button"
            : "max-w-[88%] rounded-3xl border border-line bg-white px-4 py-3 text-sm leading-6 text-ink shadow-soft"
        }
      >
        <div className="mb-1 text-xs opacity-70">{label}</div>
        <div className="whitespace-pre-wrap">{message.content}</div>
      </div>
    </div>
  );
}

function EmptyTrace() {
  return (
    <div className="grid h-full min-h-56 place-items-center rounded-3xl border border-dashed border-line bg-white/75 px-6 text-center">
      <div>
        <Target className="mx-auto h-7 w-7 text-brand" />
        <p className="mt-3 text-sm font-medium text-ink">本题还没有作答记录</p>
        <p className="mt-1 text-sm text-muted">提交第一轮回答后，AI 反馈和追问会沉淀在这里。</p>
      </div>
    </div>
  );
}
