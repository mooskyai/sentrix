// This hook is invoked by actual Next.js server bootstrap. Keep the exporter
// strictly in the Node runtime; never bundle server-held keys for Edge/browser.
export async function register() {
  if (process.env.NEXT_RUNTIME === 'nodejs' && process.env.SENTRIX_ACCEPTANCE_RUN) {
    const { initialize } = await import('./lib/tracing.mjs');
    initialize();
  }
}
