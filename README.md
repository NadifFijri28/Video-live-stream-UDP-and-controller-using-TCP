# Video Live Stream with UDP and Command communication with TCP

## Overview

This project implements a real-time video streaming system using UDP for video transmission and TCP for command communication. The system consists of three main components:

1. **Server**: Captures video from a camera, streams it via UDP, and listens for directional commands via TCP
2. **Client**: Receives the video stream and provides a web interface for viewing and control
3. **Web Interface**: Displays the video stream, coordinate grid, and control buttons

## System Architecture

```
[Camera] --> [Server (UDP Streaming + TCP Command Listener)]
                    |
                    v
            [Client (Flask Web Server)]
                    |
                    v
            [Web Browser (User Interface)]
```

## Setup Instructions

1. **Prerequisites:**
   - Python 3.x
   - OpenCV (`pip install opencv-python`)
   - Flask (`pip install flask`)

2. **Running the System:**
   - Start the server first: `python server.py`
   - Then start the client: `python client.py`
   - Access the web interface at `http://localhost:5000` if you access from same device that deploy client.py
   - Access the web interface at `http://[IP Host] :5000` if you access from other device

3. **Network Configuration:**
   - For remote devices:
     - Update server IP in client's for transmission diection via TCP in`send_direction_to_server()` Line 94
     - Update client IP in server's for transmission video livestream via UDP in`VideoStreamSender` Line 22

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
   - Reduce video resolution in `_configure_camera()` in line 48 server.py
   - Adjust JPEG quality in `cv2.imencode()` in line 71 server.py
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
