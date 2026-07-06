"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowRight,
  BookOpenCheck,
  CheckCircle2,
  Circle,
  Clock3,
  FileText,
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

import { Badge, Button, Panel } from "@/components/ui";
import { getSession, submitAnswer, transcribeAudio } from "@/lib/session-api";
import { readSse } from "@/lib/sse";
import type { Message, SessionDetail, SseDonePayload, Verdict } from "@/lib/types";

type SessionQuestion = SessionDetail["questions"][number];

const terminalStatuses = new Set(["finished", "expired", "cancelled"]);

const sessionStatusCopy: Record<string, string> = {
  created: "已创建",
  ongoing: "训练中",
  paused: "已暂停",
  finished: "已完成",
  expired: "已超时",
  cancelled: "已取消",
};

const questionStatusCopy: Record<string, string> = {
  pending: "等待中",
  answering: "作答中",
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
  const phase = getPhase(session.data?.status, current, pending, latestFollowup);
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
      <main className="grid min-h-[calc(100vh-3.5rem)] place-items-center">
        <Loader2 className="h-6 w-6 animate-spin text-brand" />
      </main>
    );
  }

  if (!current || !session.data) {
    return <main className="p-6 text-sm text-muted">会话不存在或已无法读取。</main>;
  }

  const timeText = formatSeconds(secondsLeft);
  const statusText = sessionStatusCopy[session.data.status] ?? session.data.status;
  const nextAction = getNextAction(session.data.status, current, visibleVerdict, pending);
  const answerStructure = getAnswerStructure(current.question.qtype);
  const answerGoal = getAnswerGoal(current.question.qtype);

  return (
    <main className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6">
      <section className="rounded border border-line bg-white px-4 py-3 shadow-soft">
        <div className="grid gap-3 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="border-brand/30 bg-[#edf7f4] text-brand">{statusText}</Badge>
              <Badge>{session.data.mode === "mock" ? "模拟面试" : "单题训练"}</Badge>
              <Badge>{questionStatusCopy[current.status] ?? current.status}</Badge>
              <Badge>{qtypeCopy[current.question.qtype] ?? current.question.qtype}</Badge>
            </div>
            <div className="mt-3 flex items-center gap-3">
              <div className="h-2 flex-1 overflow-hidden rounded bg-panel">
                <div className="h-full bg-brand transition-all" style={{ width: `${progressPercent}%` }} />
              </div>
              <span className="shrink-0 text-sm font-medium text-ink">
                第 {Math.max(1, currentIndex + 1)} / {Math.max(questions.length, session.data.total_questions)} 题
              </span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:min-w-[500px]">
            <Metric icon={Clock3} label="剩余时间" value={timeText} tone={secondsLeft <= 180 && !isTerminal ? "danger" : "default"} />
            <Metric icon={MessageSquareText} label="追问轮次" value={`${current.followup_count}/${session.data.max_followups}`} />
            <Metric icon={Target} label="当前阶段" value={phase.label} />
            <Metric icon={ShieldCheck} label="本题评分" value={current.final_score == null ? "--" : `${current.final_score}`} />
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)_340px]">
        <Panel className="p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink">
            <BookOpenCheck className="h-4 w-4 text-brand" />
            当前题目
          </div>
          <h1 className="mt-3 text-xl font-semibold leading-8 text-ink">{current.question.title}</h1>
          {current.question.body ? <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-muted">{current.question.body}</p> : null}

          <div className="mt-5 space-y-4">
            <InfoBlock title="本题考察点">
              <div className="flex flex-wrap gap-2">
                {current.question.tags.length ? current.question.tags.slice(0, 6).map((tag) => <Badge key={tag.id}>{tag.name}</Badge>) : <span>通用表达与基础理解</span>}
              </div>
            </InfoBlock>
            <InfoBlock title="答题目标">{answerGoal}</InfoBlock>
            <InfoBlock title="参考结构">
              <ol className="list-decimal space-y-1 pl-4">
                {answerStructure.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ol>
            </InfoBlock>
          </div>
        </Panel>

        <section className="grid min-h-[calc(100vh-12rem)] grid-rows-[auto_1fr_auto] overflow-hidden rounded border border-line bg-white shadow-soft">
          <div className="border-b border-line px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                <phase.icon className="h-4 w-4 text-brand" />
                {phase.label}
              </div>
              <span className="text-sm text-muted">{nextAction}</span>
            </div>
          </div>

          <div className="space-y-3 overflow-y-auto p-4">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {streamingText ? <MessageBubble message={{ id: -1, role: "interviewer", content: streamingText, msg_type: "followup" }} /> : null}
            {!messages.length && !streamingText ? <EmptyTrace /> : null}
          </div>

          <form onSubmit={submit} className="border-t border-line bg-white p-4">
            {actionError ? (
              <div className="mb-3 flex items-center gap-2 rounded border border-[#f0d2c6] bg-[#fff6f2] px-3 py-2 text-sm text-accent">
                <AlertCircle className="h-4 w-4" />
                {actionError}
              </div>
            ) : null}
            <textarea
              className="min-h-32 w-full resize-none rounded border border-line bg-white p-3 text-sm leading-6 text-ink placeholder:text-muted disabled:bg-panel"
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
              placeholder="输入你的回答，或使用语音作答。"
              disabled={!canAnswer}
            />
            {audioError ? <p className="mt-2 text-xs text-accent">{audioError}</p> : null}
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <Button type="button" variant="secondary" onClick={toggleRecording} disabled={!canAnswer || transcribing}>
                {transcribing ? <Loader2 className="h-4 w-4 animate-spin" /> : recording ? <Square className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                {transcribing ? "转写中" : recording ? "停止录音" : "语音作答"}
              </Button>
              <Button type="submit" disabled={!canAnswer || !answer.trim()}>
                {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                提交回答
              </Button>
            </div>
          </form>
        </section>

        <Panel className="p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink">
            <ShieldCheck className="h-4 w-4 text-brand" />
            AI 反馈
          </div>

          <div className="mt-4 space-y-4">
            <InfoBlock title="追问状态">
              {latestFollowup && current.status === "answering" ? (
                <p className="whitespace-pre-wrap">{latestFollowup.content}</p>
              ) : (
                <p>{current.followup_count > 0 ? "本题已有追问，继续围绕反馈补全回答。" : "当前暂无追问，提交后 AI 会判断是否需要继续深挖。"}</p>
              )}
            </InfoBlock>

            <InfoBlock title="评分结果">
              {visibleVerdict ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between rounded border border-line bg-panel px-3 py-2">
                    <span className="text-sm text-muted">得分</span>
                    <span className="text-lg font-semibold text-ink">{visibleVerdict.score}</span>
                  </div>
                  <div className="flex items-center justify-between rounded border border-line bg-panel px-3 py-2">
                    <span className="text-sm text-muted">掌握度</span>
                    <span className="text-sm font-medium text-ink">{masteryCopy[visibleVerdict.mastery] ?? visibleVerdict.mastery}</span>
                  </div>
                  <p className="whitespace-pre-wrap">{visibleVerdict.feedback}</p>
                </div>
              ) : (
                <p>完成作答后，这里会展示评分、掌握度和改进建议。</p>
              )}
            </InfoBlock>

            {visibleVerdict?.ideal_answer ? (
              <InfoBlock title="参考答案">
                <p className="whitespace-pre-wrap">{visibleVerdict.ideal_answer}</p>
              </InfoBlock>
            ) : null}

            <InfoBlock title="下一步">
              <div className="space-y-3">
                <p>{nextAction}</p>
                {session.data.status === "finished" ? (
                  <Link href={`/report/${params.id}`} className="inline-flex h-10 w-full items-center justify-center gap-2 rounded bg-brand px-4 text-sm font-medium text-white hover:bg-[#17675c]">
                    <FileText className="h-4 w-4" />
                    查看完整报告
                  </Link>
                ) : null}
                {session.data.status === "expired" ? (
                  <Link href="/practice" className="inline-flex h-10 w-full items-center justify-center gap-2 rounded border border-line bg-white px-4 text-sm font-medium text-ink hover:bg-panel">
                    <ArrowRight className="h-4 w-4" />
                    返回题库重练
                  </Link>
                ) : null}
              </div>
            </InfoBlock>
          </div>
        </Panel>
      </section>
    </main>
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

function getPhase(status: string | undefined, current: SessionQuestion | undefined, pending: boolean, latestFollowup: Message | undefined) {
  if (pending) return { label: "评分中", icon: Loader2 };
  if (status === "finished") return { label: "查看反馈", icon: CheckCircle2 };
  if (status === "expired") return { label: "已超时", icon: AlertCircle };
  if (status === "cancelled") return { label: "已取消", icon: AlertCircle };
  if (!current) return { label: "读取题目", icon: Circle };
  if (current.status === "scored") return { label: "查看反馈", icon: ShieldCheck };
  if (latestFollowup && current.status === "answering") return { label: "追问作答", icon: MessageSquareText };
  if (current.status === "answering") return { label: "作答中", icon: Target };
  return { label: questionStatusCopy[current.status] ?? current.status, icon: Circle };
}

function getNextAction(status: string, current: SessionQuestion, verdict: Verdict | null, pending: boolean) {
  if (pending) return "AI 正在评估本轮回答。";
  if (status === "finished") return "本轮训练已完成，可以查看完整报告。";
  if (status === "expired") return "会话已超时，本轮不能继续提交。";
  if (status === "cancelled") return "会话已取消。";
  if (current.status === "scored" || verdict) return "本题已完成，系统会进入下一题或生成报告。";
  if (current.followup_count > 0) return "回答追问，补齐缺失点后再次提交。";
  return "先组织结构化回答，再提交给 AI 面试官评估。";
}

function getAnswerGoal(qtype: string) {
  if (qtype === "coding") return "讲清思路、复杂度、边界条件，并能解释关键实现取舍。";
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
    <div className="rounded border border-line bg-panel px-3 py-2">
      <div className="flex items-center gap-1.5 text-xs text-muted">
        <Icon className={tone === "danger" ? "h-3.5 w-3.5 text-accent" : "h-3.5 w-3.5 text-brand"} />
        {label}
      </div>
      <div className={tone === "danger" ? "mt-1 text-base font-semibold text-accent" : "mt-1 text-base font-semibold text-ink"}>{value}</div>
    </div>
  );
}

function InfoBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="text-xs font-semibold uppercase tracking-normal text-muted">{title}</h2>
      <div className="mt-2 text-sm leading-6 text-ink">{children}</div>
    </section>
  );
}

