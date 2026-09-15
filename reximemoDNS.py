# reximemoDNS
#
# RexiMemo adaptation of the MIT-licensed sudomemoDNS project.
# See LICENSE and NOTICE.md for attribution.

from datetime import datetime
from ipaddress import IPv4Address, ip_address
import os
from socket import AF_INET, SOCK_DGRAM, socket
from sys import platform
from time import sleep

from dnslib import A, DNSLabel, DNSRecord, QTYPE, RCODE, RR
from dnslib.server import DNSServer


REXIMEMODNS_VERSION = "1.0.0"
DEFAULT_REXIMEMO_SERVER_IP = "141.147.76.115"
DEFAULT_UPSTREAM_DNS = "8.8.8.8"

# Keep this list aligned with RexiMemo's LOCAL_DNS_HOSTS in network_services.py.
# conntest.nintendowifi.net is intentionally not intercepted.
REXIMEMO_HOSTS = (
    "nas.nintendowifi.net",
    "flipnote.hatena.com",
    "ugomemo.hatena.ne.jp",
)


def get_platform():
    platforms = {
        "linux": "Linux",
        "linux1": "Linux",
        "linux2": "Linux",
        "darwin": "macOS",
        "win32": "Windows",
    }
    return platforms.get(platform, platform)


def format_ip(address):
    """Format an IPv4 address the way Nintendo connection screens display it."""
    octets = str(address).split(".")
    return ".".join(f"{int(octet):03d}" for octet in octets)


def _ipv4_env(name, default):
    value = (os.environ.get(name) or default).strip()
    try:
        parsed = ip_address(value)
    except ValueError as exc:
        raise SystemExit(f"[ERROR] {name} must be a valid IPv4 address; got {value!r}") from exc
    if not isinstance(parsed, IPv4Address):
        raise SystemExit(f"[ERROR] {name} must be an IPv4 address; got {value!r}")
    return str(parsed)


def get_ip():
    configured = (os.environ.get("REXIMEMODNS_BIND_IP") or "").strip()
    if configured:
        return _ipv4_env("REXIMEMODNS_BIND_IP", configured)

    probe = socket(AF_INET, SOCK_DGRAM)
    try:
        # The destination does not need to be reachable. Connecting a UDP socket
        # is only used to discover which local IPv4 address the OS would route.
        probe.connect(("10.255.255.255", 1))
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


def _port_env():
    raw = (os.environ.get("REXIMEMODNS_PORT") or "53").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"[ERROR] REXIMEMODNS_PORT must be a number; got {raw!r}") from exc
    if not 1 <= value <= 65535:
        raise SystemExit("[ERROR] REXIMEMODNS_PORT must be between 1 and 65535")
    return value


MY_IP = get_ip()
REXIMEMO_SERVER_IP = _ipv4_env("REXIMEMODNS_SERVER_IP", DEFAULT_REXIMEMO_SERVER_IP)
UPSTREAM_DNS = _ipv4_env("REXIMEMODNS_UPSTREAM_DNS", DEFAULT_UPSTREAM_DNS)
DNS_PORT = _port_env()
SERIAL = int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds())


def _print_banner():
    print("+===============================+")
    print("|      RexiMemo DNS Server      |")
    print(f"|         Version {REXIMEMODNS_VERSION:<13}|")
    print("+===============================+\n")

    print("== Welcome to reximemoDNS! ==")
    print(
        "This local DNS helper routes Flipnote Studio's Nintendo/Hatena service names "
        "to RexiMemo while forwarding unrelated DNS normally.\n"
    )

    print("== How To Use ==")
    print("First, make sure that your console is connected to the same network as this computer.\n")
    print("Then, put these settings in for DNS on your console:")
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print(f"Primary DNS:   {format_ip(MY_IP)}")
    print(f"Secondary DNS: {format_ip(DEFAULT_UPSTREAM_DNS)}")
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n")

    print("== RexiMemo Routing ==")
    print(f"RexiMemo server: {REXIMEMO_SERVER_IP}")
    for hostname in REXIMEMO_HOSTS:
        print(f"  {hostname} -> {REXIMEMO_SERVER_IP}")
    print(f"Other DNS queries -> {UPSTREAM_DNS}\n")

    print("== Getting Help ==")
    print("Join the RexiMemo Discord server: https://discord.gg/K5mKWvaruF\n")


