"""
Server penyiaran video UDP dan penerima perintah TCP dengan sinkronisasi koordinat untuk MaixCam
"""
import socket
import time
import _thread as threading
import json
import gc
from maix import camera, display, image
import struct

class VideoStreamSender:
    def __init__(self, server_ip="192.168.31", video_port=9001, command_port=9002): #Ganti IP sesuai PC
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
            'command_count': 0,
            'camera_errors': 0
        }
        
        # Inisialisasi kamera dan display
        try:
            # Gunakan resolusi yang lebih rendah untuk FPS lebih tinggi
            self.cam = camera.Camera(240, 180)  # Mengurangi resolusi dari 320x240
            self.disp = display.Display()
            print("✅ Kamera dan display berhasil diinisialisasi")
        except Exception as e:
            print("❌ Gagal inisialisasi kamera/display:", str(e))
            self.cam = None
            self.disp = None
        
        # Pengaturan kompresi gambar - dikurangi untuk performa lebih baik
        self.jpeg_quality = 40  # Mengurangi kualitas untuk FPS lebih tinggi
        self.max_packet_size = 1200  # Ukuran paket mendekati MTU
        self.target_fps = 30  # Target FPS yang lebih tinggi

    def start(self):
        """Memulai semua komponen server"""
        if self.cam is None:
            print("❌ Tidak dapat memulai: Kamera tidak tersedia")
            return
            
        self.running = True
        
        # Setup UDP untuk streaming video
        try:
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            print("✅ Socket UDP berhasil dibuat")
        except Exception as e:
            print("❌ Gagal membuat socket UDP:", str(e))
            return
        
        # Setup TCP untuk command server
        try:
            self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.tcp_sock.bind(("0.0.0.0", self.command_port))
            self.tcp_sock.listen(1)
            self.tcp_sock.settimeout(0.1)  # Timeout lebih pendek
            print("✅ Socket TCP berhasil dibuat")
        except Exception as e:
            print("❌ Gagal membuat socket TCP:", str(e))
            self.udp_sock.close()
            return
        
        # Mulai thread untuk TCP command server
        threading.start_new_thread(self._tcp_command_listener, ())
        
        print("📡 Streaming video UDP ke {}:{}".format(self.server_ip, self.video_port))
        print("🔄 Server perintah TCP di port", self.command_port)
        print("⚙️  Kualitas JPEG: {}, Max Packet Size: {}".format(self.jpeg_quality, self.max_packet_size))
        print("🎯 Target FPS: {}".format(self.target_fps))
        
        # Mulai loop utama untuk streaming video
        self._capture_and_send()

    def _generate_test_pattern(self, width=240, height=180):
        """Generate test pattern jika kamera error"""
        img = image.Image(width, height, image.RGB)
        img.draw_rectangle(0, 0, width, height, color=(0, 0, 0), thickness=-1)
        
        # Draw test pattern
        img.draw_string(30, height//2 - 15, "TEST PATTERN", 
                       scale=0.7, color=(255, 255, 255), thickness=1)
        img.draw_string(20, height//2 + 15, "Camera not available", 
                       scale=0.6, color=(255, 255, 255), thickness=1)
        
        return img

    def _capture_and_send(self):
        """Loop pengambilan dan pengiriman frame video"""
        frame_id = 0
        frame_interval = 1.0 / self.target_fps
        
        while self.running:
            try:
                start_time = time.time()
                
                # Ambil frame dari kamera atau generate test pattern
                if self.cam:
                    img = self.cam.read()
                    if not img:
                        self.frame_stats['camera_errors'] += 1
                        if self.frame_stats['camera_errors'] % 20 == 0:
                            print("⚠️ Gagal membaca frame dari kamera (error #{})".format(
                                self.frame_stats['camera_errors']))
                        img = self._generate_test_pattern()
                else:
                    img = self._generate_test_pattern()
                
                # Reset error counter jika berhasil
                if self.cam and img:
                    self.frame_stats['camera_errors'] = 0
                
                # Tambahkan overlay koordinat pada frame (opsional, bisa di-disable)
                try:
                    # Hanya update overlay setiap beberapa frame untuk menghemat waktu
                    if self.frame_stats['total_frames'] % 5 == 0:
                        with self.coord_lock:
                            img.draw_string(5, 5, "X:{} Y:{}".format(self.coord_x, self.coord_y), 
                                           scale=0.6, color=(0, 255, 0), thickness=1)
                except:
                    pass  # Skip jika gagal draw
                
                # Tampilkan preview di display MaixCam (opsional, bisa di-disable)
                if self.disp and self.frame_stats['total_frames'] % 3 == 0:
                    try:
                        self.disp.show(img)
                    except:
                        pass
                
                # Encode frame ke JPEG
                try:
                    img_bytes = img.to_jpeg(quality=self.jpeg_quality)
                    if hasattr(img_bytes, "to_bytes"):
                        img_bytes = img_bytes.to_bytes()
                except Exception as e:
                    print("⚠️ Gagal encode JPEG:", str(e))
                    time.sleep(0.05)
                    continue
                
                # Update statistik frame
                with self.coord_lock:
                    self.frame_stats['total_frames'] += 1
                    current_time = time.time()
                    elapsed = current_time - self.frame_stats['last_time']
                    
                    if elapsed >= 1.0:  # Update setiap 1 detik untuk statistik lebih akurat
                        self.frame_stats['fps'] = self.frame_stats['total_frames'] / elapsed
                        self.frame_stats['total_frames'] = 0
                        self.frame_stats['last_time'] = current_time
                        status = "LIVE" if self.cam and self.frame_stats['camera_errors'] == 0 else "TEST"
                        print("FPS: {:.1f}, Status: {}, Frame: {} bytes".format(
                            self.frame_stats['fps'], status, len(img_bytes)))

                # Kirim frame dalam chunks
                chunk_size = self.max_packet_size
                chunks = []
                for i in range(0, len(img_bytes), chunk_size):
                    chunks.append(img_bytes[i:i+chunk_size])
                
                try:
                    # Kirim metadata (frame_id, jumlah chunks)
                    metadata = struct.pack('>II', frame_id, len(chunks))
                    self.udp_sock.sendto(metadata, (self.server_ip, self.video_port))
                    
                    # Kirim setiap chunk dengan header
                    for i, chunk in enumerate(chunks):
                        header = struct.pack('>IH', frame_id, i)
                        self.udp_sock.sendto(header + chunk, (self.server_ip, self.video_port))
                        
                except Exception as e:
                    print("⚠️ Gagal mengirim video:", str(e))
                
                frame_id = (frame_id + 1) % 10000
                
                # Kontrol frame rate yang lebih presisi
                processing_time = time.time() - start_time
                sleep_time = max(0, frame_interval - processing_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
                # Bersihkan memori secara periodik
                if frame_id % 30 == 0:
                    gc.collect()

            except Exception as e:
                print("⚠️ Error pengambilan frame:", str(e))
                time.sleep(0.05)

    def _tcp_command_listener(self):
        """Server TCP untuk menerima perintah kontrol"""
        print("🖥️ Server perintah TCP siap di port", self.command_port)
        
        while self.running:
            try:
                conn, addr = self.tcp_sock.accept()
                conn.settimeout(0.1)  # Timeout lebih pendek untuk koneksi
                print("📩 Koneksi dari:", addr)
                
                data = conn.recv(64)  # Buffer lebih kecil untuk perintah sederhana
                if data:
                    try:
                        command_str = data.decode().strip()
                        
                        # Handle perintah sederhana dengan respon cepat
                        with self.coord_lock:
                            if command_str == "RIGHT": 
                                self.coord_x += 1
                                response = "{},{}".format(self.coord_x, self.coord_y)
                            elif command_str == "LEFT": 
                                self.coord_x -= 1
                                response = "{},{}".format(self.coord_x, self.coord_y)
                            elif command_str == "UP": 
                                self.coord_y += 1
                                response = "{},{}".format(self.coord_x, self.coord_y)
                            elif command_str == "DOWN": 
                                self.coord_y -= 1
                                response = "{},{}".format(self.coord_x, self.coord_y)
                            else:
                                response = "ERROR"
                            
                            conn.send(response.encode())
                            
                            self.frame_stats['command_count'] += 1
                            if response != "ERROR":
                                print("📩 Perintah {} diterima. Koordinat: ({}, {})".format(
                                    command_str, self.coord_x, self.coord_y))
                        
                    except Exception as e:
                        print("⚠️ Error parsing perintah:", str(e))
                        try:
                            conn.send(b"ERROR")
                        except:
                            pass
                
                conn.close()
                        
            except socket.timeout:
                continue
            except Exception as e:
                if "timed out" not in str(e) and "accept" not in str(e):
                    print("⚠️ Error koneksi TCP:", str(e))
                time.sleep(0.05)

    def stop(self):
        """Menghentikan semua komponen server"""
        self.running = False
        if self.udp_sock:
            self.udp_sock.close()
        if self.tcp_sock:
            self.tcp_sock.close()
        print("🛑 Server dihentikan")

# Main execution
if __name__ == '__main__':
    sender = VideoStreamSender()
    
    try:
        print("🚀 Starting MaixCam Video Stream Server...")
        sender.start()
    except KeyboardInterrupt:
        print("\n🛑 Received interrupt, shutting down...")
    except Exception as e:
        print("❌ Unexpected error:", str(e))
    finally:
        sender.stop()