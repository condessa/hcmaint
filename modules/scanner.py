"""
HCMaint - Módulo de Análise e Limpeza Linux (Debian/Ubuntu)
Detecta e remove ficheiros desnecessários no sistema
"""

import os
import subprocess
import shutil
import glob
from pathlib import Path


# ─── Utilitários ───────────────────────────────────────────────

def run(cmd, sudo=False, timeout=30):
    """Executa comando e retorna (returncode, stdout, stderr)."""
    if sudo and os.geteuid() != 0:
        cmd = ["sudo", "-n"] + (cmd if isinstance(cmd, list) else cmd.split())
    try:
        r = subprocess.run(
            cmd if isinstance(cmd, list) else cmd,
            shell=isinstance(cmd, str),
            capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)


def get_dir_size(path):
    """Retorna tamanho em bytes de uma pasta (sem seguir symlinks)."""
    total = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_symlink():
                    continue
                if entry.is_file():
                    total += entry.stat().st_size
                elif entry.is_dir():
                    total += get_dir_size(entry.path)
            except (PermissionError, OSError):
                pass
    except (PermissionError, OSError):
        pass
    return total


def get_path_size(path):
    """Tamanho de ficheiro ou pasta."""
    try:
        p = Path(path)
        if not p.exists():
            return 0
        if p.is_file():
            return p.stat().st_size
        return get_dir_size(path)
    except Exception:
        return 0


