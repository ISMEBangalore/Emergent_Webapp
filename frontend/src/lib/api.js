import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const client = axios.create({ baseURL: API });

export const api = {
  getSettings: () => client.get("/settings").then((r) => r.data),
  updateSettings: (body) => client.put("/settings", body).then((r) => r.data),
  listReports: () => client.get("/reports").then((r) => r.data),
  getReport: (id) => client.get(`/reports/${id}`).then((r) => r.data),
  deleteReport: (id) => client.delete(`/reports/${id}`).then((r) => r.data),
  createSample: () => client.post("/reports/sample").then((r) => r.data),
  createReport: (formData) =>
    client.post("/reports", formData, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data),
  updateAmounts: (id, body) => client.patch(`/reports/${id}/amounts`, body).then((r) => r.data),
  updatePublisherAmounts: (id, body) => client.patch(`/reports/${id}/publisher-amounts`, body).then((r) => r.data),
  trends: () => client.get("/trends").then((r) => r.data),
  getCumulative: () => client.get("/reports/cumulative").then((r) => r.data),
  cumulativeExportUrl: () => `${API}/reports/cumulative/export`,
  exportUrl: (id) => `${API}/reports/${id}/export`,
};
