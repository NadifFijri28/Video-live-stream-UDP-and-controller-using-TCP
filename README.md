# Video Live Stream with UDP and Command communication with TCP

## Overview

This project implements a real-time video streaming system using UDP for video transmission and TCP for command communication. The system consists of three main components:

1. **Maixcam**: Captures video from a camera, streams it via UDP, and listens for directional commands via TCP
2. **WebServer**: Receives the video stream and provides a web interface for viewing and control
3. **Web Interface**: Displays the video stream, coordinate grid, and control buttons

## System Architecture

```
               [Maixcam(UDP)]
                    |
                    v
            [Web server (Flask Web Server)]
                    |
                    v
            [Web Browser (User Interface)]
```
# Why video transmission use UDP while command transmission use TCP

| Aspect | UDP | TCP |
|--------|----------------------|-----------------------|
| **Protocol Type** | Connectionless, unreliable | Connection-oriented, reliable |
| **Latency** | Low (10-50ms) | Higher (100-500ms) |
| **Reliability** | Best-effort delivery | Guaranteed delivery |
| **Packet Ordering** | No guaranteed order | Guaranteed in-order delivery |
| **Error Handling** | No retransmission | Automatic retransmission |
| **Flow Control** | None | Built-in congestion control |
| **Header Size** | 8 bytes | 20 bytes |
| **Connection Setup** | No handshake | 3-way handshake required |
| **Data Integrity** | Basic checksum only | Comprehensive error checking |
| **Use Case** | Real-time video streaming | Critical command delivery |
| **Packet Loss Tolerance** | High (5-20% acceptable) | Zero tolerance |
| **Bandwidth Efficiency** | High (minimal overhead) | Lower (acknowledgment overhead) |
| **Connection State** | Stateless | Stateful |
| **Multicast Support** | Native support | Limited support |

## Setup Instructions

1.**Clone repositori:**
  ```bash
   git clone https://github.com/NadifFijri28/Video-live-stream-UDP-and-controller-using-TCP.git
   cd Video-live-stream-UDP-and-controller-using-TCP
   ```

2.  **Requirement:**
   - Python 3.x
   - OpenCV (`pip install opencv-python`)
   - Flask (`pip install flask`)
   - pyQt5 (`pip install pyqt5`) **For GUI in Peer2Perr**

3. **Running the System:**
   - Start the cam first: `python Maixcam.py`
   - Then start the webserver: `python Webserver.py`
   - Access the web interface at `http://localhost:5000` if you access from same device that deploy client.py
   - Access the web interface at `http://[IP Host]:5000` if you access from other device

4. **Network Configuration:**
   - For remote devices:
     - Update server IP in WebServer.py for transmission diection via TCP in`send_direction_to_server()` Line 94
     - Update client IP in Maixcam.py for transmission video livestream via UDP in`VideoStreamSender` Line 22

## Usage Guide

1. **Video Streaming:**
   - The video feed will automatically appear in the web interface
   - Server shows local preview with 'q' key to quit

2. **Coordinate Control:**
   - Use the arrow buttons to send directional commands
   - Each press adjusts coordinates by 1 unit
   - Current position is shown on the grid and as text

3. **System Monitoring:**
   - FPS: Current frames per second
   - Total Frames: Cumulative frames received
   - Last Update: Time since last frame received

## Troubleshooting

1. **No Video Displayed:**
   - Verify camera is connected and working
   - Check server and client are using correct IPs
   - Ensure firewall allows UDP on port 9001

2. **Commands Not Working:**
   - Verify TCP connection on port 9002
   - Check server console for command logs
   - Ensure client is sending to correct server IP

3. **Performance Issues:**
   - Reduce video resolution in `_configure_camera()` in line 48 Maixcam.py
   - Adjust JPEG quality in `cv2.imencode()` in line 71 Maixcam.py
   - Increase UDP buffer size if needed

## Customization Options

1. **Video Settings:**
   - Modify resolution in `_configure_camera()`
   - Adjust JPEG quality in server's `cv2.imencode()`

2. **Grid Appearance:**
   - Change grid size in `script.js` (gridCells variable)
   - Modify colors in `drawGrid()` function

3. **UI Styling:**
   - Edit `style.css` for visual changes
   - Adjust layout in `webserver.html`

## Suggestion
  I recommend you to use peer2peer method. Apart from using fewer resources, the fps obtained during transmission is also more stable and greater than the webserver method.
  when using the webserver method, the fps obtained during the experiment ranged from 10-15. Meanwhile, with the peer2peer method, the fps obtained during the experiment ranged from 20-   27.