def fmt(size_bytes):
    """Bytes → string legível."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    else:
        return f"{size_bytes / 1024 ** 3:.2f} GB"


def has_cmd(cmd):
    return shutil.which(cmd) is not None


def is_root():
    return os.geteuid() == 0


def sudo_available():
    """Verifica se sudo está disponível sem senha (NOPASSWD) ou se já somos root."""
    if is_root():
        return True
    rc, _, _ = run(["sudo", "-n", "true"])
    return rc == 0


# ─── Categorias de análise ─────────────────────────────────────

def scan_apt_cache():
    """Cache de pacotes APT em /var/cache/apt/archives/"""
    path = "/var/cache/apt/archives"
    size = get_path_size(path)
    # Contar ficheiros .deb
    try:
        debs = list(glob.glob(f"{path}/*.deb"))
        count = len(debs)
    except Exception:
        count = 0
    return {
        "key": "apt_cache",
        "label": "Cache APT (pacotes .deb)",
        "icon": "📦",
        "size": size,
        "count": count,
        "details": f"{count} pacotes em cache",
        "paths": [path],
        "clean_cmd": ["apt-get", "clean"],
        "needs_sudo": True,
        "safe": True,
    }


def scan_apt_orphans():
    """Pacotes instalados mas não necessários (autoremove)."""
    if not has_cmd("apt-get"):
        return None

    packages = []
    size_estimate = 0

    # apt-get --simulate autoremove: linhas "Remv pkg" ou "Purg pkg"
    rc, out, err = run("apt-get --simulate autoremove 2>/dev/null")
    if rc == 0 and out:
        for line in out.splitlines():
            line = line.strip()
            if line.startswith(("Remv ", "Purg ")):
                parts = line.split()
                if len(parts) >= 2:
                    pkg = parts[1].split(":")[0]
                    if pkg and pkg not in packages:
                        packages.append(pkg)

    # Fallback: secção "The following packages will be REMOVED"
    if not packages and out:
        in_section = False
        for line in out.splitlines():
            if "will be REMOVED" in line or "serão REMOVIDOS" in line or "wurden ENTFERNT" in line:
                in_section = True
                continue
            if in_section:
                if line.startswith(" ") or line.startswith("  "):
                    for pkg in line.strip().split():
                        pkg = pkg.strip("*").split(":")[0]
                        if pkg and pkg not in packages:
                            packages.append(pkg)
                elif line and not line[0].isspace():
                    in_section = False

    # Estimar tamanho via dpkg-query
    if packages:
        rc2, out2, _ = run(
            ["dpkg-query", "-Wf", "${Installed-Size}\t${Package}\n"] + packages[:100]
        )
        if rc2 == 0:
            for line in out2.splitlines():
                parts = line.split("\t")
                if len(parts) == 2:
                    try:
                        size_estimate += int(parts[0]) * 1024
                    except Exception:
                        pass

    # Se nenhum pacote detectado mas apt-get autoremove retorna algo,
    # estimar via df /usr antes/depois seria invasivo — reportar 0 e deixar
    # o utilizador confirmar manualmente pela saída do terminal.
    return {
        "key": "apt_orphans",
        "label": "Pacotes Órfãos (autoremove)",
        "icon": "🗑️",
        "size": size_estimate,
        "count": len(packages),
        "details": f"{len(packages)} pacotes desnecessários" if packages else "Nenhum órfão detectado (ou requer sudo para análise completa)",
        "paths": [],
        "packages": packages,
        "clean_cmd": ["apt-get", "autoremove", "--purge", "-y"],
        "needs_sudo": True,
        "safe": True,
    }


def scan_journal_logs():
    """Logs do systemd journal — só mostra o que pode ser removido (>30 dias)."""
    if not has_cmd("journalctl"):
        return None

    import re

    # Tamanho total actual
    total_size = 0
    rc, out, _ = run(["journalctl", "--disk-usage"])
    if rc == 0:
        m = re.search(r"take up ([0-9.]+)([BKMGT])", out)
        if m:
            val = float(m.group(1))
            unit = m.group(2)
            mult = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
            total_size = int(val * mult.get(unit, 1))

    # Simular vacuum para saber quanto seria libertado
    freed_size = 0
    rc2, out2, _ = run(["journalctl", "--vacuum-time=30d", "--dry-run"],
                        timeout=15)
    # Se --dry-run não existir, tentar sem ele mas parsear o output
    if rc2 != 0:
        # Parsear: "Freed X.XM..."
        for line in out2.splitlines():
            m2 = re.search(r"[Ff]reed[ ]+([0-9.]+)([BKMGT])", line)
            if m2:
                val = float(m2.group(1))
                unit = m2.group(2)
                mult = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
                freed_size += int(val * mult.get(unit, 1))
    else:
        for line in out2.splitlines():
            m2 = re.search(r"[Ff]reed[ ]+([0-9.]+)([BKMGT])", line)
            if m2:
                val = float(m2.group(1))
                unit = m2.group(2)
                mult = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
                freed_size += int(val * mult.get(unit, 1))

    # Se não conseguiu simular, estimar: total > 512MB provavelmente tem logs velhos
    # Mas se total < 200MB e não há confirmação, assumir 0 removível
    removable = freed_size
    if removable == 0 and total_size > 512 * 1024 * 1024:
        # Conservador: estimar 30% removível
        removable = total_size // 3

    if removable == 0:
        details = f"Total: {fmt(total_size)}  •  Todos recentes (<30 dias)"
    else:
        details = f"Total: {fmt(total_size)}  •  ~{fmt(removable)} com >30 dias"

    return {
        "key": "journal_logs",
        "label": "Logs do Systemd (journal)",
        "icon": "📋",
        "size": removable,          # só o removível
        "total_size": total_size,   # informativo
        "count": 0,
        "details": details,
        "paths": ["/var/log/journal"],
        "clean_cmd": ["journalctl", "--vacuum-time=30d"],
        "needs_sudo": True,
        "safe": True,
    }


def scan_var_logs():
    """Logs em /var/log/ (ficheiros .gz e .old antigos)."""
    path = "/var/log"
    size = 0
    files = []
    try:
        for root, dirs, filenames in os.walk(path):
            for f in filenames:
                if f.endswith((".gz", ".1", ".old", ".2", ".3", ".4")):
                    fp = os.path.join(root, f)
                    try:
                        sz = os.path.getsize(fp)
                        size += sz
                        files.append(fp)
                    except Exception:
                        pass
    except PermissionError:
        pass
    return {
        "key": "var_logs",
        "label": "Logs Antigos (/var/log/)",
        "icon": "🗒️",
        "size": size,
        "count": len(files),
        "details": f"{len(files)} ficheiros de log antigos",
        "paths": files[:200],
        "clean_cmd": None,  # manual
        "needs_sudo": True,
        "safe": True,
        "files_list": files,
    }


def scan_user_cache():
    """Cache do utilizador em ~/.cache/"""
    home = str(Path.home())
    cache_path = os.path.join(home, ".cache")
    if not os.path.exists(cache_path):
        return None

    size = 0
    subdirs = []
    try:
        for entry in os.scandir(cache_path):
            if entry.is_dir():
                sz = get_dir_size(entry.path)
                subdirs.append((entry.name, sz, entry.path))
                size += sz
            elif entry.is_file():
                try:
                    sz = entry.stat().st_size
                    size += sz
                except Exception:
                    pass
    except Exception:
        pass

    subdirs.sort(key=lambda x: x[1], reverse=True)
    top = ", ".join(f"{n} ({fmt(s)})" for n, s, _ in subdirs[:4])

    return {
        "key": "user_cache",
        "label": "Cache do Utilizador (~/.cache/)",
        "icon": "🗃️",
        "size": size,
        "count": len(subdirs),
        "details": top or f"{fmt(size)} em cache",
        "paths": [cache_path],
        "subdirs": subdirs,
        "clean_cmd": None,  # granular
        "needs_sudo": False,
        "safe": False,  # requer selecção cuidadosa
    }


def scan_thumbnails():
    """Miniaturas em ~/.cache/thumbnails/"""
    home = str(Path.home())
    path = os.path.join(home, ".cache", "thumbnails")
    if not os.path.exists(path):
        path = os.path.join(home, ".thumbnails")
    if not os.path.exists(path):
        return None
    size = get_dir_size(path)
    count = sum(1 for _ in Path(path).rglob("*.png"))
    return {
        "key": "thumbnails",
        "label": "Miniaturas de Imagens",
        "icon": "🖼️",
        "size": size,
        "count": count,
        "details": f"{count} miniaturas",
        "paths": [path],
        "clean_cmd": None,
        "needs_sudo": False,
        "safe": True,
    }


def scan_trash():
    """Reciclagem do utilizador."""
    home = str(Path.home())
    trash = os.path.join(home, ".local", "share", "Trash", "files")
    if not os.path.exists(trash):
        return None
    size = get_dir_size(trash)
    try:
        count = len(list(os.scandir(trash)))
    except Exception:
        count = 0
    return {
        "key": "trash",
        "label": "Reciclagem (~/.local/share/Trash/)",
        "icon": "🗑️",
        "size": size,
        "count": count,
        "details": f"{count} item(ns) na reciclagem",
        "paths": [os.path.join(home, ".local", "share", "Trash")],
        "clean_cmd": None,
        "needs_sudo": False,
        "safe": True,
    }


def scan_flatpak_unused():
    """Runtimes Flatpak não utilizados — confia exclusivamente no flatpak."""
    if not has_cmd("flatpak"):
        return None

    import re

    unused_refs = []
    unused_size = 0

    # Simular "flatpak uninstall --unused" com resposta "n" para ver o que
    # seria removido sem remover nada
    try:
        proc = subprocess.Popen(
            ["flatpak", "uninstall", "--unused"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        output, _ = proc.communicate(input="n\n", timeout=15)
    except Exception:
        output = ""

    # Parsear linhas "N. runtime/ID/arch/branch" ou "  ID"
    for line in output.splitlines():
        stripped = line.strip()
        m = re.match(r"^\d+[.)]\s+([\w./\-]+)", stripped)
        if m:
            ref = m.group(1)
            unused_refs.append(ref)
        elif stripped.startswith("runtime/") or stripped.startswith("app/"):
            unused_refs.append(stripped)

    # Listar runtimes com tamanho
    rc2, out2, _ = run(["flatpak", "list", "--runtime",
                         "--columns=application,branch,size"])
    all_runtimes = []
    if rc2 == 0:
        for line in out2.splitlines():
            parts = [p.strip() for p in line.split("\t")]
            if len(parts) >= 3:
                app_id = parts[0]
                branch = parts[1]
                size_str = parts[2]
                m2 = re.search(r"([0-9.,]+)\s*(MB|GB|KB|B)", size_str)
                sz = 0
                if m2:
                    val = float(m2.group(1).replace(",", "."))
                    unit = m2.group(2)
                    mult = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
                    sz = int(val * mult.get(unit, 0))
                all_runtimes.append({
                    "id": app_id, "branch": branch,
                    "size": sz, "size_str": size_str
                })

    # Tamanho dos marcados
    for rt in all_runtimes:
        if any(rt["id"] in ref for ref in unused_refs):
            unused_size += rt["size"]

    count = len(unused_refs)

    if count == 0:
        details = "Nenhum runtime obsoleto — flatpak está limpo"
        unused_size = 0
    else:
        details = f"{count} runtimes removíveis pelo flatpak"

    return {
        "key": "flatpak_unused",
        "label": "Runtimes Flatpak Não Usados",
        "icon": "📱",
        "size": unused_size,
        "count": count,
        "details": details,
        "paths": ["/var/lib/flatpak",
                   os.path.expanduser("~/.local/share/flatpak")],
        "clean_cmd": ["flatpak", "uninstall", "--unused", "-y"],
        "needs_sudo": False,
        "safe": True,
        "unused_refs": unused_refs,
        "all_runtimes": all_runtimes,
        "total_flatpak_size": sum(r["size"] for r in all_runtimes),
    }


def scan_snap_cache():
    """Cache e versões antigas de Snaps — só mostra o removível."""
    if not has_cmd("snap"):
        return None

    snap_cache = "/var/lib/snapd/cache"
    snaps_dir  = "/var/lib/snapd/snaps"
    cache_size = get_path_size(snap_cache) if os.path.exists(snap_cache) else 0

    # Snaps que NUNCA podem ser removidos enquanto há outros snaps activos
    SYSTEM_SNAPS = {"snapd", "core", "core16", "core18", "core20", "core22", "core24", "core26", "bare"}

    # Listar versões desactivadas
    rc, out, _ = run(["snap", "list", "--all"])
    removable   = []   # podem ser removidos
    blocked     = []   # são dependências obrigatórias
    removable_size = 0

    if rc == 0:
        for line in out.splitlines()[1:]:
            if "disabled" not in line:
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            snap_name = parts[0]
            revision  = parts[2]

            # Verificar se é snap de sistema não removível
            is_system = snap_name in SYSTEM_SNAPS or snap_name.startswith("core")

            # Verificar se alguma app activa depende deste snap
            # (snap list --all mostra a versão activa na mesma linha sem "disabled")
            snap_file = os.path.join(snaps_dir, f"{snap_name}_{revision}.snap")
            sz = get_path_size(snap_file) if os.path.exists(snap_file) else 0

            if is_system:
                # Tentar perceber se ainda é dependência — se existe versão mais nova activa
                # e há apps que dependem, está bloqueado
                blocked.append({"name": snap_name, "rev": revision, "size": sz, "reason": "snap de sistema"})
            else:
                removable.append({"name": snap_name, "rev": revision, "size": sz})
                removable_size += sz

    # Cache de download — ficheiros .snap que já foram instalados
    # Só contar se não coincidirem com snaps activos
    removable_cache = 0
    try:
        for f in os.listdir(snap_cache):
            if f.endswith(".snap") or f.endswith(".assert"):
                removable_cache += get_path_size(os.path.join(snap_cache, f))
    except Exception:
        pass

    total_removable = removable_size + removable_cache
    count = len(removable)

    if count == 0 and removable_cache == 0:
        details = f"Nenhuma versão removível  •  {len(blocked)} snap(s) de sistema bloqueados"
    else:
        parts_det = []
        if count > 0:
            parts_det.append(f"{count} versões antigas ({fmt(removable_size)})")
        if removable_cache > 0:
            parts_det.append(f"Cache: {fmt(removable_cache)}")
        details = "  •  ".join(parts_det)

    return {
        "key": "snap_cache",
        "label": "Cache e Versões Antigas de Snap",
        "icon": "🔩",
        "size": total_removable,
        "count": count,
        "details": details,
        "paths": [snap_cache, snaps_dir],
        "clean_cmd": None,
        "needs_sudo": True,
        "safe": True,
        "disabled_snaps": [d["name"] for d in removable],
        "disabled_detail": removable,
        "blocked_snaps": blocked,
    }


def scan_docker():
    """Imagens, volumes e containers Docker parados."""
    if not has_cmd("docker"):
        return None

    # Containers parados
    rc, out, _ = run(["docker", "ps", "-a", "--filter", "status=exited", "--format", "{{.ID}}"])
    stopped = [l.strip() for l in out.splitlines() if l.strip()] if rc == 0 else []

    # Imagens dangling
    rc2, out2, _ = run(["docker", "images", "--filter", "dangling=true", "-q"])
    dangling = [l.strip() for l in out2.splitlines() if l.strip()] if rc2 == 0 else []

    # Tamanho total do sistema Docker
    rc3, out3, _ = run(["docker", "system", "df", "--format", "{{.Size}}"])
    size = 0

    rc4, out4, _ = run(["docker", "system", "df"])
    import re
    for line in (out4 or "").splitlines():
        m = re.search(r"([\d.]+)(GB|MB|KB|B)\b", line)
        if m:
            val = float(m.group(1))
            unit = m.group(2)
            mult = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
            size += int(val * mult.get(unit, 0))

    return {
        "key": "docker",
        "label": "Docker (containers/imagens parados)",
        "icon": "🐳",
        "size": size,
        "count": len(stopped) + len(dangling),
        "details": f"{len(stopped)} containers parados  •  {len(dangling)} imagens dangling",
        "paths": [],
        "clean_cmd": ["docker", "system", "prune", "-f"],
        "needs_sudo": False,
        "safe": True,
        "stopped": stopped,
        "dangling": dangling,
    }


def scan_python_cache():
    """Ficheiros __pycache__ e .pyc em ~/Programas/ e home."""
    home = str(Path.home())
    search_dirs = [
        os.path.join(home, "Programas"),
        home,
    ]
    total_size = 0
    total_count = 0
    all_paths = []
    for base in search_dirs:
        if not os.path.exists(base):
            continue
        try:
            for root, dirs, files in os.walk(base):
                # Ignorar node_modules, .git, venvs
                dirs[:] = [d for d in dirs if d not in
                           ("node_modules", ".git", "venv", ".venv", "env", ".env")]
                if "__pycache__" in dirs:
                    p = os.path.join(root, "__pycache__")
                    sz = get_dir_size(p)
                    total_size += sz
                    total_count += 1
                    all_paths.append(p)
                for f in files:
                    if f.endswith(".pyc"):
                        fp = os.path.join(root, f)
                        try:
                            sz = os.path.getsize(fp)
                            total_size += sz
                            total_count += 1
                            all_paths.append(fp)
                        except Exception:
                            pass
        except PermissionError:
            pass

    return {
        "key": "python_cache",
        "label": "Cache Python (__pycache__ / .pyc)",
        "icon": "🐍",
        "size": total_size,
        "count": total_count,
        "details": f"{total_count} entradas em ~/Programas",
        "paths": all_paths[:500],
        "clean_cmd": None,
        "needs_sudo": False,
        "safe": True,
        "files_list": all_paths,
    }


def scan_disk_usage_top():
    """Top 10 maiores pastas em ~ e /var."""
    results = []
    for base in [str(Path.home()), "/var"]:
        try:
            rc, out, _ = run(
                f"du -sh {base}/* 2>/dev/null | sort -rh | head -8",
            )
            if rc == 0:
                for line in out.splitlines():
                    parts = line.split("\t", 1)
                    if len(parts) == 2:
                        results.append((parts[0], parts[1]))
        except Exception:
            pass
    return results


# ─── Executores de limpeza ─────────────────────────────────────

def run_in_terminal(cmd_str, title="HCMaint", log_cb=None):
    """Abre um terminal externo para comandos sudo interactivos."""
    terminals = [
        ["x-terminal-emulator", "-e"],
        ["gnome-terminal", "--"],
        ["xterm", "-title", title, "-e"],
        ["konsole", "-e"],
        ["xfce4-terminal", "-e"],
    ]
    for term in terminals:
        if has_cmd(term[0]):
            try:
                full_cmd = term + ["bash", "-c", f"{cmd_str}; echo; echo 'Prima ENTER para fechar...'; read"]
                subprocess.Popen(full_cmd)
                if log_cb:
                    log_cb(f"   Terminal aberto: {term[0]}", "muted")
                return True
            except Exception:
                pass
    if log_cb:
        log_cb("   ⚠️  Nenhum terminal encontrado — execute manualmente:", "warn")
        log_cb(f"   $ {cmd_str}", "warn")
    return False



def clean_apt_cache(log_cb=None):
    """Limpa cache APT (/var/cache/apt/archives/)."""
    _log(log_cb, "A limpar cache APT...")

    if is_root():
        cmd = ["apt-get", "clean"]
    elif has_cmd("pkexec"):
        cmd = ["pkexec", "apt-get", "clean"]
    else:
        cmd = ["sudo", "apt-get", "clean"]

    rc, out, err = run(cmd, timeout=60)
    if rc == 0:
        _log(log_cb, "✅ Cache APT limpa", "ok")
        return True, "Cache APT limpa"
    _log(log_cb, f"❌ Erro: {err or out}", "error")
    return False, err or out


def clean_apt_orphans(log_cb=None):
    """Remove pacotes órfãos. Abre terminal visível para interacção se necessário."""
    _log(log_cb, "A remover pacotes órfãos (apt-get autoremove --purge)...")

    if is_root():
        base_cmd = ["apt-get", "autoremove", "--purge", "-y"]
    else:
        # Verificar se pkexec está disponível (GUI sudo)
        if has_cmd("pkexec"):
            base_cmd = ["pkexec", "apt-get", "autoremove", "--purge", "-y"]
        elif has_cmd("sudo"):
            base_cmd = ["sudo", "apt-get", "autoremove", "--purge", "-y"]
        else:
            _log(log_cb, "❌ Sem sudo nem pkexec disponível", "error")
            return False, "Sem privilégios"

    try:
        env = os.environ.copy()
        env["DEBIAN_FRONTEND"] = "noninteractive"
        env["APT_LISTCHANGES_FRONTEND"] = "none"

        proc = subprocess.Popen(
            base_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        removed_count = 0
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            # Mostrar linhas relevantes no log
            if any(kw in line for kw in ("Removing", "Purg", "Removed",
                                          "A remover", "Removido",
                                          "freed", "libertad", "kB freed")):
                _log(log_cb, f"   {line}", "warn")
                if "Removing" in line or "A remover" in line:
                    removed_count += 1
            elif line.startswith("E:") or line.startswith("Err:"):
                _log(log_cb, f"   {line}", "error")

        proc.wait(timeout=180)
        if proc.returncode == 0:
            _log(log_cb, f"✅ Pacotes órfãos removidos ({removed_count} pacotes)", "ok")
            return True, "Pacotes órfãos removidos"
        else:
            _log(log_cb, f"❌ apt-get retornou código {proc.returncode}", "error")
            return False, f"Código de saída: {proc.returncode}"
    except subprocess.TimeoutExpired:
        _log(log_cb, "❌ Timeout — operação demorou demasiado", "error")
        return False, "Timeout"
    except Exception as e:
        _log(log_cb, f"❌ Erro: {e}", "error")
        return False, str(e)


def clean_journal_logs(keep_days=30, log_cb=None):
    """Limpa logs journal mais antigos que keep_days dias."""
    _log(log_cb, f"A limpar logs journal (mantendo últimos {keep_days} dias)...")

    cmd_base = ["journalctl", f"--vacuum-time={keep_days}d"]
    if is_root():
        cmd = cmd_base
    elif has_cmd("pkexec"):
        cmd = ["pkexec"] + cmd_base
    else:
        cmd = ["sudo"] + cmd_base

    rc, out, err = run(cmd, timeout=60)
    msg = out or err or ""
    if rc == 0:
        # Extrair linha de resumo do journalctl
        for line in msg.splitlines():
            if "freed" in line or "libertad" in line or "Deleted" in line or "Vacuuming" in line:
                _log(log_cb, f"   {line}", "muted")
        _log(log_cb, "✅ Logs journal limpos", "ok")
        return True, msg
    _log(log_cb, f"❌ Erro: {err or out}", "error")
    return False, err or out


def clean_var_logs(log_cb=None):
    _log(log_cb, "A remover logs antigos de /var/log/...")
    removed = 0
    freed = 0
    for pattern in ["/var/log/**/*.gz", "/var/log/**/*.1",
                    "/var/log/**/*.old"]:
        for f in glob.glob(pattern, recursive=True):
            try:
                sz = os.path.getsize(f)
                os.remove(f)
                removed += 1
                freed += sz
            except Exception:
                pass
    _log(log_cb, f"✅ {removed} ficheiros removidos ({fmt(freed)} libertados)", "ok")
    return True, f"{removed} ficheiros removidos"


def clean_thumbnails(log_cb=None):
    home = str(Path.home())
    for path in [
        os.path.join(home, ".cache", "thumbnails"),
        os.path.join(home, ".thumbnails"),
    ]:
        if os.path.exists(path):
            _log(log_cb, f"A limpar miniaturas em {path}...")
            try:
                shutil.rmtree(path)
                os.makedirs(path, exist_ok=True)
                _log(log_cb, "✅ Miniaturas limpas", "ok")
                return True, "Miniaturas removidas"
            except Exception as e:
                _log(log_cb, f"❌ {e}", "error")
                return False, str(e)
    return True, "Nenhuma miniatura encontrada"


def clean_trash(log_cb=None):
    home = str(Path.home())
    trash = os.path.join(home, ".local", "share", "Trash")
    _log(log_cb, "A esvaziar reciclagem...")
    freed = 0
    if os.path.exists(trash):
        freed = get_dir_size(trash)
        try:
            shutil.rmtree(trash)
            os.makedirs(os.path.join(trash, "files"), exist_ok=True)
            os.makedirs(os.path.join(trash, "info"), exist_ok=True)
            _log(log_cb, f"✅ Reciclagem esvaziada ({fmt(freed)})", "ok")
            return True, f"Reciclagem esvaziada ({fmt(freed)})"
        except Exception as e:
            _log(log_cb, f"❌ {e}", "error")
            return False, str(e)
    return True, "Reciclagem já estava vazia"


def clean_user_cache_subdir(subdir_path, log_cb=None):
    _log(log_cb, f"A limpar {subdir_path}...")
    try:
        freed = get_dir_size(subdir_path)
        shutil.rmtree(subdir_path)
        _log(log_cb, f"✅ {os.path.basename(subdir_path)} limpo ({fmt(freed)})", "ok")
        return True, fmt(freed)
    except Exception as e:
        _log(log_cb, f"❌ {e}", "error")
        return False, str(e)


def clean_flatpak_unused(log_cb=None, unused_refs=None):
    """Remove runtimes Flatpak não utilizados com output em tempo real."""
    _log(log_cb, "A remover runtimes Flatpak não utilizados...")

    try:
        cmd = ["flatpak", "uninstall", "--unused", "-y"]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        removed = 0
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            if any(kw in line for kw in ("Uninstall", "Removing", "runtime", "app")):
                _log(log_cb, f"   {line}", "warn")
                if "Uninstall" in line or "Removing" in line:
                    removed += 1
            elif line.startswith("error") or line.startswith("Error"):
                _log(log_cb, f"   {line}", "error")
            else:
                _log(log_cb, f"   {line}", "muted")

        proc.wait(timeout=120)
        if proc.returncode == 0:
            _log(log_cb, f"✅ Flatpak limpo — {removed} itens removidos", "ok")
            return True, f"{removed} itens removidos"
        else:
            # rc != 0 pode acontecer se "Nothing to do" — verificar output
            _log(log_cb, "ℹ️  flatpak: nada a remover ou já limpo", "info")
            return True, "Nada a remover"
    except Exception as e:
        _log(log_cb, f"❌ Erro: {e}", "error")
        return False, str(e)


def clean_python_cache(paths, log_cb=None):
    _log(log_cb, "A remover __pycache__ e .pyc...")
    removed = 0
    freed = 0
    for p in paths:
        try:
            if os.path.isdir(p):
                freed += get_dir_size(p)
                shutil.rmtree(p)
            elif os.path.isfile(p):
                freed += os.path.getsize(p)
                os.remove(p)
            removed += 1
        except Exception:
            pass
    _log(log_cb, f"✅ {removed} entradas removidas ({fmt(freed)})", "ok")
    return True, f"{removed} entradas removidas ({fmt(freed)})"


def clean_docker_prune(log_cb=None):
    _log(log_cb, "A limpar Docker (prune)...")
    rc, out, err = run(["docker", "system", "prune", "-f"], timeout=60)
    if rc == 0:
        _log(log_cb, f"✅ Docker limpo: {out[:80]}", "ok")
        return True, out
    _log(log_cb, f"❌ {err}", "error")
    return False, err


def clean_snap_old(disabled_snaps, log_cb=None):
    """Remove versões desactivadas de Snaps."""
    _log(log_cb, f"A remover {len(disabled_snaps)} versões antigas de Snaps...")
    removed = 0
    failed = 0
    for snap in disabled_snaps:
        _log(log_cb, f"   Remover snap: {snap}...", "muted")
        if is_root():
            cmd = ["snap", "remove", snap]
        elif has_cmd("pkexec"):
            cmd = ["pkexec", "snap", "remove", snap]
        else:
            cmd = ["sudo", "snap", "remove", snap]
        rc, out, err = run(cmd, timeout=60)
        if rc == 0:
            removed += 1
            _log(log_cb, f"   ✅ {snap} removido", "ok")
        else:
            failed += 1
            _log(log_cb, f"   ❌ {snap}: {err or out}", "error")
    _log(log_cb, f"✅ {removed} snaps removidos, {failed} erros", "ok")
    return True, f"{removed} snaps removidos"


def _log(cb, msg, tag="recv"):
    if cb:
        cb(msg, tag)


# ─── Análise completa ──────────────────────────────────────────

SCANNERS = [
    scan_apt_cache,
    scan_apt_orphans,
    scan_journal_logs,
    scan_var_logs,
    scan_user_cache,
    scan_thumbnails,
    scan_trash,
    scan_flatpak_unused,
    scan_snap_cache,
    scan_docker,
    scan_python_cache,
]


def scan_all(progress_cb=None):
    """Corre todos os scanners. Retorna lista de resultados."""
    results = []
    total = len(SCANNERS)
    for i, scanner in enumerate(SCANNERS):
        if progress_cb:
            progress_cb(i, total, f"A analisar: {scanner.__name__.replace('scan_', '').replace('_', ' ').title()}...")
        try:
            result = scanner()
            if result:
                results.append(result)
        except Exception as e:
            pass
        if progress_cb:
            progress_cb(i + 1, total, "")
    return results
