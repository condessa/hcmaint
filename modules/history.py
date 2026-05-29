"""
HCMaint - Histórico de Limpezas e Exportação de Relatórios
Registo persistente de todas as limpezas efectuadas
"""

import os
import json
import datetime
from pathlib import Path


HISTORY_FILE = os.path.join(
    str(Path.home()), ".config", "hcmaint", "history.json"
)
MAX_HISTORY_ENTRIES = 500


def _ensure_dir():
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)


def load_history():
    """Carrega o histórico de limpezas. Retorna lista de entradas."""
    _ensure_dir()
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_history(history):
    """Guarda o histórico (lista de entradas)."""
    _ensure_dir()
    # Manter só as últimas MAX_HISTORY_ENTRIES entradas
    if len(history) > MAX_HISTORY_ENTRIES:
        history = history[-MAX_HISTORY_ENTRIES:]
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def add_history_entry(
    action,
    category_label,
    freed_bytes,
    items_count=0,
    details="",
    success=True,
):
    """
    Adiciona uma entrada ao histórico.

    Args:
        action: tipo de acção ("limpeza", "análise", "exportar")
        category_label: nome da categoria limpa
        freed_bytes: bytes libertados
        items_count: número de itens processados
        details: detalhes adicionais
        success: se a operação foi bem-sucedida
    """
    history = load_history()
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "date":      datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "action":    action,
        "category":  category_label,
        "freed":     freed_bytes,
        "freed_str": fmt_size(freed_bytes),
        "items":     items_count,
        "details":   details,
        "success":   success,
    }
    history.append(entry)
    save_history(history)
    return entry


def clear_history():
    """Apaga todo o histórico."""
    _ensure_dir()
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        return True
    except Exception:
        return False


def get_history_stats(history=None):
    """
    Calcula estatísticas do histórico.
    Retorna dict com totais por categoria, total geral, etc.
    """
    if history is None:
        history = load_history()

    if not history:
        return {
            "total_freed": 0,
            "total_operations": 0,
            "by_category": {},
            "last_clean": None,
            "first_clean": None,
        }

    total_freed = sum(e.get("freed", 0) for e in history)
    by_cat = {}
    for e in history:
        cat = e.get("category", "Outro")
        by_cat.setdefault(cat, {"count": 0, "freed": 0})
        by_cat[cat]["count"] += 1
        by_cat[cat]["freed"] += e.get("freed", 0)

    return {
        "total_freed":     total_freed,
        "total_freed_str": fmt_size(total_freed),
        "total_operations": len(history),
        "by_category":     by_cat,
        "last_clean":      history[-1].get("date") if history else None,
        "first_clean":     history[0].get("date") if history else None,
    }


def fmt_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    else:
        return f"{size_bytes / 1024 ** 3:.2f} GB"


# ─── Exportação de relatórios ────────────────────────────────────────────────

def export_report_txt(scan_results, output_path=None):
    """
    Exporta relatório de análise para ficheiro de texto.
    Retorna (sucesso, caminho_do_ficheiro)
    """
    if output_path is None:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(
            str(Path.home()), f"HCMaint_relatorio_{ts}.txt"
        )

    lines = []
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    lines += [
        "=" * 60,
        "  HCMaint — Relatório de Análise do Sistema",
        "  HCsoftware",
        f"  Data: {now}",
        "=" * 60,
        "",
    ]

    # Sumário
    total = sum(r.get("size", 0) for r in scan_results)
    lines += [
        "SUMÁRIO",
        "─" * 40,
        f"  Total detectado: {fmt_size(total)}",
        f"  Categorias analisadas: {len(scan_results)}",
        f"  Categorias com dados: {sum(1 for r in scan_results if r.get('size', 0) > 0)}",
        "",
    ]

    # Por categoria
    lines += ["DETALHE POR CATEGORIA", "─" * 40]
    for r in sorted(scan_results, key=lambda x: x.get("size", 0), reverse=True):
        size = r.get("size", 0)
        if size == 0:
            continue
        label = r.get("label", r.get("key", "?"))
        icon  = r.get("icon", "•")
        details = r.get("details", "")
        lines.append(f"  {icon}  {label:<35} {fmt_size(size):>10}")
        if details:
            lines.append(f"      {details}")

    lines += ["", "─" * 40, ""]

    # Categorias limpas (0 B)
    empty = [r for r in scan_results if r.get("size", 0) == 0]
    if empty:
        lines += ["CATEGORIAS JÁ LIMPAS", "─" * 40]
        for r in empty:
            label = r.get("label", r.get("key", "?"))
            lines.append(f"  ✅  {label}")
        lines.append("")

    lines += [
        "=" * 60,
        "  Relatório gerado pelo HCMaint",
        f"  {output_path}",
        "=" * 60,
    ]

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return True, output_path
    except Exception as e:
        return False, str(e)


def export_report_html(scan_results, output_path=None):
    """
    Exporta relatório de análise em HTML formatado.
    Retorna (sucesso, caminho_do_ficheiro)
    """
    if output_path is None:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(
            str(Path.home()), f"HCMaint_relatorio_{ts}.html"
        )

    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    total = sum(r.get("size", 0) for r in scan_results)

    # Gerar linhas da tabela
    rows = ""
    for r in sorted(scan_results, key=lambda x: x.get("size", 0), reverse=True):
        size = r.get("size", 0)
        label = r.get("label", r.get("key", "?"))
        icon = r.get("icon", "•")
        details = r.get("details", "—")
        color = "#f0ad4e" if size > 100*1024*1024 else ("#5cb85c" if size == 0 else "#e8e8e8")
        rows += f"""
        <tr>
          <td>{icon} {label}</td>
          <td style="color:{color};font-weight:bold;text-align:right">{fmt_size(size)}</td>
          <td style="color:#a0a0a0">{details}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<title>HCMaint — Relatório</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background: #1e1e1e; color: #e8e8e8; margin: 0; padding: 20px; }}
  h1 {{ color: #4a90d9; }} h2 {{ color: #a0a0a0; font-size: 14px; font-weight: normal; }}
  .card {{ background: #2b2b2b; border: 1px solid #444; border-radius: 8px; padding: 20px; margin-bottom: 16px; }}
  .total {{ font-size: 36px; font-weight: bold; color: #FFD700; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #1e1e1e; color: #6e6e6e; text-align: left; padding: 8px 12px; font-size: 12px; text-transform: uppercase; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #333; }}
  tr:hover td {{ background: #333; }}
  .footer {{ color: #555; font-size: 12px; text-align: center; margin-top: 20px; }}
</style>
</head>
<body>
<div class="card">
  <h1>🛡️ HCMaint — Relatório de Análise</h1>
  <h2>HCsoftware &nbsp;•&nbsp; {now}</h2>
  <div class="total">{fmt_size(total)}</div>
  <p style="color:#a0a0a0">Total detectado em {len(scan_results)} categorias</p>
</div>
<div class="card">
  <table>
    <thead><tr><th>Categoria</th><th style="text-align:right">Tamanho</th><th>Detalhes</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
<div class="footer">Gerado pelo HCMaint &nbsp;•&nbsp; HCsoftware &nbsp;•&nbsp; {now}</div>
</body>
</html>"""

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        return True, output_path
    except Exception as e:
        return False, str(e)
