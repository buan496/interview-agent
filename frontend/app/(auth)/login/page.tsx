"use client";

import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, LogIn, Send } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button, Panel } from "@/components/ui";
import { login, requestLoginCode } from "@/lib/api";

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
    <main className="grid min-h-[calc(100vh-3.5rem)] place-items-center px-4">
      <Panel className="w-full max-w-sm p-6">
        <h1 className="text-xl font-semibold">登录</h1>
        <p className="mt-1 text-sm text-muted">使用手机号验证码进入面试练习。</p>
        <form onSubmit={submit} className="mt-5 grid gap-3">
          <label className="grid gap-1 text-sm">
            <span className="text-muted">手机号</span>
            <input className="h-10 rounded border border-line px-3" value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="请输入手机号" required minLength={6} />
          </label>
          <div className="grid grid-cols-[1fr_auto] gap-2">
            <input className="h-10 rounded border border-line px-3 text-sm" value={code} onChange={(event) => setCode(event.target.value)} placeholder="验证码" required />
            <Button type="button" variant="secondary" onClick={() => requestCode.mutate()} disabled={phone.length < 6 || requestCode.isPending}>
              {requestCode.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}获取验证码
            </Button>
          </div>
          {hint ? <p className="text-xs text-brand">{hint}</p> : null}
          {signIn.isError ? <p className="text-xs text-accent">验证码错误，请重新输入。</p> : null}
          <Button className="mt-2 w-full" type="submit" disabled={signIn.isPending || phone.length < 6 || code.length < 4}>
            {signIn.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}登录并进入练习
          </Button>
        </form>
      </Panel>
    </main>
  );
}
