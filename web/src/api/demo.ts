/** Small helper shared by the per-endpoint API modules to simulate a
 * realistic network delay in demo mode, so loading states are exercised. */
export function demoDelay<T>(value: T, ms = 450): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}
