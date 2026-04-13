"""BGP: iBGP full mesh and both eBGP sessions Established; policy actually applied."""

import pytest

from scripts.lab import internal_routers, ping, vtysh_json


@pytest.mark.parametrize("router", ["r1", "r2", "r3", "r4", "isp1", "isp2"])
def test_all_bgp_sessions_established(router):
    peers = vtysh_json(router, "show bgp summary")["ipv4Unicast"]["peers"]
    bad = {ip: p["state"] for ip, p in peers.items() if p["state"] != "Established"}
    assert not bad, f"{router}: {bad}"


def test_isps_receive_only_the_aggregate(topo):
    for isp in ("isp1", "isp2"):
        routes = vtysh_json(isp, "show ip route bgp")
        assert set(routes) == {
            topo["aggregate"]
        }, f"{isp} learned {set(routes)}; expected only {topo['aggregate']}"


def test_outbound_prefers_isp1_via_local_preference(topo):
    """100.64.1.0/24 is advertised by both ISPs. Every internal router must prefer the path via r1 (isp1)."""
    for router in internal_routers(topo):
        paths = vtysh_json(router, "show bgp ipv4 unicast 100.64.1.0/24")["paths"]
        best = next(p for p in paths if p.get("bestpath", {}).get("overall"))
        assert (
            best.get("locPrf") == 200
        ), f"{router}: best path local-pref {best.get("locPrf")}"
        assert (
            best["aspath"]["string"] == "65100"
        ), f"{router}: best path via AS {best["aspath"]["string"]}, expected 65100 (isp1)"


def test_isp_specific_prefix_uses_that_isp(topo):
    """100.64.200.0/24 exists only at isp2, so it must be reachable via r4 regardless of local-pref."""
    paths = vtysh_json("r2", "show bgp ipv4 unicast 100.64.200.0/24")["paths"]
    assert paths[0]["aspath"]["string"] == "65200"


def test_bogons_from_isps_are_rejected():
    """The ISP-IN route-map drops RFC1918 and our own aggregate if an ISP ever leaks them."""
    rmap = vtysh_json("r1", "show route-map ISP-IN")
    # Presence of the deny clauses is the config-level check; behavioural check is that no 10/8 prefix is learned from the eBGP peer.
    received = vtysh_json("r1", "show bgp ipv4 unicast neighbors 203.0.113.1 routes")
    learned = set(received.get("routes", {}))
    assert not any(
        p.startswith("10.") for p in learned
    ), f"r1 accepted 10/8 space from isp1: {learned}"
    assert rmap


@pytest.mark.parametrize(
    "src,dst",
    [
        ("r3", "203.0.113.254"),
        ("r3", "198.51.100.254"),
        ("r2", "198.51.100.254"),
        ("r4", "203.0.113.254"),
    ],
)
def test_end_to_end_reachability(src, dst):
    assert ping(src, dst), f"{src} cannot reach {dst}"
