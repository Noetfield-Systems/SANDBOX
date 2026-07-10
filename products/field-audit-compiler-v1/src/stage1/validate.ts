/**
 * Ticket 1 — stage-1 schema validator.
 *
 * Self-contained (no npm deps): a focused JSON-Schema subset validator that enforces exactly the
 * constructs VOICE_TO_OBSERVATION_SCHEMA_v1.json uses — type, required, additionalProperties:false,
 * enum (via $ref -> $defs), pattern (id shapes AS-/VN-/TR-/OB-*), const, min/max, and the
 * AuditSession anyOf(target_url|target_ref) rule. Validates AuditSession/VoiceNote/Transcript/Observation.
 *
 * Authority = none. Reads the schema next to the package; mutates nothing.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dir = dirname(fileURLToPath(import.meta.url));
const SCHEMA: any = JSON.parse(
  readFileSync(join(__dir, '..', '..', 'VOICE_TO_OBSERVATION_SCHEMA_v1.json'), 'utf8'),
);
const $DEFS: any = SCHEMA.$defs || {};

function deref(node: any): any {
  if (node && typeof node === 'object' && node.$ref) {
    return $DEFS[String(node.$ref).replace('#/$defs/', '')];
  }
  return node;
}

function typeOk(t: string, v: any): boolean {
  switch (t) {
    case 'string': return typeof v === 'string';
    case 'number': return typeof v === 'number';
    case 'integer': return Number.isInteger(v);
    case 'boolean': return typeof v === 'boolean';
    case 'array': return Array.isArray(v);
    case 'object': return v !== null && typeof v === 'object' && !Array.isArray(v);
    default: return true;
  }
}

export function validateNode(value: any, schemaNode: any, path = '', errors: string[] = []): string[] {
  const s = deref(schemaNode);
  if (!s) return errors;
  if (s.const !== undefined && value !== s.const) errors.push(`${path}: expected const ${JSON.stringify(s.const)}, got ${JSON.stringify(value)}`);
  if (s.enum && !s.enum.includes(value)) errors.push(`${path}: ${JSON.stringify(value)} not in enum [${s.enum.join(', ')}]`);
  if (s.type && !typeOk(s.type, value)) errors.push(`${path}: expected type ${s.type}, got ${Array.isArray(value) ? 'array' : typeof value}`);
  if (typeof value === 'string' && s.pattern && !new RegExp(s.pattern).test(value)) errors.push(`${path}: ${JSON.stringify(value)} fails pattern /${s.pattern}/`);
  if (typeof value === 'number') {
    if (s.minimum !== undefined && value < s.minimum) errors.push(`${path}: ${value} < minimum ${s.minimum}`);
    if (s.maximum !== undefined && value > s.maximum) errors.push(`${path}: ${value} > maximum ${s.maximum}`);
  }
  if (s.type === 'object' && typeOk('object', value)) {
    const props = s.properties || {};
    for (const req of s.required || []) if (!(req in value)) errors.push(`${path}: missing required '${req}'`);
    if (s.additionalProperties === false) {
      for (const k of Object.keys(value)) if (!(k in props)) errors.push(`${path}: unknown key '${k}' (additionalProperties:false)`);
    }
    for (const [k, v] of Object.entries(value)) if (props[k]) validateNode(v, props[k], path ? `${path}.${k}` : k, errors);
    if (Array.isArray(s.anyOf)) {
      const ok = s.anyOf.some((b: any) => (b.required || []).every((r: string) => r in value));
      if (!ok) errors.push(`${path}: fails anyOf (need one of ${JSON.stringify(s.anyOf.map((b: any) => b.required))})`);
    }
  }
  if (s.type === 'array' && Array.isArray(value) && s.items) {
    value.forEach((it, i) => validateNode(it, s.items, `${path}[${i}]`, errors));
  }
  return errors;
}

export type Stage1Type = 'AuditSession' | 'VoiceNote' | 'Transcript' | 'Observation';

export function validate(obj: any, typeName: Stage1Type): { valid: boolean; errors: string[] } {
  const node = SCHEMA.properties?.[typeName];
  if (!node) return { valid: false, errors: [`no schema for type '${typeName}'`] };
  const errors = validateNode(obj, node, typeName);
  return { valid: errors.length === 0, errors };
}
