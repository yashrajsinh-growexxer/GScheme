export interface Scheme {
  id: string;
  name: string;
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

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8501/api";

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
  if (!res.ok) throw new Error("Discover failed");
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

  if (!res.ok) throw new Error("Chat failed");
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

  if (!res.ok) throw new Error("General chat failed");
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
