/** Browser routing hints, never tenant authorization or an independent service catalog. */
export type ExplorerRange = "1h" | "6h" | "24h" | "7d";

export function linkedService(params: URLSearchParams): { service_name: string; environment: string } | null {
  const serviceName = params.get("service_name");
  const environment = params.get("environment");
  if (!serviceName || environment === null || serviceName.length > 512 || environment.length > 512) return null;
  return { service_name: serviceName, environment };
}

export function linkedRange(params: URLSearchParams, fallback: ExplorerRange): ExplorerRange {
  const range = params.get("range");
  return range === "1h" || range === "6h" || range === "24h" || range === "7d" ? range : fallback;
}

export function serviceExplorerHref(
  path: string,
  serviceName: string,
  environment: string,
  range: ExplorerRange,
  extras: Record<string, string> = {},
): string {
  const params = new URLSearchParams({ service_name: serviceName, environment, range, ...extras });
  return `${path}?${params.toString()}`;
}
