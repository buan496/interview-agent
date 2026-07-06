import createSessionRequestJson from "../../../contracts/api/create-session-request.json";
import createSessionResponseJson from "../../../contracts/api/create-session-response.json";
import metadataJson from "../../../contracts/api/metadata.json";
import practicePlanJson from "../../../contracts/api/practice-plan.json";
import questionListJson from "../../../contracts/api/question-list.json";
import radarJson from "../../../contracts/api/radar.json";
import reportsJson from "../../../contracts/api/reports.json";
import sessionDetailJson from "../../../contracts/api/session-detail.json";
import sessionReportJson from "../../../contracts/api/session-report.json";
import wrongBookJson from "../../../contracts/api/wrong-book.json";
import type { CreateSessionPayload } from "@/lib/session-api";
import type {
  CreateSessionResponse,
  Metadata,
  PracticePlan,
  Question,
  RadarItem,
  ReportListItem,
  SessionDetail,
  SessionReport,
  WrongBookItem,
} from "@/lib/types";

type JsonContract<T> = T extends string
  ? string
  : T extends number
    ? number
    : T extends boolean
      ? boolean
      : T extends null
        ? null
        : T extends Array<infer Item>
          ? JsonContract<Item>[]
          : T extends object
            ? { [Key in keyof T]: JsonContract<T[Key]> }
            : T;

const createSessionRequestContract: JsonContract<CreateSessionPayload> = createSessionRequestJson;
const createSessionResponseContract: JsonContract<CreateSessionResponse> = createSessionResponseJson;
const metadataContract: JsonContract<Metadata> = metadataJson;
const questionListContract: JsonContract<{ items: Question[]; total: number }> = questionListJson;
const practicePlanContract: JsonContract<PracticePlan> = practicePlanJson;
const radarContract: JsonContract<RadarItem[]> = radarJson;
const reportsContract: JsonContract<ReportListItem[]> = reportsJson;
const sessionDetailContract: JsonContract<SessionDetail> = sessionDetailJson;
const sessionReportContract: JsonContract<SessionReport> = sessionReportJson;
const wrongBookContract: JsonContract<WrongBookItem[]> = wrongBookJson;

export const apiContracts = {
  createSessionRequestContract,
  createSessionResponseContract,
  metadataContract,
  practicePlanContract,
  questionListContract,
  radarContract,
  reportsContract,
  sessionDetailContract,
  sessionReportContract,
  wrongBookContract,
};
