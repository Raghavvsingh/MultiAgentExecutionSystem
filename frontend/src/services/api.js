import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL;

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const analysisApi = {
  startAnalysis: async (goal) => {
    const response = await api.post('/start-analysis', { goal });
    return response.data;
  },

  getStatus: async (runId) => {
    const response = await api.get(`/status/${runId}`);
    return response.data;
  },

  getResult: async (runId) => {
    const response = await api.get(`/result/${runId}`);
    return response.data;
  },

  approveRun: async (runId, approved, feedback = null, edits = null) => {
    const response = await api.post(`/approve/${runId}`, {
      approved,
      feedback,
      edits,
    });
    return response.data;
  },

  getLogs: async (runId, limit = 100, offset = 0) => {
    const response = await api.get(`/logs/${runId}`, {
      params: { limit, offset },
    });
    return response.data;
  },

  resumeRun: async (runId) => {
    const response = await api.post(`/resume/${runId}`);
    return response.data;
  },
};

// ✅ FIXED WebSocket (IMPORTANT)
export const createWebSocket = (runId, onMessage, onError) => {
  const base = import.meta.env.VITE_API_URL.replace('https', 'wss');
  const wsUrl = `${base}/ws/${runId}`;

  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log('WebSocket connected');
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (e) {
      if (event.data !== 'keepalive' && event.data !== 'pong') {
        console.warn('Failed to parse WebSocket message:', event.data);
      }
    }
  };

  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
    if (onError) onError(error);
  };

  ws.onclose = () => {
    console.log('WebSocket closed');
  };

  const pingInterval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send('ping');
    }
  }, 25000);

  return {
    ws,
    close: () => {
      clearInterval(pingInterval);
      ws.close();
    },
  };
};

export default api;
