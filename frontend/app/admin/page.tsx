"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, Sparkles, X } from "lucide-react";

import { Badge, Button, Panel } from "@/components/ui";
import { generateFromJd, getSubmissions, reviewSubmission } from "@/lib/admin-api";

export default function AdminPage() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("pending_review");
  const [company, setCompany] = useState("");
  const [position, setPosition] = useState("");
  const [jd, setJd] = useState("");
  const submissions = useQuery({ queryKey: ["admin-submissions", status], queryFn: () => getSubmissions(status) });
  const review = useMutation({
    mutationFn: ({ id, action }: { id: number; action: "approve" | "reject" }) => reviewSubmission(id, action),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-submissions"] })
  });
  const generate = useMutation({
    mutationFn: () => generateFromJd({ jd_text: jd, company, position, count: 5 }),
    onSuccess: () => {
      setJd("");
      queryClient.invalidateQueries({ queryKey: ["admin-submissions"] });
    }
  });

  return (
    <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <div className="grid gap-5 lg:grid-cols-[360px_1fr]">
        <Panel className="h-fit p-5">
          <div className="flex items-center gap-2 font-semibold"><Sparkles className="h-4 w-4 text-brand" />从 JD 生成候选题</div>
          <div className="mt-4 grid gap-3">
            <input className="h-10 rounded border border-line px-3 text-sm" value={company} onChange={(event) => setCompany(event.target.value)} placeholder="公司" />
            <input className="h-10 rounded border border-line px-3 text-sm" value={position} onChange={(event) => setPosition(event.target.value)} placeholder="岗位" />
            <textarea className="min-h-52 rounded border border-line p-3 text-sm leading-6" value={jd} onChange={(event) => setJd(event.target.value)} placeholder="粘贴岗位 JD，系统会生成 5 道题进入审核队列" />
            <Button onClick={() => generate.mutate()} disabled={generate.isPending || jd.length < 30 || !company || !position}>
              {generate.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}生成候选题
            </Button>
          </div>
        </Panel>

        <section>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><h1 className="text-2xl font-semibold">题目审核</h1><p className="mt-1 text-sm text-muted">生成题和用户投稿统一在这里审核。</p></div>
            <select className="h-10 rounded border border-line bg-white px-3 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="pending_review">待审核</option><option value="approved">已通过</option><option value="rejected">已拒绝</option>
            </select>
          </div>
          <div className="mt-4 grid gap-3">
            {submissions.data?.map((item) => (
              <Panel key={item.id} className="p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap gap-2"><Badge>{item.source_type}</Badge><Badge>{item.company_name}</Badge><Badge>{item.position_name}</Badge><Badge>难度 {item.difficulty}</Badge></div>
                  <span className="text-xs text-muted">#{item.id}</span>
                </div>
                <h2 className="mt-3 font-semibold">{item.title}</h2>
                {item.body ? <p className="mt-2 text-sm leading-6 text-muted">{item.body}</p> : null}
                <details className="mt-3 rounded border border-line bg-panel p-3 text-sm"><summary className="cursor-pointer font-medium">参考答案</summary><p className="mt-2 whitespace-pre-wrap leading-6 text-muted">{item.answer_key}</p></details>
                {status === "pending_review" ? (
                  <div className="mt-4 flex justify-end gap-2">
                    <Button variant="secondary" onClick={() => review.mutate({ id: item.id, action: "reject" })}><X className="h-4 w-4" />拒绝</Button>
                    <Button onClick={() => review.mutate({ id: item.id, action: "approve" })}><Check className="h-4 w-4" />通过并入库</Button>
                  </div>
                ) : <p className="mt-3 text-xs text-muted">{item.review_note}</p>}
              </Panel>
            ))}
            {!submissions.isLoading && submissions.data?.length === 0 ? <Panel className="p-8 text-center text-sm text-muted">当前队列为空</Panel> : null}
          </div>
        </section>
      </div>
    </main>
  );
}
