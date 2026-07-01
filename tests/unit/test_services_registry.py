from autograde_core.services import SERVICE_PORTS, iter_services


def test_expected_service_count() -> None:
    assert len(iter_services()) == 19


def test_ports_are_unique() -> None:
    ports = [s.port for s in iter_services()]
    assert len(ports) == len(set(ports))


def test_registry_maps_all_services() -> None:
    assert set(SERVICE_PORTS.values()) == {s.port for s in iter_services()}
    assert SERVICE_PORTS["api"] == 8000
