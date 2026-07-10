/**
 * T2 — deterministic Template selector. Pure map defect_kind -> templates[].id (1:1), with
 * first-five priority and sibling spawns (how ONE observation expands into MULTIPLE workflows).
 * Loads the SSOT-locked registry mirror; fails closed on drift from the 10 spine template ids.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import type { DefectKind } from '../stage1/extract_observations.ts';

const __dir = dirname(fileURLToPath(import.meta.url));

const EXPECTED_TEMPLATE_IDS = [
  'broken_link_scan', 'cta_route_check', 'legal_footer_link_check', 'auth_entrypoint_check',
  'offer_copy_consistency_check', 'pricing_claim_consistency_check', 'request_id_visibility_check',
  'web_chat_ux_check', 'mobile_responsive_smoke_check', 'route_health_check',
];

export interface Registry {
  first_five_template_ids: string[];
  templates: Array<{ id: string; factory_category: string; value_class: string; [k: string]: any }>;
}

/** Load the registry; THROW (fail closed) if its template ids diverge from the 10 spine ids. */
export function loadRegistry(path = join(__dir, '..', 'templates', 'registry.json')): Registry {
  const reg: Registry = JSON.parse(readFileSync(path, 'utf8'));
  const ids = reg.templates.map((t) => t.id).sort();
  const expect = [...EXPECTED_TEMPLATE_IDS].sort();
  if (JSON.stringify(ids) !== JSON.stringify(expect)) {
    throw new Error(`registry drift: template ids ${JSON.stringify(ids)} != spine ${JSON.stringify(expect)}`);
  }
  return reg;
}

/** 1:1 defect_kind -> primary template_id. `other` -> null (un-routable). */
export const DEFECT_TO_TEMPLATE: Record<DefectKind, string | null> = {
  broken_link: 'broken_link_scan',
  cta_route: 'cta_route_check',
  legal_footer_link: 'legal_footer_link_check',
  auth_entrypoint: 'auth_entrypoint_check',
  offer_copy: 'offer_copy_consistency_check',
  pricing_claim: 'pricing_claim_consistency_check',
  request_id_visibility: 'request_id_visibility_check',
  web_chat_ux: 'web_chat_ux_check',
  mobile_responsive: 'mobile_responsive_smoke_check',
  route_health: 'route_health_check',
  other: null,
};

/** Sibling templates spawned from one defect_kind — the "1 observation -> N workflows" rule. */
export const SIBLING_TEMPLATES: Partial<Record<DefectKind, string[]>> = {
  pricing_claim: ['offer_copy_consistency_check'], // spine IC-4 dedup_note: spawn offer_copy sibling
};

export interface TemplateSelection {
  template_id: string;
  role: 'primary' | 'sibling';
  priority: boolean; // true if in first_five
}

/** Full selection for a defect_kind: primary + any siblings, each flagged priority if first-five. */
export function selectTemplates(defect_kind: DefectKind, registry: Registry): TemplateSelection[] {
  const primary = DEFECT_TO_TEMPLATE[defect_kind];
  if (!primary) return []; // 'other' -> un-routable, flagged upstream
  const first5 = new Set(registry.first_five_template_ids);
  const out: TemplateSelection[] = [{ template_id: primary, role: 'primary', priority: first5.has(primary) }];
  for (const sib of SIBLING_TEMPLATES[defect_kind] || []) {
    out.push({ template_id: sib, role: 'sibling', priority: first5.has(sib) });
  }
  return out;
}

/** Convenience: just the primary template id (1:1). */
export function selectTemplate(defect_kind: DefectKind): string | null {
  return DEFECT_TO_TEMPLATE[defect_kind];
}
