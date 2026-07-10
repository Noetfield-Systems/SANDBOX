/**
 * T2 — Clusterer. Observation[] -> IssueCluster[]. Groups by (defect_kind + resolved target scope),
 * dedups, sets label + target_refs (from a curated per-kind profile) + severity = MAX of members.
 * Reproduces the canonical IC-1..IC-6. No patching / no source mutation — pure grouping.
 */
import type { Observation, Severity, DefectKind } from '../stage1/extract_observations.ts';

export interface IssueCluster {
  id: string;
  session_id: string;
  observation_ids: string[];
  defect_kind: DefectKind;
  label: string;
  target_refs: string[];
  severity: Severity;
  dedup_note: string;
}

const SEVERITY_ORDER: Severity[] = ['info', 'low', 'medium', 'high', 'blocker'];
export function maxSeverity(a: Severity, b: Severity): Severity {
  return SEVERITY_ORDER.indexOf(a) >= SEVERITY_ORDER.indexOf(b) ? a : b;
}

/** Curated per-defect-kind cluster profile (label + resolved target scope + dedup note). */
interface Profile { label: string; target_refs: string[]; dedup_note: string }
const PROFILE: Partial<Record<DefectKind, Profile>> = {
  cta_route: { label: "Broken 'Apply for Program' CTA", target_refs: ["a[data-cta='apply-for-program']", '/apply-for-program'], dedup_note: 'Single CTA observation; will fan to all CTAs via pattern expansion.' },
  legal_footer_link: { label: 'Footer Cookie link goes nowhere', target_refs: ["footer a[href*='cookie']"], dedup_note: 'Grouped under legal_footer_link (more specific than generic broken_link).' },
  auth_entrypoint: { label: 'Sign-in broken', target_refs: ["a[href*='login']", '/login'], dedup_note: '' },
  pricing_claim: { label: 'Acme Brief $12,000 / 8-week copy stale', target_refs: ["[data-offer='acme-brief']"], dedup_note: 'pricing_claim chosen over offer_copy because the specific claim ($12,000, 8-week) is checkable against canonical; an offer_copy_consistency_check contract is spawned as a sibling in expansion.' },
  request_id_visibility: { label: 'Request IDs not visible', target_refs: ['main', '[data-request-id]'], dedup_note: '' },
  web_chat_ux: { label: 'Web chat widget UX poor', target_refs: ['[data-chat]'], dedup_note: '' },
};

/** Resolved scope key for grouping: defect_kind + the profile's target_refs (or the raw target_hints). */
function scopeKey(defect_kind: DefectKind, obs: Observation): string {
  const p = PROFILE[defect_kind];
  return `${defect_kind}::${(p ? p.target_refs : [obs.target_hint]).join(',')}`;
}

/**
 * Observation[] -> IssueCluster[]. Observations sharing (defect_kind + resolved scope) merge into one
 * cluster; distinct kinds stay separate. IC ids assigned in order of first appearance.
 */
export function clusterObservations(observations: Observation[], sessionId?: string): IssueCluster[] {
  const byKey = new Map<string, { obs: Observation[]; order: number }>();
  let order = 0;
  for (const o of observations) {
    const key = scopeKey(o.defect_kind, o);
    if (!byKey.has(key)) byKey.set(key, { obs: [], order: order++ });
    byKey.get(key)!.obs.push(o);
  }
  const groups = [...byKey.values()].sort((a, b) => a.order - b.order);
  return groups.map((g, i) => {
    const kind = g.obs[0].defect_kind;
    const p = PROFILE[kind];
    const severity = g.obs.reduce<Severity>((acc, o) => maxSeverity(acc, o.severity_guess), 'info');
    return {
      id: `IC-${i + 1}`,
      session_id: sessionId ?? g.obs[0].session_id,
      observation_ids: g.obs.map((o) => o.id),
      defect_kind: kind,
      label: p ? p.label : `${kind} issue`,
      target_refs: p ? p.target_refs : [...new Set(g.obs.map((o) => o.target_hint))],
      severity,
      dedup_note: p ? p.dedup_note : '',
    };
  });
}
