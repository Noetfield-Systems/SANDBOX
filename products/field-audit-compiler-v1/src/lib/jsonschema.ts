/**
 * Self-contained JSON-Schema (draft 2020-12 subset) validator shared by T3/T4/T5.
 * Handles: $ref->#/$defs, type, required, additionalProperties:false, enum, const, pattern,
 * minimum/maximum, anyOf(required), properties, items. No npm deps.
 */
import { readFileSync } from 'node:fs';

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

export function validateNode(value: any, node: any, $defs: any, path = '', errors: string[] = []): string[] {
  let s = node;
  if (s && typeof s === 'object' && s.$ref) s = $defs[String(s.$ref).replace('#/$defs/', '')];
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
    if (s.additionalProperties === false) for (const k of Object.keys(value)) if (!(k in props)) errors.push(`${path}: unknown key '${k}'`);
    for (const [k, v] of Object.entries(value)) if (props[k]) validateNode(v, props[k], $defs, path ? `${path}.${k}` : k, errors);
    if (Array.isArray(s.anyOf)) {
      const ok = s.anyOf.some((b: any) => (b.required || []).every((r: string) => r in value));
      if (!ok) errors.push(`${path}: fails anyOf ${JSON.stringify(s.anyOf.map((b: any) => b.required))}`);
    }
  }
  if (s.type === 'array' && Array.isArray(value) && s.items) value.forEach((it, i) => validateNode(it, s.items, $defs, `${path}[${i}]`, errors));
  return errors;
}

export type Validator = (value: any) => { valid: boolean; errors: string[] };

export function compile(schema: any): Validator {
  const $defs = schema.$defs || {};
  return (value: any) => { const errors = validateNode(value, schema, $defs, ''); return { valid: errors.length === 0, errors }; };
}

export function compileFromFile(path: string): Validator {
  return compile(JSON.parse(readFileSync(path, 'utf8')));
}
