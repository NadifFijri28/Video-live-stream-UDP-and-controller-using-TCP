// Fungsi untuk memperbarui statistik
function updateStats() {
    fetch('/stats')
        .then(response => response.json())
        .then(data => {
            const fpsElement = document.getElementById('fps');
            const totalFramesElement = document.getElementById('totalFrames');
            const lastUpdateElement = document.getElementById('lastUpdate');

            if (data.fps !== undefined) {
                fpsElement.textContent = data.fps;
                totalFramesElement.textContent = data.total_frames;
                lastUpdateElement.textContent = `${data.last_update.toFixed(2)}s ago`;
            }
        })
        .catch(err => {
            console.error("Gagal memuat statistik:", err);
        });

    // Ambil koordinat terbaru
    fetch('/coords')
        .then(response => response.json())
        .then(data => {
            drawCoords(data.x, data.y);
            document.getElementById('coordsText').textContent = `(${data.x}, ${data.y})`;
        })
        .catch(err => {
            console.error("Gagal mengambil koordinat:", err);
            drawCoords(0, 0);
        });
}

// Fungsi untuk menggambar koordinat
function drawCoords(x, y) {
    const canvas = document.getElementById('coordsCanvas');
    const ctx = canvas.getContext('2d');
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    
    // Bersihkan canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Gambar grid
    ctx.strokeStyle = '#ddd';
    ctx.lineWidth = 1;
    
    // Garis vertikal
    for (let i = 0; i <= canvas.width; i += 20) {
        ctx.beginPath();
        ctx.moveTo(i, 0);
        ctx.lineTo(i, canvas.height);
        ctx.stroke();
    }
    
    // Garis horizontal
    for (let j = 0; j <= canvas.height; j += 20) {
        ctx.beginPath();
        ctx.moveTo(0, j);
        ctx.lineTo(canvas.width, j);
        ctx.stroke();
    }
    
    // Gambar sumbu X dan Y
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(centerX, 0);
    ctx.lineTo(centerX, canvas.height);
    ctx.moveTo(0, centerY);
    ctx.lineTo(canvas.width, centerY);
    ctx.stroke();
    
    // Gambar titik koordinat
    const plotX = centerX + (x * 20);
    const plotY = centerY - (y * 20);
    
    ctx.fillStyle = 'red';
    ctx.beginPath();
    ctx.arc(plotX, plotY, 8, 0, Math.PI * 2);
    ctx.fill();
    
    // Label koordinat
    ctx.fillStyle = 'black';
    ctx.font = 'bold 14px Arial';
    ctx.fillText(`(${x}, ${y})`, plotX + 10, plotY - 10);
}

// Fungsi untuk mengirim arah
function sendDirection(dir) {
    fetch('/direction', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ direction: dir })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'ok') {
            console.log('Arah terkirim:', data.direction);
            // Perbarui tampilan koordinat setelah mengirim arah
            updateStats();
        }
    })
    .catch(err => {
        console.error("Gagal mengirim arah:", err);
    });
}

// Perbarui statistik setiap detik
setInterval(updateStats, 1000);
updateStats();
