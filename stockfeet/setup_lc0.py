"""Download an official lc0 Windows build for trying Stockfeet.

Fetches the upstream CPU DNNL package from the LCZero GitHub release
(GPL-3.0-or-later). Stockfeet does not claim lc0 as its own engine.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable
from pathlib import Path
from urllib.request import Request, urlopen

# Official LCZero release asset (includes default network). Prefer CPU so
# anyone can try without a CUDA GPU. See https://lczero.org/play/download/
LC0_VERSION = "v0.32.1"
LC0_ZIP_URL = (
    "https://github.com/LeelaChessZero/lc0/releases/download/"
    f"{LC0_VERSION}/lc0-{LC0_VERSION}-windows-cpu-dnnl.zip"
)
LC0_SOURCE_URL = "https://github.com/LeelaChessZero/lc0"
LC0_SITE = "https://lczero.org/"

ProgressFn = Callable[[str], None]


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def vendor_lc0_dir() -> Path:
    return project_root() / "vendor" / "lc0"


def find_lc0_exe(root: Path | None = None) -> Path | None:
    base = root or vendor_lc0_dir()
    if not base.exists():
        return None
    direct = base / "lc0.exe"
    if direct.exists():
        return direct
    matches = sorted(base.rglob("lc0.exe"))
    return matches[0] if matches else None


def write_env_lc0_path(lc0_exe: Path) -> Path:
    """Create or update .env STOCKFEET_LC0_PATH."""
    env_path = project_root() / ".env"
    line = f"STOCKFEET_LC0_PATH={lc0_exe}"
    if not env_path.exists():
        example = project_root() / ".env.example"
        body = example.read_text(encoding="utf-8") if example.exists() else ""
        if "STOCKFEET_LC0_PATH=" in body:
            lines = []
            for raw in body.splitlines():
                if raw.startswith("STOCKFEET_LC0_PATH="):
                    lines.append(line)
                else:
                    lines.append(raw)
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            env_path.write_text(
                line
                + "\nSTOCKFEET_LC0_WEIGHTS=\nSTOCKFEET_MOVETIME_MS=1000\n"
                + "STOCKFEET_OPENAI_API_KEY=\n",
                encoding="utf-8",
            )
        return env_path

    lines = env_path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    replaced = False
    for raw in lines:
        if raw.startswith("STOCKFEET_LC0_PATH="):
            out.append(line)
            replaced = True
        else:
            out.append(raw)
    if not replaced:
        out.append(line)
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return env_path


def download_lc0_cpu(
    *,
    dest_dir: Path | None = None,
    progress: ProgressFn | None = None,
) -> Path:
    """
    Download & unpack official Windows CPU lc0 into vendor/lc0.

    Returns path to lc0.exe. Writes a README.lc0.txt with GPL attribution.
    """
    dest = dest_dir or vendor_lc0_dir()
    dest.mkdir(parents=True, exist_ok=True)

    if progress:
        progress(f"Downloading official lc0 {LC0_VERSION} (CPU DNNL)…")
        progress(LC0_ZIP_URL)

    req = Request(
        LC0_ZIP_URL,
        headers={"User-Agent": "Stockfeet/0.1 (setup-lc0; +https://lczero.org/)"},
    )
    with urlopen(req, timeout=120) as resp:
        data = resp.read()

    if progress:
        progress(f"Downloaded {len(data) / (1024 * 1024):.1f} MB — extracting…")

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(dest)

    exe = find_lc0_exe(dest)
    if exe is None:
        raise FileNotFoundError(f"lc0.exe missing after extract into {dest}")

    notice = dest / "README.lc0.txt"
    notice.write_text(
        "\n".join(
            [
                "Leela Chess Zero (lc0) — official binary used by Stockfeet",
                "=" * 60,
                f"Version : {LC0_VERSION} (windows-cpu-dnnl)",
                f"Website : {LC0_SITE}",
                f"Source  : {LC0_SOURCE_URL}",
                "License : GPL-3.0-or-later",
                "",
                "This folder contains software from the LCZero project, not Stockfeet.",
                "Stockfeet (MIT) talks to lc0.exe over UCI as a separate process.",
                "If you redistribute this lc0 binary, you must also provide GPL text",
                "and corresponding source (or a valid written offer) — see Stockfeet NOTICE.",
                "",
                f"Downloaded from: {LC0_ZIP_URL}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    write_env_lc0_path(exe.resolve())
    if progress:
        progress(f"Ready: {exe}")
        progress("Updated .env STOCKFEET_LC0_PATH")
    return exe.resolve()


def ensure_lc0(*, progress: ProgressFn | None = None) -> Path:
    existing = find_lc0_exe()
    if existing is not None:
        write_env_lc0_path(existing.resolve())
        if progress:
            progress(f"Already installed: {existing}")
        return existing.resolve()
    return download_lc0_cpu(progress=progress)
