import { instrumentCheckout } from '../../../lib/tracing.mjs';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const result = await instrumentCheckout();
    return Response.json(result, { headers: { 'Cache-Control': 'no-store' } });
  } catch {
    // Do not propagate credentials, endpoint values, or exporter stack traces.
    return Response.json({ error: 'Next.js runtime export not verified.' }, { status: 503 });
  }
}
