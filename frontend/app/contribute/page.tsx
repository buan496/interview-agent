"use client";

import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Send } from "lucide-react";

import { Button, Panel } from "@/components/ui";
import { createSubmission } from "@/lib/api";

const initialForm = {
  submitter_name: "",
  company_name: "",
  position_name: "",
  title: "",
  body: "",
  answer_key: "",
  difficulty: "3",
  qtype: "knowledge",
  tags: ""
};

export default function ContributePage() {
  const [form, setForm] = useState(initialForm);
  const submission = useMutation({
    mutationFn: () =>
      createSubmission({
        submitter_name: form.submitter_name || undefined,
        company_name: form.company_name,
        position_name: form.position_name,
        title: form.title,
        body: form.body || undefined,
        answer_key: form.answer_key,
        difficulty: Number(form.difficulty),
        qtype: form.qtype,
        tags: form.tags.split(/[,，]/).map((item) => item.trim()).filter(Boolean)
      }),
    onSuccess: () => setForm(initialForm)
  });

  function update(name: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    submission.mutate();
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-6 sm:px-6">
      <h1 className="text-2xl font-semibold">投稿真实面试题</h1>
      <p className="mt-1 text-sm text-muted">请改写题目，避免粘贴受版权保护的面经原文。投稿会进入人工审核队列。</p>
      {submission.isSuccess ? (
        <Panel className="mt-5 flex items-center gap-3 border-[#b9ddd5] bg-[#f0faf7] p-4 text-sm text-brand">
          <CheckCircle2 className="h-5 w-5" />投稿成功，审核通过后会进入公开题库。
        </Panel>
      ) : null}
      <form onSubmit={submit} className="mt-5 grid gap-4">
        <Panel className="grid gap-4 p-5 md:grid-cols-2">
          <Field label="公司" value={form.company_name} onChange={(value) => update("company_name", value)} required />
          <Field label="岗位" value={form.position_name} onChange={(value) => update("position_name", value)} required />
          <Field label="投稿人（可选）" value={form.submitter_name} onChange={(value) => update("submitter_name", value)} />
          <Field label="标签（逗号分隔）" value={form.tags} onChange={(value) => update("tags", value)} placeholder="Redis, 高并发" />
          <label className="grid gap-1 text-sm">
            <span className="text-muted">题型</span>
            <select className="h-10 rounded border border-line bg-white px-3" value={form.qtype} onChange={(event) => update("qtype", event.target.value)}>
              <option value="knowledge">知识题</option><option value="coding">编码题</option><option value="system_design">系统设计</option><option value="behavioral">行为题</option>
            </select>
          </label>
          <label className="grid gap-1 text-sm">
            <span className="text-muted">难度</span>
            <select className="h-10 rounded border border-line bg-white px-3" value={form.difficulty} onChange={(event) => update("difficulty", event.target.value)}>
              {[1, 2, 3, 4, 5].map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
        </Panel>
        <Panel className="grid gap-4 p-5">
          <Field label="题目" value={form.title} onChange={(value) => update("title", value)} required />
          <Area label="补充说明" value={form.body} onChange={(value) => update("body", value)} />
          <Area label="参考答案与评分要点" value={form.answer_key} onChange={(value) => update("answer_key", value)} required minLength={20} />
          {submission.isError ? <p className="text-sm text-accent">提交失败，请检查必填项和参考答案长度。</p> : null}
          <div className="flex justify-end">
            <Button type="submit" disabled={submission.isPending}>
              {submission.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}提交审核
            </Button>
          </div>
        </Panel>
      </form>
    </main>
  );
}

function Field({ label, value, onChange, required, placeholder }: { label: string; value: string; onChange: (value: string) => void; required?: boolean; placeholder?: string }) {
  return <label className="grid gap-1 text-sm"><span className="text-muted">{label}</span><input className="h-10 rounded border border-line bg-white px-3" value={value} onChange={(event) => onChange(event.target.value)} required={required} placeholder={placeholder} /></label>;
}

function Area({ label, value, onChange, required, minLength }: { label: string; value: string; onChange: (value: string) => void; required?: boolean; minLength?: number }) {
  return <label className="grid gap-1 text-sm"><span className="text-muted">{label}</span><textarea className="min-h-28 rounded border border-line bg-white p-3 leading-6" value={value} onChange={(event) => onChange(event.target.value)} required={required} minLength={minLength} /></label>;
}
