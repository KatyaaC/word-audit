/**
 * Typed API client. One function per backend endpoint (see docs/API_CONTRACT.md).
 * With NEXT_PUBLIC_USE_MOCKS=true (the default) every call goes to lib/mock-store.ts.
 */
import { mock } from "./mock-store";
import type {
  Classification,
  Constitution,
  ConstitutionDoc,
  ContentItem,
  ContentSubmission,
  Decision,
  ExpireFactResult,
  Insights,
  LayerACheckRequest,
  LayerACheckResponse,
  LoginResponse,
  Passport,
  User,
  VerifyResult,
  WorkflowAction,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api").replace(/\/$/, "");
export const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS !== "false";

let token: string | null = null;
let currentUser: User | null = null;

export function setSession(t: string | null, u: User | null) {
  token = t;
  currentUser = u;
}

function me(): User {
  if (!currentUser) throw new Error("Not signed in");
  return currentUser;
}

async function http<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (res.status === 401 && token && typeof window !== "undefined") {
    // Session expired or the server restarted with a new secret: sign out and go back to the login page
    setSession(null, null);
    try {
      localStorage.removeItem("wordaudit.session");
    } catch {
      /* ignore */
    }
    window.location.href = "/login";
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

const post = <T,>(path: string, body?: unknown) =>
  http<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  login: (email: string, password: string): Promise<LoginResponse> =>
    USE_MOCKS ? mock.login(email, password) : post("/auth/login", { email, password }),

  layerACheck: (req: LayerACheckRequest): Promise<LayerACheckResponse> =>
    USE_MOCKS ? mock.layerACheck(req) : post("/layer-a/check", req),

  listContent: (): Promise<ContentItem[]> => (USE_MOCKS ? mock.listContent() : http("/content")),

  getContent: (id: string): Promise<ContentItem> => (USE_MOCKS ? mock.getContent(id) : http(`/content/${id}`)),

  createContent: (sub: ContentSubmission): Promise<ContentItem> =>
    USE_MOCKS ? mock.createContent(sub, me()) : post("/content", sub),

  saveVersion: (id: string, sub: ContentSubmission): Promise<ContentItem> =>
    USE_MOCKS ? mock.saveVersion(id, sub, me()) : post(`/content/${id}/versions`, sub),

  respondToFinding: (
    contentId: string,
    findingId: string,
    body: { decision: Decision; reason: string; modified_text?: string | null },
  ): Promise<ContentItem> =>
    USE_MOCKS
      ? mock.respondToFinding(contentId, findingId, body, me())
      : post(`/content/${contentId}/findings/${findingId}/response`, body),

  addComment: (contentId: string, body: string): Promise<ContentItem> =>
    USE_MOCKS ? mock.addComment(contentId, body, me()) : post(`/content/${contentId}/comments`, { body }),

  transition: (contentId: string, action: WorkflowAction, reason?: string): Promise<ContentItem> =>
    USE_MOCKS ? mock.transition(contentId, action, reason, me()) : post(`/content/${contentId}/transition`, { action, reason }),

  getPassport: (id: string): Promise<Passport> => (USE_MOCKS ? mock.getPassport(id) : http(`/passports/${id}`)),

  /** Omit `content` to verify the stored text; pass edited text for the tamper demo. */
  verifyPassport: (id: string, content?: string): Promise<VerifyResult> =>
    USE_MOCKS ? mock.verifyPassport(id, content) : post(`/passports/${id}/verify`, content === undefined ? {} : { content }),

  expireFact: (factId: string): Promise<ExpireFactResult> =>
    USE_MOCKS ? mock.expireFact(factId) : post(`/ledger/facts/${factId}/expire`),

  getInsights: (): Promise<Insights> => (USE_MOCKS ? mock.getInsights() : http("/insights")),

  getConstitution: (): Promise<Constitution> => (USE_MOCKS ? mock.getConstitution() : http("/constitution")),

  uploadConstitution: (file: File, classification: Classification): Promise<ConstitutionDoc> => {
    if (USE_MOCKS) return mock.uploadConstitution(file, classification, me());
    const form = new FormData();
    form.append("file", file);
    form.append("classification", classification);
    return http("/constitution/upload", { method: "POST", body: form });
  },

  decideRule: (ruleId: string, decision: "approve" | "reject", reason: string): Promise<Constitution> =>
    USE_MOCKS
      ? mock.decideRule(ruleId, decision, reason, me())
      : post(`/constitution/rules/${ruleId}/decision`, { decision, reason }),
};
