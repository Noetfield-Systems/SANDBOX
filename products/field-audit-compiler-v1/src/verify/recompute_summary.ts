/**
 * T4 — shared summary derivation. The EXACT CF-Worker doctrine: the verifier ignores any
 * author-claimed summary and recomputes {total,passed,failed} from checks[]. A mismatch => FAIL.
 */
export interface Check {
  name: string;
  passed: boolean;
  detail: string;
  evidence?: Record<string, any>;
}

export interface Summary { total: number; passed: number; failed: number }

export function recomputeSummary(checks: Check[]): Summary {
  return {
    total: checks.length,
    passed: checks.filter((c) => c.passed === true).length,
    failed: checks.filter((c) => c.passed === false).length,
  };
}

/** True iff the claimed summary equals the recomputation (and total == passed+failed == len). */
export function summaryMatches(summary: Summary, checks: Check[]): boolean {
  const r = recomputeSummary(checks);
  return summary.total === r.total && summary.passed === r.passed && summary.failed === r.failed
    && summary.total === summary.passed + summary.failed;
}
