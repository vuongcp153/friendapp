const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const scanBtn = document.getElementById('scanBtn');
const confirmBtn = document.getElementById('confirmBtn');
const ageEl = document.getElementById('age');
const genderEl = document.getElementById('gender');
const raceEl = document.getElementById('race');

let imageBlob;

// Khởi động camera
async function startCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    video.srcObject = stream;
  } catch (err) {
    console.error('Không thể truy cập camera:', err);
    alert('Vui lòng cấp quyền truy cập camera.');
  }
}
startCamera();

// Bật/ tắt nút Xác Nhận
confirmBtn.style.display = 'none';

scanBtn.addEventListener('click', () => {
  // Vẽ lên canvas
  const ctx = canvas.getContext('2d');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  ctx.drawImage(video, 0, 0);

  canvas.toBlob(async blob => {
    imageBlob = blob;
    const form = new FormData();
    form.append('image', blob, 'scan.png');

    try {
      const res = await fetch('/api/analyze', { method: 'POST', body: form });
      if (!res.ok) throw new Error('Phân tích ảnh thất bại');
      const attrs = await res.json();
      ageEl.textContent = attrs.age;
      genderEl.textContent = attrs.gender;
      raceEl.textContent = attrs.race;
      confirmBtn.style.display = 'inline-block';
    } catch (err) {
      console.error(err);
      alert('Lỗi khi phân tích khuôn mặt.');
    }
  }, 'image/png');
});

confirmBtn.addEventListener('click', async () => {
  const name = prompt('Nhập tên của bạn:');
  if (!name) return alert('Vui lòng nhập tên.');

  const form = new FormData();
  form.append('name', name);
  form.append('image', imageBlob, 'scan.png');

  try {
    const res = await fetch('/api/register', { method: 'POST', body: form });
    if (!res.ok) throw new Error('Lưu user thất bại');
    const { user_id } = await res.json();
    localStorage.setItem('user_id', user_id);
    localStorage.setItem('name', name);
    window.location.href = '/video';
  } catch (err) {
    console.error(err);
    alert('Lỗi khi đăng ký.');
  }
});