import { Panel } from "@/components/ui";

export default function ReportPage() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-5 sm:px-6">
      <h1 className="text-2xl font-semibold">面试报告</h1>
      <Panel className="mt-4 p-6 text-sm text-muted">报告将在模拟面试结束后生成。</Panel>
    </main>
  );
}

