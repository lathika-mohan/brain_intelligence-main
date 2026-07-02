export const storage = {
  get: (key: string): string | null => typeof window !== 'undefined' ? localStorage.getItem(key) : null,
  set: (key: string, value: string): void => { if (typeof window !== 'undefined') localStorage.setItem(key, value); },
  remove: (key: string): void => { if (typeof window !== 'undefined') localStorage.removeItem(key); },
};
