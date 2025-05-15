const socket = io();
let localStream, pc,name;
let CURRENT_ROOM_ID = null;
const user_id = localStorage.getItem('user_id');
let isCaller = false;
let isMatched = false;
const overlay = document.getElementById('overlay');
const chatBox = document.getElementById('messages');

const config = {
      iceServers: [
        { urls: "stun:stun.l.google.com:19302" },
        {
          urls: "turn:relay1.expressturn.com:3478",
          username: "efun-user",
          credential: "efun-pass"
        }
      ]
};

async function start() {
  // Lấy media
  localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
  document.getElementById('localVideo').srcObject = localStream;
  remoteVideo.srcObject = createLoadingStream();


  // Tham gia queue
  socket.emit('join_queue', { user_id });

  // Khi có match
  socket.on('matched', async data => {
    const { room, users } = data;
    CURRENT_ROOM_ID = room;
    console.log(users);
    // Xác định người gọi
    isCaller = users[0] === user_id;
    // Tạo RTCPeerConnection
    pc = new RTCPeerConnection(config);
    // Thêm tracks
    localStream.getTracks().forEach(track => pc.addTrack(track, localStream));
    // Signaling ICE
    pc.onicecandidate = e => {
      if (e.candidate) socket.emit('signal', { room, candidate: e.candidate });
    };
    // Nhận track
    pc.ontrack = e => {
      document.getElementById('remoteVideo').srcObject = e.streams[0];
    };
    // Kết nối vào room signaling
    socket.emit('join_room', { room });

    if (isCaller) {
      // Caller tạo offer
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      socket.emit('signal', { room, sdp: pc.localDescription });
    }
  });

  // Xử lý signaling
  socket.on('signal', async msg => {
    const { sdp, candidate } = msg;
    try {
      if (sdp) {
        if (sdp.type === 'offer') {
          // Responder nhận offer
          await pc.setRemoteDescription(new RTCSessionDescription(sdp));
          const answer = await pc.createAnswer();
          await pc.setLocalDescription(answer);
          socket.emit('signal', { room: msg.room, sdp: pc.localDescription });
        } else if (sdp.type === 'answer' && isCaller) {
          // Caller nhận answer
          await pc.setRemoteDescription(new RTCSessionDescription(sdp));
        }
      }
      if (candidate) {
        await pc.addIceCandidate(new RTCIceCandidate(candidate));
      }
    } catch (err) {
      console.error('Error handling signal:', err);
    }
  });

  // Kết thúc
  document.getElementById('leaveBtn').onclick = () => {
    pc.close();
    socket.emit('leave_room', { room: CURRENT_ROOM_ID });
    window.location.href = '/';
  };
}


document.getElementById('sendBtn').onclick = () => {
  const msg = document.getElementById('chat-input').value;
  if (!msg.trim()) return;
  socket.emit('chat_message', { room: CURRENT_ROOM_ID, message: msg });
  document.getElementById('chat-input').value = "";
};
socket.on('chat_message', data => {
  console.log(socket.id);
  console.log(CURRENT_ROOM_ID);
  addMessage(data.sender, data.message);
});

socket.on('partner_left', (data) => {
  if (pc) pc.close();
  console.log(data);
  remoteVideo.srcObject = createLoadingStream();
});

function addMessage(sender, text) {
  const div = document.getElementById('messages');
  const p = document.createElement('p');
  p.innerHTML = `<strong>${sender}:</strong> ${text}`;
  div.appendChild(p);
  div.scrollTop = div.scrollHeight;
}

document.getElementById('nextBtn').onclick = () => {
  chatBox.innerHTML = "";  // Xóa toàn bộ tin nhắn cũ
  if (pc) pc.close();
  socket.emit('leave_room', { room: CURRENT_ROOM_ID });
  socket.emit('join_queue', { user_id });
};

document.getElementById('leaveBtn').onclick = () => {
  chatBox.innerHTML = "";  // Xóa toàn bộ tin nhắn cũ
  if (pc) pc.close();
  socket.emit('leave_room', { room });
  // có thể redirect hoặc show kết thúc
};

function createLoadingStream() {
  const canvas = document.createElement('canvas');
  canvas.width = 640;
  canvas.height = 480;
  const ctx = canvas.getContext('2d');

  let angle = 0;

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#111';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.beginPath();
    ctx.strokeStyle = '#3498db';
    ctx.lineWidth = 10;
    ctx.arc(canvas.width / 2, canvas.height / 2, 50, angle, angle + Math.PI * 1.5);
    ctx.stroke();

    angle += 0.05;
    requestAnimationFrame(draw);
  }

  draw();

  return canvas.captureStream(30); // 30 fps fake video stream
}

start();

