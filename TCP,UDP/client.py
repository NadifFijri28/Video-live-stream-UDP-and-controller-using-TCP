# Import library untuk komunikasi jaringan, threading, pengolahan gambar, dan web server
import socket
import threading
import cv2
import numpy as np
import os
import time
from flask import Flask, Response, render_template, request, jsonify


# Inisialisasi aplikasi Flask dan variabel global untuk menyimpan frame video terbaru
app = Flask(__name__, template_folder='.')
latest_frame = {'data': b'', 'timestamp': 0, 'counter': 0, 'stats': {'fps': 0}}

class VideoStreamReceiver:
    """
    Kelas untuk menerima stream video melalui UDP dan mengupdate frame terbaru
    """
    def __init__(self, ip="0.0.0.0", port=9001):
        # Alamat IP dan port untuk menerima data video
        self.ip = ip
        self.port = port
        self.running = False
        self.sock = None
        self.frame_stats = {'last_time': time.time(), 'fps': 0, 'total_frames': 0}
        
    def start(self):
        # Memulai thread untuk menerima frame video
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        self.sock.bind((self.ip, self.port))
        threading.Thread(target=self._receive_frames, daemon=True).start()
        print(f"🚀 UDP receiver started on {self.ip}:{self.port}")

    def _receive_frames(self):
        # Fungsi utama untuk menerima dan memproses frame video
        while self.running:
            try:
                # Menerima metadata jumlah potongan frame
                data, _ = self.sock.recvfrom(4)
                num_chunks = int.from_bytes(data, 'big')
                
                # Menerima semua potongan frame
                chunks = []
                for _ in range(num_chunks):
                    chunk, _ = self.sock.recvfrom(65507)
                    chunks.append(chunk)
                
                frame_data = b''.join(chunks)
                
                # Mengubah data menjadi frame gambar
                np_frame = np.frombuffer(frame_data, dtype=np.uint8)
                frame = cv2.imdecode(np_frame, cv2.IMREAD_COLOR)
                
                if frame is not None:
                    # Hitung FPS
                    self.frame_stats['total_frames'] += 1
                    current_time = time.time()
                    if current_time - self.frame_stats['last_time'] >= 1.0:
                        self.frame_stats['fps'] = self.frame_stats['total_frames']
                        self.frame_stats['total_frames'] = 0
                        self.frame_stats['last_time'] = current_time
                    
                    # Update frame terbaru ke variabel global
                    latest_frame.update({
                        'data': frame_data,
                        'timestamp': time.time(),
                        'counter': latest_frame['counter'] + 1,
                        'stats': self.frame_stats.copy()
                    })
                    
            except Exception as e:
                print(f"\n⚠️ Error receiving frame: {str(e)}")
                time.sleep(1)  # Tunggu sebelum mencoba lagi

    def stop(self):
        # Menghentikan penerimaan frame
        self.running = False
        if self.sock:
            self.sock.close()

def send_direction_to_server(direction, server_ip='127.0.0.1', server_port=9002):
    # Fungsi untuk mengirimkan perintah arah ke server melalui TCP
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((server_ip, server_port))
            s.sendall(direction.encode())
    except Exception as e:
        print(f"⚠️ Failed to send direction: {e}")

@app.route('/')
def index():
    # Endpoint utama untuk menampilkan halaman web
    return render_template('webserver.html')

first_access_logged = False  # Variabel untuk mencatat akses pertama ke stream video

@app.route('/video_feed')
def video_feed():
    # Endpoint untuk streaming video ke web client
    global first_access_logged
    if not first_access_logged:
        client_ip = request.remote_addr
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"🌐 Device {client_ip} connected to video stream at {now}")
        first_access_logged = True
    def generate():
        # Generator untuk mengirim frame video secara terus-menerus
        while True:
            if latest_frame['data']:
                yield (b'--frame\r\n'
                      b'Content-Type: image/jpeg\r\n\r\n' + 
                      latest_frame['data'] + b'\r\n')
            time.sleep(0.03)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stats')
def stats():
    # Endpoint untuk mendapatkan statistik streaming video
    if latest_frame['data']:
        return {
            'fps': latest_frame['stats']['fps'],
            'last_update': time.time() - latest_frame['timestamp'],
            'total_frames': latest_frame['counter']
        }
    return {'status': 'no frames received'}

@app.route('/direction', methods=['POST'])
def direction():
    # Endpoint untuk menerima perintah arah dari web client dan meneruskannya ke server
    direction = None
    if request.is_json:
        direction = request.json.get('direction')
    elif 'direction' in request.form:
        direction = request.form['direction']
    if direction:
        send_direction_to_server(direction)
        return jsonify({'status': 'ok', 'direction': direction})
    return jsonify({'status': 'error', 'message': 'No direction received'}), 400

if __name__ == '__main__':
    # Program utama: inisialisasi dan jalankan server video serta web server
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
        print(f"🌐 Web server running at http://{local_ip}:5000 (akses dari device lain di jaringan yang sama)")
        app.run(host="0.0.0.0", port=5000, threaded=True)
    finally:
        receiver.stop()