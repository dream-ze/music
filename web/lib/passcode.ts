const KEY = "ze_passcode"

export function getPasscode(): string {
  try {
    return localStorage.getItem(KEY) || ""
  } catch {
    return ""
  }
}

export function setPasscode(v: string): void {
  try {
    localStorage.setItem(KEY, v)
  } catch {
    /* ignore */
  }
}

export function hasPasscode(): boolean {
  return getPasscode().length > 0
}
