from importlib.metadata import distribution


def test_every_console_script_target_imports():
    scripts = [
        ep
        for ep in distribution("prenatalppkt").entry_points
        if ep.group == "console_scripts"
    ]
    for entry_point in scripts:
        assert callable(entry_point.load()), entry_point.value
