"use client";

import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Loader2, LogIn, Send, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";

import { AppButton, AppCard, AppInput, BrandLogo, PageShell } from "@/components/ui";
import { login, requestLoginCode } from "@/lib/auth-api";

export default function LoginPage() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [hint, setHint] = useState("");
  const requestCode = useMutation({
    mutationFn: () => requestLoginCode(phone),
    onSuccess: (data) => {
      setHint(data.development_code ? `开发验证码：${data.development_code}` : "验证码已发送");
      if (data.development_code) setCode(data.development_code);
    }
  });
  const signIn = useMutation({
    mutationFn: () => login(phone, code),
    onSuccess: (data) => {
      window.localStorage.setItem("access_token", data.access_token);
      router.push("/practice");
    }
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    signIn.mutate();
  }

  return (
    <PageShell className="grid items-center overflow-hidden py-10 sm:py-14">
      <section className="grid items-center gap-8 lg:grid-cols-[1.05fr_0.95fr] lg:gap-14">
        <div className="mx-auto grid max-w-2xl gap-7 text-center lg:mx-0 lg:text-left">
          <BrandLogo className="mx-auto w-52 lg:mx-0" priority />
          <div className="space-y-5">
            <div className="inline-flex items-center gap-2 rounded-full border border-line bg-surface/80 px-3 py-1 text-xs font-medium text-brand shadow-soft">
              <Sparkles className="h-3.5 w-3.5" />
              AI 面试训练 Agent
            </div>
            <h1 className="text-4xl font-semibold leading-tight tracking-[0] text-ink sm:text-5xl">
              训练闭环，让进步可见
            </h1>
            <p className="mx-auto max-w-xl text-base leading-8 text-muted lg:mx-0">
              面向大厂面试的训练闭环系统。完成答题、AI 追问、结构化复盘和下一轮计划，让薄弱点持续被看见、被训练、被修正。
            </p>
          </div>

          <div className="grid gap-3 text-left sm:grid-cols-3">
            <ValuePoint title="真实 Session" detail="单题与模拟面试都进入受控训练流程" />
            <ValuePoint title="结构化复盘" detail="沉淀得分、缺口、表达问题和行动项" />
            <ValuePoint title="下一轮计划" detail="根据错题与能力画像继续推荐训练" />
          </div>
        </div>

        <AppCard className="mx-auto w-full max-w-md p-6 sm:p-8">
          <div className="mb-7 flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-brand">欢迎回来</p>
              <h2 className="mt-2 text-2xl font-semibold text-ink">登录训练系统</h2>
              <p className="mt-2 text-sm leading-6 text-muted">使用手机号验证码进入你的今日训练台。</p>
            </div>
            <BrandLogo variant="mark" className="h-12 w-12 shrink-0 rounded-2xl bg-brandMist p-1.5" />
          </div>

          <form onSubmit={submit} className="grid gap-4">
            <AppInput
              label="手机号"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              placeholder="请输入手机号"
              required
              minLength={6}
              inputMode="tel"
              autoComplete="tel"
            />

            <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
              <AppInput
                label="验证码"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder="请输入验证码"
                required
                autoComplete="one-time-code"
                error={signIn.isError ? "验证码错误，请重新输入。" : undefined}
              />
              <AppButton
                type="button"
                variant="secondary"
                className="self-end whitespace-nowrap"
                onClick={() => requestCode.mutate()}
                disabled={phone.length < 6 || requestCode.isPending}
              >
                {requestCode.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                获取验证码
              </AppButton>
            </div>

            {hint ? <p className="rounded-control bg-brandSoft px-3 py-2 text-xs font-medium text-brand">{hint}</p> : null}

            <AppButton className="mt-2 w-full" type="submit" size="lg" disabled={signIn.isPending || phone.length < 6 || code.length < 4}>
              {signIn.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
              登录并进入训练
            </AppButton>
          </form>
        </AppCard>
      </section>
    </PageShell>
  );
}

function ValuePoint({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="rounded-app border border-line/80 bg-surface/70 p-4 shadow-soft backdrop-blur">
      <div className="flex items-center gap-2 text-sm font-semibold text-ink">
        <CheckCircle2 className="h-4 w-4 text-brand" />
        {title}
      </div>
      <p className="mt-2 text-xs leading-5 text-muted">{detail}</p>
    </div>
  );
}
