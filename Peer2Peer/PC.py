"""
Aplikasi GUI untuk menerima video dan kontrol robot P2P
- Menerima video dari Maixcam.py via UDP
- Mengirim perintah arah ke Maixcam.py via TCP (JSON)
- Menampilkan statistik dan koordinat
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
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QTimer, Qt

class VideoReceiver:
    def __init__(self, ip="0.0.0.0", port=9001):
        # IP dan port UDP untuk menerima video dari Maixcam.py
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
                print(f"\n⚠️ Gagal menerima frame: {str(e)}")
                time.sleep(1)

    def stop(self):
        self.running = False
        if self.sock:
            self.sock.close()

class RobotGUI(QMainWindow):
    def __init__(self, server_ip='127.0.0.1', command_port=9002):
        super().__init__()
        self.setWindowTitle("Robot P2P Control & Video Stream")
        self.setGeometry(100, 100, 1000, 650)
        self.setStyleSheet("background-color: #f5f5f5;")
        
        # Konfigurasi IP/port Maixcam.py
        self.server_ip = server_ip
        self.command_port = command_port

        # Inisialisasi video receiver
        self.video_receiver = VideoReceiver()
        self.video_receiver.start()

        # Variabel koordinat
        self.coords = {'x': 0, 'y': 0}

        # Setup UI
        self.init_ui()

        # Timer untuk update frame
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)  # ~30 FPS
        
    def init_ui(self):
        # Widget utama
        main_widget = QWidget()
        grid = QGridLayout()

        # Judul aplikasi di atas tengah
        title_label = QLabel("Robot P2P Control & Video Stream")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #222; margin-bottom: 10px;")
        grid.addWidget(title_label, 0, 0, 1, 2)

        # Video di kiri atas
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("border: 3px solid #1976d2; background: #222;")
        self.video_label.setFixedSize(640, 480)
        grid.addWidget(self.video_label, 1, 0, 2, 1)

        # Statistik di bawah video
        self.stats_label = QLabel("FPS: 0 | Total Frame: 0")
        self.stats_label.setAlignment(Qt.AlignLeft)
        self.stats_label.setStyleSheet("font-size: 16px; color: #1976d2; margin-top: 8px; margin-left: 10px;")
        grid.addWidget(self.stats_label, 3, 0, 1, 1)

        # Kontrol arah di kanan atas
        btn_grid = QGridLayout()
        self.btn_up = QPushButton("↑ ATAS")
        self.btn_left = QPushButton("← KIRI")
        self.btn_stop = QPushButton("■ STOP")
        self.btn_right = QPushButton("→ KANAN")
        self.btn_down = QPushButton("↓ BAWAH")
        for btn in [self.btn_up, self.btn_left, self.btn_stop, self.btn_right, self.btn_down]:
            btn.setFixedSize(120, 60)
            btn.setStyleSheet("font-size: 18px; font-weight: bold; background: #1976d2; color: #fff; border-radius: 8px;")
        btn_grid.addWidget(self.btn_up, 0, 1)
        btn_grid.addWidget(self.btn_left, 1, 0)
        btn_grid.addWidget(self.btn_stop, 1, 1)
        btn_grid.addWidget(self.btn_right, 1, 2)
        btn_grid.addWidget(self.btn_down, 2, 1)
        self.btn_up.clicked.connect(lambda: self.send_command('UP'))
        self.btn_left.clicked.connect(lambda: self.send_command('LEFT'))
        self.btn_stop.clicked.connect(lambda: self.send_command('STOP'))
        self.btn_right.clicked.connect(lambda: self.send_command('RIGHT'))
        self.btn_down.clicked.connect(lambda: self.send_command('DOWN'))
        control_widget = QWidget()
        control_widget.setLayout(btn_grid)
        grid.addWidget(control_widget, 1, 1, 1, 1)

        # Diagram kartesian di kanan bawah kontrol
        self.diagram_label = QLabel()
        self.diagram_label.setFixedSize(220, 220)
        self.diagram_label.setAlignment(Qt.AlignCenter)
        self.diagram_label.setStyleSheet("border: 2px solid #1976d2; background: #fff; margin-top: 18px;")
        grid.addWidget(self.diagram_label, 2, 1, 1, 1)

        # Koordinat di bawah diagram
        self.coords_label = QLabel("Koordinat: (0, 0)")
        self.coords_label.setAlignment(Qt.AlignCenter)
        self.coords_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #1976d2; margin-top: 10px;")
        grid.addWidget(self.coords_label, 3, 1, 1, 1)

        main_widget.setLayout(grid)
        self.setCentralWidget(main_widget)
    
    def update_frame(self):
        if self.video_receiver.current_frame is not None:
            frame = self.video_receiver.current_frame
            # Konversi frame OpenCV ke QImage
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)

            # Tampilkan di QLabel dengan ukuran tetap
            pixmap = QPixmap.fromImage(qt_image)
            pixmap = pixmap.scaled(640, 480, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.video_label.setPixmap(pixmap)

            # Update statistik
            self.stats_label.setText(
                f"FPS: {self.video_receiver.frame_stats['fps']} | "
                f"Total Frame: {self.video_receiver.frame_stats['total_frames']}"
            )

        # Update diagram koordinat
        self.update_diagram()

    def update_diagram(self):
        # Gambar diagram koordinat mirip webserver.html
        from PyQt5.QtGui import QPainter, QPen, QColor, QBrush
        import math
        pixmap = QPixmap(220, 220)
        pixmap.fill(QColor('#fff'))
        painter = QPainter(pixmap)
        pen_axis = QPen(QColor('#1976d2'), 3)
        pen_grid = QPen(QColor('#bbb'), 1, Qt.DashLine)
        pen_point = QPen(QColor('#d32f2f'), 0)
        brush_point = QBrush(QColor('#d32f2f'))

        # Draw grid
        painter.setPen(pen_grid)
        for i in range(1, 5):
            painter.drawLine(0, i*44, 220, i*44)
            painter.drawLine(i*44, 0, i*44, 220)

        # Draw axis
        painter.setPen(pen_axis)
        painter.drawLine(110, 0, 110, 220)
        painter.drawLine(0, 110, 220, 110)

        # Draw point (robot position)
        x = self.coords.get('x', 0)
        y = self.coords.get('y', 0)
        # Map x,y (-100..100) to diagram (0..220)
        px = int(110 + x)
        py = int(110 - y)
        painter.setPen(pen_point)
        painter.setBrush(brush_point)
        painter.drawEllipse(px-7, py-7, 14, 14)

        painter.end()
        self.diagram_label.setPixmap(pixmap)
    
    def send_command(self, direction):
        """
        Kirim perintah arah ke Maixcam.py via TCP (JSON)
        dan update koordinat dari respons
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                s.connect((self.server_ip, self.command_port))
                command = json.dumps({'direction': direction})
                s.sendall(command.encode())
                response = s.recv(1024)
                if response:
                    data = json.loads(response.decode())
                    if data.get('status') == 'ok' and 'x' in data and 'y' in data:
                        self.coords = {'x': data['x'], 'y': data['y']}
                        self.coords_label.setText(f"Koordinat: ({self.coords['x']}, {self.coords['y']})")
                    else:
                        print(f"⚠️ Respons tidak valid: {data}")
                else:
                    print("⚠️ Tidak ada respons dari Maixcam.py")
        except Exception as e:
            print(f"⚠️ Gagal mengirim perintah: {e}")
    
    def closeEvent(self, event):
        self.video_receiver.stop()
        event.accept()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="GUI Robot P2P")
    parser.add_argument('--server_ip', type=str, default='127.0.0.1', help='IP Maixcam.py')
    parser.add_argument('--command_port', type=int, default=9002, help='Port TCP Maixcam.py')
    args = parser.parse_args()

    app = QApplication(sys.argv)
    gui = RobotGUI(server_ip=args.server_ip, command_port=args.command_port)
    gui.show()
    sys.exit(app.exec_())