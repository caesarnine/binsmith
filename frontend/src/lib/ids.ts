export function createId(prefix?: string) {
  let value = "";
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    value = crypto.randomUUID();
  } else {
    const random = Math.random().toString(36).slice(2, 10);
    value = `${Date.now().toString(36)}-${random}`;
  }
  return prefix ? `${prefix}-${value}` : value;
}
