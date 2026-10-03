// Local-only static server matching rest_server.py's / and /static mounts.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../../scraper/web/static');
const routes = {
  '/': ['index.html', 'text/html'],
  '/static/index.html': ['index.html', 'text/html'],
  '/static/app.js': ['app.js', 'text/javascript'],
};
http.createServer((req, res) => {
  const target = routes[new URL(req.url, 'http://127.0.0.1').pathname];
  if (!target) {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({ detail: 'Not Found' }));
  }
  res.writeHead(200, { 'Content-Type': target[1] });
  res.end(fs.readFileSync(path.join(root, target[0])));
}).listen(18765, '127.0.0.1');
