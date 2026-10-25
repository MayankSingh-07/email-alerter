import argparse
import sys
from unittest.mock import MagicMock, patch
import pytest

import main


def test_main_cli_once_mode(tmp_path, monkeypatch):
    test_args = ["main.py", "--once"]
    monkeypatch.setattr(sys, "argv", test_args)

    mock_cfg = MagicMock()
    mock_cfg.db_path = str(tmp_path / "alerts.db")
    monkeypatch.setattr("main.load_config", lambda: mock_cfg)

    mock_service_instance = MagicMock()
    mock_service_instance.run_once.return_value = 2
    mock_service_cls = MagicMock(return_value=mock_service_instance)
    monkeypatch.setattr("main.EmailMonitorService", mock_service_cls)

    exit_code = main.main()
    assert exit_code == 0
    mock_service_instance.run_once.assert_called_once_with(alert_new=True)
    assert not mock_service_instance.start.called


def test_main_cli_baseline_mode(tmp_path, monkeypatch):
    test_args = ["main.py", "--baseline"]
    monkeypatch.setattr(sys, "argv", test_args)

    mock_cfg = MagicMock()
    mock_cfg.db_path = str(tmp_path / "alerts.db")
    monkeypatch.setattr("main.load_config", lambda: mock_cfg)

    mock_service_instance = MagicMock()
    mock_service_instance.run_once.return_value = 0
    mock_service_cls = MagicMock(return_value=mock_service_instance)
    monkeypatch.setattr("main.EmailMonitorService", mock_service_cls)

    exit_code = main.main()
    assert exit_code == 0
    mock_service_instance.run_once.assert_called_once_with(alert_new=False)
    assert not mock_service_instance.start.called


def test_main_cli_daemon_mode(tmp_path, monkeypatch):
    test_args = ["main.py", "--daemon"]
    monkeypatch.setattr(sys, "argv", test_args)

    mock_cfg = MagicMock()
    mock_cfg.db_path = str(tmp_path / "alerts.db")
    monkeypatch.setattr("main.load_config", lambda: mock_cfg)

    mock_service_instance = MagicMock()
    mock_service_cls = MagicMock(return_value=mock_service_instance)
    monkeypatch.setattr("main.EmailMonitorService", mock_service_cls)

    exit_code = main.main()
    assert exit_code == 0
    mock_service_instance.start.assert_called_once()


def test_main_cli_default_is_daemon_mode(tmp_path, monkeypatch):
    test_args = ["main.py"]
    monkeypatch.setattr(sys, "argv", test_args)

    mock_cfg = MagicMock()
    mock_cfg.db_path = str(tmp_path / "alerts.db")
    monkeypatch.setattr("main.load_config", lambda: mock_cfg)

    mock_service_instance = MagicMock()
    mock_service_cls = MagicMock(return_value=mock_service_instance)
    monkeypatch.setattr("main.EmailMonitorService", mock_service_cls)

    exit_code = main.main()
    assert exit_code == 0
    mock_service_instance.start.assert_called_once()
