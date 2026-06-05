"""Windows desktop capture helpers and display/session diagnostics."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import TYPE_CHECKING

import win32api
import win32con
import win32gui
import win32ui

if TYPE_CHECKING:
    from PIL import Image

PW_RENDERFULLCONTENT = 2
UOI_NAME = 2
DISPLAY_DEVICE_ACTIVE = getattr(win32con, "DISPLAY_DEVICE_ACTIVE", 0x00000001)

_VIRTUAL_DISPLAY_MARKERS = (
    "virtual display",
    "vdd",
    "idd",
    "indirect display",
    "parsec",
    "usbmmidd",
)


@dataclass(frozen=True)
class DisplayDiagnostics:
    session_locked: bool
    input_desktop: str
    primary_width: int
    primary_height: int
    virtual_screen_width: int
    virtual_screen_height: int
    monitor_count: int
    active_displays: tuple[str, ...]
    virtual_display_detected: bool
    gdi_grab_ok: bool
    gdi_grab_error: str

    def summary(self) -> str:
        parts = [
            f"desktop={self.input_desktop}",
            "locked" if self.session_locked else "unlocked",
            f"primary={self.primary_width}x{self.primary_height}",
            f"virtual_screen={self.virtual_screen_width}x{self.virtual_screen_height}",
            f"monitors={self.monitor_count}",
            f"gdi_grab={'ok' if self.gdi_grab_ok else 'FAILED'}",
        ]
        if self.virtual_display_detected:
            parts.append("virtual_display=detected")
        elif self.active_displays:
            parts.append(f"displays={'; '.join(self.active_displays[:3])}")
        if self.gdi_grab_error:
            parts.append(f"gdi_error={self.gdi_grab_error}")
        return ", ".join(parts)


def _input_desktop_name() -> tuple[str, bool]:
    user32 = ctypes.windll.user32
    hdesk = user32.OpenInputDesktop(0, False, 0)
    if not hdesk:
        return ("<unavailable>", True)
    try:
        needed = ctypes.c_ulong()
        user32.GetUserObjectInformationW(hdesk, UOI_NAME, None, 0, ctypes.byref(needed))
        if needed.value == 0:
            return ("<unknown>", True)
        buffer = ctypes.create_unicode_buffer(needed.value)
        user32.GetUserObjectInformationW(
            hdesk,
            UOI_NAME,
            buffer,
            needed.value,
            ctypes.byref(needed),
        )
        name = buffer.value or "<unknown>"
        return (name, name.lower() != "default")
    finally:
        user32.CloseDesktop(hdesk)


def _active_display_names() -> list[str]:
    names: list[str] = []
    device_index = 0
    while True:
        try:
            adapter = win32api.EnumDisplayDevices(None, device_index)
        except win32api.error:
            break
        device_index += 1
        if not adapter.DeviceName:
            continue
        monitor_index = 0
        while True:
            try:
                monitor = win32api.EnumDisplayDevices(adapter.DeviceName, monitor_index)
            except win32api.error:
                break
            monitor_index += 1
            if monitor.StateFlags & DISPLAY_DEVICE_ACTIVE:
                label = monitor.DeviceString or monitor.DeviceName
                if label and label not in names:
                    names.append(label)
    return names


def _test_gdi_grab() -> tuple[bool, str]:
    try:
        from PIL import ImageGrab

        ImageGrab.grab(bbox=(0, 0, 1, 1))
        return True, ""
    except OSError as exc:
        return False, str(exc)
    except Exception as exc:  # pylint: disable=broad-except
        return False, f"{type(exc).__name__}: {exc}"


def collect_display_diagnostics() -> DisplayDiagnostics:
    input_desktop, session_locked = _input_desktop_name()
    active_displays = tuple(_active_display_names())
    virtual_display_detected = any(
        any(marker in display.lower() for marker in _VIRTUAL_DISPLAY_MARKERS)
        for display in active_displays
    )
    gdi_ok, gdi_error = _test_gdi_grab()
    return DisplayDiagnostics(
        session_locked=session_locked,
        input_desktop=input_desktop,
        primary_width=int(win32api.GetSystemMetrics(win32con.SM_CXSCREEN)),
        primary_height=int(win32api.GetSystemMetrics(win32con.SM_CYSCREEN)),
        virtual_screen_width=int(win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)),
        virtual_screen_height=int(win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)),
        monitor_count=int(win32api.GetSystemMetrics(win32con.SM_CMONITORS)),
        active_displays=active_displays,
        virtual_display_detected=virtual_display_detected,
        gdi_grab_ok=gdi_ok,
        gdi_grab_error=gdi_error,
    )


def capture_hwnd_client(hwnd: int) -> "Image.Image":
    """Capture the client area of a window (works when full-desktop GDI grab fails)."""
    from PIL import Image

    left, top, right, bottom = win32gui.GetClientRect(hwnd)  # pylint: disable=c-extension-no-member
    width = right - left
    height = bottom - top
    if width < 1 or height < 1:
        raise OSError(f"Invalid client size {width}x{height}")

    hwnd_dc = win32gui.GetWindowDC(hwnd)  # pylint: disable=c-extension-no-member
    if not hwnd_dc:
        raise OSError("GetWindowDC failed")
    try:
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        try:
            save_dc = mfc_dc.CreateCompatibleDC()
            try:
                bitmap = win32ui.CreateBitmap()
                try:
                    bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
                    save_dc.SelectObject(bitmap)
                    if not win32gui.PrintWindow(hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT):  # pylint: disable=c-extension-no-member
                        if save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY) == 0:
                            raise OSError("PrintWindow and BitBlt capture failed")
                    bmpinfo = bitmap.GetInfo()
                    bmpstr = bitmap.GetBitmapBits(True)
                    return Image.frombuffer(
                        "RGB",
                        (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
                        bmpstr,
                        "raw",
                        "BGRX",
                        0,
                        1,
                    )
                finally:
                    win32gui.DeleteObject(bitmap.GetHandle())  # pylint: disable=c-extension-no-member
            finally:
                save_dc.DeleteDC()
        finally:
            mfc_dc.DeleteDC()
    finally:
        win32gui.ReleaseDC(hwnd, hwnd_dc)  # pylint: disable=c-extension-no-member
