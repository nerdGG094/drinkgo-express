// Servidor roda em async_mode="threading" no Werkzeug — WebSocket "puro" não
// é suportado, só polling. Forçar polling evita o AssertionError no terminal
// (write() before start_response) sem perder funcionalidade — os eventos
// continuam chegando em tempo quase real.
const socket = io('/admin', { path: '/socket.io', transports: ['polling'] });

socket.on('connect', () => {
  console.log('Conectado ao SocketIO (admin namespace)');
});

socket.on('novo_pedido', data => {
  console.log('Novo pedido recebido', data);
  location.reload();
});

socket.on('status_atualizado', data => {
  console.log('Status atualizado', data);
  const card = document.getElementById('pedido-' + data.pedido_id);
  if (card) {
    const span = card.querySelector('.status');
    if (span) {
      span.textContent = data.status;
      span.className = 'status status-' + data.status;
    }
  }
});

function alterarStatus(pedidoId, novoStatus) {
  fetch(`/admin/api/pedido/${pedidoId}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: novoStatus })
  }).then(r => r.json()).then(data => {
    console.log('Status alterado', data);
  });
}
