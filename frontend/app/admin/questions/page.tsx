"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, CheckCircle2, Edit3, Loader2, Plus, RotateCcw, Save } from "lucide-react";

import {
  AdminAccessDenied,
  AdminError,
  AdminField,
  AdminSectionHeader,
  AdminShell,
  StatusBadge,
  adminInputClass,
  adminTextareaClass,
  isForbidden,
} from "@/components/admin-console";
import { AppButton, AppCard, Badge, cn } from "@/components/ui";
import {
  archiveAdminQuestion,
  createAdminQuestion,
  getAdminQuestions,
  getAdminRubrics,
  publishAdminQuestion,
  updateAdminQuestion,
} from "@/lib/admin-console-api";
import type { AdminQuestion, AdminQuestionPayload, AdminQuestionType } from "@/lib/admin-console-types";

const emptyForm = {
  title: "",
  prompt: "",
  answer_reference: "",
  difficulty: "3",
  qtype: "knowledge" as AdminQuestionType,
  company_name: "",
  position_name: "",
  tags: "",
  source_note: "",
  status: "draft" as "draft" | "published",
  default_rubric_version_id: "",
};

export default function AdminQuestionsPage() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [tag, setTag] = useState("");
  const [position, setPosition] = useState("");
  const [editing, setEditing] = useState<AdminQuestion | null>(null);
  const [form, setForm] = useState(emptyForm);

  const questions = useQuery({
    queryKey: ["admin-questions", status, difficulty, tag, position],
    queryFn: () => getAdminQuestions({ status, difficulty, tag, position, limit: 100 }),
    retry: false,
  });
  const rubrics = useQuery({
    queryKey: ["admin-rubrics", "published-for-question"],
    queryFn: () => getAdminRubrics({ limit: 100 }),
    retry: false,
  });

  const publishedVersions = useMemo(
    () => (rubrics.data?.items ?? []).flatMap((rubric) => rubric.versions.filter((version) => version.status === "published").map((version) => ({ rubric, version }))),
    [rubrics.data?.items]
  );

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["admin-questions"] });
    queryClient.invalidateQueries({ queryKey: ["admin-rubrics"] });
  };

  const save = useMutation({
    mutationFn: () => {
      const payload = toQuestionPayload(form);
      return editing ? updateAdminQuestion(editing.id, payload) : createAdminQuestion(payload);
    },
    onSuccess: () => {
      setEditing(null);
      setForm(emptyForm);
      invalidate();
    },
  });

  const publish = useMutation({
    mutationFn: publishAdminQuestion,
    onSuccess: invalidate,
  });

  const archive = useMutation({
    mutationFn: archiveAdminQuestion,
    onSuccess: invalidate,
  });

  if (isForbidden(questions.error) || isForbidden(rubrics.error)) {
    return <AdminAccessDenied />;
  }

  function startEdit(question: AdminQuestion) {
    setEditing(question);
    setForm({
      title: question.title,
      prompt: question.body ?? "",
      answer_reference: question.answer_reference,
      difficulty: String(question.difficulty),
      qtype: question.qtype,
      company_name: question.company?.name ?? "",
      position_name: question.position?.name ?? "",
      tags: question.tags.map((item) => item.name).join(", "),
      source_note: question.source_note ?? "",
      status: question.status === "published" ? "published" : "draft",
      default_rubric_version_id: question.default_rubric_version_id ? String(question.default_rubric_version_id) : "",
    });
  }

  function resetForm() {
    setEditing(null);
    setForm(emptyForm);
  }

  const canSave = form.title.trim().length >= 6 && form.answer_reference.trim().length >= 20;

  return (
    <AdminShell
      eyebrow="Question Bank"
      title="题库管理"
      description="管理面向 Agent 工程师岗位的面试题。普通用户只会读取已发布题目，草稿和归档题不会进入用户侧题库。"
      actions={
        <>
          <Link href="/admin">
            <AppButton variant="secondary">后台总览</AppButton>
          </Link>
          <Link href="/admin/rubrics">
            <AppButton variant="secondary">Rubric 管理</AppButton>
          </Link>
        </>
      }
    >
      <section className="grid gap-5 xl:grid-cols-[420px_1fr]">
        <AppCard className="h-fit p-5">
          <AdminSectionHeader
            title={editing ? `编辑题目 #${editing.id}` : "创建题目"}
            description="textarea 即可满足 v1 运营录入；不引入复杂富文本。"
            right={
              editing ? (
                <AppButton variant="ghost" className="h-9 px-3" onClick={resetForm}>
                  <RotateCcw className="h-4 w-4" />
                  退出编辑
                </AppButton>
              ) : null
            }
          />
          <form
            className="mt-5 grid gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              if (canSave) save.mutate();
            }}
          >
            <AdminField label="题目标题">
              <input className={adminInputClass} value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="例如：如何设计 Agent 工具调用链路？" />
            </AdminField>
            <AdminField label="题目正文 / Prompt">
              <textarea className={adminTextareaClass} value={form.prompt} onChange={(event) => setForm({ ...form, prompt: event.target.value })} placeholder="补充题目背景、约束或追问方向" />
            </AdminField>
            <AdminField label="参考答案">
              <textarea className={cn(adminTextareaClass, "min-h-36")} value={form.answer_reference} onChange={(event) => setForm({ ...form, answer_reference: event.target.value })} placeholder="写清楚核心得分点，至少 20 个字符" />
            </AdminField>
            <div className="grid gap-3 sm:grid-cols-2">
              <AdminField label="题型">
                <select className={adminInputClass} value={form.qtype} onChange={(event) => setForm({ ...form, qtype: event.target.value as AdminQuestionType })}>
                  <option value="knowledge">知识点</option>
                  <option value="system_design">系统设计</option>
                  <option value="coding">编码题</option>
                  <option value="behavioral">行为面试</option>
                </select>
              </AdminField>
              <AdminField label="难度">
                <select className={adminInputClass} value={form.difficulty} onChange={(event) => setForm({ ...form, difficulty: event.target.value })}>
                  {[1, 2, 3, 4, 5].map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </AdminField>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <AdminField label="公司">
                <input className={adminInputClass} value={form.company_name} onChange={(event) => setForm({ ...form, company_name: event.target.value })} placeholder="可选" />
              </AdminField>
              <AdminField label="岗位">
                <input className={adminInputClass} value={form.position_name} onChange={(event) => setForm({ ...form, position_name: event.target.value })} placeholder="例如 AI Agent 工程师" />
              </AdminField>
            </div>
            <AdminField label="标签">
              <input className={adminInputClass} value={form.tags} onChange={(event) => setForm({ ...form, tags: event.target.value })} placeholder="逗号分隔，例如 RAG, Tool Use, Redis" />
            </AdminField>
            <AdminField label="默认 Rubric Version">
              <select className={adminInputClass} value={form.default_rubric_version_id} onChange={(event) => setForm({ ...form, default_rubric_version_id: event.target.value })}>
                <option value="">使用系统默认</option>
                {publishedVersions.map(({ rubric, version }) => (
                  <option key={version.id} value={version.id}>
                    #{version.id} {rubric.name} / {version.version}
                  </option>
                ))}
              </select>
            </AdminField>
            {!editing ? (
              <AdminField label="初始状态">
                <select className={adminInputClass} value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value as "draft" | "published" })}>
                  <option value="draft">草稿</option>
                  <option value="published">已发布</option>
                </select>
              </AdminField>
            ) : null}
            <AdminField label="来源备注">
              <input className={adminInputClass} value={form.source_note} onChange={(event) => setForm({ ...form, source_note: event.target.value })} placeholder="可选，来源链接或运营备注" />
            </AdminField>
            <AdminError error={save.error} />
            <AppButton type="submit" disabled={!canSave || save.isPending}>
              {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : editing ? <Save className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
              {editing ? "保存修改" : "创建题目"}
            </AppButton>
          </form>
        </AppCard>

        <div className="grid gap-5">
          <AppCard className="p-5">
            <AdminSectionHeader title="筛选" description={`当前共 ${questions.data?.total ?? 0} 道题`} />
            <div className="mt-4 grid gap-3 md:grid-cols-4">
              <AdminField label="状态">
                <select className={adminInputClass} value={status} onChange={(event) => setStatus(event.target.value)}>
                  <option value="">全部</option>
                  <option value="draft">草稿</option>
                  <option value="published">已发布</option>
                  <option value="archived">已归档</option>
                </select>
              </AdminField>
              <AdminField label="难度">
                <select className={adminInputClass} value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>
                  <option value="">全部</option>
                  {[1, 2, 3, 4, 5].map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </AdminField>
              <AdminField label="标签">
                <input className={adminInputClass} value={tag} onChange={(event) => setTag(event.target.value)} placeholder="精确标签名" />
              </AdminField>
              <AdminField label="岗位">
                <input className={adminInputClass} value={position} onChange={(event) => setPosition(event.target.value)} placeholder="精确岗位名" />
              </AdminField>
            </div>
          </AppCard>

          <AdminError error={questions.error || rubrics.error || publish.error || archive.error} />

          <div className="grid gap-3">
            {questions.isLoading ? (
              <AppCard className="grid min-h-40 place-items-center p-6 text-sm text-muted">
                <Loader2 className="h-5 w-5 animate-spin text-brand" />
              </AppCard>
            ) : null}
            {questions.data?.items.map((question) => (
              <QuestionCard
                key={question.id}
                question={question}
                onEdit={() => startEdit(question)}
                onPublish={() => publish.mutate(question.id)}
                onArchive={() => archive.mutate(question.id)}
                busy={publish.isPending || archive.isPending}
              />
            ))}
            {!questions.isLoading && questions.data?.items.length === 0 ? <AppCard className="p-8 text-center text-sm text-muted">当前筛选下没有题目</AppCard> : null}
          </div>
        </div>
      </section>
    </AdminShell>
  );
}

