from unittest.mock import patch

from netos.events.monitoring import EventStore
from netos.monitoring.service import MonitorService
from netos.network.models import InterfaceAddress, InterfaceInfo, InterfaceStatistics
from netos.network.system import discover_interfaces, read_interface_statistics


def test_discovery_handles_interface_without_ipv4():
    address = type("Address", (), {"family": 9999, "address": "aa:bb:cc:dd:ee:ff", "netmask": None})()
    stats = type("Stats", (), {"isup": True, "mtu": 1500})()
    with patch("netos.network.system.psutil.net_if_addrs", return_value={"virtual0": [address]}), \
        patch("netos.network.system.psutil.net_if_stats", return_value={"virtual0": stats}), \
        patch("netos.network.system._interface_index", return_value=None), \
        patch("netos.network.system._linux_virtual", return_value=True), \
        patch("netos.network.system._linux_interface_type", return_value="virtual"):
        interfaces = discover_interfaces()
    assert interfaces[0].addresses == ()
    assert interfaces[0].is_virtual is True


def test_statistics_are_mapped_from_real_counter_shape():
    counter = type(
        "Counter",
        (),
        {
            "bytes_recv": 10,
            "bytes_sent": 20,
            "packets_recv": 1,
            "packets_sent": 2,
            "errin": 3,
            "errout": 4,
            "dropin": 5,
            "dropout": 6,
        },
    )()
    with patch("netos.network.system.psutil.net_io_counters", return_value={"eth0": counter}):
        statistics = read_interface_statistics()
    assert statistics["eth0"].bytes_received == 10
    assert statistics["eth0"].transmit_drops == 6


def test_rates_ignore_counter_reset():
    service = MonitorService(5, True)
    first = InterfaceStatistics("eth0", 100, 100, 1, 1, 0, 0, 0, 0)
    reset = InterfaceStatistics("eth0", 10, 10, 1, 1, 0, 0, 0, 0)
    service._update_rates({"eth0": first}, 1.0)
    service._update_rates({"eth0": reset}, 2.0)
    assert service.snapshot()[3] == {}


def test_events_are_not_duplicated_for_unchanged_interfaces():
    interface = InterfaceInfo(
        "eth0", 1, None, (InterfaceAddress("192.0.2.1", "ipv4", 24),),
        True, 1500, "ethernet", False, False,
    )
    store = EventStore()
    store.observe_interfaces((interface,))
    store.observe_interfaces((interface,))
    assert len(store.list()) == 1


def test_windows_does_not_fake_linux_arp_data():
    with patch("netos.network.system.platform.system", return_value="Windows"):
        from netos.network.system import read_arp_cache

        assert read_arp_cache() == ()
