"""
HCCleaner - Módulo Desinstalador de Programas
Lista todos os programas instalados, desinstala com ou sem desinstalador oficial,
e limpa ficheiros/registo residuais automaticamente após desinstalação.
"""

import os
import re
import shutil
import subprocess
import platform
import time
from pathlib import Path

try:
    import winreg
    WINREG_OK = True
except ImportError:
    WINREG_OK = False


UNINSTALL_PATHS = [
    (winreg.HKEY_LOCAL_MACHINE if WINREG_OK else None,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", False),
    (winreg.HKEY_LOCAL_MACHINE if WINREG_OK else None,
     r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", False),
    (winreg.HKEY_CURRENT_USER if WINREG_OK else None,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", True),
]

# Programas protegidos que requerem método especial (não têm desinstalador normal)
PROTECTED_PROGRAMS = {
    "microsoft edge": "edge",
    "microsoft edge webview2": "edge_webview",
    "internet explorer": "ie",
    "windows subsystem for linux": "wsl",
}

# Pastas de instalação padrão para pesquisa de residuais
INSTALL_BASE_DIRS = [
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
    os.path.join(os.environ.get("APPDATA", ""), ""),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), ""),
]

# Chaves de registo a pesquisar para residuais
REGISTRY_RESIDUAL_PATHS = [
    (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", ["HKLM", "HKCU"]),
    (r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", ["HKLM"]),
    (r"SOFTWARE", ["HKCU", "HKLM"]),
    (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", ["HKCU", "HKLM"]),
    (r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce", ["HKCU", "HKLM"]),
    (r"SOFTWARE\Classes\Installer\Products", ["HKLM"]),
    (r"SOFTWARE\Classes\Installer\Features", ["HKLM"]),
]


def _read_value(key, name, default=""):
    try:
        val, _ = winreg.QueryValueEx(key, name)
        return val if val else default
    except Exception:
        return default


def _hive_handle(hive_str):
    if not WINREG_OK:
        return None
    return {
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
        "HKCU": winreg.HKEY_CURRENT_USER,
        "HKCR": winreg.HKEY_CLASSES_ROOT,
    }.get(hive_str)


def get_installed_programs():
    """Retorna lista de todos os programas instalados."""
    programs = []
    seen = set()

    if not WINREG_OK or platform.system() != "Windows":
        return _get_demo_programs()

    for hive, path, is_user in UNINSTALL_PATHS:
        if hive is None:
            continue
        try:
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        except OSError:
            continue

        i = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(key, i)
                i += 1
            except OSError:
                break

            try:
                sub = winreg.OpenKey(key, subkey_name)
                name = _read_value(sub, "DisplayName")
                if not name or name in seen:
                    sub.Close()
                    continue

                uninstall_str = _read_value(sub, "UninstallString")
                quiet_str     = _read_value(sub, "QuietUninstallString")
                install_loc   = _read_value(sub, "InstallLocation")
                publisher     = _read_value(sub, "Publisher")

                system_component = _read_value(sub, "SystemComponent", "0")
                if system_component == "1":
                    sub.Close()
                    continue

                size_kb = _read_value(sub, "EstimatedSize", 0)
                try:
                    size_mb = round(int(size_kb) / 1024, 1)
                except Exception:
                    size_mb = 0

                install_date = _read_value(sub, "InstallDate", "")
                if install_date and len(install_date) == 8:
                    try:
                        install_date = f"{install_date[6:8]}/{install_date[4:6]}/{install_date[:4]}"
                    except Exception:
                        pass

                # Detectar se é programa protegido (sem desinstalador normal)
                name_lower = name.lower()
                protected_type = None
                for pat, ptype in PROTECTED_PROGRAMS.items():
                    if pat in name_lower:
                        protected_type = ptype
                        break

                has_uninstaller = bool(uninstall_str or quiet_str)

                programs.append({
                    "name": name,
                    "version": _read_value(sub, "DisplayVersion"),
                    "publisher": publisher,
                    "install_date": install_date,
                    "size_mb": size_mb,
                    "uninstall_string": uninstall_str or quiet_str,
                    "quiet_uninstall": quiet_str,
                    "install_location": install_loc,
                    "is_user": is_user,
                    "key_name": subkey_name,
                    "has_uninstaller": has_uninstaller,
                    "protected_type": protected_type,
                    "hive": "HKCU" if is_user else "HKLM",
                    "reg_path": path,
                })
                seen.add(name)
                sub.Close()
            except Exception:
                pass

        key.Close()

    programs.sort(key=lambda x: x["name"].lower())
    return programs


def _get_demo_programs():
    return [
        {"name": "Exemplo App 1", "version": "1.0.0", "publisher": "Demo",
         "install_date": "01/01/2024", "size_mb": 150.5,
         "uninstall_string": "", "quiet_uninstall": "", "install_location": "",
         "is_user": False, "key_name": "", "has_uninstaller": False,
         "protected_type": None, "hive": "HKLM", "reg_path": ""},
        {"name": "Microsoft Edge", "version": "124.0", "publisher": "Microsoft",
         "install_date": "01/01/2024", "size_mb": 450.0,
         "uninstall_string": "", "quiet_uninstall": "", "install_location": "",
         "is_user": False, "key_name": "", "has_uninstaller": False,
         "protected_type": "edge", "hive": "HKLM", "reg_path": ""},
    ]


# ─────────────────────────────────────────────
# DESINSTALAÇÃO NORMAL
# ─────────────────────────────────────────────

def uninstall_program(program, silent=False, callback=None):
    """
    Desinstala via desinstalador oficial e aguarda conclusão.
    Retorna (sucesso, mensagem)
    """
    if platform.system() != "Windows":
        return False, "Apenas disponível no Windows"

    uninstall_str = program.get("quiet_uninstall") if silent else program.get("uninstall_string")
    if not uninstall_str:
        uninstall_str = program.get("uninstall_string", "")

    if not uninstall_str:
        return False, "Sem desinstalador disponível"

    if callback:
        callback(f"A iniciar desinstalador de '{program['name']}'...")

    try:
        proc = subprocess.Popen(uninstall_str, shell=True)
        if callback:
            callback("Desinstalador em execução — aguardar conclusão...")
        proc.wait(timeout=300)  # espera até 5 minutos
        if callback:
            callback(f"Desinstalador concluído (código {proc.returncode})")
        return True, f"Desinstalação concluída (código {proc.returncode})"
    except subprocess.TimeoutExpired:
        return False, "Tempo limite excedido (>5min)"
    except Exception as e:
        return False, f"Erro: {e}"


# ─────────────────────────────────────────────
# DESINSTALAÇÃO FORÇADA (sem desinstalador)
# ─────────────────────────────────────────────

def force_uninstall(program, callback=None):
    """
    Remove um programa sem usar o seu desinstalador:
    1. Termina processos relacionados
    2. Remove pasta de instalação
    3. Remove entradas de registo
    Retorna (sucesso, relatorio_dict)
    """
    if platform.system() != "Windows":
        return False, {"error": "Apenas disponível no Windows"}

    name = program["name"]
    report = {
        "processes_killed": [],
        "folders_removed": [],
        "reg_keys_removed": [],
        "errors": [],
    }

    # ── 1. Terminar processos ──
    if callback:
        callback("🔴 A terminar processos relacionados...")
    _kill_related_processes(name, report, callback)

    # ── 2. Remover pasta de instalação ──
    if callback:
        callback("🗑️ A remover ficheiros de instalação...")
    _remove_install_folder(program, report, callback)

    # ── 3. Remover entradas de registo do programa ──
    if callback:
        callback("🔑 A limpar registo...")
    _remove_registry_entries(program, report, callback)

    success = len(report["folders_removed"]) > 0 or len(report["reg_keys_removed"]) > 0
    return success, report


def _kill_related_processes(prog_name, report, callback=None):
    """Termina processos cujo nome contém palavras-chave do programa."""
    keywords = _extract_keywords(prog_name)
    try:
        result = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.strip().splitlines():
            parts = line.strip('"').split('","')
            if len(parts) < 2:
                continue
            proc_name = parts[0]
            pid = parts[1]
            proc_lower = proc_name.lower()
            if any(kw in proc_lower for kw in keywords):
                try:
                    subprocess.run(["taskkill", "/F", "/PID", pid],
                                   capture_output=True, timeout=5, creationflags=0x08000000)
                    report["processes_killed"].append(proc_name)
                    if callback:
                        callback(f"   Processo terminado: {proc_name} (PID {pid})")
                except Exception as e:
                    report["errors"].append(f"Não foi possível terminar {proc_name}: {e}")
    except Exception as e:
        report["errors"].append(f"Erro ao listar processos: {e}")

    time.sleep(1)  # dar tempo ao SO para libertar ficheiros


def _remove_install_folder(program, report, callback=None):
    """Remove a pasta de instalação do programa."""
    folders_to_try = []

    # Pasta conhecida do registo
    install_loc = program.get("install_location", "")
    if install_loc and os.path.exists(install_loc):
        folders_to_try.append(install_loc)

    # Pesquisar por nome nas pastas base
    keywords = _extract_keywords(program["name"])
    for base in INSTALL_BASE_DIRS:
        if not os.path.exists(base):
            continue
        try:
            for entry in os.listdir(base):
                entry_lower = entry.lower()
                if any(kw in entry_lower for kw in keywords):
                    full = os.path.join(base, entry)
                    if os.path.isdir(full) and full not in folders_to_try:
                        folders_to_try.append(full)
        except (PermissionError, OSError):
            pass

    for folder in folders_to_try:
        if callback:
            callback(f"   A remover: {folder}")
        try:
            shutil.rmtree(folder, ignore_errors=False)
            report["folders_removed"].append(folder)
        except Exception as e:
            # Tentar com takeown + icacls primeiro
            try:
                subprocess.run(["takeown", "/f", folder, "/r", "/d", "S"],
                                capture_output=True, timeout=30, creationflags=0x08000000)
                subprocess.run(["icacls", folder, "/grant", "administrators:F", "/t"],
                                capture_output=True, timeout=30, creationflags=0x08000000)
                shutil.rmtree(folder, ignore_errors=True)
                report["folders_removed"].append(folder)
            except Exception as e2:
                report["errors"].append(f"Não foi possível remover {folder}: {e2}")


def _remove_registry_entries(program, report, callback=None):
    """Remove entradas de registo residuais do programa."""
    if not WINREG_OK:
        return

    keywords = _extract_keywords(program["name"])
    name = program["name"]

    # 1. Remover entrada de Uninstall conhecida
    key_name = program.get("key_name", "")
    reg_path = program.get("reg_path", "")
    hive_str = program.get("hive", "HKLM")

    if key_name and reg_path:
        hive = _hive_handle(hive_str)
        if hive:
            try:
                key = winreg.OpenKey(hive, reg_path, 0,
                                     winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY)
                winreg.DeleteKey(key, key_name)
                key.Close()
                report["reg_keys_removed"].append(f"{hive_str}\\{reg_path}\\{key_name}")
                if callback:
                    callback(f"   Registo removido: {key_name}")
            except Exception as e:
                report["errors"].append(f"Não foi possível remover chave Uninstall: {e}")

    # 2. Pesquisar outras entradas residuais por palavra-chave
    for reg_path_search, hives in REGISTRY_RESIDUAL_PATHS:
        for hive_str_s in hives:
            hive = _hive_handle(hive_str_s)
            if not hive:
                continue
            try:
                key = winreg.OpenKey(hive, reg_path_search, 0,
                                     winreg.KEY_READ | winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY)
                subkeys = []
                i = 0
                while True:
                    try:
                        subkeys.append(winreg.EnumKey(key, i))
                        i += 1
                    except OSError:
                        break

                for sk in subkeys:
                    sk_lower = sk.lower()
                    if any(kw in sk_lower for kw in keywords):
                        try:
                            _delete_key_recursive(key, sk)
                            report["reg_keys_removed"].append(
                                f"{hive_str_s}\\{reg_path_search}\\{sk}")
                            if callback:
                                callback(f"   Chave removida: {sk}")
                        except Exception as e:
                            report["errors"].append(f"Chave {sk}: {e}")
                key.Close()
            except (OSError, PermissionError):
                pass


def _delete_key_recursive(parent_key, subkey_name):
    """Remove uma chave de registo recursivamente."""
    try:
        key = winreg.OpenKey(parent_key, subkey_name, 0,
                             winreg.KEY_READ | winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY)
        subkeys = []
        i = 0
        while True:
            try:
                subkeys.append(winreg.EnumKey(key, i))
                i += 1
            except OSError:
                break
        for sk in subkeys:
            _delete_key_recursive(key, sk)
        key.Close()
    except Exception:
        pass
    winreg.DeleteKey(parent_key, subkey_name)


# ─────────────────────────────────────────────
# DESINSTALAÇÃO DO MICROSOFT EDGE
# ─────────────────────────────────────────────

def uninstall_edge(callback=None):
    """
    Remove o Microsoft Edge usando o seu próprio setup com flags especiais.
    Retorna (sucesso, mensagem)
    """
    if platform.system() != "Windows":
        return False, "Apenas Windows"

    if callback:
        callback("🔷 A localizar instalação do Edge...")

    # Localizar setup.exe do Edge
    edge_dirs = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application",
        r"C:\Program Files\Microsoft\Edge\Application",
    ]

    setup_path = None
    for base in edge_dirs:
        if not os.path.exists(base):
            continue
        # Procurar versão mais recente
        try:
            versions = sorted(
                [d for d in os.listdir(base) if re.match(r'^\d+\.\d+', d)],
                key=lambda v: [int(x) for x in v.split('.')[:4] if x.isdigit()],
                reverse=True
            )
            for ver in versions:
                candidate = os.path.join(base, ver, "Installer", "setup.exe")
                if os.path.exists(candidate):
                    setup_path = candidate
                    break
        except Exception:
            pass
        if setup_path:
            break

    if not setup_path:
        # Método alternativo: via winget
        if callback:
            callback("   Setup do Edge não encontrado. A tentar via winget...")
        return _uninstall_via_winget("Microsoft Edge", callback)

    if callback:
        callback(f"   Setup encontrado: {setup_path}")
        callback("   A executar desinstalação forçada do Edge...")

    try:
        # Flags especiais do Edge para desinstalação forçada
        cmd = [
            setup_path,
            "--uninstall",
            "--system-level",
            "--verbose-logging",
            "--force-uninstall",
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=120)
        if proc.returncode == 0:
            if callback:
                callback("✅ Edge desinstalado com sucesso")
            return True, "Microsoft Edge removido com sucesso"
        else:
            # Tentar modo user-level
            cmd2 = [setup_path, "--uninstall", "--verbose-logging", "--force-uninstall"]
            proc2 = subprocess.run(cmd2, capture_output=True, timeout=120)
            if proc2.returncode == 0:
                if callback:
                    callback("✅ Edge desinstalado (user-level)")
                return True, "Microsoft Edge removido (user-level)"
            return False, f"Edge: código de saída {proc2.returncode}"
    except subprocess.TimeoutExpired:
        return False, "Tempo limite excedido"
    except Exception as e:
        return False, f"Erro: {e}"


def _uninstall_via_winget(prog_name, callback=None):
    """Tenta desinstalar via winget."""
    try:
        result = subprocess.run(
            ["winget", "uninstall", "--name", prog_name, "--force", "--silent"],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode == 0:
            if callback:
                callback(f"✅ '{prog_name}' removido via winget")
            return True, f"'{prog_name}' removido via winget"
        else:
            return False, f"winget falhou: {result.stderr[:200]}"
    except FileNotFoundError:
        return False, "winget não disponível neste sistema"
    except Exception as e:
        return False, f"Erro winget: {e}"


# ─────────────────────────────────────────────
# LIMPEZA RESIDUAL PÓS-DESINSTALAÇÃO
# ─────────────────────────────────────────────

def clean_residuals(program, callback=None):
    """
    Após desinstalação, remove tudo o que ficou:
    - Pastas de dados do utilizador (AppData, ProgramData)
    - Entradas de registo residuais
    - Ficheiros temporários relacionados
    Retorna dict com relatório
    """
    report = {
        "folders_removed": [],
        "reg_keys_removed": [],
        "files_removed": [],
        "errors": [],
        "bytes_freed": 0,
    }

    name = program["name"]
    keywords = _extract_keywords(name)

    if callback:
        callback(f"🧹 A limpar resíduos de '{name}'...")

    # ── Pastas de dados do utilizador ──
    user_data_bases = [
        os.environ.get("APPDATA", ""),
        os.environ.get("LOCALAPPDATA", ""),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp"),
        r"C:\ProgramData",
        os.path.join(os.path.expanduser("~"), "AppData", "Roaming"),
        os.path.join(os.path.expanduser("~"), "AppData", "Local"),
    ]

    for base in user_data_bases:
        if not base or not os.path.exists(base):
            continue
        try:
            for entry in os.listdir(base):
                entry_lower = entry.lower()
                if any(kw in entry_lower for kw in keywords):
                    full = os.path.join(base, entry)
                    if os.path.isdir(full):
                        if callback:
                            callback(f"   A remover pasta: {full}")
                        try:
                            size = _folder_size(full)
                            shutil.rmtree(full, ignore_errors=True)
                            report["folders_removed"].append(full)
                            report["bytes_freed"] += size
                        except Exception as e:
                            report["errors"].append(f"{full}: {e}")
                    elif os.path.isfile(full):
                        try:
                            size = os.path.getsize(full)
                            os.remove(full)
                            report["files_removed"].append(full)
                            report["bytes_freed"] += size
                        except Exception as e:
                            report["errors"].append(f"{full}: {e}")
        except (PermissionError, OSError):
            pass

    # ── Registo residual ──
    if WINREG_OK:
        _remove_registry_entries(program, report, callback)

    # ── Pasta de instalação (se ainda existir) ──
    install_loc = program.get("install_location", "")
    if install_loc and os.path.exists(install_loc):
        if callback:
            callback(f"   Pasta de instalação ainda presente: {install_loc}")
        try:
            size = _folder_size(install_loc)
            shutil.rmtree(install_loc, ignore_errors=True)
            report["folders_removed"].append(install_loc)
            report["bytes_freed"] += size
        except Exception as e:
            report["errors"].append(f"{install_loc}: {e}")

    return report


def _folder_size(path):
    total = 0
    try:
        for dirpath, _, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except Exception:
                    pass
    except Exception:
        pass
    return total


def _extract_keywords(name):
    """Extrai palavras-chave de um nome de programa para pesquisa."""
    # Remover versões, parênteses, etc.
    clean = re.sub(r'\b(v\d+|\d+\.\d+[\.\d]*|x86|x64|bit|version|update|patch)\b', '', name, flags=re.I)
    clean = re.sub(r'[^\w\s]', ' ', clean)
    words = [w.lower() for w in clean.split() if len(w) >= 4]
    # Sempre incluir a primeira palavra significativa
    first = name.split()[0].lower() if name.split() else ""
    if first and first not in words and len(first) >= 3:
        words.insert(0, first)
    return list(dict.fromkeys(words))  # remover duplicados mantendo ordem


def open_programs_and_features():
    if platform.system() == "Windows":
        try:
            subprocess.Popen(["control", "appwiz.cpl"])
        except Exception:
            pass
