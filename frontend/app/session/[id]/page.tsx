"use client";

import { FormEvent, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Send, ShieldCheck } from "lucide-react";

import { Badge, Button, Panel } from "@/components/ui";
import { API_BASE, getSession } from "@/lib/api";
import { readSse } from "@/lib/sse";
import type { Message, SseDonePayload, Verdict } from "@/lib/types";

export default function SessionPage({ params }: { params: { id: string } }) {
  const queryClient = useQueryClient();
  const session = useQuery({ queryKey: ["session", params.id], queryFn: () => getSession(params.id) });
  const [answer, setAnswer] = useState("");
  const [streamingText, setStreamingText] = useState("");
  const [pending, setPending] = useState(false);
  const [verdict, setVerdict] = useState<Verdict | null>(null);

  const current = session.data?.questions[0];
  const messages = useMemo<Message[]>(() => current?.messages ?? [], [current]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!current || !answer.trim() || pending) return;
    setPending(true);
    setStreamingText("");
    setVerdict(null);
    const content = answer.trim();
    setAnswer("");
    const response = await fetch(`${API_BASE}/sessions/${params.id}/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sq_id: current.sq_id, content })
    });
    if (!response.ok) {
      setPending(false);
      throw new Error(await response.text());
    }
    await readSse(response, (item) => {
      if (item.event === "token") {
        const payload = JSON.parse(item.data) as { text: string };
        setStreamingText((value) => value + payload.text);
      }
      if (item.event === "done") {
        const payload = JSON.parse(item.data) as SseDonePayload;
        setVerdict(payload.verdict ?? null);
      }
    });
    await queryClient.invalidateQueries({ queryKey: ["session", params.id] });
    setPending(false);
  }

  if (session.isLoading) {
    return (
      <main className="grid min-h-[calc(100vh-3.5rem)] place-items-center">
        <Loader2 className="h-6 w-6 animate-spin text-brand" />
      </main>
    );
  }

  if (!current) {
    return <main className="p-6 text-sm text-muted">会话不存在</main>;
  }

  return (
    <main className="mx-auto grid max-w-7xl gap-5 px-4 py-5 sm:px-6 lg:grid-cols-[380px_1fr]">
      <Panel className="h-fit p-5">
        <div className="mb-4 flex flex-wrap gap-2">
          <Badge>难度 {current.question.difficulty}</Badge>
          <Badge>{current.question.qtype}</Badge>
          {current.question.tags.slice(0, 4).map((tag) => (
            <Badge key={tag.id}>{tag.name}</Badge>
          ))}
        </div>
        <h1 className="text-xl font-semibold leading-8 text-ink">{current.question.title}</h1>
        {current.question.body ? <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-muted">{current.question.body}</p> : null}
        {current.final_score != null ? (
          <div className="mt-5 rounded border border-line bg-panel p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-ink">
              <ShieldCheck className="h-4 w-4 text-brand" />
              {current.final_score} 分
            </div>
            <p className="mt-1 text-sm text-muted">掌握度：{current.mastery}</p>
          </div>
        ) : null}
      </Panel>

      <section className="grid min-h-[calc(100vh-6rem)] grid-rows-[1fr_auto] overflow-hidden rounded border border-line bg-white shadow-soft">
        <div className="space-y-3 overflow-y-auto p-4">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {streamingText ? (
            <div className="flex justify-start">
              <div className="max-w-[86%] rounded border border-line bg-panel px-4 py-3 text-sm leading-6 text-ink">{streamingText}</div>
            </div>
          ) : null}
          {verdict ? (
            <div className="rounded border border-[#f0d2c6] bg-[#fff6f2] p-4">
              <div className="text-sm font-semibold text-ink">参考答案</div>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-muted">{verdict.ideal_answer}</p>
            </div>
          ) : null}
        </div>

        <form onSubmit={submit} className="border-t border-line bg-white p-4">
          <textarea
            className="min-h-28 w-full resize-none rounded border border-line bg-white p-3 text-sm leading-6"
            value={answer}
            onChange={(event) => setAnswer(event.target.value)}
            placeholder="输入你的回答"
            disabled={pending || current.final_score != null}
          />
          <div className="mt-3 flex justify-end">
            <Button type="submit" disabled={pending || !answer.trim() || current.final_score != null}>
              {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              提交
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
      <div
        className={
          isCandidate
            ? "max-w-[86%] rounded bg-steel px-4 py-3 text-sm leading-6 text-white"
            : "max-w-[86%] rounded border border-line bg-panel px-4 py-3 text-sm leading-6 text-ink"
        }
      >
        <div className="mb-1 text-xs opacity-70">{isCandidate ? "候选人" : message.msg_type === "question" ? "题目" : "面试官"}</div>
        <div className="whitespace-pre-wrap">{message.content}</div>
      </div>
    </div>
  );
}

