// Fix the infinite loop in the /api/process endpoint
function processRequest(req, res) {
  // Add a check to prevent infinite loop
  if (req.body.data && req.body.data.length > 1000) {
    return res.status(400).json({ error: 'Request data too large' });
  }

  // Existing code to process the request
  // ...
}

// Optimize CPU usage by using worker threads
import { Worker } from 'worker_threads';

function handleRequest(req, res) {
  const worker = new Worker('./worker.js');
  worker.on('message', result => {
    res.json(result);
  });
  worker.postMessage(req.body);
}