"""
HCCleaner - Módulo de Limpeza de Registo do Windows
Detecta e corrige entradas inválidas no registo
"""

import os
import platform
from pathlib import Path

# Importação condicional do winreg
try:
    import winreg
    WINREG_OK = True
except ImportError:
    WINREG_OK = False


# Categorias de entradas de registo a verificar
REGISTRY_CHECKS = [
    {
        "key": "startup_invalid",
        "label": "Entradas de Arranque Inválidas",
        "icon": "🚀",
        "hive": "HKCU",
        "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
        "check": "file_exists",
    },
    {
        "key": "startup_invalid_lm",
        "label": "Arranque Global Inválido",
        "icon": "🚀",
        "hive": "HKLM",
        "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
        "check": "file_exists",
    },
    {
        "key": "uninstall_orphans",
        "label": "Desinstaladores Órfãos",
        "icon": "🗑️",
        "hive": "HKLM",
        "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        "check": "subkey_install_location",
    },
    {
        "key": "uninstall_orphans_user",
        "label": "Desinstaladores Órfãos (Utilizador)",
        "icon": "🗑️",
        "hive": "HKCU",
        "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        "check": "subkey_install_location",
    },
    {
        "key": "mru_lists",
        "label": "Listas MRU (Ficheiros Recentes)",
        "icon": "📂",
        "hive": "HKCU",
        "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\RecentDocs",
        "check": "mru_clear",
    },
    {
        "key": "shared_dlls",
        "label": "DLLs Partilhadas Inválidas",
        "icon": "⚙️",
        "hive": "HKLM",
        "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\SharedDLLs",
        "check": "file_exists_values",
    },
    {
        "key": "open_with",
        "label": "Associações de Ficheiros Inválidas",
        "icon": "🔗",
        "hive": "HKCU",
        "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\FileExts",
        "check": "open_with_orphan",
    },
    {
        "key": "app_paths",
        "label": "Caminhos de Aplicação Inválidos",
        "icon": "📁",
        "hive": "HKLM",
        "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
        "check": "subkey_default_path",
    },
]

HIVES = {
    "HKCU": winreg.HKEY_CURRENT_USER if WINREG_OK else None,
    "HKLM": winreg.HKEY_LOCAL_MACHINE if WINREG_OK else None,
    "HKCR": winreg.HKEY_CLASSES_ROOT if WINREG_OK else None,
}


def _open_key(hive_str, path, write=False):
    if not WINREG_OK:
        return None
    hive = HIVES.get(hive_str)
    if hive is None:
        return None
    access = winreg.KEY_READ | winreg.KEY_WOW64_64KEY
    if write:
        access |= winreg.KEY_WRITE
    try:
        return winreg.OpenKey(hive, path, 0, access)
    except (OSError, PermissionError):
        return None


def _enum_values(key):
    values = []
    if key is None:
        return values
    i = 0
    while True:
        try:
            name, data, vtype = winreg.EnumValue(key, i)
            values.append((name, data, vtype))
            i += 1
        except OSError:
            break
    return values


def _enum_subkeys(key):
    subkeys = []
    if key is None:
        return subkeys
    i = 0
    while True:
        try:
            subkeys.append(winreg.EnumKey(key, i))
            i += 1
        except OSError:
            break
    return subkeys


# Apps de sistema que o Windows resolve via PATH — nunca reportar como inválidas
SYSTEM_APP_PATHS_WHITELIST = {
    "msedge.exe", "microsoftedge.exe", "microsoftedgecp.exe",
    "tabtip.exe", "tabtip32.exe",
    "iexplore.exe", "wwahost.exe",
    "mspaint.exe", "notepad.exe", "calc.exe", "wordpad.exe",
    "explorer.exe", "cmd.exe", "powershell.exe", "pwsh.exe",
    "msiexec.exe", "wusa.exe", "dism.exe",
    "regedit.exe", "taskmgr.exe", "control.exe",
    "osk.exe", "magnify.exe", "narrator.exe",
    "snippingtool.exe", "snip-sketch.exe",
    "write.exe", "charmap.exe", "mspaint.exe",
    "winver.exe", "msconfig.exe", "dxdiag.exe",
}


def _path_exists(path_str):
    """
    Verifica se um executável existe:
    1. Expandindo variáveis de ambiente
    2. Testando o caminho absoluto
    3. Testando via PATH do sistema (para exe sem caminho completo)
    """
    if not path_str:
        return False
    try:
        # Limpar aspas e argumentos
        clean = path_str.strip('"').split('"')[0].strip()
        expanded = os.path.expandvars(clean)
        parts = expanded.split()
        exe = parts[0] if parts else expanded

        # 1. Caminho absoluto
        if os.path.exists(exe):
            return True

        # 2. Só o nome do ficheiro — procurar no PATH
        basename = os.path.basename(exe).lower()
        if basename in SYSTEM_APP_PATHS_WHITELIST:
            return True  # app de sistema conhecida, não reportar

        # 3. Procurar no PATH do sistema
        import shutil
        if shutil.which(basename):
            return True

        # 4. Localizações comuns do Windows
        for base in [
            os.environ.get("SystemRoot", r"C:\Windows"),
            os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32"),
            os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "SysWOW64"),
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ]:
            if base and os.path.exists(os.path.join(base, basename)):
                return True

        return False
    except Exception:
        return False


