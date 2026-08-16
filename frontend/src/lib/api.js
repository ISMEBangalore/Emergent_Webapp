import axios from "axios";
import { clearSession, getToken } from "@/lib/auth";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const client = axios.create({ baseURL: API });

client.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err?.response?.status === 401) {
      clearSession();
      window.dispatchEvent(new Event("auth:unauthorized"));
    }
    return Promise.reject(err);
  },
);

function filenameFromDisposition(disposition, fallback) {
  const match = /filename="?([^";]+)"?/i.exec(disposition || "");
  return match ? match[1] : fallback;
}

async function download(path, params, fallbackName) {
  const res = await client.get(path, { params, responseType: "blob" });
  const filename = filenameFromDisposition(res.headers["content-disposition"], fallbackName);
  const blobUrl = window.URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(blobUrl);
}

export const api = {
  login: (username, password) => client.post("/auth/login", { username, password }).then((r) => r.data),
  me: () => client.get("/auth/me").then((r) => r.data),
  getSettings: () => client.get("/settings").then((r) => r.data),
  updateSettings: (body) => client.put("/settings", body).then((r) => r.data),
  getAvailable: () => client.get("/available").then((r) => r.data),
  listReports: () => client.get("/reports").then((r) => r.data),
  getReport: (id) => client.get(`/reports/${id}`).then((r) => r.data),
  deleteReport: (id) => client.delete(`/reports/${id}`).then((r) => r.data),
  createSample: () => client.post("/reports/sample").then((r) => r.data),
  createReport: (formData) =>
    client.post("/reports", formData, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data),
  updateAmounts: (id, body) => client.patch(`/reports/${id}/amounts`, body).then((r) => r.data),
  regenerateReport: (id, body) => client.post(`/reports/${id}/regenerate`, body).then((r) => r.data),
  updatePublisherAmounts: (id, body) => client.patch(`/reports/${id}/publisher-amounts`, body).then((r) => r.data),
  trends: () => client.get("/trends").then((r) => r.data),
  listViews: () => client.get("/views").then((r) => r.data),
  createView: (body) => client.post("/views", body).then((r) => r.data),
  deleteView: (id) => client.delete(`/views/${id}`).then((r) => r.data),
  getCumulative: (params) => client.get("/reports/cumulative", { params }).then((r) => r.data),
  downloadReport: (id, params = {}) => download(`/reports/${id}/export`, params, "report.xlsx"),
  downloadCumulative: (params) => download("/reports/cumulative/export", params, "report_range.xlsx"),
};
