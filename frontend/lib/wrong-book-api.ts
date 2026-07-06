import { request } from "@/lib/api-client";
import type { WrongBookItem } from "@/lib/types";

export function getWrongBook() {
  return request<WrongBookItem[]>("/me/wrong-book");
}
