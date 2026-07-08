"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BookOpenText, ChevronRight, Gauge, Loader2, ShieldCheck } from "lucide-react";

import { AdminAccessDenied, AdminError, AdminSectionHeader, AdminShell, isForbidden } from "@/components/admin-console";
import { AppButton, AppCard, Badge } from "@/components/ui";
import { getAdminQuestions, getAdminRubrics } from "@/lib/admin-console-api";

export default function AdminPage() {
  const questions = useQuery({
    queryKey: ["admin-console", "questions", "overview"],
    queryFn: () => getAdminQuestions({ limit: 1 }),
    retry: false,
  });
  const rubrics = useQuery({
    queryKey: ["admin-console", "rubrics", "overview"],
    queryFn: () => getAdminRubrics({ limit: 1 }),
    retry: false,
  });

  if (isForbidden(questions.error) || isForbidden(rubrics.error)) {
    return <AdminAccessDenied />;
  }

  const loading = questions.isLoading || rubrics.isLoading;

  return (
    <AdminShell
      eyebrow="Admin Console v1"
      title="后台管理控制台"
      description="面向题库运营和评分标准维护的最小后台。前端只做体验控制，真实权限以后端 RBAC 为准。"
      actions={
        <Link href="/practice">
          <AppButton variant="secondary">返回今日训练</AppButton>
        </Link>
      }
    >
      <section className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <div className="grid gap-5 md:grid-cols-2">
          <ConsoleEntry
            href="/admin/questions"
            icon={<BookOpenText className="h-5 w-5" />}
            title="题库管理"
            description="创建、编辑、发布和归档题目；普通用户只能读取已发布题目。"
            metric={loading ? "加载中" : `${questions.data?.total ?? 0} 题`}
          />
          <ConsoleEntry
            href="/admin/rubrics"
            icon={<Gauge className="h-5 w-5" />}
            title="评分标准管理"
            description="维护 Rubric 和版本，确保评分结果与历史报告可追溯。"
            metric={loading ? "加载中" : `${rubrics.data?.total ?? 0} 套`}
          />
        </div>

        <AppCard className="p-5">
          <AdminSectionHeader title="当前权限模型" description="admin 和 content_operator 可以进入本后台；普通 user 会收到 403。 " />
          <div className="mt-5 grid gap-3">
            <InfoRow label="权限来源" value="后端 RBAC" />
            <InfoRow label="题库写操作" value="admin / content_operator" />
            <InfoRow label="Rubric 写操作" value="admin / content_operator" />
            <InfoRow label="用户管理" value="未开放" />
          </div>
          <div className="mt-5 rounded-2xl border border-brand/15 bg-brandMist p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-ink">
              <ShieldCheck className="h-4 w-4 text-brand" />
              权限校验说明
            </div>
            <p className="mt-2 text-sm leading-6 text-muted">页面加载后会请求 admin API。若后端返回 403，前端只展示无权限提示，不绕过后端校验。</p>
          </div>
          {loading ? (
            <div className="mt-4 flex items-center gap-2 text-sm text-muted">
              <Loader2 className="h-4 w-4 animate-spin text-brand" />
              正在校验后台权限
            </div>
          ) : null}
          <AdminError error={questions.error || rubrics.error} />
        </AppCard>
      </section>
    </AdminShell>
  );
}

function ConsoleEntry({
  href,
  icon,
  title,
  description,
  metric,
}: {
  href: string;
  icon: React.ReactNode;
  title: string;
  description: string;
  metric: string;
}) {
  return (
    <Link href={href} className="group block">
      <AppCard className="flex min-h-[250px] flex-col p-6 transition group-hover:-translate-y-0.5 group-hover:border-brand/30">
        <div className="flex items-center justify-between gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-2xl bg-brandSoft text-brand">{icon}</span>
          <Badge className="border-brand/20 bg-brandSoft text-brand">{metric}</Badge>
        </div>
        <h2 className="mt-6 text-2xl font-semibold text-ink">{title}</h2>
        <p className="mt-3 text-sm leading-6 text-muted">{description}</p>
        <span className="mt-auto inline-flex items-center gap-2 pt-6 text-sm font-semibold text-brand">
          进入管理
          <ChevronRight className="h-4 w-4" />
        </span>
      </AppCard>
    </Link>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl border border-line bg-white p-3 text-sm">
      <span className="text-muted">{label}</span>
      <span className="font-semibold text-ink">{value}</span>
    </div>
  );
}
