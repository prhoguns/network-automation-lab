# Network Automation Lab

A six-router service-provider-style topology running real routing daemons (FRRouting) in Docker:
OSPF backbone, iBGP full mesh, dual-homed eBGP to two upstream ISPs with routing policy — all
generated from one YAML source of truth, and verified by an automated test suite that CI runs on
every push by actually booting the network.

```
          isp1 (AS 65100)                 isp2 (AS 65200)
            |  203.0.113.0/29               |  198.51.100.0/29
          [r1] ---------- 10.0.12.0/29 ---- [r2]
           |  \  cost 50                     |
   10.0.13.0/29  \ 10.0.14.0/29       10.0.24.0/29
           |        \                        |
          [r3] ---------- 10.0.34.0/29 ---- [r4]

   r1–r4: AS 65000 · OSPF area 0 · iBGP full mesh on loopbacks · next-hop-self
   r1 ⇄ isp1, r4 ⇄ isp2: eBGP · isp1 preferred outbound (local-preference 200)
```

**Stack:** FRRouting 10.1 (OSPFv2, BGP-4) · Docker Compose · Python (PyYAML, Jinja2) · pytest

## What is automated

| Layer | Where | What |
|---|---|---|
| Source of truth | [`inventory/topology.yml`](inventory/topology.yml) | Routers, links, addressing, OSPF costs, ASNs, peers, policy knobs |
| Config generation | [`templates/frr.conf.j2`](templates/frr.conf.j2) + [`scripts/render.py`](scripts/render.py) | One template renders every router (edge, core, ISP roles); also renders `docker-compose.yml` with one bridge network per link |
| Boot-time fix-up | [`scripts/entrypoint.sh`](scripts/entrypoint.sh) | Docker does not guarantee `ethN` order, so OSPF costs are declared per IP and mapped to the interface at boot |
| Verification | [`tests/`](tests/) | 22 checks against the live lab via `vtysh … json` — see below |
| Drift check | `tests/test_render.py` | Committed configs must equal a fresh render; every config must pass `vtysh --dry-run` |

## Routing policy implemented

- **Outbound:** only the `10.0.0.0/16` aggregate leaves the AS (`aggregate-address … summary-only` + `ISP-OUT` route-map). The ISPs' tests assert they learn exactly one prefix.
- **Inbound:** `ISP-IN` drops bogons (RFC 1918, loopback, link-local, multicast) and our own aggregate if an upstream leaks it back; then sets local-preference 200 via isp1, 100 via isp2.
- **Result:** every internal router prefers isp1 for prefixes both ISPs announce, but a prefix only isp2 has (`100.64.200.0/24`) still routes via r4.
- **IGP:** the r1–r4 diagonal is cost 50 so r1→r4 traffic takes the two cost-10 hops via r2 or r3 (ECMP). A test asserts the diagonal is never a next hop.

## Verification suite

```
tests/test_ospf.py      4 adjacency checks (every neighbour FULL) · all loopbacks in every RIB · diagonal avoided
tests/test_bgp.py       6 routers all sessions Established · ISPs see only the aggregate · local-pref honoured ·
                        isp2-only prefix via isp2 · bogon filter · 4 end-to-end pings across the AS boundary
tests/test_render.py    configs match inventory · every config parses (vtysh --dry-run)
```

## Run it

```bash
git clone https://github.com/prhoguns/network-automation-lab.git && cd network-automation-lab
pip install -r requirements.txt
python scripts/render.py          # inventory → configs/ + docker-compose.yml
docker compose up -d              # six FRR routers, ~10 s
sleep 60                          # OSPF + BGP convergence
pytest -v                         # 22 tests against the live network
docker exec -it r1 vtysh          # poke around: show ip ospf neighbor / show bgp summary / show ip route
```

Change something in `inventory/topology.yml` (add a router, flip `preferred_isp: isp2`, change a cost),
re-render, `docker compose up -d`, re-run the tests. The `preferred_isp` test will tell you whether the
policy did what you meant.

## Things learned the hard way (all fixed, all in git history)

- Docker reserves an address in every bridge subnet for the host; `/30` links collide with router addresses. Use `/29` and pin the gateway to the last usable address.
- `neighbor X update-source lo` picks the *first* address on `lo`, which is 127.0.0.1 inside a container — iBGP sat in *Active* forever. Source from the loopback IP, not the interface.
- An entrypoint with `set -e` and a `[ -n "$x" ] && …` short-circuit exits non-zero when the test is false, and four routers died silently. Explicit `if` blocks.
- FRR's default BGP connect-retry is 120 s, which makes a lab feel broken. `timers connect 10` for every neighbour.
- Interface names are not stable across container boots, so per-interface OSPF cost has to be resolved from the IP at start-up.

## Next

- Add a route reflector and drop the full mesh; test that r2/r3 still learn external prefixes.
- IPv6 dual-stack from the same inventory.
- Replace `docker exec vtysh` with NAPALM/Netmiko over SSH so the same tests run against real Cisco/Juniper boxes.
- BGP communities from the ISPs and a `no-export` policy.
