export interface Scheme {
  id: string;
  name: string;
  url?: string;
  description: string;
  state: string;
  category: string;
  matchScore?: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export type Profile = Record<string, string | number | boolean | undefined>;

export interface SchemeCompareData {
  scheme_id: string;
  name: string;
  state: string;
  category: string;
  url: string;
  details: string;
  eligibility: string;
  benefits: string;
  income_cap: string;
  age_limits: string;
  documents_required: string[];
  application_mode: string;
  application_process: string;
  gender_tags: string[];
  caste_tags: string[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8501/api";

async function readErrorMessage(res: Response, fallback: string): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string" && data.detail.trim()) return data.detail;
    if (typeof data?.error === "string" && data.error.trim()) return data.error;
  } catch {
    try {
      const text = await res.text();
      if (text.trim()) return text;
    } catch {
      // Ignore secondary parse failures.
    }
  }
  return fallback;
}

// Connect to FastAPI Search
export async function searchSchemes(query: string): Promise<Scheme[]> {
  const res = await fetch(API_BASE + "/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) throw new Error("Search failed");
  return await res.json();
}

// Connect to FastAPI Discover
export async function discoverSchemes(profile: Profile): Promise<{ summary: string; schemes: Scheme[] }> {
  const res = await fetch(API_BASE + "/discover", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile }),
  });
  if (!res.ok) throw new Error(await readErrorMessage(res, "Discover failed"));
  const data = await res.json();

  return {
    summary: "",
    schemes: data.schemes,
  };
}

// Connect to FastAPI Chat (Streaming)
export async function chatAboutScheme(
  schemeId: string, 
  message: string, 
  history: ChatMessage[], 
  onChunk: (text: string) => void
): Promise<string> {
  const res = await fetch(API_BASE + "/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scheme_id: schemeId,
      message: message,
      history: history.map(h => ({ role: h.role, content: h.content })),
    }),
  });

  if (!res.ok) throw new Error(await readErrorMessage(res, "Chat failed"));
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let fullResponse = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunkText = decoder.decode(value, { stream: true });
    fullResponse += chunkText;
    onChunk(chunkText);
  }
  
  return fullResponse;
}

export async function generalChatAboutSchemes(
  message: string, 
  history: ChatMessage[], 
  profile: Profile,
  schemes: Scheme[],
  onChunk: (text: string) => void
): Promise<string> {
  const res = await fetch(API_BASE + "/general-chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: message,
      history: history.map(h => ({ role: h.role, content: h.content })),
      profile: profile,
      schemes: schemes.map(s => ({ id: s.id }))
    }),
  });

  if (!res.ok) throw new Error(await readErrorMessage(res, "General chat failed"));
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let fullResponse = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunkText = decoder.decode(value, { stream: true });
    fullResponse += chunkText;
    onChunk(chunkText);
  }
  
  return fullResponse;
}

// --- Comparison API ---

export async function getSchemeCompareData(schemeId: string): Promise<SchemeCompareData> {
  const res = await fetch(API_BASE + `/scheme/${schemeId}/compare-data`);
  if (!res.ok) throw new Error("Failed to fetch comparison data");
  return await res.json();
}

export async function compareSchemes(schemeIds: string[]): Promise<SchemeCompareData[]> {
  const res = await fetch(API_BASE + "/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scheme_ids: schemeIds }),
  });
  if (!res.ok) throw new Error("Compare failed");
  return await res.json();
}

// --- STT API ---

export async function transcribeAudio(
  audioBlob: Blob,
  mode: "transcribe" | "translate" | "translit" | "verbatim" | "codemix" = "transcribe"
): Promise<{ transcript: string; language_code: string }> {
  const formData = new FormData();
  formData.append("file", audioBlob, "recording.webm");
  formData.append("mode", mode);
  
  const res = await fetch(API_BASE + "/stt", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(await readErrorMessage(res, "STT failed"));
  return await res.json();
}
