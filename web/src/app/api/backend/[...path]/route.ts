import { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const FORWARDED_REQUEST_HEADERS = [
  "accept",
  "authorization",
  "content-type",
  "idempotency-key",
] as const;

const HOP_BY_HOP_RESPONSE_HEADERS = new Set([
  "connection",
  "content-length",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

type RouteContext = { params: Promise<{ path: string[] }> };

function upstreamUrl(request: NextRequest, path: string[]): URL | null {
  const base = process.env.API_BASE_URL?.trim();
  if (!base) return null;

  const upstream = new URL(
    path.map((segment) => encodeURIComponent(segment)).join("/"),
    `${base.replace(/\/+$/, "")}/`,
  );
  upstream.search = request.nextUrl.search;
  return upstream;
}

function proxyError(detail: string, status = 502): Response {
  return Response.json(
    { detail: { error_code: "UPSTREAM_UNAVAILABLE", detail } },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}

async function proxy(request: NextRequest, { params }: RouteContext): Promise<Response> {
  const { path } = await params;
  const target = upstreamUrl(request, path);
  if (!target) {
    return proxyError("The web service is missing its server-side API_BASE_URL configuration.", 503);
  }

  const headers = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      cache: "no-store",
    });
  } catch {
    return proxyError(`Unable to contact the configured API at ${target.origin}.`);
  }

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, name) => {
    if (!HOP_BY_HOP_RESPONSE_HEADERS.has(name.toLowerCase())) {
      responseHeaders.set(name, value);
    }
  });
  responseHeaders.set("Cache-Control", "no-store");
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}

export const GET = proxy;
export const HEAD = proxy;
export const OPTIONS = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
