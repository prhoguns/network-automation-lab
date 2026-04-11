"""OSPF: every internal router must be FULL with every directly connected internal neighbour, and the
expensive diagonal must not be used for r1<->r4 traffic."""

import pytest

from scripts.lab import internal_routers, vtysh_json


def expected_neighbours(topo, router):
    out = set()
    for link in topo["links"]:
        if not link["name"].startswith("l"):
            continue
        ends = {link["a"][0], link["b"][0]}
        if router in ends:
            out |= ends - {router}
    return out


@pytest.mark.parametrize("router", ["r1", "r2", "r3", "r4"])
def test_ospf_adjacencies_full(topo, router):
    data = vtysh_json(router, "show ip ospf neighbor")
    got = {}
    for rid, entries in data["neighbors"].items():
        got[rid] = entries[0].get("nbrState") or entries[0].get("converged")
    want_ids = {
        topo["routers"][n]["loopback"] for n in expected_neighbours(topo, router)
    }
    assert set(got) == want_ids, f"{router}: neighbours {set(got)} != {want_ids}"
    for rid, state in got.items():
        assert str(state).startswith("Full"), f"{router}: neighbour {rid} is {state}"


def test_all_loopbacks_in_every_rib(topo):
    for router in internal_routers(topo):
        rib = vtysh_json(router, "show ip route ospf")
        for other in internal_routers(topo):
            if other == router:
                continue
            prefix = topo["routers"][other]["loopback"] + "/32"
            assert prefix in rib, f"{router} has no OSPF route to {other} ({prefix})"


def test_r1_to_r4_avoids_the_cost_50_diagonal(topo):
    """r1-r4 direct link costs 50; two hops via r2 or r3 cost 20. Traffic must take the 20."""
    route = vtysh_json("r1", "show ip route 10.0.255.4/32")["10.0.255.4/32"][0]
    assert route["metric"] == 20
    next_hops = {nh["ip"] for nh in route["nexthops"]}
    assert next_hops <= {"10.0.12.2", "10.0.13.2"}, f"r1 uses diagonal: {next_hops}"
    assert "10.0.14.2" not in next_hops
