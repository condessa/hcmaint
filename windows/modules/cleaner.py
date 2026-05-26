"""
HCCleaner - Módulo de Limpeza de Ficheiros
Limpa temporários, cache, logs, ficheiros inúteis do Windows
"""

import os
import shutil
import tempfile
import glob
import ctypes
import platform
from pathlib import Path
from datetime import datetime

# Categorias de limpeza com caminhos e padrões
CLEAN_TARGETS = {
    "windows_temp": {
        "label": "Temporários do Windows",
        "icon": "🗑️",
        "paths": [
            os.environ.get("TEMP", ""),
            os.environ.get("TMP", ""),
            r"C:\Windows\Temp",
        ],
        "patterns": ["*"],
        "recursive": True,
    },
    "prefetch": {
        "label": "Prefetch do Windows",
        "icon": "⚡",
        "paths": [r"C:\Windows\Prefetch"],
        "patterns": ["*.pf"],
        "recursive": False,
    },
    "browser_cache_chrome": {
        "label": "Cache do Google Chrome",
        "icon": "🌐",
        "paths": [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\User Data\Default\Cache"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\User Data\Default\Code Cache"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\User Data\Default\GPUCache"),
        ],
        "patterns": ["*"],
        "recursive": True,
    },
    "browser_cache_firefox": {
        "label": "Cache do Firefox",
        "icon": "🦊",
        "paths": [
            os.path.join(os.environ.get("APPDATA", ""), r"Mozilla\Firefox\Profiles"),
        ],
        "patterns": ["cache2", "startupCache", "thumbnails"],
        "recursive": True,
        "subfolders_only": True,
    },
    "browser_cache_edge": {
        "label": "Cache do Microsoft Edge",
        "icon": "🔷",
        "paths": [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Edge\User Data\Default\Cache"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Edge\User Data\Default\Code Cache"),
        ],
        "patterns": ["*"],
        "recursive": True,
    },
    "windows_logs": {
        "label": "Logs do Windows",
        "icon": "📋",
        "paths": [
            r"C:\Windows\Logs",
            r"C:\Windows\debug",
        ],
        "patterns": ["*.log", "*.etl", "*.txt"],
        "recursive": True,
    },
    "windows_update_cache": {
        "label": "Cache do Windows Update",
        "icon": "🔄",
        "paths": [
            r"C:\Windows\SoftwareDistribution\Download",
        ],
        "patterns": ["*"],
        "recursive": True,
    },
    "recycle_bin": {
        "label": "Reciclagem",
        "icon": "♻️",
        "paths": [],
        "special": "recycle_bin",
    },
    "thumbnail_cache": {
        "label": "Cache de Miniaturas",
        "icon": "🖼️",
        "paths": [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Windows\Explorer"),
        ],
        "patterns": ["thumbcache_*.db", "iconcache_*.db"],
        "recursive": False,
    },
    "recent_files": {
        "label": "Ficheiros Recentes",
        "icon": "📂",
        "paths": [
            os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Recent"),
        ],
        "patterns": ["*.lnk"],
        "recursive": False,
    },
    "error_reports": {
        "label": "Relatórios de Erros",
        "icon": "⚠️",
        "paths": [
            r"C:\ProgramData\Microsoft\Windows\WER\ReportArchive",
            r"C:\ProgramData\Microsoft\Windows\WER\ReportQueue",
            os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Windows\WER"),
        ],
        "patterns": ["*"],
        "recursive": True,
    },
    "font_cache": {
        "label": "Cache de Fontes",
        "icon": "🔤",
        "paths": [r"C:\Windows\ServiceProfiles\LocalService\AppData\Local\FontCache"],
        "patterns": ["*.dat", "*.bin"],
        "recursive": False,
    },
    "memory_dumps": {
        "label": "Dumps de Memória",
        "icon": "💾",
        "paths": [r"C:\Windows", r"C:\Windows\Minidump"],
        "patterns": ["*.dmp", "MEMORY.DMP"],
        "recursive": False,
    },
}


def get_size(path):
    """Retorna tamanho em bytes de um ficheiro ou pasta."""
    try:
        if os.path.isfile(path):
            return os.path.getsize(path)
        total = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                try:
                    fp = os.path.join(dirpath, f)
                    if not os.path.islink(fp):
                        total += os.path.getsize(fp)
                except (OSError, PermissionError):
                    pass
        return total
    except (OSError, PermissionError):
        return 0


