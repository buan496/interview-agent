"use client";

import { useQuery } from "@tanstack/react-query";
import { RotateCcw } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { Badge, Button, Panel } from "@/components/ui";
import { API_BASE, createSession } from "@/lib/api";

type WrongBookItem = {
  question_id: number;
  title: string;
  last_score?: number | null;
  fail_count: number;
  next_review?: string | null;
  tags: Array<{ id: number; name: string }>;
};

async function getWrongBook() {
  const response = await fetch(`${API_BASE}/me/wrong-book`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<WrongBookItem[]>;
}

export default function WrongBookPage() {
  const router = useRouter();
  const query = useQuery({ queryKey: ["wrong-book"], queryFn: getWrongBook });
  const retry = useMutation({
    mutationFn: (questionId: number) => createSession({ mode: "single", question_id: questionId }),
    onSuccess: (data) => router.push(`/session/${data.session_id}`)
  });
  return (
    <main className="mx-auto max-w-5xl px-4 py-5 sm:px-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">错题本</h1>
      </div>
      <div className="grid gap-3">
        {query.data?.map((item) => (
          <Panel key={item.question_id} className="p-4">
            <div className="flex flex-wrap gap-2">
              <Badge>{item.last_score ?? 0} 分</Badge>
              <Badge>{item.fail_count} 次</Badge>
              {item.next_review ? <Badge>{item.next_review}</Badge> : null}
            </div>
            <h2 className="mt-3 text-base font-semibold">{item.title}</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {item.tags.map((tag) => (
                <Badge key={tag.id}>{tag.name}</Badge>
              ))}
            </div>
            <Button className="mt-4" variant="secondary" onClick={() => retry.mutate(item.question_id)} disabled={retry.isPending}>
              <RotateCcw className="h-4 w-4" />
              重练
            </Button>
          </Panel>
        ))}
        {!query.isLoading && query.data?.length === 0 ? <Panel className="p-8 text-center text-sm text-muted">暂无错题</Panel> : null}
      </div>
    </main>
  );
}
