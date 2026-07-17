export const AI_UNAVAILABLE_ENVELOPE = {
  status: 'AI_UNAVAILABLE',
  ui_message:
    'Advanced analytics and AI chat are temporarily offline. Local rule-based telemetry monitoring remains operational.',
} as const;

export type AiUnavailableEnvelope = typeof AI_UNAVAILABLE_ENVELOPE;

export function isAiUnavailableEnvelope(value: unknown): value is AiUnavailableEnvelope {
  return (
    typeof value === 'object' &&
    value !== null &&
    (value as Record<string, unknown>).status === AI_UNAVAILABLE_ENVELOPE.status &&
    (value as Record<string, unknown>).ui_message === AI_UNAVAILABLE_ENVELOPE.ui_message
  );
}
