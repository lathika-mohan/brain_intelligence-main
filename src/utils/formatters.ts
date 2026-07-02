export function formatMetricValue(value: number, precision = 2): string {
  return value.toFixed(precision);
}
