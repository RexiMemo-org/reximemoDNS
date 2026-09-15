# reximemoDNS

A small local DNS helper for connecting Flipnote Studio to **RexiMemo** when a network or ISP does not reliably allow the console to use RexiMemo's public DNS directly.

It runs on a computer on the same local network as the Nintendo DSi. Flipnote Studio's Nintendo/Hatena hostnames are redirected to RexiMemo, while unrelated DNS lookups are forwarded to a normal upstream resolver.

## Default RexiMemo routing

reximemoDNS redirects these hostnames to RexiMemo's legacy service address:

- `nas.nintendowifi.net`
- `flipnote.hatena.com`
- `ugomemo.hatena.ne.jp`

The default RexiMemo server IP is **141.147.76.115**. All other DNS queries are forwarded to **8.8.8.8** by default.

`conntest.nintendowifi.net` is deliberately not intercepted, matching RexiMemo's server-side DNS configuration.

## Running on Windows:

Run the .exe provided in this release. You may have to click past a warning from Windows SmartScreen (as it sometimes turns its nose up at applications bundled by PyInstaller) or your firewall (as it needs to listen for DNS requests).

## Setup:

1. Put the computer running reximemoDNS and the DSi on the same local network.
2. Run reximemoDNS as Administrator/root because DNS uses port 53.
3. Enter the **Primary DNS** address printed by the program into the DSi connection settings.
4. Use `008.008.008.008` as Secondary DNS.
5. Save the connection and open Flipnote Studio → Flipnote Hatena.

## Running from command line:

### Install requirements

```bash
python -m pip install -r requirements.txt
```

### Run

```bash
sudo python3 reximemoDNS.py
```

When it starts, it prints the LAN address to enter on the DSi.

## Configuration

The defaults are already set for the current RexiMemo server, but they can be changed with environment variables:

- `REXIMEMODNS_SERVER_IP` — RexiMemo legacy-service IPv4 address. Default: `141.147.76.115`
- `REXIMEMODNS_UPSTREAM_DNS` — resolver used for all non-RexiMemo names. Default: `8.8.8.8`
- `REXIMEMODNS_BIND_IP` — local interface/address on which to listen. By default, reximemoDNS detects the computer's LAN IPv4 address.
- `REXIMEMODNS_PORT` — DNS listening port. Default: `53`

Example:

```bash
REXIMEMODNS_SERVER_IP=141.147.76.115 REXIMEMODNS_UPSTREAM_DNS=1.1.1.1 sudo python3 reximemoDNS.py
```

On Windows PowerShell:

```powershell
$env:REXIMEMODNS_SERVER_IP="141.147.76.115"
$env:REXIMEMODNS_UPSTREAM_DNS="1.1.1.1"
python reximemoDNS.py
```

## Troubleshooting

If the program cannot bind to port 53, run it as Administrator/root and make sure another DNS server is not already using that port.

If no console requests appear in the log, check the computer firewall and confirm the DSi's Primary DNS exactly matches the address printed by reximemoDNS.

If ordinary websites or the DSi connection test stop resolving while reximemoDNS is running, verify that `REXIMEMODNS_UPSTREAM_DNS` points to a reachable DNS resolver.

For RexiMemo support, join the Discord server: **https://discord.gg/K5mKWvaruF**

## Building a Windows executable

Install Nuitka and its build dependencies:

```powershell
python -m pip install -r requirements.txt nuitka zstandard
```

Then build:

```powershell
python -m nuitka --standalone --onefile -o reximemoDNS.exe reximemoDNS.py
```

No RexiMemo-specific icon is bundled in this source tree, so the executable uses the default application icon unless you supply one when building.

## License and attribution

reximemoDNS is derived from the open-source `sudomemoDNS` project by Austin Burk / Team Sudomemo. The original MIT copyright and license are preserved in `LICENSE`.

See `NOTICE.md` for attribution and RexiMemo-specific changes.
