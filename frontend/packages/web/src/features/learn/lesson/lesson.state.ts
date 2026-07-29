// Persist quiz result across mode switches without re-render churn.
export const resultRef: { current: { correct: number; gain: number } | null } = { current: null };
