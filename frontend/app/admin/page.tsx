import { Panel } from "@/components/ui";

export default function AdminPage() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-5 sm:px-6">
      <h1 className="text-2xl font-semibold">题目审核</h1>
      <Panel className="mt-4 p-6 text-sm text-muted">审核队列将在题库规模化阶段接入。</Panel>
    </main>
  );
}

