"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, CheckCircle2, Loader2, Plus, Save } from "lucide-react";

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
  archiveAdminRubricVersion,
  createAdminRubric,
  createAdminRubricVersion,
  getAdminRubrics,
  publishAdminRubricVersion,
} from "@/lib/admin-console-api";
import type { Rubric, RubricVersion } from "@/lib/admin-console-types";

const defaultDimensions = JSON.stringify(
  [
    { name: "正确性", weight: 40, description: "回答是否准确覆盖核心概念" },
    { name: "完整性", weight: 30, description: "是否覆盖关键步骤、边界和风险" },
    { name: "表达结构", weight: 20, description: "表达是否清晰、有层次" },
    { name: "工程深度", weight: 10, description: "是否体现真实工程经验" },
  ],
  null,
  2
);

export default function AdminRubricsPage() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("");
  const [rubricName, setRubricName] = useState("");
  const [rubricDescription, setRubricDescription] = useState("");
  const [rubricStatus, setRubricStatus] = useState<"draft" | "published">("draft");
  const [selectedRubricId, setSelectedRubricId] = useState("");
  const [version, setVersion] = useState("v1");
  const [scoringScale, setScoringScale] = useState("0-100");
  const [dimensionsJson, setDimensionsJson] = useState(defaultDimensions);
  const [promptTemplate, setPromptTemplate] = useState(
    "请根据题目、候选人回答和参考答案，从正确性、完整性、表达结构、工程深度四个维度评分，并输出结构化反馈。"
  );
  const [jsonError, setJsonError] = useState("");

  const rubrics = useQuery({
    queryKey: ["admin-rubrics", status],
    queryFn: () => getAdminRubrics({ status, limit: 100 }),
    retry: false,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin-rubrics"] });

  const createRubric = useMutation({
    mutationFn: () => createAdminRubric({ name: rubricName.trim(), description: rubricDescription.trim() || null, status: rubricStatus }),
    onSuccess: (data) => {
      setRubricName("");
      setRubricDescription("");
      setRubricStatus("draft");
      setSelectedRubricId(String(data.id));
      invalidate();
    },
  });

  const createVersion = useMutation({
    mutationFn: () => {
      const dimensions = parseDimensions(dimensionsJson);
      setJsonError("");
      return createAdminRubricVersion(Number(selectedRubricId), {
        version: version.trim(),
        scoring_scale: scoringScale.trim() || "0-100",
        prompt_template: promptTemplate.trim(),
        dimensions_json: dimensions,
      });
    },
    onSuccess: () => {
      setVersion("v1");
      setScoringScale("0-100");
      setDimensionsJson(defaultDimensions);
      setPromptTemplate("请根据题目、候选人回答和参考答案，从正确性、完整性、表达结构、工程深度四个维度评分，并输出结构化反馈。");
      invalidate();
    },
    onError: (error) => {
      if (error instanceof SyntaxError) {
        setJsonError(error.message);
      }
    },
  });

  const publish = useMutation({
    mutationFn: publishAdminRubricVersion,
    onSuccess: invalidate,
  });
  const archive = useMutation({
    mutationFn: archiveAdminRubricVersion,
    onSuccess: invalidate,
  });

  const selectedRubric = useMemo(() => rubrics.data?.items.find((item) => item.id === Number(selectedRubricId)), [rubrics.data?.items, selectedRubricId]);

  if (isForbidden(rubrics.error)) {
    return <AdminAccessDenied />;
  }

  const canCreateRubric = rubricName.trim().length >= 3;
  const canCreateVersion = Boolean(selectedRubricId) && version.trim().length > 0 && promptTemplate.trim().length >= 20;

  return (
    <AdminShell
      eyebrow="Scoring Rubric"
      title="评分标准管理"
      description="管理评分标准和版本。新的评分会记录实际使用的 rubric_version_id，历史报告不会被后续版本覆盖。"
      actions={
        <>
          <Link href="/admin">
            <AppButton variant="secondary">后台总览</AppButton>
          </Link>
          <Link href="/admin/questions">
            <AppButton variant="secondary">题库管理</AppButton>
          </Link>
        </>
      }
    >
      <section className="grid gap-5 xl:grid-cols-[420px_1fr]">
        <div className="grid h-fit gap-5">
          <AppCard className="p-5">
            <AdminSectionHeader title="创建 Rubric" description="先创建标准，再为它创建可发布的版本。" />
            <form
              className="mt-5 grid gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                if (canCreateRubric) createRubric.mutate();
              }}
            >
              <AdminField label="名称">
                <input className={adminInputClass} value={rubricName} onChange={(event) => setRubricName(event.target.value)} placeholder="例如 Agent 工程能力评分标准" />
              </AdminField>
              <AdminField label="描述">
                <textarea className={adminTextareaClass} value={rubricDescription} onChange={(event) => setRubricDescription(event.target.value)} placeholder="说明适用岗位、题型和评分口径" />
              </AdminField>
              <AdminField label="初始状态">
                <select className={adminInputClass} value={rubricStatus} onChange={(event) => setRubricStatus(event.target.value as "draft" | "published")}>
                  <option value="draft">草稿</option>
                  <option value="published">已发布</option>
                </select>
              </AdminField>
              <AdminError error={createRubric.error} />
              <AppButton type="submit" disabled={!canCreateRubric || createRubric.isPending}>
                {createRubric.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                创建 Rubric
              </AppButton>
            </form>
          </AppCard>

          <AppCard className="p-5">
            <AdminSectionHeader title="创建 Version" description="dimensions 使用 JSON 数组；prompt_template 只保存评分模板，不保存用户回答。" />
            <form
              className="mt-5 grid gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                setJsonError("");
                try {
                  if (canCreateVersion) createVersion.mutate();
                } catch (error) {
                  setJsonError(error instanceof Error ? error.message : "dimensions_json 不是合法 JSON");
                }
              }}
            >
              <AdminField label="所属 Rubric">
                <select className={adminInputClass} value={selectedRubricId} onChange={(event) => setSelectedRubricId(event.target.value)}>
                  <option value="">请选择 Rubric</option>
                  {rubrics.data?.items.map((item) => (
                    <option key={item.id} value={item.id}>
                      #{item.id} {item.name}
                    </option>
                  ))}
                </select>
              </AdminField>
              <div className="grid gap-3 sm:grid-cols-2">
                <AdminField label="版本号">
                  <input className={adminInputClass} value={version} onChange={(event) => setVersion(event.target.value)} placeholder="v1" />
                </AdminField>
                <AdminField label="评分范围">
                  <input className={adminInputClass} value={scoringScale} onChange={(event) => setScoringScale(event.target.value)} placeholder="0-100" />
                </AdminField>
              </div>
              <AdminField label="维度 JSON">
                <textarea className={cn(adminTextareaClass, "min-h-52 font-mono text-xs")} value={dimensionsJson} onChange={(event) => setDimensionsJson(event.target.value)} />
              </AdminField>
              <AdminField label="Prompt Template">
                <textarea className={cn(adminTextareaClass, "min-h-36")} value={promptTemplate} onChange={(event) => setPromptTemplate(event.target.value)} />
              </AdminField>
              {selectedRubric ? <p className="text-xs text-muted">当前将为「{selectedRubric.name}」创建新版本。</p> : null}
              {jsonError ? <div className="rounded-2xl border border-red-100 bg-red-50 p-3 text-sm text-red-700">{jsonError}</div> : null}
              <AdminError error={createVersion.error instanceof SyntaxError ? null : createVersion.error} />
              <AppButton type="submit" disabled={!canCreateVersion || createVersion.isPending}>
                {createVersion.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                创建 Version
              </AppButton>
            </form>
          </AppCard>
        </div>

        <div className="grid gap-5">
          <AppCard className="p-5">
            <AdminSectionHeader title="Rubric 列表" description={`当前共 ${rubrics.data?.total ?? 0} 套评分标准`} />
            <div className="mt-4 max-w-xs">
              <AdminField label="状态筛选">
                <select className={adminInputClass} value={status} onChange={(event) => setStatus(event.target.value)}>
                  <option value="">全部</option>
                  <option value="draft">草稿</option>
                  <option value="published">已发布</option>
                  <option value="archived">已归档</option>
                </select>
              </AdminField>
            </div>
          </AppCard>

          <AdminError error={rubrics.error || publish.error || archive.error} />

          <div className="grid gap-3">
            {rubrics.isLoading ? (
              <AppCard className="grid min-h-40 place-items-center p-6 text-sm text-muted">
                <Loader2 className="h-5 w-5 animate-spin text-brand" />
              </AppCard>
            ) : null}
            {rubrics.data?.items.map((rubric) => (
              <RubricCard
                key={rubric.id}
                rubric={rubric}
                onSelect={() => setSelectedRubricId(String(rubric.id))}
                onPublish={(id) => publish.mutate(id)}
                onArchive={(id) => archive.mutate(id)}
                busy={publish.isPending || archive.isPending}
              />
            ))}
            {!rubrics.isLoading && rubrics.data?.items.length === 0 ? <AppCard className="p-8 text-center text-sm text-muted">当前没有 Rubric</AppCard> : null}
          </div>
        </div>
      </section>
    </AdminShell>
  );
}