function QuestionCard({
  question,
  onEdit,
  onPublish,
  onArchive,
  busy,
}: {
  question: AdminQuestion;
  onEdit: () => void;
  onPublish: () => void;
  onArchive: () => void;
  busy?: boolean;
}) {
  return (
    <AppCard className="p-5">
      <div className="flex flex-col justify-between gap-3 lg:flex-row">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={question.status} />
            <Badge>难度 {question.difficulty}</Badge>
            <Badge>{question.qtype}</Badge>
            {question.default_rubric_version_id ? <Badge className="border-brand/20 bg-brandSoft text-brand">Rubric #{question.default_rubric_version_id}</Badge> : null}
          </div>
          <h3 className="mt-3 text-lg font-semibold leading-7 text-ink">{question.title}</h3>
          {question.body ? <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted">{question.body}</p> : null}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <AppButton variant="secondary" className="h-10 px-3" onClick={onEdit}>
            <Edit3 className="h-4 w-4" />
            编辑
          </AppButton>
          {question.status !== "published" ? (
            <AppButton className="h-10 px-3" onClick={onPublish} disabled={busy}>
              <CheckCircle2 className="h-4 w-4" />
              发布
            </AppButton>
          ) : null}
          {question.status !== "archived" ? (
            <AppButton variant="secondary" className="h-10 px-3" onClick={onArchive} disabled={busy}>
              <Archive className="h-4 w-4" />
              归档
            </AppButton>
          ) : null}
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {question.company ? <Badge>{question.company.name}</Badge> : null}
        {question.position ? <Badge>{question.position.name}</Badge> : null}
        {question.tags.map((tag) => (
          <Badge key={tag.id}>{tag.name}</Badge>
        ))}
      </div>
      <details className="mt-4 rounded-2xl border border-line bg-white p-3 text-sm">
        <summary className="cursor-pointer font-semibold text-ink">参考答案</summary>
        <p className="mt-2 whitespace-pre-wrap leading-6 text-muted">{question.answer_reference}</p>
      </details>
    </AppCard>
  );
}

function toQuestionPayload(form: typeof emptyForm): AdminQuestionPayload {
  return {
    title: form.title.trim(),
    prompt: form.prompt.trim() || null,
    answer_reference: form.answer_reference.trim(),
    difficulty: Number(form.difficulty),
    qtype: form.qtype,
    company_name: form.company_name.trim() || null,
    position_name: form.position_name.trim() || null,
    tags: form.tags
      .split(/[，,]/)
      .map((item) => item.trim())
      .filter(Boolean),
    source_note: form.source_note.trim() || null,
    status: form.status,
    default_rubric_version_id: form.default_rubric_version_id ? Number(form.default_rubric_version_id) : null,
  };
}

