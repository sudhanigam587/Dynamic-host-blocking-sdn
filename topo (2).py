# sudo python3 topo.py   (start ryu first)
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.topo import Topo
from mininet.cli import CLI

class T(Topo):
    def build(self):
        s1 = self.addSwitch('s1', protocols='OpenFlow13')
        for i in range(1, 5):   # h1,h2 normal clients; h3 attacker; h4 server
            self.addHost('h%d' % i, ip='10.0.0.%d/24' % i)
            self.addLink('h%d' % i, s1)

if __name__ == '__main__':
    net = Mininet(topo=T(), controller=lambda n: RemoteController(n, ip='127.0.0.1', port=6633),
                  switch=OVSSwitch, autoSetMacs=True)
    net.start(); CLI(net); net.stop()
