from netos.monitoring import service as monitoring_module
from netos.monitoring.service import MonitorService


def test_inventory_persistence_failure_does_not_stop_collection(monkeypatch):
    monkeypatch.setattr(monitoring_module, "discover_interfaces", lambda: ())
    monkeypatch.setattr(monitoring_module, "read_arp_cache", lambda: ())
    monkeypatch.setattr(monitoring_module, "read_interface_statistics", lambda: {})
    monitor = MonitorService(interval_seconds=1, discovery_enabled=True)
    monitor.set_observation_sink(
        lambda observations: (_ for _ in ()).throw(RuntimeError("database down"))
    )

    monitor.collect_once()

    events = monitor.events.list()
    assert any(
        event.resource == "inventory" and "database down" in event.description
        for event in events
    )
