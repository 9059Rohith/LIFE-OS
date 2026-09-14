export interface VoiceApproval {
  event_id: string;
  version: number;
  action_ids: string[];
  captured_at: number;
}
export function isApprovalCommand(text: string): boolean {
  return /^(please\s+)?approve (the |this |my |current )?(plan|all( actions)?)[.!]?$/i.test(
    text.trim(),
  );
}