class RexiMemoDNSLogger(object):
    def log_recv(self, handler, data):
        pass

    def log_send(self, handler, data):
        pass

    def log_request(self, handler, request):
        qname = str(request.q.qname).rstrip(".")
        qtype = QTYPE.get(request.q.qtype, str(request.q.qtype))
        print(
            "[INFO] DNS request from %s: %s %s"
            % (handler.client_address[0], qtype, qname)
        )

    def log_reply(self, handler, reply):
        answer_count = len(reply.rr)
        print(
            "[INFO] DNS response to %s: %d answer%s"
            % (handler.client_address[0], answer_count, "" if answer_count == 1 else "s")
        )

    def log_error(self, handler, error):
        print("[ERROR] Invalid DNS request from %s: %s" % (handler.client_address[0], error))

    def log_truncated(self, handler, reply):
        pass

    def log_data(self, dnsobj):
        pass


class Resolver:
    def __init__(self):
        self.reximemo_names = {DNSLabel(name) for name in REXIMEMO_HOSTS}

    def _reximemo_reply(self, request):
        reply = request.reply()
        # Mirror RexiMemo's own DNS behavior: A/ANY gets the legacy-service IPv4
        # address. Other query types get an authoritative empty NOERROR response.
        if request.q.qtype in (QTYPE.A, QTYPE.ANY):
            reply.add_answer(
                RR(
                    rname=request.q.qname,
                    rtype=QTYPE.A,
                    rclass=1,
                    ttl=0,
                    rdata=A(REXIMEMO_SERVER_IP),
                )
            )
        return reply

    def _forward(self, request, handler):
        try:
            raw = request.send(
                UPSTREAM_DNS,
                53,
                tcp=(getattr(handler, "protocol", "udp") == "tcp"),
                timeout=3,
            )
            reply = DNSRecord.parse(raw)
            # Never relay a mismatched DNS transaction as if it answered this query.
            if reply.header.id != request.header.id:
                raise ValueError("upstream DNS transaction ID mismatch")
            return reply
        except Exception as exc:
            print(f"[ERROR] Upstream DNS lookup via {UPSTREAM_DNS} failed: {exc}")
            reply = request.reply()
            reply.header.rcode = RCODE.SERVFAIL
            return reply

    def resolve(self, request, handler):
        if request.q.qname in self.reximemo_names:
            return self._reximemo_reply(request)
        return self._forward(request, handler)


def main():
    _print_banner()
    print("[INFO] Starting reximemoDNS...")
    print("[INFO] Detected operating system:", get_platform())

    current_platform = get_platform()
    if current_platform in {"Linux", "macOS"}:
        print("[INFO] DNS uses UDP/TCP port 53, so this normally must run as root.")
        print("[INFO] If no requests appear, also check whether another service is already using port 53.")
    elif current_platform == "Windows":
        print("[INFO] Windows may ask you to allow reximemoDNS through the firewall.")

    resolver = Resolver()
    logger = RexiMemoDNSLogger()

    try:
        servers = [
            DNSServer(resolver=resolver, port=DNS_PORT, address=MY_IP, tcp=True, logger=logger),
            DNSServer(resolver=resolver, port=DNS_PORT, address=MY_IP, tcp=False, logger=logger),
        ]
    except PermissionError:
        print("[ERROR] Permission denied while opening DNS port. Run as Administrator/root.")
        raise SystemExit(1)
    except OSError as exc:
        print(f"[ERROR] Could not bind DNS server to {MY_IP}:{DNS_PORT}: {exc}")
        raise SystemExit(1)

    print(f"[INFO] reximemoDNS is ready on {MY_IP}:{DNS_PORT} (UDP/TCP).")
    print("[INFO] Waiting for DNS requests from your console...")

    for server in servers:
        server.start_thread()

    try:
        while True:
            sleep(0.1)
    except KeyboardInterrupt:
        print("\n[INFO] Stopping reximemoDNS...")
    finally:
        for server in servers:
            server.stop()


if __name__ == "__main__":
    main()
