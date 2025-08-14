"""
Aplikasi GUI untuk kontrol robot P2P dengan sinkronisasi koordinat
"""
import sys
import socket
import threading
import cv2
import numpy as np
import time
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, 
                             QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout)
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QBrush
from PyQt5.QtCore import QTimer, Qt

class VideoReceiver:
    def __init__(self, ip="0.0.0.0", port=9001):
        self.ip = ip
        self.port = port
        self.running = False
        self.sock = None
        self.frame_stats = {'last_time': time.time(), 'fps': 0, 'total_frames': 0}
        self.current_frame = None
        
    def start(self):
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        self.sock.bind((self.ip, self.port))
        threading.Thread(target=self._receive_frames, daemon=True).start()
        print(f"🚀 Penerima video UDP berjalan di {self.ip}:{self.port}")

    def _receive_frames(self):
        while self.running:
            try:
                data, _ = self.sock.recvfrom(4)
                num_chunks = int.from_bytes(data, 'big')
                
                chunks = []
                for _ in range(num_chunks):
                    chunk, _ = self.sock.recvfrom(65507)
                    chunks.append(chunk)
                
                frame_data = b''.join(chunks)
                np_frame = np.frombuffer(frame_data, dtype=np.uint8)
                frame = cv2.imdecode(np_frame, cv2.IMREAD_COLOR)
                
                if frame is not None:
                    self.frame_stats['total_frames'] += 1
                    current_time = time.time()
                    if current_time - self.frame_stats['last_time'] >= 1.0:
                        self.frame_stats['fps'] = self.frame_stats['total_frames']
                        self.frame_stats['total_frames'] = 0
                        self.frame_stats['last_time'] = current_time
                    
                    self.current_frame = frame
                    
            except Exception as e:
                print(f"⚠️ Gagal menerima frame: {str(e)}")
                time.sleep(1)

    def stop(self):
        self.running = False
        if self.sock:
            self.sock.close()

