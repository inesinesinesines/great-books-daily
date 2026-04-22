/**
 * gbd-dispatch — Cloudflare Worker that bridges a public static page
 * (GitHub Pages) to a private GitHub Actions workflow_dispatch.
 *
 * The GitHub PAT lives only here, as a Wrangler secret (GITHUB_TOKEN),
 * and is never exposed to the browser. The Worker enforces:
 *   - Origin allowlist (CORS)
 *   - POST-only, JSON-only
 *   - book_id integer sanity range
 * Rate limiting is delegated to GitHub Actions concurrency + idempotency
 * (the workflow commits nothing when the target report already exists).
 */

const REPO = "inesinesinesines/great-books-daily";
const WORKFLOW_FILE = "generate-book.yml";
const REF = "main";

const ALLOWED_ORIGINS = [
  "https://inesinesinesines.github.io",
  "http://127.0.0.1:8765",
  "http://localhost:8765",
];

function corsHeaders(origin) {
  const allowed = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    "Access-Control-Allow-Origin": allowed,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

function json(body, init = {}, cors = {}) {
  return new Response(JSON.stringify(body), {
    ...init,
    headers: { ...cors, "Content-Type": "application/json", ...(init.headers || {}) },
  });
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const cors = corsHeaders(origin);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }
    if (request.method !== "POST") {
      return json({ error: "method_not_allowed" }, { status: 405 }, cors);
    }
    if (!ALLOWED_ORIGINS.includes(origin)) {
      return json({ error: "origin_forbidden", origin }, { status: 403 }, cors);
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return json({ error: "invalid_json" }, { status: 400 }, cors);
    }

    // Two modes: by book_id (curated catalog), or by (title, author) for
    // external classics dynamically registered in books.json.
    let inputs, replyPayload;
    if (body?.kind === "external" || (body?.title && body?.author && !body?.book_id)) {
      const title = String(body.title || "").trim();
      const author = String(body.author || "").trim();
      if (!title || !author || title.length > 200 || author.length > 100) {
        return json({ error: "invalid_title_or_author" }, { status: 400 }, cors);
      }
      // Guard against header/newline injection through workflow inputs
      if (/[\r\n\x00]/.test(title) || /[\r\n\x00]/.test(author)) {
        return json({ error: "invalid_chars" }, { status: 400 }, cors);
      }
      inputs = { title, author };
      replyPayload = { kind: "external", title, author };
    } else {
      const bookId = Number(body?.book_id);
      if (!Number.isInteger(bookId) || bookId < 1 || bookId > 500) {
        return json({ error: "invalid_book_id" }, { status: 400 }, cors);
      }
      inputs = { book_id: String(bookId) };
      replyPayload = { kind: "curated", book_id: bookId };
    }

    if (!env.GITHUB_TOKEN) {
      return json({ error: "worker_misconfigured" }, { status: 500 }, cors);
    }

    const ghRes = await fetch(
      `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`,
      {
        method: "POST",
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Bearer ${env.GITHUB_TOKEN}`,
          "X-GitHub-Api-Version": "2022-11-28",
          "User-Agent": "gbd-dispatch-worker",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ref: REF, inputs }),
      },
    );

    if (ghRes.status === 204) {
      return json(
        {
          ok: true,
          ...replyPayload,
          actions_url: `https://github.com/${REPO}/actions/workflows/${WORKFLOW_FILE}`,
          message: "dispatched — wait ~1-2 minutes then refresh",
        },
        { status: 202 },
        cors,
      );
    }

    const text = await ghRes.text();
    return json(
      { ok: false, upstream_status: ghRes.status, upstream_body: text.slice(0, 400) },
      { status: 502 },
      cors,
    );
  },
};
