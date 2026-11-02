# Ryu app: L2 learning switch + per-host TCP connection-rate detection + dynamic blocking
# run: ryu-manager controller.py
import time, json, logging
from collections import defaultdict, deque
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4, tcp
from ryu.lib import hub

WINDOW = 5          # sec, sliding window
MAX_CONNS = 20      # new TCP conns from one src within WINDOW => suspicious
BLOCK_TIME = 30     # sec, 0 = permanent
LOGFILE = 'events.log'

class HostBlocker(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.mac_to_port = {}
        self.dps = {}
        self.conns = defaultdict(deque)   # src_ip -> timestamps of new conns
        self.blocklist = {}               # src_ip -> unblock time
        self.f = open(LOGFILE, 'a')
        hub.spawn(self._stats_loop)
        hub.spawn(self._unblock_loop)

    def log(self, msg):
        line = '%s %s' % (time.strftime('%H:%M:%S'), msg)
        self.logger.info(line); self.f.write(line + '\n'); self.f.flush()

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features(self, ev):
        dp = ev.msg.datapath; p = dp.ofproto_parser; o = dp.ofproto
        self.dps[dp.id] = dp
        self.add_flow(dp, 0, p.OFPMatch(), [p.OFPActionOutput(o.OFPP_CONTROLLER, o.OFPCML_NO_BUFFER)])

    def add_flow(self, dp, prio, match, actions, idle=0, hard=0):
        p = dp.ofproto_parser; o = dp.ofproto
        inst = [p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, actions)] if actions else []
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=prio, match=match, instructions=inst,
                                 idle_timeout=idle, hard_timeout=hard))

    def del_flow(self, dp, match, prio):
        p = dp.ofproto_parser; o = dp.ofproto
        dp.send_msg(p.OFPFlowMod(datapath=dp, command=o.OFPFC_DELETE, out_port=o.OFPP_ANY,
                                 out_group=o.OFPG_ANY, priority=prio, match=match))

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):
        msg = ev.msg; dp = msg.datapath; o = dp.ofproto; p = dp.ofproto_parser
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth.ethertype == 0x88cc: return
        self.mac_to_port.setdefault(dp.id, {})[eth.src] = in_port
        out = self.mac_to_port[dp.id].get(eth.dst, o.OFPP_FLOOD)
        actions = [p.OFPActionOutput(out)]

        ip = pkt.get_protocol(ipv4.ipv4); t = pkt.get_protocol(tcp.tcp)
        if ip and t:
            src = ip.src
            if src in self.blocklist:
                return  # drop rule already/being installed
            # each new TCP connection = new 5-tuple = one packet-in (flow has idle timeout)
            now = time.time(); q = self.conns[src]
            q.append(now)
            while q and now - q[0] > WINDOW: q.popleft()
            if len(q) > MAX_CONNS:
                self.block(src, len(q)); return
            m = p.OFPMatch(eth_type=0x0800, ipv4_src=src, ipv4_dst=ip.dst, ip_proto=6,
                           tcp_src=t.src_port, tcp_dst=t.dst_port)
            self.add_flow(dp, 10, m, actions, idle=5)
        elif out != o.OFPP_FLOOD:
            self.add_flow(dp, 1, p.OFPMatch(in_port=in_port, eth_dst=eth.dst, eth_src=eth.src), actions, idle=30)

        data = msg.data if msg.buffer_id == o.OFP_NO_BUFFER else None
        dp.send_msg(p.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id, in_port=in_port,
                                   actions=actions, data=data))

    def block(self, src, rate):
        self.blocklist[src] = time.time() + BLOCK_TIME if BLOCK_TIME else float('inf')
        self.log('DETECTED src=%s conns=%d in %ds (thr=%d)' % (src, rate, WINDOW, MAX_CONNS))
        for dp in self.dps.values():
            p = dp.ofproto_parser
            self.add_flow(dp, 100, p.OFPMatch(eth_type=0x0800, ipv4_src=src), [])  # no actions = drop
        self.log('BLOCKED src=%s (drop rule prio 100, %ss)' % (src, BLOCK_TIME or 'permanent'))

    def _unblock_loop(self):
        while True:
            hub.sleep(1)
            now = time.time()
            for src in [s for s, t in self.blocklist.items() if t <= now]:
                del self.blocklist[src]; self.conns[src].clear()
                for dp in self.dps.values():
                    self.del_flow(dp, dp.ofproto_parser.OFPMatch(eth_type=0x0800, ipv4_src=src), 100)
                self.log('UNBLOCKED src=%s' % src)

    # flow statistics collection
    def _stats_loop(self):
        while True:
            for dp in list(self.dps.values()):
                dp.send_msg(dp.ofproto_parser.OFPFlowStatsRequest(dp))
            hub.sleep(3)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def stats_reply(self, ev):
        per = defaultdict(lambda: [0, 0, 0])
        for s in ev.msg.body:
            src = s.match.get('ipv4_src')
            if src and s.priority == 10:
                per[src][0] += 1; per[src][1] += s.packet_count; per[src][2] += s.byte_count
        for src, (n, pk, by) in per.items():
            self.logger.info('STATS src=%s active_flows=%d pkts=%d bytes=%d', src, n, pk, by)