function MessageBubble({ message }: { message: Pick<Message, "id" | "role" | "content" | "msg_type"> }) {
  const isCandidate = message.role === "candidate";
  const label = isCandidate ? "候选人" : message.msg_type === "question" ? "题目" : message.msg_type === "verdict" ? "评分反馈" : "AI 面试官";
  return (
    <div className={isCandidate ? "flex justify-end" : "flex justify-start"}>
      <div className={isCandidate ? "max-w-[88%] rounded bg-steel px-4 py-3 text-sm leading-6 text-white" : "max-w-[88%] rounded border border-line bg-panel px-4 py-3 text-sm leading-6 text-ink"}>
        <div className="mb-1 text-xs opacity-70">{label}</div>
        <div className="whitespace-pre-wrap">{message.content}</div>
      </div>
    </div>
  );
}

function EmptyTrace() {
  return (
    <div className="grid h-full min-h-56 place-items-center rounded border border-dashed border-line bg-panel px-6 text-center">
      <div>
        <Target className="mx-auto h-7 w-7 text-brand" />
        <p className="mt-3 text-sm font-medium text-ink">本题还没有作答记录</p>
        <p className="mt-1 text-sm text-muted">提交第一轮回答后，AI 反馈和追问会沉淀在这里。</p>
      </div>
    </div>
  );
}
