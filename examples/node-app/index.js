const http = require('http');

const PORT = parseInt(process.env.PORT || '3000', 10);

const server = http.createServer((req, res) => {
  if (req.url === '/' || req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'healthy',
      app: 'node-sample-app',
      port: PORT,
      message: 'Hello from DeployHub Node.js runtime!'
    }));
  } else {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'not found' }));
  }
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[node-app] Server started at http://0.0.0.0:${PORT}`);
});