def format_size(size_bytes):
    """Formata bytes para string legível."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes/1024:.1f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes/1024**2:.1f} MB"
    else:
        return f"{size_bytes/1024**3:.2f} GB"


def scan_category(cat_key, callback=None):
    """
    Analisa uma categoria e retorna lista de ficheiros/pastas encontrados.
    callback(msg) para progresso.
    """
    cat = CLEAN_TARGETS.get(cat_key, {})
    found = []
    total_size = 0

    if cat.get("special") == "recycle_bin":
        # Reciclagem - verifica via SHEmptyRecycleBin disponibilidade
        try:
            rb_size = get_recycle_bin_size()
            if rb_size > 0:
                found.append({"path": "Reciclagem", "size": rb_size, "type": "special_recycle"})
                total_size += rb_size
        except Exception:
            pass
        return found, total_size

    for base_path in cat.get("paths", []):
        if not base_path or not os.path.exists(base_path):
            continue

        patterns = cat.get("patterns", ["*"])
        recursive = cat.get("recursive", False)

        if cat.get("subfolders_only"):
            # Firefox: percorre perfis e procura subpastas específicas
            try:
                for profile in os.listdir(base_path):
                    profile_path = os.path.join(base_path, profile)
                    if os.path.isdir(profile_path):
                        for sub in patterns:
                            sub_path = os.path.join(profile_path, sub)
                            if os.path.exists(sub_path):
                                sz = get_size(sub_path)
                                found.append({"path": sub_path, "size": sz, "type": "folder"})
                                total_size += sz
            except PermissionError:
                pass
            continue

        for pattern in patterns:
            if pattern == "*":
                # Todos os itens na pasta
                try:
                    for item_name in os.listdir(base_path):
                        full = os.path.join(base_path, item_name)
                        try:
                            sz    = get_size(full)
                            ftype = "folder" if os.path.isdir(full) else "file"
                            # Não listar pastas vazias bloqueadas (ex: Arduino IDE temp)
                            # a não ser que sejam ficheiros — pastas de 0B apenas enchem a lista
                            if sz == 0 and ftype == "folder":
                                # Verificar se a pasta tem algum conteúdo (mesmo bloqueado)
                                try:
                                    has_content = any(True for _ in os.scandir(full))
                                except Exception:
                                    has_content = False
                                if not has_content:
                                    continue  # pasta vazia — ignorar
                            found.append({"path": full, "size": sz, "type": ftype})
                            total_size += sz
                        except Exception:
                            pass
                except PermissionError:
                    pass
            else:
                # Padrão específico
                search = os.path.join(base_path, "**", pattern) if recursive else os.path.join(base_path, pattern)
                try:
                    for match in glob.glob(search, recursive=recursive):
                        try:
                            sz = get_size(match)
                            ftype = "folder" if os.path.isdir(match) else "file"
                            found.append({"path": match, "size": sz, "type": ftype})
                            total_size += sz
                        except Exception:
                            pass
                except Exception:
                    pass

    return found, total_size


def clean_item(item):
    """
    Remove um item (ficheiro ou pasta).
    Para ficheiros bloqueados tenta takeown + icacls antes de desistir.
    Retorna (sucesso, erro_msg)
    """
    path      = item.get("path")
    item_type = item.get("type")

    if item_type == "special_recycle":
        try:
            empty_recycle_bin()
            return True, None
        except Exception as e:
            return False, str(e)

    if not path or not os.path.exists(path):
        return True, None  # já não existe — considerar limpo

    # ── Tentativa 1: remoção normal ──────────────────────────────────────────
    try:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=False)
            # Recriar pasta de sistema se necessário
            try:
                os.makedirs(path, exist_ok=True)
            except Exception:
                pass
        else:
            os.remove(path)
        return True, None
    except Exception:
        pass

    # ── Tentativa 2: takeown + icacls (ficheiros bloqueados) ─────────────────
    if platform.system() == "Windows":
        try:
            import subprocess
            NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW — sem janela CMD visível
            subprocess.run(["takeown", "/f", path, "/r", "/d", "S"],
                           capture_output=True, timeout=15,
                           creationflags=NO_WINDOW)
            subprocess.run(["icacls", path, "/grant", "administrators:F", "/t"],
                           capture_output=True, timeout=15,
                           creationflags=NO_WINDOW)
            # Tentar novamente após tomar posse
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                    try:
                        os.makedirs(path, exist_ok=True)
                    except Exception:
                        pass
                else:
                    os.remove(path)
                return True, None
            except Exception as e2:
                return False, f"Bloqueado: {e2}"
        except Exception as e3:
            return False, f"takeown falhou: {e3}"

    return False, "Sem permissão para remover"


def get_recycle_bin_size():
    """
    Obtém o tamanho real da reciclagem usando SHQueryRecycleBinW —
    a mesma API que o Explorer usa para mostrar o tamanho.
    """
    if platform.system() != "Windows":
        return 0
    try:
        import ctypes
        class SHQUERYRBINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize",      ctypes.c_ulong),
                ("i64Size",     ctypes.c_longlong),
                ("i64NumItems", ctypes.c_longlong),
            ]
        info = SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
        ret = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
        if ret == 0:  # S_OK
            return max(0, info.i64Size)
    except Exception:
        pass
    return 0


def empty_recycle_bin():
    """
    Esvazia a reciclagem no Windows.
    Tenta 3 métodos por ordem de fiabilidade:
    1. SHEmptyRecycleBinW (API Shell — mais limpo)
    2. rd /s /q em cada $Recycle.Bin (CMD directo)
    3. Apagar ficheiros individualmente com takeown
    """
    if platform.system() != "Windows":
        return

    errors = []

    # ── Método 1: API Shell ──────────────────────────────────────────────────
    try:
        import ctypes
        # Flags: SHERB_NOCONFIRMATION=1, SHERB_NOPROGRESSUI=2, SHERB_NOSOUND=4
        ret = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x0007)
        if ret == 0 or ret == -2147418113:  # S_OK ou já vazia
            return
        errors.append(f"SHEmptyRecycleBinW retornou {ret:#010x}")
    except Exception as e:
        errors.append(f"SHEmptyRecycleBinW: {e}")

    # ── Método 2: CMD rd /s /q directamente nas pastas ────────────────────────
    import subprocess
    NO_WINDOW  = 0x08000000  # CREATE_NO_WINDOW
    cleaned_any = False
    for drive in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        rb = f"{drive}:\\$Recycle.Bin"
        if not os.path.exists(rb):
            continue
        try:
            subprocess.run(
                ["takeown", "/f", rb, "/r", "/d", "S"],
                capture_output=True, timeout=30,
                creationflags=NO_WINDOW
            )
            subprocess.run(
                ["icacls", rb, "/grant", "administrators:F", "/t"],
                capture_output=True, timeout=30,
                creationflags=NO_WINDOW
            )
            # Apagar conteúdo de cada pasta de utilizador dentro de $Recycle.Bin
            try:
                for sid_folder in os.listdir(rb):
                    sid_path = os.path.join(rb, sid_folder)
                    if os.path.isdir(sid_path):
                        for item in os.listdir(sid_path):
                            item_path = os.path.join(sid_path, item)
                            try:
                                if os.path.isdir(item_path):
                                    shutil.rmtree(item_path, ignore_errors=True)
                                else:
                                    os.remove(item_path)
                                cleaned_any = True
                            except Exception:
                                pass
            except Exception:
                pass
        except Exception as e:
            errors.append(f"rd {drive}: {e}")

    if cleaned_any:
        return

    if errors:
        raise RuntimeError("; ".join(errors))


def scan_all(progress_callback=None):
    """
    Analisa todas as categorias.
    Retorna dict {cat_key: {"items": [...], "size": int, "label": str}}
    """
    results = {}
    keys = list(CLEAN_TARGETS.keys())
    total = len(keys)

    for i, key in enumerate(keys):
        cat = CLEAN_TARGETS[key]
        if progress_callback:
            progress_callback(i, total, f"A analisar: {cat['label']}...")
        items, size = scan_category(key)
        results[key] = {
            "items": items,
            "size": size,
            "label": cat["label"],
            "icon": cat.get("icon", "📁"),
        }
        if progress_callback:
            progress_callback(i + 1, total, f"{cat['label']}: {format_size(size)}")

    return results