def scan_registry_check(check_def, progress_callback=None):
    """Escaneia uma categoria de registo. Retorna lista de problemas."""
    issues = []
    if not WINREG_OK or platform.system() != "Windows":
        return issues

    check_type = check_def["check"]
    hive_str = check_def["hive"]
    reg_path = check_def["path"]
    label = check_def["label"]

    key = _open_key(hive_str, reg_path)
    if key is None:
        return issues

    try:
        if check_type == "file_exists":
            # Valores cujo dado aponta para um executável inexistente
            for name, data, vtype in _enum_values(key):
                if isinstance(data, str) and not _path_exists(data):
                    issues.append({
                        "label": label,
                        "hive": hive_str,
                        "path": reg_path,
                        "name": name,
                        "data": data,
                        "type": "value",
                        "description": f"Executável não encontrado: {data[:80]}",
                        "severity": "warning",
                    })

        elif check_type == "file_exists_values":
            for name, data, vtype in _enum_values(key):
                if isinstance(name, str) and not _path_exists(name):
                    issues.append({
                        "label": label,
                        "hive": hive_str,
                        "path": reg_path,
                        "name": name,
                        "data": str(data),
                        "type": "value",
                        "description": f"DLL não encontrada: {name[:80]}",
                        "severity": "info",
                    })

        elif check_type == "subkey_install_location":
            for subkey_name in _enum_subkeys(key):
                try:
                    sub = winreg.OpenKey(key, subkey_name)
                    install_loc = None
                    uninstall_str = None
                    try:
                        install_loc, _ = winreg.QueryValueEx(sub, "InstallLocation")
                    except OSError:
                        pass
                    try:
                        uninstall_str, _ = winreg.QueryValueEx(sub, "UninstallString")
                    except OSError:
                        pass
                    # Verifica se o local de instalação existe
                    if install_loc and not os.path.exists(os.path.expandvars(install_loc)):
                        display_name = subkey_name
                        try:
                            display_name, _ = winreg.QueryValueEx(sub, "DisplayName")
                        except Exception:
                            pass
                        issues.append({
                            "label": label,
                            "hive": hive_str,
                            "path": reg_path,
                            "name": subkey_name,
                            "data": install_loc,
                            "type": "subkey",
                            "description": f"Pasta de instalação inválida: {display_name}",
                            "severity": "warning",
                        })
                    sub.Close()
                except Exception:
                    pass

        elif check_type == "subkey_default_path":
            for subkey_name in _enum_subkeys(key):
                # Ignorar se o nome da subchave for uma app de sistema conhecida
                if subkey_name.lower() in SYSTEM_APP_PATHS_WHITELIST:
                    continue
                try:
                    sub = winreg.OpenKey(key, subkey_name)
                    default_path = None
                    try:
                        default_path, _ = winreg.QueryValueEx(sub, "")
                    except OSError:
                        pass
                    if default_path and not _path_exists(default_path):
                        issues.append({
                            "label": label,
                            "hive": hive_str,
                            "path": reg_path,
                            "name": subkey_name,
                            "data": default_path,
                            "type": "subkey",
                            "description": f"Aplicação não encontrada: {subkey_name}",
                            "severity": "info",
                        })
                    sub.Close()
                except Exception:
                    pass

        elif check_type == "mru_clear":
            # Conta entradas MRU
            values = _enum_values(key)
            if values:
                issues.append({
                    "label": label,
                    "hive": hive_str,
                    "path": reg_path,
                    "name": "_ALL_VALUES_",
                    "data": f"{len(values)} entradas",
                    "type": "key_values",
                    "description": f"{len(values)} documentos recentes guardados",
                    "severity": "info",
                })

    except Exception:
        pass
    finally:
        key.Close()

    return issues


def delete_registry_issue(issue):
    """
    Remove uma entrada de registo problemática.
    Retorna (sucesso, msg)
    """
    if not WINREG_OK or platform.system() != "Windows":
        return False, "winreg não disponível"

    hive = HIVES.get(issue["hive"])
    if hive is None:
        return False, "Hive inválido"

    try:
        if issue["type"] == "value":
            key = winreg.OpenKey(hive, issue["path"], 0,
                                  winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY)
            winreg.DeleteValue(key, issue["name"])
            key.Close()
            return True, None

        elif issue["type"] == "subkey":
            key = winreg.OpenKey(hive, issue["path"], 0,
                                  winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY)
            winreg.DeleteKey(key, issue["name"])
            key.Close()
            return True, None

        elif issue["type"] == "key_values":
            # Limpa todos os valores de uma chave
            key = winreg.OpenKey(hive, issue["path"], 0,
                                  winreg.KEY_WRITE | winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            values = _enum_values(key)
            for name, _, _ in values:
                try:
                    winreg.DeleteValue(key, name)
                except Exception:
                    pass
            key.Close()
            return True, None

        else:
            return False, "Tipo desconhecido"

    except PermissionError as e:
        return False, f"Sem permissão: {e}"
    except Exception as e:
        return False, str(e)


def scan_all_registry(progress_callback=None):
    """Analisa todas as categorias de registo."""
    all_issues = []
    total = len(REGISTRY_CHECKS)

    for i, check_def in enumerate(REGISTRY_CHECKS):
        if progress_callback:
            progress_callback(i, total, f"Registo: {check_def['label']}...")
        issues = scan_registry_check(check_def)
        all_issues.extend(issues)
        if progress_callback:
            progress_callback(i + 1, total, f"{check_def['label']}: {len(issues)} problemas")

    return all_issues
