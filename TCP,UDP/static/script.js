// Inisialisasi canvas
const canvas = document.getElementById('coordsCanvas');
const ctx = canvas.getContext('2d');
const canvasSize = 500; // Ukuran canvas dalam pixel
const gridCells = 100;  // Jumlah grid dalam satu sumbu
const cellSize = canvasSize / gridCells; // Ukuran setiap cell dalam pixel
const center = gridCells / 2; // Titik pusat (0,0)

// Fungsi untuk menggambar grid 100x100
function drawGrid() {
    // Bersihkan canvas
    ctx.clearRect(0, 0, canvasSize, canvasSize);
    
    // Gambar background putih
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, canvasSize, canvasSize);
    
    // Gambar grid lines
    ctx.strokeStyle = '#eee'; // Warna garis grid lebih terang
    ctx.lineWidth = 0.5;
    
    // Garis vertikal (100 garis)
    for (let x = 0; x <= gridCells; x++) {
        ctx.beginPath();
        ctx.moveTo(x * cellSize, 0);
        ctx.lineTo(x * cellSize, canvasSize);
        ctx.stroke();
    }
    
    // Garis horizontal (100 garis)
    for (let y = 0; y <= gridCells; y++) {
        ctx.beginPath();
        ctx.moveTo(0, y * cellSize);
        ctx.lineTo(canvasSize, y * cellSize);
        ctx.stroke();
    }
    
    // Gambar sumbu X dan Y lebih tebal
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(center * cellSize, 0);
    ctx.lineTo(center * cellSize, canvasSize);
    ctx.moveTo(0, center * cellSize);
    ctx.lineTo(canvasSize, center * cellSize);
    ctx.stroke();
    
    // Label sumbu
    ctx.fillStyle = '#555';
    ctx.font = 'bold 12px Arial';
    ctx.fillText('Y', center * cellSize + 10, 15);
    ctx.fillText('X', canvasSize - 15, center * cellSize - 10);
}

// Fungsi untuk menggambar titik koordinat
function drawCoords(x, y) {
    // Gambar ulang grid
    drawGrid();
    
    // Konversi koordinat (-50 to 50) ke posisi pixel
    const plotX = center * cellSize + (x * cellSize);
    const plotY = center * cellSize - (y * cellSize);
    
    // Gambar titik koordinat (lebih kecil)
    ctx.fillStyle = 'red';
    ctx.beginPath();
    ctx.arc(plotX, plotY, 3, 0, Math.PI * 2);
    ctx.fill();
    
    // Label koordinat
    ctx.fillStyle = 'black';
    ctx.font = '12px Arial';
    ctx.fillText(`(${x}, ${y})`, plotX + 8, plotY - 8);
    
    // Update teks koordinat
    document.getElementById('coordsText').textContent = `(${x}, ${y})`;
}

// Fungsi untuk memperbarui statistik dan koordinat
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
        .catch(err => console.error("Error fetching stats:", err));

    // Ambil koordinat terbaru
    fetch('/coords')
        .then(response => response.json())
        .then(data => drawCoords(data.x, data.y))
        .catch(err => {
            console.error("Error fetching coords:", err);
            drawCoords(0, 0);
        });
}

// Fungsi untuk mengirim perintah arah
function sendDirection(dir) {
    fetch('/direction', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ direction: dir })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'ok') {
            console.log('Direction sent:', data.direction);
            updateStats(); // Segarkan tampilan setelah mengirim
        }
    })
    .catch(err => console.error("Error sending direction:", err));
}

// Inisialisasi saat halaman dimuat
window.onload = function() {
    // Set ukuran canvas (pastikan di HTML canvas memiliki width/height yang sesuai)
    canvas.width = canvasSize;
    canvas.height = canvasSize;
    
    drawGrid();
    drawCoords(0, 0);
    
    // Perbarui setiap detik
    setInterval(updateStats, 1000);
    updateStats();
};