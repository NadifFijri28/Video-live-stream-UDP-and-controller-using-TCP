"""
- Mengambil video dari kamera dan mengirim ke client via UDP.
- Mendengarkan perintah arah dari client via TCP dan mengubah koordinat kartesian.
- Menampilkan preview video lokal.
- Menampilkan log koordinat setiap kali perintah arah diterima.
"""
# Import library untuk pengolahan video, komunikasi jaringan, dan threading
import cv2
import socket
import time
import numpy as np
import threading  

class VideoStreamSender:
    """
    Kelas utama server:
    - start(): Memulai streaming video dan listener TCP.
    - _capture_and_send(): Loop pengambilan frame dan pengiriman ke client.
    - _tcp_command_listener(): Listener TCP untuk menerima perintah arah dan update koordinat.
    - stop(): Menghentikan streaming dan release resource.
    """
    def __init__(self, ip="127.0.0.1", port=9001, camera_index=0):
        # Ubah 'ip' di sini ke IP client (penerima video) jika ingin streaming ke perangkat lain.
        # Contoh: ip="192.168.1.**" jika client berada di jaringan lokal dengan IP tersebut.

        # Inisialisasi variabel utama
        self.coord_x = 0
        self.coord_y = 0
        self.ip = ip
        self.port = port
        self.camera_index = camera_index
        self.running = False
        self.sock = None
        self.frame_stats = {'last_time': time.time(), 'fps': 0, 'total_frames': 0}
        self.cap = None

    def start(self):
        # Mulai streaming video dan listener TCP dalam thread terpisah
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
        self.cap = cv2.VideoCapture(self.camera_index)
        self._configure_camera()
        threading.Thread(target=self._capture_and_send, daemon=True).start()
        threading.Thread(target=self._tcp_command_listener, daemon=True).start()
        print(f"📡 Streaming to {self.ip}:{self.port}")

    def _configure_camera(self):
        # Set resolusi dan FPS kamera
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

    def _capture_and_send(self):
        # Loop utama: ambil frame dari kamera, encode, kirim ke client
        while self.running:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    print("⚠️ Camera error")
                    time.sleep(1)
                    continue

                self.frame_stats['total_frames'] += 1
                current_time = time.time()
                if current_time - self.frame_stats['last_time'] >= 1.0:
                    self.frame_stats['fps'] = self.frame_stats['total_frames']
                    self.frame_stats['total_frames'] = 0
                    self.frame_stats['last_time'] = current_time

                _, buffer = cv2.imencode('.jpg', frame, [
                    cv2.IMWRITE_JPEG_QUALITY, 80,
                    cv2.IMWRITE_JPEG_PROGRESSIVE, 1
                ])
                data = buffer.tobytes()

                chunk_size = 65507
                chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]

                try:
                    self.sock.sendto(len(chunks).to_bytes(4, 'big'), (self.ip, self.port))
                    for chunk in chunks:
                        self.sock.sendto(chunk, (self.ip, self.port))
                except Exception as e:
                    print(f"\n⚠️ Send error: {str(e)}")
                    time.sleep(1)

                cv2.imshow('Sender Preview', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.stop()
                    break

            except Exception as e:
                print(f"\n⚠️ Capture error: {str(e)}")
                time.sleep(1)

    def _tcp_command_listener(self):
        # Listener TCP: menerima perintah arah dari client dan update koordinat
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp_sock.bind(("0.0.0.0", 9002))
        tcp_sock.listen(1)
        print("🡺 TCP command server listening on port 9002")
        while self.running:
            conn, addr = tcp_sock.accept()
            with conn:
                data = conn.recv(1024)
                if data:
                    direction = data.decode().strip().upper()
                    arah_map = {
                        "LEFT": "kiri",
                        "RIGHT": "kanan",
                        "UP": "atas",
                        "DOWN": "bawah"
                    }
                    arah_log = arah_map.get(direction, direction)
                    
                    if direction == "RIGHT":
                        self.coord_x += 1
                    elif direction == "LEFT":
                        self.coord_x -= 1
                    elif direction == "UP":
                        self.coord_y += 1
                    elif direction == "DOWN":
                        self.coord_y -= 1
                    
                    print(f"\n➡️ Received direction: {arah_log} | Koordinat saat ini: ({self.coord_x}, {self.coord_y})")

    def stop(self):
        # Stop streaming dan release semua resource
        self.running = False
        if self.cap:
            self.cap.release()
        if self.sock:
            self.sock.close()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    # Entry point program
    # Membuat objek sender dan mulai streaming video
    # --- PETUNJUK ---
    # Ubah ip="127.0.0.1" ke IP client (penerima video) jika ingin streaming ke perangkat lain.
    # Contoh: ip="192.168.1.10"
    sender = VideoStreamSender(ip="127.0.0.1")
    try:
        sender.start()
        # Loop utama agar program tetap berjalan
        while sender.running:
            time.sleep(1)
    except KeyboardInterrupt:
        # Stop streaming jika user menekan Ctrl+C
        pass
    finally:
        sender.stop()