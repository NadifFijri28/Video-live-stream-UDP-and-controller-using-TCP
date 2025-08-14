"""
Server penyiaran video UDP dan penerima perintah TCP dengan sinkronisasi koordinat
"""
import cv2
import socket
import time
import numpy as np
import threading
import json

class VideoStreamSender:
    def __init__(self, server_ip="127.0.0.1", video_port=9001, command_port=9002, camera_index=0):
        # Inisialisasi koordinat dengan thread lock
        self.coord_x = 0
        self.coord_y = 0
        self.coord_lock = threading.Lock()
        
        # Konfigurasi jaringan
        self.server_ip = server_ip
        self.video_port = video_port
        self.command_port = command_port
        self.camera_index = camera_index
        
        # Status kontrol
        self.running = False
        self.udp_sock = None
        self.cap = None
        
        # Statistik
        self.frame_stats = {
            'last_time': time.time(),
            'fps': 0,
            'total_frames': 0,
            'command_count': 0
        }

    def start(self):
        """Memulai semua komponen server"""
        self.running = True
        
        # Setup UDP untuk streaming video
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
        
        # Setup kamera
        self.cap = cv2.VideoCapture(self.camera_index)
        self._configure_camera()
        
        # Mulai thread untuk TCP command server
        threading.Thread(target=self._tcp_command_listener, daemon=True).start()
        
        # Mulai thread untuk streaming video
        threading.Thread(target=self._capture_and_send, daemon=True).start()
        
        print(f"📡 Streaming video UDP ke {self.server_ip}:{self.video_port}")
        print(f"🔄 Server perintah TCP di port {self.command_port}")

    def _configure_camera(self):
        """Konfigurasi kamera"""
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

    def _capture_and_send(self):
        """Loop pengambilan dan pengiriman frame video"""
        while self.running:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    print("⚠️ Gagal membaca frame dari kamera")
                    time.sleep(1)
                    continue

                # Update statistik frame
                with self.coord_lock:
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
                    # Kirim jumlah chunks dulu
                    self.udp_sock.sendto(len(chunks).to_bytes(4, 'big'), (self.server_ip, self.video_port))
                    # Kirim setiap chunk
                    for chunk in chunks:
                        self.udp_sock.sendto(chunk, (self.server_ip, self.video_port))
                except Exception as e:
                    print(f"⚠️ Gagal mengirim video: {str(e)}")
                    time.sleep(1)

                # Tampilkan preview lokal
                cv2.imshow('Preview Server', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.stop()
                    break

            except Exception as e:
                print(f"⚠️ Error pengambilan frame: {str(e)}")
                time.sleep(1)

    def _tcp_command_listener(self):
        """Server TCP untuk menerima perintah kontrol"""
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp_sock.bind(("0.0.0.0", self.command_port))
        tcp_sock.listen(5)  # Antrian 5 koneksi
        
        print(f"🖥️ Server perintah TCP siap di port {self.command_port}")
        
        while self.running:
            try:
                conn, addr = tcp_sock.accept()
                conn.settimeout(2.0)  # Timeout 2 detik
                with conn:
                    data = conn.recv(1024)
                    if data:
                        try:
                            command = json.loads(data.decode())
                            
                            # Handle permintaan sinkronisasi koordinat
                            if 'sync' in command:
                                with self.coord_lock:
                                    response = {
                                        'status': 'ok',
                                        'x': self.coord_x,
                                        'y': self.coord_y,
                                        'type': 'sync_response'
                                    }
                                conn.sendall(json.dumps(response).encode())
                            
                            # Handle perintah gerakan
                            elif 'direction' in command:
                                direction = command['direction'].upper()
                                
                                with self.coord_lock:
                                    # Update koordinat
                                    if direction == "KANAN": self.coord_x += 1
                                    elif direction == "KIRI": self.coord_x -= 1
                                    elif direction == "ATAS": self.coord_y += 1
                                    elif direction == "BAWAH": self.coord_y -= 1
                                    
                                    # Kirim respon dengan koordinat terbaru
                                    response = {
                                        'status': 'ok',
                                        'x': self.coord_x,
                                        'y': self.coord_y,
                                        'type': 'move_response'
                                    }
                                    conn.sendall(json.dumps(response).encode())
                                    
                                    self.frame_stats['command_count'] += 1
                                    print(f"📩 Perintah {direction} diterima. Koordinat: ({self.coord_x}, {self.coord_y})")
                            
                        except json.JSONDecodeError:
                            conn.sendall(json.dumps({
                                'status': 'error',
                                'message': 'Format JSON tidak valid'
                            }).encode())
                        
            except socket.timeout:
                continue
            except Exception as e:
                print(f"⚠️ Error koneksi TCP: {str(e)}")
                
        tcp_sock.close()

    def stop(self):
        """Menghentikan semua komponen server"""
        self.running = False
        if self.cap:
            self.cap.release()
        if self.udp_sock:
            self.udp_sock.close()
        cv2.destroyAllWindows()
        print("🛑 Server dihentikan")

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