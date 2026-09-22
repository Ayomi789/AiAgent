"""Pre-flight capability checks for full (LLM + browser) scans.

Deterministic probes run anywhere. Full scans need two things most small
instances lack: ~2 GB of RAM for Chromium, and a working LLM key + model.
This module checks both and explains failures in plain words, so the UI can
disable what won't work instead of showing jargon.
"""

from __future__ import annotations

FULL_SCAN_MIN_RAM_MB = 1536  # Chromium + server comfortably wants ~2 GB


def total_ram_mb() -> int | None:
    """System RAM in MB, or None when it cannot be determined."""
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    try:  # Windows fallback
        import ctypes

        class _MemStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        st = _MemStatus()
        st.dwLength = ctypes.sizeof(_MemStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return int(st.ullTotalPhys // (1024 * 1024))
    except Exception:
        pass
    return None


def check_full_scan(config_name: str | None = None) -> dict:
    """Can this instance run a full scan right now? Always JSON-safe."""
    from qaagent.doctor import probe_llm

    reasons: list[str] = []

    ram = total_ram_mb()
    ram_ok = ram is None or ram >= FULL_SCAN_MIN_RAM_MB
    if not ram_ok:
        reasons.append(
            f"This instance has about {ram} MB of memory — full scans need "
            "around 2 GB for the browser. Upgrade the plan, or run a "
            "deterministic scan instead (it needs almost nothing)."
        )

    llm_ok: bool | None = None
    llm_message = ""
    llm_cfg = None
    if config_name:
        # Same resolution as a real run, but never auto-create anything.
        from pathlib import Path

        from qaagent.cli import _resolve_config
        from qaagent.config import RunConfig

        try:
            cfg_path: Path | None = _resolve_config(Path(config_name))
        except FileNotFoundError:
            cfg_path = None
        if cfg_path is not None:
            try:
                llm_cfg = RunConfig.from_yaml(cfg_path).llm
            except Exception as exc:
                reasons.append(f"Could not read that config: {exc}")
    check = probe_llm(llm_cfg)
    llm_ok = check.status == "ok"
    llm_message = check.detail
    if not llm_ok:
        reasons.append(
            "The AI backend is not answering cleanly right now "
            f"({check.detail}). Full scans need it; deterministic scans do not."
        )

    return {
        "ram_mb": ram,
        "ram_ok": ram_ok,
        "llm_ok": llm_ok,
        "llm_message": llm_message,
        "full_ok": ram_ok and bool(llm_ok),
        "reasons": reasons,
    }
