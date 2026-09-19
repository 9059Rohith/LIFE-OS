let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    credentials: "same-origin",
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(method !== "GET" ? { "X-CSRF-Token": csrf } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const error = (await response.json().catch(() => ({
      detail: "The server could not complete this request.",
    }))) as { detail?: unknown };
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : `Request failed (${response.status}). Check the input and try again.`,
    );
  }
  return response.status === 204
    ? (undefined as T)
    : (response.json() as Promise<T>);
}
export function subscribeEvent(id: string, onNotice: () => void): () => void {
  const source = new EventSource(`/api/events/${encodeURIComponent(id)}/stream`);
  source.onmessage = () => onNotice();
  return () => source.close();
}
export async function audioRequest(
  path: string,
  body: FormData | { text: string },
): Promise<Response> {
  const form = body instanceof FormData;
  const response = await fetch(`/api/voice/${path}`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "X-CSRF-Token": csrf,
      ...(!form ? { "Content-Type": "application/json" } : {}),
    },
    body: form ? body : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = (await response
      .json()
      .catch(() => ({ detail: "Voice service unavailable." }))) as {
      detail?: string;
    };
    throw new Error(error.detail || "Voice service unavailable.");
  }
  return response;
}
