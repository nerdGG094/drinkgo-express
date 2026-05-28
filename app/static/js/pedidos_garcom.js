// Polling para evitar erro no Werkzeug + threading — ver comentário em admin_realtime.js
const socket = io('/public', { path: '/socket.io', transports: ['polling'] });
  socket.on('novo_pedido', () => location.reload());
  socket.on('status_atualizado', () => location.reload());