# usage: python3 client.py <server_ip> <conns_per_sec> <duration_s> [port]
# normal host: ~1 conn/s.  attacker: e.g. 50 conns/s
import socket, sys, time
ip, rate, dur = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
port = int(sys.argv[4]) if len(sys.argv) > 4 else 5000
ok = fail = 0; end = time.time() + dur
while time.time() < end:
    t0 = time.time()
    try:
        s = socket.create_connection((ip, port), timeout=1)
        s.sendall(b'hi'); s.recv(64); s.close(); ok += 1
    except Exception: fail += 1
    time.sleep(max(0, 1.0 / rate - (time.time() - t0)))
print('ok=%d fail=%d' % (ok, fail))