class RobotGUI(QMainWindow):
    def __init__(self, server_ip='127.0.0.1', command_port=9002):
        super().__init__()
        self.setWindowTitle("Robot P2P Control")
        self.setGeometry(100, 100, 900, 600)
        
        # Konfigurasi koneksi
        self.server_ip = server_ip
        self.command_port = command_port
        self.coords = {'x': 0, 'y': 0}
        self.coord_lock = threading.Lock()
        
        # Inisialisasi video receiver
        self.video_receiver = VideoReceiver()
        self.video_receiver.start()
        
        # Mulai thread sinkronisasi koordinat
        threading.Thread(target=self._sync_coords, daemon=True).start()
        
        # Setup UI
        self.init_ui()
        
        # Timer untuk update frame
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        
        # Panel video
        video_panel = QVBoxLayout()
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("border: 2px solid #333;")
        self.video_label.setFixedSize(640, 480)
        video_panel.addWidget(self.video_label)
        
        # Statistik
        self.stats_label = QLabel("FPS: 0 | Total Frame: 0")
        video_panel.addWidget(self.stats_label)
        
        # Panel kontrol
        control_panel = QVBoxLayout()
        
        # Tombol kontrol
        btn_grid = QGridLayout()
        self.btn_up = QPushButton("↑ ATAS")
        self.btn_left = QPushButton("← KIRI")
        self.btn_stop = QPushButton("■ STOP")
        self.btn_right = QPushButton("→ KANAN")
        self.btn_down = QPushButton("↓ BAWAH")
        
        # Style tombol
        for btn in [self.btn_up, self.btn_left, self.btn_stop, self.btn_right, self.btn_down]:
            btn.setFixedSize(100, 60)
            btn.setStyleSheet("font-size: 14px; font-weight: bold;")
        
        # Layout tombol
        btn_grid.addWidget(self.btn_up, 0, 1)
        btn_grid.addWidget(self.btn_left, 1, 0)
        btn_grid.addWidget(self.btn_stop, 1, 1)
        btn_grid.addWidget(self.btn_right, 1, 2)
        btn_grid.addWidget(self.btn_down, 2, 1)
        
        # Koneksi tombol
        self.btn_up.clicked.connect(lambda: self.send_command('ATAS'))
        self.btn_left.clicked.connect(lambda: self.send_command('KIRI'))
        self.btn_stop.clicked.connect(lambda: self.send_command('BERHENTI'))
        self.btn_right.clicked.connect(lambda: self.send_command('KANAN'))
        self.btn_down.clicked.connect(lambda: self.send_command('BAWAH'))
        control_panel.addLayout(btn_grid)
        
        # Diagram koordinat
        self.diagram_label = QLabel()
        self.diagram_label.setFixedSize(220, 220)
        control_panel.addWidget(self.diagram_label)
        
        # Label koordinat
        self.coords_label = QLabel("Koordinat: (0, 0)")
        self.coords_label.setAlignment(Qt.AlignCenter)
        control_panel.addWidget(self.coords_label)
        
        # Gabungkan panel
        main_layout.addLayout(video_panel, 70)
        main_layout.addLayout(control_panel, 30)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def update_frame(self):
        if self.video_receiver.current_frame is not None:
            frame = self.video_receiver.current_frame
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.video_label.setPixmap(QPixmap.fromImage(qt_image).scaled(
                self.video_label.width(), 
                self.video_label.height(),
                Qt.KeepAspectRatio
            ))
            
            self.stats_label.setText(
                f"FPS: {self.video_receiver.frame_stats['fps']} | "
                f"Total Frame: {self.video_receiver.frame_stats['total_frames']}"
            )
        
        # Update diagram koordinat
        self.update_diagram()

    def update_diagram(self):
        pixmap = QPixmap(220, 220)
        pixmap.fill(Qt.white)
        painter = QPainter(pixmap)
        
        # Gambar grid
        painter.setPen(QPen(Qt.gray, 1, Qt.DashLine))
        for i in range(0, 220, 44):
            painter.drawLine(0, i, 220, i)
            painter.drawLine(i, 0, i, 220)
        
        # Gambar sumbu
        painter.setPen(QPen(Qt.blue, 2))
        painter.drawLine(110, 0, 110, 220)  # Sumbu Y
        painter.drawLine(0, 110, 220, 110)  # Sumbu X
        
        # Gambar titik koordinat
        with self.coord_lock:
            x, y = self.coords['x'], self.coords['y']
        
        # Normalisasi koordinat (-50,50) ke (0,220)
        px = int(110 + x * 2.2)
        py = int(110 - y * 2.2)
        
        painter.setPen(QPen(Qt.red, 0))
        painter.setBrush(QBrush(Qt.red))
        painter.drawEllipse(px-5, py-5, 10, 10)
        
        painter.end()
        self.diagram_label.setPixmap(pixmap)
        self.coords_label.setText(f"Koordinat: ({x}, {y})")

    def _sync_coords(self):
        """Sinkronisasi koordinat dengan server secara berkala"""
        while self.video_receiver.running:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2.0)
                    s.connect((self.server_ip, self.command_port))
                    s.sendall(json.dumps({'sync': True}).encode())
                    data = s.recv(1024)
                    if data:
                        response = json.loads(data.decode())
                        if response.get('status') == 'ok' and response.get('type') == 'sync_response':
                            with self.coord_lock:
                                self.coords = {'x': response['x'], 'y': response['y']}
            except Exception as e:
                print(f"⚠️ Gagal sinkronisasi koordinat: {str(e)}")
            
            time.sleep(10)  # Sinkron setiap 10 detik

    def send_command(self, direction):
        """Kirim perintah gerakan ke server"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                s.connect((self.server_ip, self.command_port))
                s.sendall(json.dumps({'direction': direction}).encode())
                
                data = s.recv(1024)
                if data:
                    response = json.loads(data.decode())
                    if response.get('status') == 'ok' and response.get('type') == 'move_response':
                        with self.coord_lock:
                            self.coords = {'x': response['x'], 'y': response['y']}
        except Exception as e:
            print(f"⚠️ Gagal mengirim perintah: {str(e)}")

    def closeEvent(self, event):
        self.video_receiver.stop()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = RobotGUI()
    gui.show()
    sys.exit(app.exec_())