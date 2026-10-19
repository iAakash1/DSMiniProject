export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Context = { params: Promise<{ path: string[] }> };

function controlApiInternalUrl(): string {
  return process.env.CONTROL_API_INTERNAL_URL ?? "http://control-api:7900";
}

const ALLOWED_LIFECYCLE_PATH = /^coordinators(\/[A-Za-z0-9_-]+\/(stop|restart|delete))?$/;

export async function POST(request: Request, context: Context): Promise<Response> {
  const { path } = await context.params;
  const joined = path.join("/");

  if (!ALLOWED_LIFECYCLE_PATH.test(joined)) {
    return Response.json(
      { detail: "this proxy only forwards coordinator lifecycle actions" },
      { status: 404 },
    );
  }

  const operatorToken = process.env.CONTROL_API_OPERATOR_TOKEN ?? "";
  if (!operatorToken) {
    return Response.json(
      { detail: "CONTROL_API_OPERATOR_TOKEN is not configured on the control-plane server — lifecycle actions are disabled" },
      { status: 503 },
    );
  }

  let body: unknown = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${controlApiInternalUrl()}/${joined}`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${operatorToken}`,
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch (error) {
    return Response.json(
      { detail: `control API unreachable: ${error instanceof Error ? error.message : "unknown error"}` },
      { status: 502 },
    );
  }

  const payload = await upstream.json().catch(() => ({ detail: "control API returned a non-JSON response" }));
  return Response.json(payload, { status: upstream.status });
}
