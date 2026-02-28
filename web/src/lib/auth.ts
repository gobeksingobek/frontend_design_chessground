const AUTH_KEY = "cg_web_authed";
const TOKEN_KEY = "cg_web_api_token";

export function isAuthed(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(AUTH_KEY) === "true";
}

export function setWebAuth(token: string | null) {
  if (typeof window === "undefined") return;
  if (token && token.trim()) {
    window.localStorage.setItem(AUTH_KEY, "true");
    window.localStorage.setItem(TOKEN_KEY, token.trim());
    return;
  }
  window.localStorage.removeItem(AUTH_KEY);
  window.localStorage.removeItem(TOKEN_KEY);
}

export function getWebToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}
