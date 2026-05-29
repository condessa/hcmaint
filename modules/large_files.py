"""
HCMaint - Scanner de Ficheiros Grandes
Encontra ficheiros acima de um limiar de tamanho em pastas do utilizador
"""

import os
import stat
from pathlib import Path
from datetime import datetime


HOME = str(Path.home())

# Pastas a ignorar completamente
SKIP_DIRS = {
    ".git", ".svn", ".hg",
    "node_modules", ".node_modules",
    "venv", ".venv", "env", ".env",
    ".cargo", ".gradle",
    "proc", "sys", "dev",
}

# Extensões de ficheiros grandes conhecidos (para categorização)
EXT_CATEGORIES = {
    "video":   {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
                ".m4v", ".mpg", ".mpeg", ".ts", ".mts", ".vob"},
    "iso":     {".iso", ".img", ".dmg", ".vmdk", ".vdi", ".vhd"},
    "arquivo": {".tar", ".gz", ".bz2", ".xz", ".zip", ".rar", ".7z",
                ".tar.gz", ".tar.bz2", ".tar.xz", ".tgz"},
    "backup":  {".bak", ".backup", ".old", ".orig"},
    "log":     {".log", ".out", ".err"},
    "db":      {".db", ".sqlite", ".sqlite3", ".sql"},
    "build":   {".o", ".a", ".so", ".dll", ".exe", ".deb", ".rpm", ".apk"},
    "dump":    {".dmp", ".core", ".dump"},
}

EXT_ICONS = {
    "video":   "🎬",
    "iso":     "💿",
    "arquivo": "📦",
    "backup":  "📋",
    "log":     "🗒️",
    "db":      "🗄️",
    "build":   "⚙️",
    "dump":    "💾",
    "outro":   "📄",
}


def fmt(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    else:
        return f"{size_bytes / 1024 ** 3:.2f} GB"


def get_file_category(path):
    """Categoriza um ficheiro pela extensão."""
    ext = os.path.splitext(path)[1].lower()
    for cat, exts in EXT_CATEGORIES.items():
        if ext in exts:
            return cat
    return "outro"


def scan_large_files(
    min_size_mb=50,
    search_paths=None,
    progress_cb=None,
    max_results=500,
):
    """
    Encontra ficheiros maiores que min_size_mb em search_paths.

    Retorna lista de dicts ordenada por tamanho (maior primeiro):
    {"path", "size", "size_str", "category", "icon", "modified", "modified_str"}
    """
    if search_paths is None:
        search_paths = [HOME, "/var/log", "/tmp"]

    min_bytes = min_size_mb * 1024 * 1024
    found = []
    scanned_dirs = 0

    for base in search_paths:
        if not os.path.exists(base):
            continue

        for root, dirs, files in os.walk(base, followlinks=False):
            # Filtrar pastas a ignorar
            dirs[:] = [
                d for d in dirs
                if d not in SKIP_DIRS
                and not d.startswith(".")
                or d in {".local", ".config", ".cache"}
            ]

            scanned_dirs += 1
            if progress_cb and scanned_dirs % 50 == 0:
                short = root if len(root) < 50 else "..." + root[-47:]
                progress_cb(f"A pesquisar: {short}")

            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    st = os.stat(fpath, follow_symlinks=False)
                    if stat.S_ISREG(st.st_mode) and st.st_size >= min_bytes:
                        cat = get_file_category(fpath)
                        mtime = datetime.fromtimestamp(st.st_mtime)
                        found.append({
                            "path":         fpath,
                            "size":         st.st_size,
                            "size_str":     fmt(st.st_size),
                            "category":     cat,
                            "icon":         EXT_ICONS.get(cat, "📄"),
                            "modified":     mtime,
                            "modified_str": mtime.strftime("%d/%m/%Y"),
                            "name":         fname,
                        })
                        if len(found) >= max_results:
                            found.sort(key=lambda x: x["size"], reverse=True)
                            return found
                except (PermissionError, OSError, FileNotFoundError):
                    pass

    found.sort(key=lambda x: x["size"], reverse=True)
    return found


def delete_large_file(path, log_cb=None):
    """Remove um ficheiro grande. Retorna (sucesso, bytes_freed)."""
    try:
        size = os.path.getsize(path)
        os.remove(path)
        if log_cb:
            log_cb(f"✅ Removido: {os.path.basename(path)} ({fmt(size)})", "ok")
        return True, size
    except PermissionError as e:
        if log_cb:
            log_cb(f"❌ Sem permissão: {path}", "error")
        return False, 0
    except Exception as e:
        if log_cb:
            log_cb(f"❌ Erro: {e}", "error")
        return False, 0


def get_stats(large_files):
    """Estatísticas de uma lista de ficheiros grandes."""
    if not large_files:
        return {"total": 0, "count": 0, "by_category": {}}

    total = sum(f["size"] for f in large_files)
    by_cat = {}
    for f in large_files:
        cat = f["category"]
        by_cat.setdefault(cat, {"count": 0, "size": 0})
        by_cat[cat]["count"] += 1
        by_cat[cat]["size"] += f["size"]

    return {
        "total":       total,
        "count":       len(large_files),
        "by_category": by_cat,
    }
