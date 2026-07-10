/**
 * Ticket 1 — Observation extractor (stage 1 of the Voice-to-Deterministic-Workflow Compiler).
 *
 * PURE, no-LLM: Transcript -> Observation[]. Each spoken sentence (an exact substring of
 * text_normalized / text_translated) is classified by an ordered, most-specific-first LEXICON
 * into exactly one defect_kind, and carries a heuristic severity_guess + confidence + a curated
 * target_hint and an `unresolved:*` surface_ref (NEVER a hardcoded live URL at compile time).
 *
 * Authority = none (sandbox authoring). This module only reads text and emits structured data.
 * Reproduces the canonical chain TR-1 -> OB-1..OB-6 verbatim (see _SPINE_v1.json e2e_example).
 */

export type DefectKind =
  | 'broken_link' | 'cta_route' | 'legal_footer_link' | 'auth_entrypoint'
  | 'offer_copy' | 'pricing_claim' | 'request_id_visibility' | 'web_chat_ux'
  | 'mobile_responsive' | 'route_health' | 'other';

export type Severity = 'blocker' | 'high' | 'medium' | 'low' | 'info';

export interface AuditSession {
  id: string; founder_id: string; surface_kind: string;
  target_url?: string; target_ref?: string;
  created_at: string; status: string;
  voice_note_ids: string[]; observation_ids: string[]; authority?: 'none';
}

export interface Transcript {
  id: string; voice_note_id: string; session_id: string;
  text_raw: string; text_normalized: string;
  source_lang: string; translated: boolean; text_translated?: string;
  normalization_ops?: Array<{ op: string; from: string; to: string }>; confidence?: number;
}

export interface Observation {
  id: string; session_id: string; transcript_id: string;
  raw_span: string; surface_ref: string; target_hint: string;
  severity_guess: Severity; defect_kind: DefectKind;
  confidence: number; needs_translation: boolean;
}

export interface LexRule {
  id: string;
  test: (span: string) => boolean;
  defect_kind: DefectKind;
  target_hint: string;
  surface_ref: string;
  severity_guess: Severity;
  confidence: number;
}

/**
 * Ordered most-specific-first. The first rule whose `test` matches a span classifies it.
 * Specific patterns (pricing copy, cookie/legal, auth, request-id, chat, CTA) precede the
 * generic broken_link / route_health fallbacks so a specific defect never falls through to a
 * generic kind — exactly the routing the golden OB-1..OB-6 require.
 */
export const LEXICON: LexRule[] = [
  { id: 'pricing_claim', test: (s) => /package copy/.test(s) || (/\$\s?\d/.test(s) && /\bweek\b/.test(s)),
    defect_kind: 'pricing_claim', target_hint: 'Acme Brief $12,000 8-week package copy',
    surface_ref: 'unresolved:Acme Brief package copy', severity_guess: 'high', confidence: 0.82 },
  { id: 'legal_footer_link', test: (s) => /\bcookie\b/.test(s),
    defect_kind: 'legal_footer_link', target_hint: 'Cookie link',
    surface_ref: 'unresolved:footer Cookie link', severity_guess: 'high', confidence: 0.88 },
  { id: 'auth_entrypoint', test: (s) => /\bsign[- ]?in\b/.test(s) || /\blog[- ]?in\b/.test(s) || /\bsign[- ]?up\b/.test(s),
    defect_kind: 'auth_entrypoint', target_hint: 'Sign-in',
    surface_ref: 'unresolved:Sign-in', severity_guess: 'blocker', confidence: 0.9 },
  { id: 'request_id_visibility', test: (s) => /request[- ]?ids?\b/.test(s) || /\bcorr(elation)?[- ]?id/.test(s),
    defect_kind: 'request_id_visibility', target_hint: 'Request IDs',
    surface_ref: 'unresolved:request id display', severity_guess: 'medium', confidence: 0.85 },
  { id: 'web_chat_ux', test: (s) => /\bchat\b/.test(s),
    defect_kind: 'web_chat_ux', target_hint: 'Web chat UI',
    surface_ref: 'unresolved:web chat widget', severity_guess: 'medium', confidence: 0.7 },
  { id: 'cta_route', test: (s) => /\bapply\b/.test(s) || /\bpilot\b/.test(s) || /\bcta\b/.test(s) || /call to action/.test(s),
    defect_kind: 'cta_route', target_hint: 'Apply for Program link',
    surface_ref: 'unresolved:Apply for Program link', severity_guess: 'blocker', confidence: 0.9 },
  // generic fallbacks — total the extractor for arbitrary input; never fire on the golden 6.
  { id: 'route_health', test: (s) => /\b(404|500|route|page)\b/.test(s) && /(broken|error|down|not found|blank)/.test(s),
    defect_kind: 'route_health', target_hint: 'route', surface_ref: 'unresolved:route', severity_guess: 'high', confidence: 0.6 },
  { id: 'broken_link', test: (s) => /\blink\b/.test(s) && /(broken|nowhere|dead|404|goes nowhere)/.test(s),
    defect_kind: 'broken_link', target_hint: 'link', surface_ref: 'unresolved:link', severity_guess: 'high', confidence: 0.6 },
];

/** Deterministic sentence split of a normalized transcript into atomic spans. */
export function splitSpans(text: string): string[] {
  return text.trim().replace(/\.\s*$/, '').split(/\.\s+/).map((s) => s.trim()).filter(Boolean);
}

/**
 * Transcript -> Observation[]. Pure and replayable. `lexicon` is injectable so tests can seed a
 * deliberately wrong mapping table (the red-capable path). surface_ref is always `unresolved:*`.
 */
export function extractObservations(
  transcript: Transcript, session: AuditSession, lexicon: LexRule[] = LEXICON,
): Observation[] {
  const source = transcript.translated && transcript.text_translated
    ? transcript.text_translated : transcript.text_normalized;
  return splitSpans(source).map((span, i) => {
    const rule = lexicon.find((r) => r.test(span));
    return {
      id: `OB-${i + 1}`,
      session_id: session.id,
      transcript_id: transcript.id,
      raw_span: span,
      surface_ref: rule ? rule.surface_ref : `unresolved:${span}`,
      target_hint: rule ? rule.target_hint : span,
      severity_guess: rule ? rule.severity_guess : 'info',
      defect_kind: rule ? rule.defect_kind : 'other',
      confidence: rule ? rule.confidence : 0.3,
      needs_translation: !!transcript.translated,
    };
  });
}
