import axios from "axios";

/** Turn unknown thrown values (API errors, validation, network) into a
 *  human-friendly message. Works with the API's error envelope. */
export function getErrorMessage(
  err: unknown,
  fallback = "Something went wrong. Please try again.",
): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as
      | { detail?: unknown; errors?: Array<{ message?: string }> }
      | undefined;

    if (Array.isArray(data?.errors) && data.errors.length) {
      const messages = data.errors
        .map((e) => e.message)
        .filter(Boolean)
        .join(" ");
      if (messages) return messages;
    }
    if (typeof data?.detail === "string" && data.detail) {
      return data.detail;
    }
    if (err.code === "ERR_NETWORK") {
      return "Cannot reach the server. Make sure it's running and its CORS settings allow this origin.";
    }
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return fallback;
}