function RubricCard({
  rubric,
  onSelect,
  onPublish,
  onArchive,
  busy,
}: {
  rubric: Rubric;
  onSelect: () => void;
  onPublish: (id: number) => void;
  onArchive: (id: number) => void;
  busy?: boolean;
}) {
  return (
    <AppCard className="p-5">
      <div className="flex flex-col justify-between gap-3 lg:flex-row">
        <div>
          <div className="flex flex-wrap gap-2">
            <StatusBadge status={rubric.status} />
            <Badge>{rubric.versions.length} 个版本</Badge>
          </div>
          <h3 className="mt-3 text-lg font-semibold text-ink">{rubric.name}</h3>
          {rubric.description ? <p className="mt-2 text-sm leading-6 text-muted">{rubric.description}</p> : null}
        </div>
        <AppButton variant="secondary" className="h-10 px-3" onClick={onSelect}>
          选择并创建版本
        </AppButton>
      </div>

      <div className="mt-5 grid gap-3">
        {rubric.versions.map((version) => (
          <VersionRow key={version.id} version={version} onPublish={() => onPublish(version.id)} onArchive={() => onArchive(version.id)} busy={busy} />
        ))}
        {rubric.versions.length === 0 ? <div className="rounded-2xl border border-line bg-white p-4 text-sm text-muted">还没有版本，先创建 v1。</div> : null}
      </div>
    </AppCard>
  );
}

