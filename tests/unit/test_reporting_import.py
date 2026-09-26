from __future__ import annotations


def test_reporting_package_imports_without_removed_calibration_module() -> None:
    import commander_lab.reporting as reporting

    assert reporting.__all__ == []
