"""
- Menerima video dari server via UDP dan menampilkan di web.
- Menyediakan webserver (Flask) untuk kontrol arah dan visualisasi koordinat.
- Mengirim perintah arah ke server via TCP.
- Menyimpan dan menampilkan statistik frame dan koordinat.
"""
# Import library untuk komunikasi jaringan, threading, pengolahan gambar, dan web server
import socket
import threading
import cv2
import numpy as np
import os
import time
import json
from flask import Flask, Response, render_template, request, jsonify

# Inisialisasi aplikasi Flask dan variabel global
from flask import send_from_directory
app = Flask(__name__, template_folder='.', static_folder='static')
@app.route('/static/<path:filename>')
def static_files(filename):
    # Endpoint untuk melayani file statis (CSS/JS)
    return send_from_directory(app.static_folder, filename)
latest_frame = {'data': b'', 'timestamp': 0, 'counter': 0, 'stats': {'fps': 0}}
current_coords = {'x': 0, 'y': 0}  # Menyimpan koordinat terbaru

class VideoStreamReceiver:
    """
    Kelas utama client:
    - start(): Mulai menerima stream video dari server UDP.
    - _receive_frames(): Loop menerima frame, update statistik, update frame terbaru.
    - stop(): Menghentikan receiver dan release resource.
    """
    def __init__(self, ip="0.0.0.0", port=9001):
        # Ubah 'ip' di sini ke IP client jika ingin menerima hanya dari IP tertentu.
        # Biasanya biarkan "0.0.0.0" agar menerima dari semua alamat.

        # Inisialisasi variabel utama
        self.ip = ip
        self.port = port
        self.running = False
        self.sock = None
        self.frame_stats = {'last_time': time.time(), 'fps': 0, 'total_frames': 0}
        self.buffer_size = 65536  # Meningkatkan buffer untuk throughput tinggi
        
    def start(self):
        # Mulai receiver UDP dalam thread terpisah
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.buffer_size)
        self.sock.bind((self.ip, self.port))
        threading.Thread(target=self._receive_frames, daemon=True).start()
        print(f"🚀 UDP receiver started on {self.ip}:{self.port}")

    def _receive_frames(self):
        # Loop utama: menerima frame dari server, update statistik dan frame terbaru
        packet_buffer = {}
        
        while self.running:
            try:
                # Terima metadata frame
                metadata, _ = self.sock.recvfrom(1024)
                metadata = json.loads(metadata.decode())
                frame_id = metadata['frame_id']
                num_chunks = metadata['num_chunks']
                
                # Terima semua chunk untuk frame ini
                chunks = [None] * num_chunks
                chunks_received = 0
                timeout = time.time() + 0.1  # Timeout 100ms untuk frame
                
                while chunks_received < num_chunks and time.time() < timeout:
                    try:
                        chunk_data, _ = self.sock.recvfrom(65507)
                        chunk_id = int.from_bytes(chunk_data[4:6], 'big')
                        if chunk_id < num_chunks:
                            chunks[chunk_id] = chunk_data[6:]  # Hapus header
                            chunks_received += 1
                    except:
                        pass
                
                # Jika semua chunk diterima, reassemble frame
                if chunks_received == num_chunks and all(chunks):
                    frame_data = b''.join(chunks)
                    np_frame = np.frombuffer(frame_data, dtype=np.uint8)
                    frame = cv2.imdecode(np_frame, cv2.IMREAD_COLOR)
                    
                    if frame is not None:
                        self.frame_stats['total_frames'] += 1
                        current_time = time.time()
                        elapsed = current_time - self.frame_stats['last_time']
                        
                        if elapsed >= 1.0:
                            self.frame_stats['fps'] = self.frame_stats['total_frames'] / elapsed
                            self.frame_stats['total_frames'] = 0
                            self.frame_stats['last_time'] = current_time
                        
                        latest_frame.update({
                            'data': frame_data,
                            'timestamp': current_time,
                            'counter': latest_frame['counter'] + 1,
                            'stats': self.frame_stats.copy()
                        })
                
            except Exception as e:
                print(f"\n⚠️ Error receiving frame: {str(e)}")
                time.sleep(0.001)  # Mengurangi sleep time untuk responsivitas

    def stop(self):
        # Stop receiver dan release resource
        self.running = False
        if self.sock:
            self.sock.close()

def send_direction_to_server(direction, server_ip='192.168.31', server_port=9002): #Ganti IP sesuai maixcam
    # Fungsi untuk mengirim perintah arah ke server via TCP
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)  # Timeout lebih pendek
            s.connect((server_ip, server_port))
            s.sendall(direction.encode())
    except Exception as e:
        print(f"⚠️ Failed to send direction: {e}")

@app.route('/')
def index():
    # Endpoint utama webserver, menampilkan halaman kontrol dan video
    return render_template('webserver.html')

first_access_logged = False

@app.route('/video_feed')
def video_feed():
    # Endpoint streaming video ke web, format MJPEG
    global first_access_logged
    if not first_access_logged:
        client_ip = request.remote_addr
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"🌐 Device {client_ip} connected to video stream at {now}")
        first_access_logged = True
    
    def generate():
        last_frame_time = time.time()
        while True:
            if latest_frame['data']:
                yield (b'--frame\r\n'
                      b'Content-Type: image/jpeg\r\n\r\n' + 
                      latest_frame['data'] + b'\r\n')
                # Menjaga frame rate konsisten
                elapsed = time.time() - last_frame_time
                sleep_time = max(0, 1/30 - elapsed)  # Target 30 FPS
                time.sleep(sleep_time)
                last_frame_time = time.time()
            else:
                time.sleep(0.01)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stats')
def stats():
    # Endpoint statistik frame untuk web
    if latest_frame['data']:
        return {
            'fps': round(latest_frame['stats']['fps'], 1),
            'last_update': time.time() - latest_frame['timestamp'],
            'total_frames': latest_frame['counter']
        }
    return {'status': 'no frames received'}

@app.route('/coords')
def get_coords():
    # Endpoint koordinat kartesian untuk web
    global current_coords
    return jsonify(current_coords)

@app.route('/direction', methods=['POST'])
def direction():
    # Endpoint menerima perintah arah dari web, update koordinat dan kirim ke server
    global current_coords
    direction = None
    if request.is_json:
        direction = request.json.get('direction')
    elif 'direction' in request.form:
        direction = request.form['direction']
    
    if direction:
        # Update koordinat lokal
        if direction == "RIGHT":
            current_coords['x'] += 1
        elif direction == "LEFT":
            current_coords['x'] -= 1
        elif direction == "UP":
            current_coords['y'] += 1
        elif direction == "DOWN":
            current_coords['y'] -= 1
        
        send_direction_to_server(direction)
        return jsonify({
            'status': 'ok', 
            'direction': direction,
            'coords': current_coords
        })
    return jsonify({'status': 'error', 'message': 'No direction received'}), 400

if __name__ == '__main__':
    # Entry point program client
    import socket
    def get_local_ip():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = 'localhost'
        finally:
            s.close()
        return ip

    receiver = VideoStreamReceiver()
    receiver.start()
    try:
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        local_ip = get_local_ip()
        print(f"🌐 Web server running at http://localhost:5000")
        print(f"🌐 Web server running at http://{local_ip}:5000")
        app.run(host="0.0.0.0", port=5000, threaded=True)
    finally:
        receiver.stop()