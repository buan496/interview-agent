"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock3, FileText, Loader2, Mic, Send, ShieldCheck, Square } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Badge, Button, Panel } from "@/components/ui";
import { getSession, submitAnswer, transcribeAudio } from "@/lib/session-api";
import { readSse } from "@/lib/sse";
import type { Message, SseDonePayload, Verdict } from "@/lib/types";

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
  const [secondsLeft, setSecondsLeft] = useState(45 * 60);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const questions = session.data?.questions ?? [];
  const current = questions.find((item) => item.final_score == null) ?? questions.at(-1);
  const currentIndex = current ? questions.findIndex((item) => item.sq_id === current.sq_id) : -1;
  const messages = useMemo<Message[]>(() => current?.messages ?? [], [current]);
  const isFinished = session.data?.status === "finished";
  const isTerminal = ["finished", "expired", "cancelled"].includes(session.data?.status ?? "");

  useEffect(() => {
    if (typeof session.data?.remaining_seconds === "number") {
      setSecondsLeft(session.data.remaining_seconds);
    }
  }, [session.data?.remaining_seconds]);

  useEffect(() => {
    if (session.data?.mode !== "mock" || isTerminal) return;
    const timer = window.setInterval(() => setSecondsLeft((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [session.data?.mode, isTerminal]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!current || !answer.trim() || pending || isTerminal) return;
    setPending(true);
    setStreamingText("");
    setVerdict(null);
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
          setStreamingText(payload.message);
        }
      });
      await queryClient.invalidateQueries({ queryKey: ["session", params.id] });
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
    return <main className="grid min-h-[calc(100vh-3.5rem)] place-items-center"><Loader2 className="h-6 w-6 animate-spin text-brand" /></main>;
  }
  if (!current) return <main className="p-6 text-sm text-muted">会话不存在</main>;

  const minutes = Math.floor(secondsLeft / 60).toString().padStart(2, "0");
  const seconds = (secondsLeft % 60).toString().padStart(2, "0");

  return (
    <main className="mx-auto grid max-w-7xl gap-5 px-4 py-5 sm:px-6 lg:grid-cols-[380px_1fr]">
      <Panel className="h-fit p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            <Badge>第 {Math.max(1, currentIndex + 1)} / {questions.length} 题</Badge>
            <Badge>难度 {current.question.difficulty}</Badge>
            <Badge>{current.question.qtype}</Badge>
          </div>
          {session.data?.mode === "mock" ? <span className="flex items-center gap-1 text-xs text-muted"><Clock3 className="h-3.5 w-3.5" />{minutes}:{seconds}</span> : null}
        </div>
        <div className="mb-4 h-1.5 overflow-hidden rounded bg-panel">
          <div className="h-full bg-brand transition-all" style={{ width: `${Math.max(8, ((currentIndex + (current.final_score != null ? 1 : 0)) / questions.length) * 100)}%` }} />
        </div>
        <div className="mb-4 flex flex-wrap gap-2">
          {current.question.tags.slice(0, 4).map((tag) => <Badge key={tag.id}>{tag.name}</Badge>)}
        </div>
        <h1 className="text-xl font-semibold leading-8 text-ink">{current.question.title}</h1>
        {current.question.body ? <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-muted">{current.question.body}</p> : null}
        {current.final_score != null ? (
          <div className="mt-5 rounded border border-line bg-panel p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-ink"><ShieldCheck className="h-4 w-4 text-brand" />{current.final_score} 分</div>
            <p className="mt-1 text-sm text-muted">掌握度：{current.mastery}</p>
          </div>
        ) : null}
        {isFinished ? (
          <Link href={`/report/${params.id}`} className="mt-5 inline-flex h-10 w-full items-center justify-center gap-2 rounded bg-brand px-4 text-sm font-medium text-white">
            <FileText className="h-4 w-4" />查看完整报告
          </Link>
        ) : null}
      </Panel>

      <section className="grid min-h-[calc(100vh-6rem)] grid-rows-[1fr_auto] overflow-hidden rounded border border-line bg-white shadow-soft">
        <div className="space-y-3 overflow-y-auto p-4">
          {messages.map((message) => <MessageBubble key={message.id} message={message} />)}
          {streamingText ? <div className="flex justify-start"><div className="max-w-[86%] rounded border border-line bg-panel px-4 py-3 text-sm leading-6 text-ink">{streamingText}</div></div> : null}
          {verdict ? <div className="rounded border border-[#f0d2c6] bg-[#fff6f2] p-4"><div className="text-sm font-semibold text-ink">参考答案</div><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-muted">{verdict.ideal_answer}</p></div> : null}
        </div>

        <form onSubmit={submit} className="border-t border-line bg-white p-4">
          <textarea className="min-h-28 w-full resize-none rounded border border-line bg-white p-3 text-sm leading-6" value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder="输入你的回答，或点击麦克风进行语音转写" disabled={pending || isTerminal} />
          {audioError ? <p className="mt-2 text-xs text-accent">{audioError}</p> : null}
          <div className="mt-3 flex items-center justify-between gap-3">
            <Button type="button" variant="secondary" onClick={toggleRecording} disabled={pending || transcribing || isTerminal}>
              {transcribing ? <Loader2 className="h-4 w-4 animate-spin" /> : recording ? <Square className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              {transcribing ? "转写中" : recording ? "停止录音" : "语音作答"}
            </Button>
            <Button type="submit" disabled={pending || !answer.trim() || isTerminal}>
              {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}提交
            </Button>
          </div>
        </form>
      </section>
    </main>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isCandidate = message.role === "candidate";
  return (
    <div className={isCandidate ? "flex justify-end" : "flex justify-start"}>
      <div className={isCandidate ? "max-w-[86%] rounded bg-steel px-4 py-3 text-sm leading-6 text-white" : "max-w-[86%] rounded border border-line bg-panel px-4 py-3 text-sm leading-6 text-ink"}>
        <div className="mb-1 text-xs opacity-70">{isCandidate ? "候选人" : message.msg_type === "question" ? "题目" : "面试官"}</div>
        <div className="whitespace-pre-wrap">{message.content}</div>
      </div>
    </div>
  );
}
