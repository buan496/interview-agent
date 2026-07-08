import Link from "next/link";
import { ArrowLeft, ShieldAlert } from "lucide-react";

import { ApiError } from "@/lib/api-client";
import { AppButton, AppCard, Badge, PageShell, cn } from "@/components/ui";

export function isForbidden(error: unknown) {
  return error instanceof ApiError && error.status === 403;
}

export function formatAdminError(error: unknown) {
  if (error instanceof ApiError) {
    const requestId = error.detail && typeof error.detail === "object" && "request_id" in error.detail ? ` request_id=${String(error.detail.request_id)}` : "";
    return `${error.message || "请求失败"}${requestId}`;
  }
  return error instanceof Error ? error.message : "请求失败";
}

export function AdminShell({
  eyebrow,
  title,
  description,
  actions,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <PageShell className="grid gap-6 pb-12">
      <AppCard className="relative overflow-hidden p-6 sm:p-8">
        <div className="absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-brandSoft to-transparent" />
        <div className="relative flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
          <div className="max-w-3xl">
            <p className="text-sm font-semibold text-brand">{eyebrow}</p>
            <h1 className="mt-2 text-3xl font-semibold leading-tight text-ink sm:text-4xl">{title}</h1>
            <p className="mt-3 text-sm leading-6 text-muted sm:text-base">{description}</p>
          </div>
          {actions ? <div className="flex flex-wrap gap-3">{actions}</div> : null}
        </div>
      </AppCard>
      {children}
    </PageShell>
  );
}

export function AdminAccessDenied() {
  return (
    <PageShell className="grid place-items-center py-16">
      <AppCard className="max-w-xl p-8 text-center">
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-brandSoft text-brand">
          <ShieldAlert className="h-5 w-5" />
        </div>
        <h1 className="mt-5 text-2xl font-semibold text-ink">没有后台权限</h1>
        <p className="mt-3 text-sm leading-6 text-muted">后台能力由后端 RBAC 控制。当前账号不是 admin 或 content_operator，无法管理题库和评分标准。</p>
        <Link href="/practice" className="mt-6 inline-flex">
          <AppButton>
            <ArrowLeft className="h-4 w-4" />
            返回今日训练
          </AppButton>
        </Link>
      </AppCard>
    </PageShell>
  );
}

export function AdminSectionHeader({ title, description, right }: { title: string; description?: string; right?: React.ReactNode }) {
  return (
    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
      <div>
        <h2 className="text-xl font-semibold text-ink">{title}</h2>
        {description ? <p className="mt-1 text-sm leading-6 text-muted">{description}</p> : null}
      </div>
      {right ? <div className="flex flex-wrap gap-2">{right}</div> : null}
    </div>
  );
}

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const label: Record<string, string> = {
    draft: "草稿",
    published: "已发布",
    archived: "已归档",
  };
  return (
    <Badge
      className={cn(
        status === "published" && "border-emerald-200 bg-emerald-50 text-emerald-700",
        status === "draft" && "border-brand/20 bg-brandSoft text-brand",
        status === "archived" && "border-slate-200 bg-slate-50 text-slate-500",
        className
      )}
    >
      {label[status] ?? status}
    </Badge>
  );
}

export function AdminField({
  label,
  children,
  className,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={cn("grid gap-2 text-sm", className)}>
      <span className="font-medium text-ink">{label}</span>
      {children}
    </label>
  );
}

export const adminInputClass =
  "h-11 rounded-control border border-line bg-white px-3 text-sm text-ink transition placeholder:text-[#98a2b3] focus:border-brand focus:outline-none focus:ring-4 focus:ring-brand/10";

export const adminTextareaClass =
  "min-h-28 rounded-control border border-line bg-white p-3 text-sm leading-6 text-ink transition placeholder:text-[#98a2b3] focus:border-brand focus:outline-none focus:ring-4 focus:ring-brand/10";

export function AdminError({ error }: { error: unknown }) {
  if (!error) return null;
  return <div className="rounded-2xl border border-red-100 bg-red-50 p-3 text-sm text-red-700">{formatAdminError(error)}</div>;
}

