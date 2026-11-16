export async function api(path, options = {}) {
  const response = await fetch('/api/v1' + path, options);
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error('The server returned an unexpected response. Check that the backend is running.');
  }
  if (!response.ok) {
    const error = new Error(typeof data.detail === 'string' ? data.detail : 'Invalid request. Check your input.');
    error.code = data.error_code;
    error.retryable = data.retryable === true;
    error.reference = data.reference;
    throw error;
  }
  return data;
}
