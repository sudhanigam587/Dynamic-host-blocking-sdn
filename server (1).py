# threaded TCP echo server. usage: python3 server.py [port]
import socket, threading, sys
port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
def handle(c, a):
    with c:
        while (d := c.recv(1024)): c.sendall(b'ACK:' + d)
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('0.0.0.0', port)); s.listen(128)
print('listening', port)
while True:
    c, a = s.accept(); threading.Thread(target=handle, args=(c, a), daemon=True).start()
