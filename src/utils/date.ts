export function formatTelemetryTimestamp(date: Date | string | number): string {
  const d = new Date(date);
  return d.toISOString().replace('T', ' ').substring(0, 19);
}
