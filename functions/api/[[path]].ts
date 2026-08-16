/**
 * Cloudflare Pages Function API Proxy for Project Loot Raiders.
 * 
 * Securely forwards browser requests from https://loot-raiders.pages.dev/api/*
 * to the backend API via the configured HTTPS target (context.env.BACKEND_API_URL).
 * 
 * Invocation Route: /api/*
 */

interface Env {
  BACKEND_API_URL?: string;
  LOOT_BACKEND_URL?: string;
}

// Strict Allowlist of permitted API route prefixes
const ALLOWED_ROUTES: string[] = [
  // Authentication routes
  '/api/login',
  '/api/verify-otp',
  '/api/resend-otp',

  // Public data & feed routes
  '/api/deals',
  '/api/deals/public',
  '/api/status',
  '/api/config',
  '/api/scraper/health',
  '/api/lootmap/events',
  '/api/rewards/scratch',
  '/api/channel/growth',
  '/api/whatsapp/share',
  '/api/push/subscribe',
  '/api/tma/deals',
  '/api/deals/history',
  '/api/deals/stream',
  '/api/v1/deals',
  '/api/v1/gamification',
  '/api/v1/wishlist',
  '/api/v1/revenue',

  // Authenticated administration routes
  '/api/settings',
  '/api/selectors',
  '/api/analytics',
  '/api/clicks',
  '/api/logs',
  '/api/deals/delete',
  '/api/manual/crawl',
  '/api/manual/post',
  '/api/toggle',
  '/api/scan',
  '/api/processes/cleanup',
  '/api/v1/brain'
];

function isRouteAllowed(pathname: string): boolean {
  return ALLOWED_ROUTES.some(allowed => 
    pathname === allowed || pathname.startsWith(`${allowed}/`) || pathname.startsWith(`${allowed}?`)
  );
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const request = context.request;
  const url = new URL(request.url);
  const pathname = url.pathname;

  // 1. Handle CORS preflight OPTIONS request directly
  if (request.method.toUpperCase() === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Origin": request.headers.get("Origin") || "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With, Accept",
        "Access-Control-Max-Age": "86400",
      }
    });
  }

  // 2. Enforce strict route allowlist security check
  if (!isRouteAllowed(pathname)) {
    return new Response(JSON.stringify({
      error: "Forbidden",
      message: "Requested API endpoint is not in the allowed gateway routes."
    }), {
      status: 404,
      headers: { "Content-Type": "application/json" }
    });
  }

  // 3. Resolve backend API base URL from Cloudflare Environment Variables
  const rawTarget = context.env.BACKEND_API_URL || context.env.LOOT_BACKEND_URL || "";
  const backendBase = rawTarget.trim().replace(/\/+$/, "");

  if (!backendBase) {
    return new Response(JSON.stringify({
      error: "Backend Gateway Unconfigured",
      message: "Please configure BACKEND_API_URL in your Cloudflare Pages environment variables.",
      status: "unconfigured"
    }), {
      status: 503,
      headers: { "Content-Type": "application/json" }
    });
  }

  // 4. Construct target URL with preserved path and query parameters
  const targetUrl = `${backendBase}${pathname}${url.search}`;

  // 5. Construct clean forward headers (preserve Content-Type, Authorization, Accept)
  const forwardHeaders = new Headers();
  const allowedHeaders = ["content-type", "authorization", "accept", "user-agent", "x-requested-with"];
  
  request.headers.forEach((value, key) => {
    if (allowedHeaders.includes(key.toLowerCase())) {
      forwardHeaders.set(key, value);
    }
  });

  // 6. Build fetch options preserving HTTP method and request body
  const fetchOptions: RequestInit = {
    method: request.method,
    headers: forwardHeaders,
    redirect: "follow"
  };

  if (!["GET", "HEAD", "OPTIONS"].includes(request.method.toUpperCase())) {
    fetchOptions.body = request.body;
  }

  // 7. Execute forward fetch with safe error handling
  try {
    const backendResponse = await fetch(targetUrl, fetchOptions);

    // Build clean response headers
    const responseHeaders = new Headers();
    const allowedResponseHeaders = ["content-type", "cache-control", "authorization", "set-cookie"];
    
    backendResponse.headers.forEach((value, key) => {
      if (allowedResponseHeaders.includes(key.toLowerCase())) {
        responseHeaders.set(key, value);
      }
    });

    // Ensure Content-Type header exists
    if (!responseHeaders.has("content-type")) {
      responseHeaders.set("content-type", "application/json");
    }

    return new Response(backendResponse.body, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: responseHeaders
    });
  } catch (err: any) {
    return new Response(JSON.stringify({
      error: "Gateway Communication Error",
      message: "Unable to reach backend service through the secure tunnel."
    }), {
      status: 502,
      headers: { "Content-Type": "application/json" }
    });
  }
};
