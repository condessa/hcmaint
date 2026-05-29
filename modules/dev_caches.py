"""
HCMaint - Módulo de Cache de Desenvolvimento
Detecta e limpa caches de ferramentas de desenvolvimento:
npm, cargo, gradle, maven, go, pip, composer, etc.
"""

import os
import shutil
from pathlib import Path


def get_dir_size(path):
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


def fmt(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    else:
        return f"{size_bytes / 1024 ** 3:.2f} GB"


HOME = str(Path.home())


# Definição de todas as caches de desenvolvimento
DEV_CACHE_DEFS = [
    {
        "key": "npm",
        "label": "npm (Node.js)",
        "icon": "📦",
        "paths": [
            os.path.join(HOME, ".npm"),
            os.path.join(HOME, ".npm/_cacache"),
        ],
        "safe": True,
        "description": "Cache de pacotes npm. Regenerada automaticamente.",
    },
    {
        "key": "yarn",
        "label": "Yarn",
        "icon": "🧶",
        "paths": [
            os.path.join(HOME, ".yarn/cache"),
            os.path.join(HOME, ".cache/yarn"),
        ],
        "safe": True,
        "description": "Cache de pacotes Yarn.",
    },
    {
        "key": "cargo",
        "label": "Cargo (Rust)",
        "icon": "🦀",
        "paths": [
            os.path.join(HOME, ".cargo/registry/cache"),
            os.path.join(HOME, ".cargo/registry/src"),
            os.path.join(HOME, ".cargo/git/db"),
        ],
        "safe": True,
        "description": "Cache de crates Rust. Regenerada ao compilar.",
    },
    {
        "key": "gradle",
        "label": "Gradle (Java/Android)",
        "icon": "☕",
        "paths": [
            os.path.join(HOME, ".gradle/caches"),
            os.path.join(HOME, ".gradle/wrapper/dists"),
        ],
        "safe": True,
        "description": "Cache de dependências Gradle. Pode ser grande em projectos Android.",
    },
    {
        "key": "maven",
        "label": "Maven (Java)",
        "icon": "☕",
        "paths": [
            os.path.join(HOME, ".m2/repository"),
        ],
        "safe": False,
        "description": "Repositório local Maven. Contém JARs — limpar obriga a re-descarregar tudo.",
    },
    {
        "key": "go_mod",
        "label": "Go Modules",
        "icon": "🐹",
        "paths": [
            os.path.join(HOME, "go/pkg/mod/cache"),
            os.path.join(HOME, ".cache/go-build"),
        ],
        "safe": True,
        "description": "Cache de módulos Go e build cache.",
    },
    {
        "key": "pip_cache",
        "label": "pip (Python)",
        "icon": "🐍",
        "paths": [
            os.path.join(HOME, ".cache/pip"),
        ],
        "safe": True,
        "description": "Cache de pacotes pip. Regenerada automaticamente.",
    },
    {
        "key": "uv_cache",
        "label": "uv (Python)",
        "icon": "🐍",
        "paths": [
            os.path.join(HOME, ".cache/uv"),
        ],
        "safe": True,
        "description": "Cache do gestor uv. Regenerada automaticamente.",
    },
    {
        "key": "composer",
        "label": "Composer (PHP)",
        "icon": "🐘",
        "paths": [
            os.path.join(HOME, ".composer/cache"),
        ],
        "safe": True,
        "description": "Cache de pacotes Composer PHP.",
    },
    {
        "key": "docker_build",
        "label": "Docker Build Cache",
        "icon": "🐳",
        "paths": [],
        "special": "docker_buildx",
        "safe": True,
        "description": "Cache de layers Docker. Regenerada ao fazer build.",
    },
    {
        "key": "gem",
        "label": "RubyGems",
        "icon": "💎",
        "paths": [
            os.path.join(HOME, ".gem"),
        ],
        "safe": False,
        "description": "Gems Ruby instaladas localmente.",
    },
    {
        "key": "pnpm",
        "label": "pnpm",
        "icon": "📦",
        "paths": [
            os.path.join(HOME, ".local/share/pnpm/store"),
            os.path.join(HOME, ".pnpm-store"),
        ],
        "safe": True,
        "description": "Store do pnpm (Node.js).",
    },
    {
        "key": "ccache",
        "label": "ccache (C/C++)",
        "icon": "⚙️",
        "paths": [
            os.path.join(HOME, ".ccache"),
            os.path.join(HOME, ".cache/ccache"),
        ],
        "safe": True,
        "description": "Cache de compilação C/C++.",
    },
]


def scan_dev_caches():
    """
    Analisa todas as caches de desenvolvimento.
    Retorna lista de resultados por ferramenta.
    """
    results = []

    for defn in DEV_CACHE_DEFS:
        if defn.get("special") == "docker_buildx":
            # Docker build cache via CLI
            try:
                import subprocess
                r = subprocess.run(
                    ["docker", "system", "df", "--format", "{{.BuildCache}}"],
                    capture_output=True, text=True, timeout=8
                )
                # Tentar obter tamanho da build cache
                r2 = subprocess.run(
                    ["docker", "buildx", "du"],
                    capture_output=True, text=True, timeout=8
                )
                size = 0
                import re
                for line in (r2.stdout + r.stdout).splitlines():
                    m = re.search(r"([0-9.]+)\s*(GB|MB|KB|B)\b", line)
                    if m:
                        val = float(m.group(1))
                        unit = m.group(2)
                        mult = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
                        size += int(val * mult.get(unit, 0))
                if size > 0:
                    results.append({
                        **defn,
                        "size": size,
                        "exists": True,
                        "paths_found": [],
                    })
            except Exception:
                pass
            continue

        total_size = 0
        paths_found = []
        for path in defn.get("paths", []):
            if os.path.exists(path):
                sz = get_dir_size(path)
                if sz > 0:
                    total_size += sz
                    paths_found.append((path, sz))

        if total_size > 0:
            results.append({
                **defn,
                "size": total_size,
                "exists": True,
                "paths_found": paths_found,
            })

    return results


def clean_dev_cache(cache_def, log_cb=None):
    """
    Limpa uma cache de desenvolvimento.
    Retorna (freed_bytes, errors)
    """
    freed = 0
    errors = 0

    def log(msg, tag="recv"):
        if log_cb:
            log_cb(msg, tag)

    if cache_def.get("special") == "docker_buildx":
        log("A limpar Docker build cache...", "info")
        try:
            import subprocess
            subprocess.run(["docker", "buildx", "prune", "-f"],
                           capture_output=True, timeout=60)
            log("✅ Docker build cache limpa", "ok")
        except Exception as e:
            log(f"❌ Erro: {e}", "error")
            errors += 1
        return freed, errors

    for path, sz in cache_def.get("paths_found", []):
        log(f"   A limpar {path} ({fmt(sz)})...", "muted")
        try:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
                os.makedirs(path, exist_ok=True)
            elif os.path.isfile(path):
                os.remove(path)
            freed += sz
            log(f"   ✅ {fmt(sz)} libertados", "ok")
        except Exception as e:
            log(f"   ❌ {e}", "error")
            errors += 1

    return freed, errors


def get_total_dev_cache_size(results=None):
    """Retorna tamanho total de todas as caches de desenvolvimento."""
    if results is None:
        results = scan_dev_caches()
    return sum(r["size"] for r in results)
