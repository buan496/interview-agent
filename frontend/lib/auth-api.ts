import { request } from "@/lib/api-client";

export function requestLoginCode(phone: string) {
  return request<{ status: string; expires_in: number; development_code?: string }>("/auth/request-code", {
    method: "POST",
    body: JSON.stringify({ phone })
  });
}

export function login(phone: string, code: string) {
  return request<{ access_token: string; token_type: string; expires_in: number }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ phone, code })
  });
}
