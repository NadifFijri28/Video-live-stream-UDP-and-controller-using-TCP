"""
Server penyiaran video UDP dan penerima perintah TCP dengan sinkronisasi koordinat untuk MaixCam
"""
import socket
import time
import _thread as threading
import json
import gc
from maix import camera, app
import struct

class VideoStreamSender:
    def __init__(self, server_ip="192.168.31", video_port=9001, command_port=9002): #Ganti IP sesuai server
        # Inisialisasi koordinat dengan thread lock
        self.coord_x = 0
        self.coord_y = 0
        self.coord_lock = threading.allocate_lock()
        
        # Konfigurasi jaringan
        self.server_ip = server_ip
        self.video_port = video_port
        self.command_port = command_port
        
        # Status kontrol
        self.running = False
        self.udp_sock = None
        self.tcp_sock = None
        
        # Statistik
        self.frame_stats = {
            'last_time': time.time(),
            'fps': 0,
            'total_frames': 0,
            'command_count': 0
        }
        
        # Inisialisasi kamera
        self.cam = camera.Camera(320, 240)  # Resolusi lebih rendah untuk FPS lebih tinggi
        
        # Pengaturan kompresi gambar
        self.jpeg_quality = 70  # Kualitas JPEG sedikit lebih tinggi untuk kualitas yang baik
        self.max_packet_size = 1400  # Ukuran paket mendekati MTU untuk efisiensi

    def start(self):
        """Memulai semua komponen server"""
        self.running = True
        
        # Setup UDP untuk streaming video
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Setup TCP untuk command server
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_sock.bind(("0.0.0.0", self.command_port))
        self.tcp_sock.listen(1)
        
        # Mulai thread untuk TCP command server
        threading.start_new_thread(self._tcp_command_listener, ())
        
        print("📡 Streaming video UDP ke {}:{}".format(self.server_ip, self.video_port))
        print("🔄 Server perintah TCP di port", self.command_port)
        print("⚙️  Kualitas JPEG: {}, Max Packet Size: {}".format(self.jpeg_quality, self.max_packet_size))
        
        # Mulai loop utama untuk streaming video
        self._capture_and_send()

    def _capture_and_send(self):
        """Loop pengambilan dan pengiriman frame video"""
        frame_id = 0
        
        while self.running and not app.need_exit():
            try:
                start_time = time.time()
                
                # Ambil frame dari kamera
                img = self.cam.read()
                if not img:
                    time.sleep(0.01)
                    continue
                
                # Encode frame ke JPEG
                if hasattr(img, "to_jpeg"):
                    img_bytes = img.to_jpeg(quality=self.jpeg_quality)
                elif hasattr(img, "encode"):
                    img_bytes = img.encode(".jpg", quality=self.jpeg_quality)
                else:
                    # Jika tidak ada metode encoding, coba resize dulu
                    if hasattr(img, "resize"):
                        small_img = img.resize((320, 240))
                        img_bytes = small_img.to_jpeg(quality=self.jpeg_quality)
                    else:
                        continue
                
                # Konversi ke bytes jika perlu
                if hasattr(img_bytes, "to_bytes"):
                    img_bytes = img_bytes.to_bytes()
                
                # Update statistik frame
                with self.coord_lock:
                    self.frame_stats['total_frames'] += 1
                    current_time = time.time()
                    elapsed = current_time - self.frame_stats['last_time']
                    
                    if elapsed >= 1.0:
                        self.frame_stats['fps'] = self.frame_stats['total_frames'] / elapsed
                        self.frame_stats['total_frames'] = 0
                        self.frame_stats['last_time'] = current_time
                        print("FPS: {:.1f}, Ukuran Frame: {} bytes".format(
                            self.frame_stats['fps'], len(img_bytes)))

                # Kirim frame dalam chunks
                chunk_size = self.max_packet_size
                chunks = [img_bytes[i:i+chunk_size] for i in range(0, len(img_bytes), chunk_size)]
                
                # Kirim metadata (frame_id, jumlah chunks)
                metadata = json.dumps({
                    'frame_id': frame_id,
                    'num_chunks': len(chunks),
                    'total_size': len(img_bytes)
                }).encode()
                
                try:
                    # Kirim metadata
                    self.udp_sock.sendto(metadata, (self.server_ip, self.video_port))
                    
                    # Kirim setiap chunk dengan header (frame_id + chunk_number)
                    for i, chunk in enumerate(chunks):
                        header = struct.pack('>IH', frame_id, i)  # 4-byte frame ID + 2-byte chunk number
                        chunk_with_header = header + chunk
                        self.udp_sock.sendto(chunk_with_header, (self.server_ip, self.video_port))
                        
                except Exception as e:
                    print("⚠️ Gagal mengirim video:", str(e))
                
                frame_id = (frame_id + 1) % 10000
                
                # Kontrol frame rate untuk mencapai ~30 FPS
                processing_time = time.time() - start_time
                sleep_time = max(0, 1/30 - processing_time)  # Target 30 FPS
                time.sleep(sleep_time)
                
                # Bersihkan memori
                gc.collect()

            except Exception as e:
                print("⚠️ Error pengambilan frame:", str(e))
                time.sleep(0.01)

    def _tcp_command_listener(self):
        """Server TCP untuk menerima perintah kontrol"""
        print("🖥️ Server perintah TCP siap di port", self.command_port)
        
        while self.running:
            try:
                conn, addr = self.tcp_sock.accept()
                conn.settimeout(0.5)  # Timeout lebih pendek
                print("📩 Koneksi dari:", addr)
                
                data = conn.recv(1024)
                if data:
                    try:
                        command = data.decode().strip()
                        
                        # Handle perintah gerakan
                        if command in ["RIGHT", "LEFT", "UP", "DOWN"]:
                            with self.coord_lock:
                                # Update koordinat
                                if command == "RIGHT": self.coord_x += 1
                                elif command == "LEFT": self.coord_x -= 1
                                elif command == "UP": self.coord_y += 1
                                elif command == "DOWN": self.coord_y -= 1
                                
                                # Kirim respon dengan koordinat terbaru
                                response = f"{self.coord_x},{self.coord_y}"
                                conn.send(response.encode())
                                
                                self.frame_stats['command_count'] += 1
                                print("📩 Perintah {} diterima. Koordinat: ({}, {})".format(
                                    command, self.coord_x, self.coord_y))
                        
                    except Exception as e:
                        conn.send(b"ERROR")
                
                conn.close()
                        
            except Exception as e:
                if "timed out" not in str(e):
                    print("⚠️ Error koneksi TCP:", str(e))
                time.sleep(0.01)

    def stop(self):
        """Menghentikan semua komponen server"""
        self.running = False
        if self.udp_sock:
            self.udp_sock.close()
        if self.tcp_sock:
            self.tcp_sock.close()
        print("🛑 Server dihentikan")

if __name__ == '__main__':
    sender = VideoStreamSender()
    try:
        sender.start()
    except Exception as e:
        print("❌ Error:", str(e))
    finally:
        sender.stop()