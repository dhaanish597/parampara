/** localStorage that never throws: it can be missing or blocked (Safari private mode, tests). */
function store(): Storage | null {
  try {
    return typeof window !== "undefined" && window.localStorage ? window.localStorage : null;
  } catch {
    return null;
  }
}

export function readStored(key: string): string | null {
  try {
    return store()?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

export function writeStored(key: string, value: string): void {
  try {
    store()?.setItem(key, value);
  } catch {
    // Storage full or blocked: the preference simply is not remembered.
  }
}
