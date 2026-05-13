"""
Tests for Issue #2 — Panel Docking System + Command Palette.
Tests for Issue #17 — CDockManager integration in MainWindow.
Tests verify behavior through public interfaces only.
"""
import json
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6Ads import CDockWidget, CDockManager

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

def test_base_panel_is_cdock_widget(qapp):
    """BasePanel is a CDockWidget whose title matches the name passed in."""
    panel = BasePanel("Notes")
    assert isinstance(panel, CDockWidget)
    assert panel.windowTitle() == "Notes"


# ---------------------------------------------------------------------------
# Cycle 3b — BasePanel.closed signal emits when the panel is closed
# ---------------------------------------------------------------------------

def test_base_panel_closed_signal_emits_on_close(qapp):
    """BasePanel.closed is emitted when closeDockWidget() is called."""
    panel = BasePanel("Notes")
    received = []
    panel.closed.connect(lambda: received.append(True))
    panel.closeDockWidget()
    assert received == [True]


# ---------------------------------------------------------------------------
# Cycle 4 — CDockManager is the central widget (Issue #17 tracer bullet)
# ---------------------------------------------------------------------------

def test_cdock_manager_is_central_widget(qapp):
    """MainWindow uses CDockManager as its central widget (not a QLabel placeholder)."""
    window = MainWindow(registry=PanelRegistry())
    assert isinstance(window.centralWidget(), CDockManager)


# ---------------------------------------------------------------------------
# Cycle 5 — MainWindow.add_panel opens a panel in the workspace
# ---------------------------------------------------------------------------

def test_add_panel_opens_in_workspace(qapp):
    """add_panel('Notes') registers the panel as open in the workspace."""
    registry = PanelRegistry()
    registry.register("Notes", BasePanel)
    window = MainWindow(registry=registry)
    window.add_panel("Notes")
    assert "Notes" in window._open_panels


def test_add_panel_unknown_type_does_nothing(qapp):
    """add_panel with an unregistered name adds no panel to the workspace."""
    window = MainWindow(registry=PanelRegistry())
    window.add_panel("Ghost")
    assert window._open_panels == []


# ---------------------------------------------------------------------------
# Cycle 6 — Closing a panel removes it from the workspace
# ---------------------------------------------------------------------------

def test_add_panel_does_not_open_duplicate(qapp):
    """Calling add_panel with an already-open name does not create a second panel."""
    registry = PanelRegistry()
    registry.register("Notes", BasePanel)
    window = MainWindow(registry=registry)
    window.add_panel("Notes")
    window.add_panel("Notes")
    assert len(window._open_panels) == 1


def test_closing_panel_removes_it(qapp):
    """Closing a panel via closeDockWidget removes it from the open panels list."""
    registry = PanelRegistry()
    registry.register("Notes", BasePanel)
    window = MainWindow(registry=registry)
    window.add_panel("Notes")
    panel = window._panel_instances["Notes"]
    panel.closeDockWidget()
    QApplication.processEvents()
    assert "Notes" not in window._open_panels


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
    assert len(window2._open_panels) == 1


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
