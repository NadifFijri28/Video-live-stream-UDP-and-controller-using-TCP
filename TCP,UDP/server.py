# Import library untuk pengolahan video, komunikasi jaringan, dan threading
import cv2
import socket
import time
import numpy as np
import threading  

class VideoStreamSender:
    """
    Kelas untuk menangkap video dari kamera dan mengirimkannya ke client melalui UDP,
    serta menerima perintah arah dari client melalui TCP.
    """
    def __init__(self, ip="127.0.0.1", port=9001, camera_index=0):
        # Koordinat kartesius
        self.coord_x = 0
        self.coord_y = 0
        # Inisialisasi alamat IP, port tujuan, dan index kamera
        self.ip = ip
        self.port = port
        self.camera_index = camera_index
        self.running = False
        self.sock = None
        self.frame_stats = {'last_time': time.time(), 'fps': 0, 'total_frames': 0}
        self.cap = None

    def start(self):
        # Memulai thread untuk streaming video dan mendengarkan perintah TCP
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
        self.cap = cv2.VideoCapture(self.camera_index)
        self._configure_camera()
        threading.Thread(target=self._capture_and_send, daemon=True).start()
        print(f"📡 Streaming to {self.ip}:{self.port}")

    def _configure_camera(self):
        # Mengatur resolusi dan FPS kamera
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

    def _capture_and_send(self):
        # Fungsi utama untuk menangkap frame dari kamera dan mengirimkannya ke client
        while self.running:
            try:
                ret, frame = self.cap.read()  # Membaca frame dari kamera
                if not ret:
                    print("⚠️ Camera error")
                    time.sleep(1)
                    continue

                # Hitung FPS
                self.frame_stats['total_frames'] += 1
                current_time = time.time()
                if current_time - self.frame_stats['last_time'] >= 1.0:
                    self.frame_stats['fps'] = self.frame_stats['total_frames']
                    self.frame_stats['total_frames'] = 0
                    self.frame_stats['last_time'] = current_time

                # Encode frame ke JPEG dan kirim
                _, buffer = cv2.imencode('.jpg', frame, [
                    cv2.IMWRITE_JPEG_QUALITY, 80,
                    cv2.IMWRITE_JPEG_PROGRESSIVE, 1
                ])
                data = buffer.tobytes()

                # Bagi data menjadi beberapa chunk agar sesuai dengan batas UDP
                chunk_size = 65507  # Max UDP packet size
                chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]

                try:
                    self.sock.sendto(len(chunks).to_bytes(4, 'big'), (self.ip, self.port))  # Kirim jumlah chunk terlebih dahulu
                    for chunk in chunks:
                        self.sock.sendto(chunk, (self.ip, self.port))

                except Exception as e:
                    print(f"\n⚠️ Send error: {str(e)}")
                    time.sleep(1)  # Wait before retrying

                # Tampilkan preview video
                cv2.imshow('Sender Preview', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.stop()
                    break

            except Exception as e:
                print(f"\n⚠️ Capture error: {str(e)}")
                time.sleep(1)

    def stop(self):
        # Menghentikan streaming video dan melepaskan resource
        self.running = False
        if self.cap:
            self.cap.release()
        if self.sock:
            self.sock.close()
        cv2.destroyAllWindows()
    def _tcp_command_listener(self):
        # Fungsi untuk menerima perintah arah dari client melalui TCP
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Membuka socket TCP
        tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp_sock.bind(("0.0.0.0", 9002))  # Bind ke semua interface pada port 9002
        tcp_sock.listen(1)
        print("🡺 TCP command server listening on port 9002")
        while self.running:
            # Loop untuk menerima perintah selama server berjalan
            conn, addr = tcp_sock.accept()
            with conn:
                data = conn.recv(1024)  # Menerima data perintah arah
                if data:
                    direction = data.decode().strip().upper()
                    # Mapping arah ke bahasa Indonesia
                    arah_map = {
                        "LEFT": "kiri",
                        "RIGHT": "kanan",
                        "UP": "atas",
                        "DOWN": "bawah"
                    }
                    arah_log = arah_map.get(direction, direction)
                    # Update koordinat kartesius
                    if direction == "RIGHT":
                        self.coord_x += 1
                    elif direction == "LEFT":
                        self.coord_x -= 1
                    elif direction == "UP":
                        self.coord_y += 1
                    elif direction == "DOWN":
                        self.coord_y -= 1
                    print(f"\n➡️ Received direction: {arah_log} | Koordinat saat ini: ({self.coord_x}, {self.coord_y})")
    def start(self):
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
        self.cap = cv2.VideoCapture(self.camera_index)
        self._configure_camera()
        threading.Thread(target=self._capture_and_send, daemon=True).start()
        threading.Thread(target=self._tcp_command_listener, daemon=True).start()
        print(f"📡 Streaming to {self.ip}:{self.port}")   

if __name__ == '__main__':
    # Program utama: inisialisasi dan jalankan pengirim video serta server perintah TCP
    sender = VideoStreamSender(ip="127.0.0.1")  # Ganti dengan IP server jika berbeda
    try:
        # Mulai streaming dan server perintah
        sender.start()
        while sender.running:
            # Loop utama agar program tetap berjalan
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        # Pastikan resource dilepas saat program dihentikan
        sender.stop()