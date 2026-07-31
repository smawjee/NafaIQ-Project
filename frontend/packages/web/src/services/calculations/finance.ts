// Frontend mirror of backend app.services.calculations (finance).

export function savingsRate(income: number, expenses: number): number {
  if (income <= 0) return 0;
  return Math.round(((income - expenses) / income) * 10000) / 100;
}

export function budgetUsage(spent: number, limit: number): number {
  if (limit <= 0) return 0;
  return Math.round((spent / limit) * 10000) / 100;
}

export function goalProgress(saved: number, target: number): number {
  if (target <= 0) return 0;
  return Math.min(100, Math.round((saved / target) * 10000) / 100);
}

export function compareToLastMonth(
  current: number,
  last: number,
): { absolute: number; pct: number | null } {
  if (last === 0) return { absolute: Math.round((current - last) * 100) / 100, pct: null };
  return {
    absolute: Math.round((current - last) * 100) / 100,
    pct: Math.round(((current - last) / Math.abs(last)) * 10000) / 100,
  };
}
