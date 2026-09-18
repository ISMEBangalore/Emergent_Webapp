// Minimal static file server for the traffic lab's HTML visualizations.
//
// The only reason this exists instead of a plain static host: the Google
// Maps page needs its API key injected at runtime from the GOOGLE_MAPS_API_KEY
// environment variable, never committed to the repo. This writes that key
// into docs/google-map-key.local.js (already gitignored) once at startup,
// then serves the docs/ directory as-is.
const http = require("http");
const fs = require("fs");
const path = require("path");

const DOCS_DIR = path.join(__dirname, "..", "docs");
const PORT = process.env.PORT || 3000;

const keyFilePath = path.join(DOCS_DIR, "google-map-key.local.js");
const apiKey = process.env.GOOGLE_MAPS_API_KEY || "";
fs.writeFileSync(keyFilePath, `window.GOOGLE_MAPS_API_KEY = ${JSON.stringify(apiKey)};\n`);
if (!apiKey) {
  console.warn("GOOGLE_MAPS_API_KEY is not set — /google-map.html will show its setup banner.");
}

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".csv": "text/csv; charset=utf-8",
  ".yaml": "text/yaml; charset=utf-8",
  ".svg": "image/svg+xml",
};

const server = http.createServer((req, res) => {
  const requestedPath = decodeURIComponent((req.url || "/").split("?")[0]);
  const relativePath = requestedPath === "/" ? "/index.html" : requestedPath;
  const filePath = path.join(DOCS_DIR, relativePath);

  if (!filePath.startsWith(DOCS_DIR)) {
    res.writeHead(403);
    return res.end("Forbidden");
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404, { "Content-Type": "text/plain" });
      return res.end("Not found");
    }
    const ext = path.extname(filePath);
    res.writeHead(200, { "Content-Type": MIME_TYPES[ext] || "application/octet-stream" });
    res.end(data);
  });
});

server.listen(PORT, () => {
  console.log(`Serving ${DOCS_DIR} on port ${PORT}`);
});