function VersionRow({
  version,
  onPublish,
  onArchive,
  busy,
}: {
  version: RubricVersion;
  onPublish: () => void;
  onArchive: () => void;
  busy?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-line bg-white p-4">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-start">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={version.status} />
            <Badge>#{version.id}</Badge>
            <Badge>{version.scoring_scale}</Badge>
            <Badge>{version.dimensions_json.length} 维度</Badge>
          </div>
          <p className="mt-3 font-semibold text-ink">{version.version}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {version.status !== "published" ? (
            <AppButton className="h-10 px-3" onClick={onPublish} disabled={busy}>
              <CheckCircle2 className="h-4 w-4" />
              发布
            </AppButton>
          ) : null}
          {version.status !== "archived" ? (
            <AppButton variant="secondary" className="h-10 px-3" onClick={onArchive} disabled={busy}>
              <Archive className="h-4 w-4" />
              归档
            </AppButton>
          ) : null}
        </div>
      </div>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer font-medium text-brand">查看维度和模板摘要</summary>
        <pre className="mt-3 max-h-48 overflow-auto rounded-2xl bg-brandMist p-3 text-xs leading-5 text-ink">{JSON.stringify(version.dimensions_json, null, 2)}</pre>
        <p className="mt-3 line-clamp-3 text-sm leading-6 text-muted">{version.prompt_template}</p>
      </details>
    </div>
  );
}

function parseDimensions(value: string): Array<Record<string, unknown>> {
  const parsed = JSON.parse(value) as unknown;
  if (!Array.isArray(parsed)) {
    throw new SyntaxError("dimensions_json 必须是数组");
  }
  return parsed.map((item) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new SyntaxError("每个维度必须是对象");
    }
    return item as Record<string, unknown>;
  });
}

