import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export const API = `${BACKEND_URL}/api`;
export const WS_BASE = `${BACKEND_URL.replace(/^http/, "ws")}/api/ws`;

const apiClient = axios.create({
  baseURL: API,
  withCredentials: true,
});

export default apiClient;
