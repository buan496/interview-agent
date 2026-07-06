"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { BookOpenCheck, Loader2, RotateCcw } from "lucide-react";
import { useRouter } from "next/navigation";

import { Badge, Button, Panel } from "@/components/ui";
import { createSession } from "@/lib/session-api";
import { getWrongBook } from "@/lib/wrong-book-api";

export default function WrongBookPage() {
  const router = useRouter();
  const query = useQuery({ queryKey: ["wrong-book"], queryFn: getWrongBook });
  const retry = useMutation({
    mutationFn: (questionId: number) => createSession({ mode: "single", question_id: questionId }),
    onSuccess: (data) => router.push(`/session/${data.session_id}`),
  });

  return (
    <main className="mx-auto max-w-5xl px-4 py-5 sm:px-6">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-ink">
            <BookOpenCheck className="h-4 w-4 text-brand" />
            错题复习
          </div>
          <h1 className="mt-2 text-2xl font-semibold text-ink">把低分题重新拉回训练闭环</h1>
          <p className="mt-1 text-sm text-muted">错题重练会创建新的单题 Session，并继续沉淀评分、掌握度和标签能力。</p>
        </div>
        <Badge>{query.data?.length ?? 0} 道错题</Badge>
      </div>

      <div className="grid gap-3">
        {query.data?.map((item) => (
          <Panel key={item.question_id} className="p-4">
            <div className="flex flex-wrap gap-2">
              <Badge>{item.last_score ?? 0} 分</Badge>
              <Badge>失误 {item.fail_count} 次</Badge>
              {item.next_review ? <Badge>下次复习 {item.next_review}</Badge> : null}
            </div>
            <h2 className="mt-3 text-base font-semibold leading-6 text-ink">{item.title}</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {item.tags.map((tag) => (
                <Badge key={tag.id}>{tag.name}</Badge>
              ))}
            </div>
            <Button className="mt-4" variant="secondary" onClick={() => retry.mutate(item.question_id)} disabled={retry.isPending}>
              {retry.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
              重练
            </Button>
          </Panel>
        ))}
        {!query.isLoading && query.data?.length === 0 ? <Panel className="p-8 text-center text-sm text-muted">暂无错题。完成训练后，低分题会自动进入这里。</Panel> : null}
      </div>
    </main>
  );
}
