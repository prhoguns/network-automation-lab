#!/bin/sh
# Start FRR, then apply per-interface OSPF costs at runtime. Docker assigns eth0..ethN in an order we do
# not control, so costs are declared per IP in /etc/frr/ospf-costs and mapped to whichever interface
# holds that IP once the container is up. Applied via vtysh, so frr.conf on disk stays exactly as rendered.
/usr/lib/frr/docker-start &
frr_pid=$!

if [ -s /etc/frr/ospf-costs ]; then
  i=0
  until vtysh -c 'show ip ospf' >/dev/null 2>&1 || [ $i -ge 30 ]; do i=$((i+1)); sleep 1; done
  while read -r ip cost; do
    if [ -n "$ip" ]; then
      ifname=$(ip -o -4 addr show | awk -v ip="$ip" '$4 ~ "^"ip"/" {print $2}')
      if [ -n "$ifname" ]; then
        vtysh -c 'configure terminal' -c "interface $ifname" -c "ip ospf cost $cost" >/dev/null 2>&1 || echo "cost apply failed for $ip"
      fi
    fi
  done < /etc/frr/ospf-costs
fi
wait $frr_pid
