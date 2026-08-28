import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export const API = `${BACKEND_URL}/api`;
export const WS_BASE = `${BACKEND_URL.replace(/^http/, "ws")}/api/ws`;

export const getShareToken = () =>
  new URLSearchParams(window.location.search).get("share") || null;

const apiClient = axios.create({
  baseURL: API,
  withCredentials: true,
});

// Attach the link share token (if the user opened a shared link) so the gateway
// can grant link-based access without a session.
apiClient.interceptors.request.use((config) => {
  const share = getShareToken();
  if (share) {
    config.headers = config.headers || {};
    config.headers["X-Share-Token"] = share;
  }
  return config;
});

export default apiClient;
