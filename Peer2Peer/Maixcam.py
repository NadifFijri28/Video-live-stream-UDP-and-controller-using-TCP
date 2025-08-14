"""
- Mengambil video dari kamera dan mengirim langsung ke WebServer.py via UDP
- Menerima perintah arah dari WebServer.py via TCP dan mengupdate koordinat
- Menampilkan preview video lokal
- Menampilkan log koordinat saat menerima perintah arah
"""
import cv2
import socket
import time
import numpy as np
import threading  
import json

class VideoStreamSender:
    def __init__(self, server_ip="127.0.0.1", video_port=9001, command_port=9002, camera_index=0):
        # Inisialisasi koordinat
        self.coord_x = 0
        self.coord_y = 0
        self.server_ip = server_ip  # IP WebServer.py
        self.video_port = video_port  # Port untuk streaming video
        self.command_port = command_port  # Port untuk perintah kontrol
        self.camera_index = camera_index
        self.running = False
        self.sock = None
        self.frame_stats = {'last_time': time.time(), 'fps': 0, 'total_frames': 0}
        self.cap = None

    def start(self):
        self.running = True
        # Setup UDP untuk streaming video
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
        
        # Setup kamera
        self.cap = cv2.VideoCapture(self.camera_index)
        self._configure_camera()
        
        # Mulai thread untuk TCP command server
        threading.Thread(target=self._tcp_command_listener, daemon=True).start()
        
        # Mulai thread untuk streaming video
        threading.Thread(target=self._capture_and_send, daemon=True).start()
        
        print(f"📡 Streaming video ke {self.server_ip}:{self.video_port}")
        print(f"🡺 Server perintah TCP berjalan di port {self.command_port}")

    def _configure_camera(self):
        # Konfigurasi kamera
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

    def _capture_and_send(self):
        while self.running:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    print("⚠️ Gagal membaca frame dari kamera")
                    time.sleep(1)
                    continue

                # Update statistik frame
                self.frame_stats['total_frames'] += 1
                current_time = time.time()
                if current_time - self.frame_stats['last_time'] >= 1.0:
                    self.frame_stats['fps'] = self.frame_stats['total_frames']
                    self.frame_stats['total_frames'] = 0
                    self.frame_stats['last_time'] = current_time

                # Encode frame ke JPEG
                _, buffer = cv2.imencode('.jpg', frame, [
                    cv2.IMWRITE_JPEG_QUALITY, 80,
                    cv2.IMWRITE_JPEG_PROGRESSIVE, 1
                ])
                data = buffer.tobytes()

                # Kirim frame dalam chunks
                chunk_size = 65507  # Ukuran maksimum UDP
                chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]

                try:
                    # Kirim jumlah chunks terlebih dahulu
                    self.sock.sendto(len(chunks).to_bytes(4, 'big'), (self.server_ip, self.video_port))
                    # Kirim setiap chunk
                    for chunk in chunks:
                        self.sock.sendto(chunk, (self.server_ip, self.video_port))
                except Exception as e:
                    print(f"\n⚠️ Gagal mengirim video: {str(e)}")
                    time.sleep(1)

                # Tampilkan preview lokal
                cv2.imshow('Preview Pengirim', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.stop()
                    break

            except Exception as e:
                print(f"\n⚠️ Error pengambilan frame: {str(e)}")
                time.sleep(1)

    def _tcp_command_listener(self):
        # Server TCP untuk menerima perintah arah
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp_sock.bind(("0.0.0.0", self.command_port))
        tcp_sock.listen(1)
        
        while self.running:
            conn, addr = tcp_sock.accept()
            with conn:
                data = conn.recv(1024)
                if data:
                    try:
                        command = json.loads(data.decode())
                        direction = command.get('direction', '').upper()
                        
                        # Update koordinat berdasarkan perintah
                        if direction == "RIGHT":
                            self.coord_x += 1
                        elif direction == "LEFT":
                            self.coord_x -= 1
                        elif direction == "UP":
                            self.coord_y += 1
                        elif direction == "DOWN":
                            self.coord_y -= 1
                        
                        # Kirim balik koordinat terbaru
                        response = {
                            'status': 'ok',
                            'x': self.coord_x,
                            'y': self.coord_y
                        }
                        conn.sendall(json.dumps(response).encode())
                        
                        print(f"\n➡️ Perintah diterima: {direction} | Koordinat: ({self.coord_x}, {self.coord_y})")
                        
                    except Exception as e:
                        print(f"⚠️ Error memproses perintah: {str(e)}")

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
        if self.sock:
            self.sock.close()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    sender = VideoStreamSender()
    try:
        sender.start()
        while sender.running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        sender.stop()