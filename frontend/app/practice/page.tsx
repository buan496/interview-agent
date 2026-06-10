"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, Filter, RotateCcw, Search } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button, Panel, Badge } from "@/components/ui";
import { createSession, getMetadata, getQuestions } from "@/lib/api";

const difficultyOptions = [1, 2, 3, 4, 5];

export default function PracticePage() {
  const router = useRouter();
  const [companyId, setCompanyId] = useState("");
  const [positionId, setPositionId] = useState("");
  const [tagId, setTagId] = useState("");
  const [difficulty, setDifficulty] = useState("");

  const metadata = useQuery({ queryKey: ["metadata"], queryFn: getMetadata });
  const params = useMemo(() => {
    const value = new URLSearchParams({ page_size: "12" });
    if (companyId) value.set("company_id", companyId);
    if (positionId) value.set("position_id", positionId);
    if (tagId) value.append("tag_ids", tagId);
    if (difficulty) value.set("difficulty", difficulty);
    return value;
  }, [companyId, positionId, tagId, difficulty]);

  const questions = useQuery({ queryKey: ["questions", params.toString()], queryFn: () => getQuestions(params) });
  const startSession = useMutation({
    mutationFn: (override?: { company_id?: number; position_id?: number }) =>
      createSession({
        mode: "single",
        company_id: override?.company_id ?? (companyId ? Number(companyId) : undefined),
        position_id: override?.position_id ?? (positionId ? Number(positionId) : undefined),
        tag_ids: tagId ? [Number(tagId)] : [],
        difficulty: difficulty ? Number(difficulty) : undefined
      }),
    onSuccess: (data) => router.push(`/session/${data.session_id}`)
  });

  const reset = () => {
    setCompanyId("");
    setPositionId("");
    setTagId("");
    setDifficulty("");
  };

  return (
    <main className="mx-auto grid max-w-7xl gap-5 px-4 py-5 sm:px-6 lg:grid-cols-[320px_1fr]">
      <Panel className="h-fit p-4">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Filter className="h-4 w-4 text-brand" />
            筛选
          </div>
          <Button variant="ghost" className="h-8 px-2" onClick={reset} title="重置筛选">
            <RotateCcw className="h-4 w-4" />
          </Button>
        </div>

        <div className="grid gap-3">
          <label className="grid gap-1 text-sm">
            <span className="text-muted">公司</span>
            <select className="h-10 rounded border border-line bg-white px-3" value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
              <option value="">全部</option>
              {metadata.data?.companies.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>

          <label className="grid gap-1 text-sm">
            <span className="text-muted">岗位</span>
            <select className="h-10 rounded border border-line bg-white px-3" value={positionId} onChange={(e) => setPositionId(e.target.value)}>
              <option value="">全部</option>
              {metadata.data?.positions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>

          <label className="grid gap-1 text-sm">
            <span className="text-muted">标签</span>
            <select className="h-10 rounded border border-line bg-white px-3" value={tagId} onChange={(e) => setTagId(e.target.value)}>
              <option value="">全部</option>
              {metadata.data?.tags.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>

          <label className="grid gap-1 text-sm">
            <span className="text-muted">难度</span>
            <select className="h-10 rounded border border-line bg-white px-3" value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
              <option value="">全部</option>
              {difficultyOptions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>

          <Button className="mt-2" onClick={() => startSession.mutate()} disabled={startSession.isPending}>
            <Search className="h-4 w-4" />
            开始单题
          </Button>
        </div>
      </Panel>

      <section className="grid gap-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-ink">题库</h1>
            <p className="mt-1 text-sm text-muted">共 {questions.data?.total ?? 0} 题</p>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {questions.data?.items.map((item) => (
            <Panel key={item.id} className="flex min-h-[210px] flex-col p-4">
              <div className="mb-3 flex flex-wrap gap-2">
                <Badge>{item.company?.name ?? "通用"}</Badge>
                <Badge>{item.position?.name ?? "岗位通用"}</Badge>
                <Badge className="border-[#f0d2c6] bg-[#fff6f2] text-accent">难度 {item.difficulty}</Badge>
              </div>
              <h2 className="line-clamp-3 text-base font-semibold leading-6 text-ink">{item.title}</h2>
              <div className="mt-3 flex flex-wrap gap-2">
                {item.tags.slice(0, 4).map((tag) => (
                  <Badge key={tag.id}>{tag.name}</Badge>
                ))}
              </div>
              <Button
                variant="secondary"
                className="mt-auto w-full"
                onClick={() => {
                  startSession.mutate({
                    company_id: item.company?.id ?? undefined,
                    position_id: item.position?.id ?? undefined
                  });
                }}
              >
                练这类题
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Panel>
          ))}
        </div>

        {!questions.isLoading && questions.data?.items.length === 0 ? (
          <Panel className="p-8 text-center text-sm text-muted">暂无匹配题目</Panel>
        ) : null}
      </section>
    </main>
  );
}
