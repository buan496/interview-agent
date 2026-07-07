import { request } from "@/lib/api-client";
import type { AbilityProfile } from "@/lib/types";

export function getAbilityProfile() {
  return request<AbilityProfile>("/me/ability-profile");
}
