"""
Tests for Issue #2 — Panel Docking System + Command Palette.
Tests verify behavior through public interfaces only.
"""
import json
import pytest
from PyQt6.QtWidgets import QDockWidget, QApplication

from cbosa.ui.panels import BasePanel, PanelRegistry
from cbosa.ui.command_palette import CommandPalette
from cbosa.ui.main_window import MainWindow


# ---------------------------------------------------------------------------
# Cycle 1 — PanelRegistry: register/get (tracer bullet)
# ---------------------------------------------------------------------------

def test_panel_registry_retrieves_registered_type():
    """Registering a panel class by name lets you retrieve it by that name."""
    registry = PanelRegistry()
    registry.register("Notes", BasePanel)
    assert registry.get("Notes") is BasePanel


# ---------------------------------------------------------------------------
# Cycle 2 — PanelRegistry: all_names
# ---------------------------------------------------------------------------

def test_panel_registry_all_names():
    """all_names() returns every registered panel type name."""
    registry = PanelRegistry()
    registry.register("Notes", BasePanel)
    registry.register("Finance", BasePanel)
    assert set(registry.all_names()) == {"Notes", "Finance"}


# ---------------------------------------------------------------------------
# Cycle 3 — BasePanel is a QDockWidget with correct title
# ---------------------------------------------------------------------------

def test_base_panel_is_dock_widget(qapp):
    """BasePanel is a QDockWidget whose title matches the name passed in."""
    panel = BasePanel("Notes")
    assert isinstance(panel, QDockWidget)
    assert panel.windowTitle() == "Notes"


# ---------------------------------------------------------------------------
# Cycle 4 — MainWindow.add_panel adds a dock widget
# ---------------------------------------------------------------------------

def test_add_panel_adds_dock_widget(qapp):
    """add_panel('Notes') creates one QDockWidget child in the main window."""
    registry = PanelRegistry()
    registry.register("Notes", BasePanel)
    window = MainWindow(registry=registry)
    window.add_panel("Notes")
    assert len(window.findChildren(QDockWidget)) == 1


def test_add_panel_unknown_type_does_nothing(qapp):
    """add_panel with an unregistered name adds no dock widget."""
    window = MainWindow(registry=PanelRegistry())
    window.add_panel("Ghost")
    assert window.findChildren(QDockWidget) == []


# ---------------------------------------------------------------------------
# Cycle 5 — Closing a panel removes it from the window
# ---------------------------------------------------------------------------

def test_add_panel_does_not_open_duplicate(qapp):
    """Calling add_panel with an already-open name does not create a second panel."""
    registry = PanelRegistry()
    registry.register("Notes", BasePanel)
    window = MainWindow(registry=registry)
    window.add_panel("Notes")
    window.add_panel("Notes")
    assert len(window.findChildren(QDockWidget)) == 1


def test_closing_panel_removes_it(qapp):
    """Closing a dock widget removes it entirely from the main window."""
    registry = PanelRegistry()
    registry.register("Notes", BasePanel)
    window = MainWindow(registry=registry)
    window.add_panel("Notes")
    dock = window.findChildren(QDockWidget)[0]
    dock.close()
    QApplication.processEvents()
    assert window.findChildren(QDockWidget) == []


# ---------------------------------------------------------------------------
# Cycle 6 — Layout saves panel names to JSON on close
# ---------------------------------------------------------------------------

def test_layout_saves_panel_names(qapp, tmp_path):
    """Closing the main window writes open panel names to layout.json."""
    registry = PanelRegistry()
    registry.register("Notes", BasePanel)
    layout_path = tmp_path / "layout.json"
    window = MainWindow(registry=registry, layout_path=layout_path)
    window.add_panel("Notes")
    window.close()
    data = json.loads(layout_path.read_text())
    assert "Notes" in data["panels"]


# ---------------------------------------------------------------------------
# Cycle 7 — Layout restores panels on next launch
# ---------------------------------------------------------------------------

def test_layout_restores_panels_on_launch(qapp, tmp_path):
    """Opening a new window with a saved layout restores the same panels."""
    registry = PanelRegistry()
    registry.register("Notes", BasePanel)
    layout_path = tmp_path / "layout.json"

    window1 = MainWindow(registry=registry, layout_path=layout_path)
    window1.add_panel("Notes")
    window1.close()

    window2 = MainWindow(registry=registry, layout_path=layout_path)
    assert len(window2.findChildren(QDockWidget)) == 1


# ---------------------------------------------------------------------------
# Cycle 8 — CommandPalette lists all registered panel types
# ---------------------------------------------------------------------------

def test_default_registry_has_panels_after_app_bootstrap():
    """_register_panels() populates a registry with the expected placeholder panels."""
    from cbosa.app import _register_panels
    from cbosa.ui.panels import PanelRegistry
    isolated = PanelRegistry()
    _register_panels(isolated)
    assert len(isolated.all_names()) > 0
    assert "Note Browser" in isolated.all_names()


def test_command_palette_lists_panel_types(qapp):
    """CommandPalette shows one list item per registered panel type."""
    registry = PanelRegistry()
    registry.register("Notes", BasePanel)
    registry.register("Finance", BasePanel)
    palette = CommandPalette(registry)
    items = {
        palette.list_widget.item(i).text()
        for i in range(palette.list_widget.count())
    }
    assert items == {"Notes", "Finance"}
