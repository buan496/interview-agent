import { Panel } from "@/components/ui";

export default function MockPage() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-5 sm:px-6">
      <h1 className="text-2xl font-semibold">模拟面试</h1>
      <Panel className="mt-4 p-6 text-sm text-muted">模拟面试将在单题闭环稳定后开放。</Panel>
    </main>
  );
}

