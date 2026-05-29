"""
HCMaint v1.0.0
HCsoftware — Ferramenta de Manutenção do Linux (Debian/Ubuntu)
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hc_theme import (
    HCApplication, create_button, create_card, setup_log_area,
    BG_MAIN, BG_PANEL, BG_CARD, BG_TOPBAR, BG_SIDEBAR, BG_INPUT,
    ACCENT, ACCENT_HOV, ACCENT_DRK, TEXT_PRI, TEXT_SEC, TEXT_MUT,
    SUCCESS, DANGER, WARNING, INFO, GREEN, RED, YELLOW,
    BORDER, DIVIDER, LOG_BG,
)
from modules.scanner import (
    scan_all, fmt, is_root, sudo_available,
    scan_disk_usage_top,
    clean_apt_cache, clean_apt_orphans, clean_journal_logs,
    clean_var_logs, clean_thumbnails, clean_trash,
    clean_user_cache_subdir, clean_flatpak_unused,
    clean_python_cache, clean_docker_prune, clean_snap_old,
)
from modules.dev_caches import (
    scan_dev_caches, clean_dev_cache, get_total_dev_cache_size,
    fmt as fmt_dev,
)
from modules.large_files import (
    scan_large_files, delete_large_file, get_stats,
    fmt as fmt_lf, EXT_ICONS,
)
from modules.history import (
    load_history, add_history_entry, clear_history,
    get_history_stats, export_report_txt, export_report_html,
    fmt_size as fmt_hist,
)


# ─── Versão e Actualizações ───────────────────────────────────

APP_VERSION   = "1.1.0"
GITHUB_REPO   = "condessa/hcmaint"
GITHUB_API    = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_DL_URL = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/main.zip"


def check_for_updates(current_version, callback):
    """
    Verifica actualizações Linux no GitHub em background.
    Procura especificamente por releases com prefixo "linux-".
    callback(latest_version, release_notes) se há actualização.
    callback(None, None) se está actualizado ou erro.
    """
    import urllib.request
    import json
    import re

    # URL para listar todas as releases (não só a latest)
    RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases"

    try:
        req = urllib.request.Request(
            RELEASES_API,
            headers={"User-Agent": f"HCMaint/{current_version}"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            releases = json.loads(r.read().decode())

        # Filtrar só releases com prefixo "linux-"
        linux_releases = [
            rel for rel in releases
            if rel.get("tag_name", "").startswith("linux-")
        ]

        if not linux_releases:
            # Nenhuma release Linux publicada ainda — silencioso
            callback(None, None)
            return

        # A mais recente (primeira da lista — GitHub ordena por data)
        latest_rel  = linux_releases[0]
        tag          = latest_rel.get("tag_name", "")
        release_body = latest_rel.get("body", "")

        # Extrair versão — ex: "linux-v1.1.1-build3" → "1.1.1"
        m = re.search(r"v([0-9]+\.[0-9]+\.[0-9]+)", tag)
        if not m:
            callback(None, None)
            return

        latest = m.group(1)

        def vt(v):
            return tuple(int(x) for x in v.split("."))

        if vt(latest) > vt(current_version):
            callback(latest, release_body)
        else:
            callback(None, None)

    except Exception:
        callback(None, None)


# ─── Nav Button ───────────────────────────────────────────────

class NavBtn(tk.Frame):
    def __init__(self, parent, icon, label, command):
        super().__init__(parent, bg=BG_SIDEBAR, cursor="hand2")
        self._cmd = command
        self._active = False

        self._bar = tk.Frame(self, bg=BG_SIDEBAR, width=3)
        self._bar.pack(side=tk.LEFT, fill=tk.Y)

        inner = tk.Frame(self, bg=BG_SIDEBAR)
        inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=10)

        tk.Label(inner, text=icon, font=("Segoe UI Emoji", 15),
                 bg=BG_SIDEBAR, fg=TEXT_SEC).pack(side=tk.LEFT, padx=(0, 8))
        self._lbl = tk.Label(inner, text=label, font=("Segoe UI", 10),
                              bg=BG_SIDEBAR, fg=TEXT_SEC, anchor=tk.W)
        self._lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        for w in (self, inner, self._lbl):
            w.bind("<Button-1>", lambda e: self._cmd())
            w.bind("<Enter>", self._on)
            w.bind("<Leave>", self._off)

    def _on(self, e=None):
        if not self._active:
            self.configure(bg=BG_PANEL)
            self.winfo_children()[1].configure(bg=BG_PANEL)
            self._lbl.configure(bg=BG_PANEL)

    def _off(self, e=None):
        if not self._active:
            self.configure(bg=BG_SIDEBAR)
            self.winfo_children()[1].configure(bg=BG_SIDEBAR)
            self._lbl.configure(bg=BG_SIDEBAR)

    def set_active(self, v):
        self._active = v
        bg = BG_CARD if v else BG_SIDEBAR
        fg = ACCENT if v else TEXT_SEC
        self._bar.configure(bg=ACCENT if v else BG_SIDEBAR)
        self.configure(bg=bg)
        self.winfo_children()[1].configure(bg=bg)
        self._lbl.configure(bg=bg, fg=fg,
                             font=("Segoe UI", 10, "bold") if v else ("Segoe UI", 10))


# ─── Main App ─────────────────────────────────────────────────

class HCMaint(HCApplication):
    def __init__(self):
        super().__init__(title=f"HCMaint v{APP_VERSION} — Manutenção Linux", geometry="1280x760")
        self.resizable(True, True)

        self._pages = {}
        self._nav = {}
        self._current = None
        self._scan_results = []
        self._selected_result = None

        self._build_layout()
        self._show("dashboard")

        # Info de root
        if is_root():
            self.set_status("A correr como root — acesso total", "success")
        elif sudo_available():
            self.set_status("sudo disponível — limpezas de sistema activadas", "info")
        else:
            self.set_status("⚠️  Sem sudo — algumas limpezas requerem privilégios", "warning")

        # Verificar actualizações em background após 3 segundos
        self.after(3000, self._check_updates_background)

    # ── Layout ──────────────────────────────────────────────────

    def _check_updates_background(self):
        """Verifica actualizações em background sem bloquear a UI."""
        def on_result(latest, notes):
            if latest:
                self.after(0, lambda: self._show_update_dialog(latest, notes))
        threading.Thread(
            target=check_for_updates,
            args=(APP_VERSION, on_result),
            daemon=True
        ).start()

    def _show_update_dialog(self, latest_version, release_notes):
        """Mostra diálogo de actualização disponível."""
        import webbrowser

        win = tk.Toplevel(self)
        win.title("Actualização Disponível — HCMaint")
        win.configure(bg=BG_MAIN)
        win.geometry("500x360")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        # Barra accent no topo
        tk.Frame(win, bg=ACCENT, height=5).pack(fill=tk.X)

        body = tk.Frame(win, bg=BG_MAIN)
        body.pack(fill=tk.BOTH, expand=True, padx=24, pady=16)

        # Ícone + título
        title_f = tk.Frame(body, bg=BG_MAIN)
        title_f.pack(fill=tk.X, pady=(0, 12))
        tk.Label(title_f, text="🎉", font=("Segoe UI Emoji", 26),
                 bg=BG_MAIN).pack(side=tk.LEFT, padx=(0, 12))
        col = tk.Frame(title_f, bg=BG_MAIN)
        col.pack(side=tk.LEFT)
        tk.Label(col, text="Nova versão disponível!",
                 font=("Segoe UI", 14, "bold"),
                 bg=BG_MAIN, fg=TEXT_PRI).pack(anchor=tk.W)
        tk.Label(col,
                 text=f"v{APP_VERSION}  →  v{latest_version}",
                 font=("Segoe UI", 12),
                 bg=BG_MAIN, fg=ACCENT).pack(anchor=tk.W)

        tk.Frame(body, bg=DIVIDER, height=1).pack(fill=tk.X, pady=8)

        # Notas da release
        tk.Label(body, text="O que há de novo:",
                 font=("Segoe UI", 9, "bold"),
                 bg=BG_MAIN, fg=TEXT_SEC, anchor=tk.W).pack(fill=tk.X)

        notes_box = tk.Text(body, bg=BG_CARD, fg=TEXT_PRI,
                             font=("Segoe UI", 9), bd=0,
                             wrap=tk.WORD, height=7,
                             state=tk.NORMAL)
        notes_box.pack(fill=tk.BOTH, expand=True, pady=6)
        short = "\n".join(
            l for l in (release_notes or "").splitlines()
            if l.strip() and not l.startswith("#")
        )[:500]
        notes_box.insert(tk.END, short or "Consulte o GitHub para detalhes.")
        notes_box.config(state=tk.DISABLED)

        tk.Frame(body, bg=DIVIDER, height=1).pack(fill=tk.X, pady=8)

        # Instruções de actualização
        tk.Label(body,
                 text="Para actualizar: descarrega o ZIP e substitui os ficheiros em ~/Programas/HCMaint/",
                 font=("Segoe UI", 8), bg=BG_MAIN, fg=TEXT_MUT,
                 wraplength=440, justify=tk.LEFT).pack(fill=tk.X, pady=(0, 8))

        # Botões
        btn_f = tk.Frame(body, bg=BG_MAIN)
        btn_f.pack(fill=tk.X)

        def do_download():
            webbrowser.open(f"https://github.com/{GITHUB_REPO}/releases/latest")
            win.destroy()

        def do_later():
            win.destroy()

        create_button(btn_f, "⬇️  Ver Releases no GitHub", do_download, "primary").pack(side=tk.LEFT, padx=(0, 8))
        create_button(btn_f, "Mais tarde", do_later, "secondary").pack(side=tk.LEFT)

        tk.Label(body, text=f"Versão instalada: v{APP_VERSION}",
                 font=("Segoe UI", 8), bg=BG_MAIN, fg=TEXT_MUT).pack(
            side=tk.BOTTOM, anchor=tk.E, pady=(8, 0))

    def _build_layout(self):
        sidebar = tk.Frame(self.main_container, bg=BG_SIDEBAR, width=210)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        hdr = tk.Frame(sidebar, bg=BG_TOPBAR, height=50)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🐧 HCMaint", font=("Segoe UI", 12, "bold"),
                 bg=BG_TOPBAR, fg=ACCENT).pack(side=tk.LEFT, padx=14, pady=13)

        tk.Frame(sidebar, bg=DIVIDER, height=1).pack(fill=tk.X)

        for icon, label, key in [
            ("🏠", "Dashboard",   "dashboard"),
            ("🔍", "Análise",     "scan"),
            ("🧹", "Limpeza",     "clean"),
            ("🛠️", "Ferramentas", "tools"),
            ("💾", "Espaço",      "disk"),
            ("ℹ️",  "Sobre",       "about"),
        ]:
            btn = NavBtn(sidebar, icon, label, lambda k=key: self._show(k))
            btn.pack(fill=tk.X)
            self._nav[key] = btn

        tk.Frame(sidebar, bg=DIVIDER, height=1).pack(fill=tk.X, pady=(8, 0))
        tk.Label(sidebar, text=f"v{APP_VERSION}  •  HCsoftware",
                 font=("Segoe UI", 7), bg=BG_SIDEBAR, fg=TEXT_MUT).pack(
            side=tk.BOTTOM, pady=8)

        self._content = tk.Frame(self.main_container, bg=BG_MAIN)
        self._content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._pages["dashboard"] = self._pg_dashboard()
        self._pages["scan"]      = self._pg_scan()
        self._pages["clean"]     = self._pg_clean()
        self._pages["tools"]     = self._pg_tools()
        self._pages["disk"]      = self._pg_disk()
        self._pages["about"]     = self._pg_about()

    def _show(self, key):
        if self._current:
            self._pages[self._current].pack_forget()
            self._nav[self._current].set_active(False)
        self._pages[key].pack(fill=tk.BOTH, expand=True)
        self._nav[key].set_active(True)
        self._current = key

    # ── Dashboard ───────────────────────────────────────────────

    def _pg_dashboard(self):
        page = tk.Frame(self._content, bg=BG_MAIN)

        hdr = tk.Frame(page, bg=BG_MAIN)
        hdr.pack(fill=tk.X, padx=20, pady=(18, 6))
        tk.Label(hdr, text="Dashboard", font=("Segoe UI", 18, "bold"),
                 bg=BG_MAIN, fg=TEXT_PRI).pack(side=tk.LEFT)
        tk.Label(hdr, text=f"  {datetime.now().strftime('%d %B %Y')}",
                 font=("Segoe UI", 11), bg=BG_MAIN, fg=TEXT_MUT).pack(side=tk.LEFT)
        tk.Frame(page, bg=DIVIDER, height=1).pack(fill=tk.X, padx=20)

        # Cards de estado
        cards_f = tk.Frame(page, bg=BG_MAIN)
        cards_f.pack(fill=tk.X, padx=20, pady=14)

        self._dash_vals = {}

        # (icon, title, init_text, color, click_action, tooltip)
        card_defs = [
            ("🗑️", "A Libertar",       "Clique em Analisar", WARNING,
             self._quick_scan,
             "Clique para iniciar análise completa"),
            ("📦", "APT Cache",         "—", ACCENT,
             lambda: [self._show("clean"), None],
             "Clique para ir para Limpeza → APT Clean"),
            ("📋", "Logs",              "—", INFO,
             lambda: [self._show("clean"), None],
             "Clique para ir para Limpeza → Logs"),
            ("🗃️", "Cache Utilizador", "—", SUCCESS,
             lambda: [self._show("scan"), self._scan_tree.selection_set("user_cache") if self._scan_results else None],
             "Clique para ir para Análise"),
        ]

        for icon, title, init, color, action, tooltip in card_defs:
            c = tk.Frame(cards_f, bg=BG_CARD, cursor="hand2",
                         highlightthickness=1, highlightbackground=BORDER)
            c.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

            lbl_icon = tk.Label(c, text=icon, font=("Segoe UI Emoji", 20),
                                bg=BG_CARD, fg=color)
            lbl_icon.pack(pady=(12, 2))
            v = tk.Label(c, text=init, font=("Segoe UI", 10, "bold"),
                         bg=BG_CARD, fg=color)
            v.pack()
            lbl_title = tk.Label(c, text=title, font=("Segoe UI", 8),
                                 bg=BG_CARD, fg=TEXT_MUT)
            lbl_title.pack()
            lbl_tip = tk.Label(c, text=tooltip, font=("Segoe UI", 7),
                               bg=BG_CARD, fg=TEXT_MUT, pady=0)
            lbl_tip.pack(pady=(0, 10))

            # Hover + click em todos os widgets do card
            BG_HOV = "#555555"
            def _enter(e, frame=c, children=(lbl_icon, v, lbl_title, lbl_tip)):
                frame.configure(bg=BG_HOV, highlightbackground=ACCENT)
                for w in children:
                    w.configure(bg=BG_HOV)
            def _leave(e, frame=c, children=(lbl_icon, v, lbl_title, lbl_tip)):
                frame.configure(bg=BG_CARD, highlightbackground=BORDER)
                for w in children:
                    w.configure(bg=BG_CARD)

            for w in (c, lbl_icon, v, lbl_title, lbl_tip):
                w.bind("<Enter>", _enter)
                w.bind("<Leave>", _leave)
                w.bind("<Button-1>", lambda e, a=action: a())

            self._dash_vals[title] = v

        # Botões rápidos
        bf = tk.Frame(page, bg=BG_MAIN)
        bf.pack(pady=6)
        create_button(bf, "⚡  Análise Rápida", self._quick_scan, "primary").pack(side=tk.LEFT, padx=5)
        create_button(bf, "✨  Limpeza Segura", self._safe_clean, "teal").pack(side=tk.LEFT, padx=5)
        create_button(bf, "💾  Análise de Espaço", lambda: [self._show("disk"), self._run_disk()], "olive").pack(side=tk.LEFT, padx=5)

        # Log
        lc = create_card(page, title="ACTIVIDADE")
        lc.pack(fill=tk.BOTH, expand=True, padx=20, pady=(6, 14))
        lf, lt = setup_log_area(lc)
        lf.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self._dash_log = lt

        # Progressbar
        self._dash_pb = ttk.Progressbar(page, style="HC.Horizontal.TProgressbar", mode="determinate")
        self._dash_pb.pack(fill=tk.X, padx=20, pady=(0, 6))

        return page

    def _dlog(self, msg, tag="recv"):
        self._dash_log.config(state=tk.NORMAL)
        ts = datetime.now().strftime("%H:%M:%S")
        self._dash_log.insert(tk.END, f"[{ts}]  {msg}\n", tag)
        self._dash_log.see(tk.END)
        self._dash_log.config(state=tk.DISABLED)

    def _quick_scan(self):
        self._dash_pb["value"] = 0
        self._dlog("▶  Análise iniciada...", "info")
        threading.Thread(target=self._quick_scan_worker, daemon=True).start()

    def _quick_scan_worker(self):
        def prog(i, total, msg):
            pct = i / total * 100 if total else 0
            self.after(0, lambda: self._dash_pb.__setitem__("value", pct))
            if msg:
                self.after(0, lambda m=msg: self._dlog(f"   {m}", "muted"))

        self._scan_results = scan_all(progress_cb=prog)
        total_size = sum(r["size"] for r in self._scan_results)

        # Actualizar cards
        apt = next((r for r in self._scan_results if r["key"] == "apt_cache"), None)
        logs = next((r for r in self._scan_results if r["key"] == "journal_logs"), None)
        cache = next((r for r in self._scan_results if r["key"] == "user_cache"), None)

        self.after(0, lambda: self._dash_vals["A Libertar"].config(text=fmt(total_size)))
        if apt:
            self.after(0, lambda: self._dash_vals["APT Cache"].config(text=fmt(apt["size"])))
        if logs:
            self.after(0, lambda: self._dash_vals["Logs"].config(text=fmt(logs["size"])))
        if cache:
            self.after(0, lambda: self._dash_vals["Cache Utilizador"].config(text=fmt(cache["size"])))

        self.after(0, lambda: self._dlog(f"✅  Total detectado: {fmt(total_size)}", "ok"))
        self.after(0, lambda: self._dash_pb.__setitem__("value", 100))
        self.after(0, lambda: self.set_status(f"Análise concluída — {fmt(total_size)} a libertar", "success"))
        self.after(0, self._refresh_scan_page)

    def _safe_clean(self):
        """Limpa categorias 100% seguras sem pedir confirmação extra."""
        if not self._scan_results:
            messagebox.showinfo("HCMaint", "Execute primeiro uma Análise Rápida.")
            return
        if messagebox.askyesno("Limpeza Segura",
                                "Limpar automaticamente:\n"
                                "• Cache APT\n• Logs journal > 30 dias\n"
                                "• Miniaturas\n• Cache Python\n\n"
                                "Estas operações são reversíveis ou regeneráveis."):
            threading.Thread(target=self._safe_clean_worker, daemon=True).start()

    def _safe_clean_worker(self):
        freed = 0

        def log(msg, tag="recv"):
            self.after(0, lambda m=msg, t=tag: self._dlog(m, t))

        log("🧹  Limpeza segura iniciada...", "info")

        ok, msg = clean_apt_cache(log_cb=log)
        if ok:
            r = next((r for r in self._scan_results if r["key"] == "apt_cache"), None)
            if r:
                freed += r["size"]

        ok, msg = clean_journal_logs(30, log_cb=log)

        ok, msg = clean_thumbnails(log_cb=log)
        if ok:
            r = next((r for r in self._scan_results if r["key"] == "thumbnails"), None)
            if r:
                freed += r["size"]

        py = next((r for r in self._scan_results if r["key"] == "python_cache"), None)
        if py:
            clean_python_cache(py.get("files_list", []), log_cb=log)
            freed += py["size"]

        log(f"─── Limpeza segura concluída — ~{fmt(freed)} libertados ───", "info")
        self.after(0, lambda: self.set_status(f"Limpeza segura concluída (~{fmt(freed)} libertados)", "success"))

    # ── Página Análise ──────────────────────────────────────────

    def _pg_scan(self):
        page = tk.Frame(self._content, bg=BG_MAIN)

        hdr = tk.Frame(page, bg=BG_MAIN)
        hdr.pack(fill=tk.X, padx=20, pady=(16, 6))
        tk.Label(hdr, text="🔍  Análise do Sistema", font=("Segoe UI", 16, "bold"),
                 bg=BG_MAIN, fg=TEXT_PRI).pack(side=tk.LEFT)
        bf = tk.Frame(hdr, bg=BG_MAIN)
        bf.pack(side=tk.RIGHT)
        create_button(bf, "🔍 Analisar", self._run_scan, "teal").pack(side=tk.LEFT, padx=4)
        create_button(bf, "🧹 Limpar Seleccionado", self._clean_selected_scan, "primary").pack(side=tk.LEFT, padx=4)

        tk.Frame(page, bg=DIVIDER, height=1).pack(fill=tk.X, padx=20, pady=4)

        self._scan_pb = ttk.Progressbar(page, style="HC.Horizontal.TProgressbar", mode="determinate")
        self._scan_pb.pack(fill=tk.X, padx=20, pady=(4, 8))

        # PanedWindow — divisão ajustável pelo utilizador
        paned = tk.PanedWindow(page, orient=tk.HORIZONTAL,
                               bg=BG_SIDEBAR, sashwidth=5,
                               sashrelief=tk.FLAT, bd=0)
        paned.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 0))

        # ── Esquerda: lista de categorias ──────────────────────
        left_outer = tk.Frame(paned, bg=BG_MAIN)
        paned.add(left_outer, minsize=360, width=430)

        left = create_card(left_outer, title="CATEGORIAS DETECTADAS")
        left.pack(fill=tk.BOTH, expand=True)

        self._scan_tree = ttk.Treeview(left, style="HC.Treeview",
                                        columns=("size", "count"), show="tree headings",
                                        selectmode="browse")
        self._scan_tree.heading("#0", text="Categoria")
        self._scan_tree.heading("size", text="Tamanho")
        self._scan_tree.heading("count", text="Items")
        self._scan_tree.column("#0", width=240, stretch=True)
        self._scan_tree.column("size", width=100, anchor=tk.E, stretch=False)
        self._scan_tree.column("count", width=60, anchor=tk.CENTER, stretch=False)
        sb = ttk.Scrollbar(left, style="HC.Vertical.TScrollbar", command=self._scan_tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._scan_tree.configure(yscrollcommand=sb.set)
        self._scan_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._scan_tree.bind("<<TreeviewSelect>>", self._on_scan_select)

        # Total no fundo da lista
        self._scan_total_lbl = tk.Label(left_outer, text="",
                                         font=("Segoe UI", 9, "bold"),
                                         bg=BG_TOPBAR, fg=ACCENT, anchor=tk.E, padx=10, pady=4)
        self._scan_total_lbl.pack(fill=tk.X)

        # ── Direita: painel de detalhes estruturado ────────────
        right_outer = tk.Frame(paned, bg=BG_MAIN)
        paned.add(right_outer, minsize=280)

        right = create_card(right_outer, title="DETALHES DA CATEGORIA")
        right.pack(fill=tk.BOTH, expand=True)

        # Cabeçalho de detalhe com ícone + nome + tamanho
        self._det_header = tk.Frame(right, bg=BG_PANEL)
        self._det_header.pack(fill=tk.X, padx=8, pady=(8, 0))

        self._det_icon_lbl = tk.Label(self._det_header, text="",
                                       font=("Segoe UI Emoji", 24),
                                       bg=BG_PANEL, fg=ACCENT)
        self._det_icon_lbl.pack(side=tk.LEFT, padx=(8, 6), pady=6)

        det_title_col = tk.Frame(self._det_header, bg=BG_PANEL)
        det_title_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._det_name_lbl = tk.Label(det_title_col, text="Seleccione uma categoria",
                                       font=("Segoe UI", 11, "bold"),
                                       bg=BG_PANEL, fg=TEXT_PRI, anchor=tk.W)
        self._det_name_lbl.pack(fill=tk.X)
        self._det_sub_lbl = tk.Label(det_title_col, text="",
                                      font=("Segoe UI", 9),
                                      bg=BG_PANEL, fg=TEXT_MUT, anchor=tk.W)
        self._det_sub_lbl.pack(fill=tk.X)

        self._det_size_lbl = tk.Label(self._det_header, text="",
                                       font=("Segoe UI", 18, "bold"),
                                       bg=BG_PANEL, fg=YELLOW, padx=12)
        self._det_size_lbl.pack(side=tk.RIGHT)

        tk.Frame(right, bg=DIVIDER, height=1).pack(fill=tk.X, padx=8, pady=(6, 0))

        # Grid de propriedades
        props_f = tk.Frame(right, bg=BG_CARD)
        props_f.pack(fill=tk.X, padx=8, pady=6)

        def prop_row(parent, label, var_label, color=TEXT_PRI):
            row = tk.Frame(parent, bg=BG_CARD)
            row.pack(fill=tk.X, padx=6, pady=2)
            tk.Label(row, text=label, font=("Segoe UI", 9),
                     bg=BG_CARD, fg=TEXT_MUT, width=14, anchor=tk.W).pack(side=tk.LEFT)
            lbl = tk.Label(row, text="—", font=("Segoe UI", 9, "bold"),
                           bg=BG_CARD, fg=color, anchor=tk.W)
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            return lbl

        self._det_items_lbl  = prop_row(props_f, "Itens:",      "—")
        self._det_sudo_lbl   = prop_row(props_f, "Requer sudo:", "—", WARNING)
        self._det_safe_lbl   = prop_row(props_f, "Segurança:",  "—", SUCCESS)
        self._det_paths_lbl  = prop_row(props_f, "Caminho:",    "—", INFO)

        tk.Frame(right, bg=DIVIDER, height=1).pack(fill=tk.X, padx=8, pady=(2, 4))

        # Barra de limpeza rápida
        det_btn_f = tk.Frame(right, bg=BG_CARD)
        det_btn_f.pack(fill=tk.X, padx=8, pady=(0, 6))
        create_button(det_btn_f, "🧹  Limpar Esta Categoria",
                      self._clean_selected_scan, "primary").pack(side=tk.LEFT, padx=4)

        # Área de texto para pacotes/ficheiros
        detail_lbl = tk.Frame(right, bg=BG_TOPBAR)
        detail_lbl.pack(fill=tk.X, padx=8)
        tk.Label(detail_lbl, text="CONTEÚDO", font=("Segoe UI", 8, "bold"),
                 bg=BG_TOPBAR, fg=TEXT_MUT, padx=6, pady=4).pack(side=tk.LEFT)
        tk.Frame(right, bg=DIVIDER, height=1).pack(fill=tk.X, padx=8)

        self._detail_text = tk.Text(right, bg=LOG_BG, fg=TEXT_PRI,
                                     font=("Consolas", 9), bd=0,
                                     wrap=tk.WORD, state=tk.DISABLED)
        sb2 = ttk.Scrollbar(right, style="HC.Vertical.TScrollbar", command=self._detail_text.yview)
        sb2.pack(side=tk.RIGHT, fill=tk.Y, padx=(0,4), pady=4)
        self._detail_text.configure(yscrollcommand=sb2.set)
        self._detail_text.pack(fill=tk.BOTH, expand=True, padx=(8,0), pady=(0,8))
        self._detail_text.tag_config("header", foreground=ACCENT, font=("Consolas", 9, "bold"))
        self._detail_text.tag_config("ok",   foreground=SUCCESS)
        self._detail_text.tag_config("warn", foreground=WARNING)
        self._detail_text.tag_config("dim",  foreground=TEXT_MUT)
        self._detail_text.tag_config("size", foreground=YELLOW)

        return page

    def _run_scan(self):
        self._scan_tree.delete(*self._scan_tree.get_children())
        self._scan_pb["value"] = 0
        self.set_status("A analisar sistema...", "info")
        threading.Thread(target=self._run_scan_worker, daemon=True).start()

    def _run_scan_worker(self):
        def prog(i, total, msg):
            pct = i / total * 100 if total else 0
            self.after(0, lambda: self._scan_pb.__setitem__("value", pct))
            if msg:
                self.after(0, lambda m=msg: self.set_status(m, "info"))

        self._scan_results = scan_all(progress_cb=prog)
        self.after(0, self._refresh_scan_page)

    def _refresh_scan_page(self):
        self._scan_tree.delete(*self._scan_tree.get_children())
        total = 0
        for r in self._scan_results:
            size = r["size"]
            total += size
            tag = "found" if size > 0 else "empty"
            self._scan_tree.insert("", tk.END, iid=r["key"],
                                    text=f"  {r['icon']}  {r['label']}",
                                    values=(fmt(size), r.get("count", 0) or ""),
                                    tags=(tag,))
        self._scan_tree.tag_configure("found", foreground=WARNING)
        self._scan_tree.tag_configure("empty", foreground=TEXT_MUT)
        self._scan_total_lbl.config(text=f"Total detectado:  {fmt(total)}")
        self._scan_pb["value"] = 100
        self.set_status(f"Análise concluída — {fmt(total)} a libertar", "success")

    def _on_scan_select(self, e=None):
        sel = self._scan_tree.selection()
        if not sel:
            return
        key = sel[0]
        result = next((r for r in self._scan_results if r["key"] == key), None)
        if not result:
            return
        self._selected_result = result

        # ── Actualizar widgets de detalhe estruturado ──
        needs_sudo = result.get("needs_sudo", False)
        safe = result.get("safe", True)
        size = result["size"]
        count = result.get("count", 0)

        self._det_icon_lbl.config(text=result.get("icon", "📁"))
        self._det_name_lbl.config(text=result["label"])
        self._det_sub_lbl.config(text=result.get("details", ""))
        # Para journal, mostrar tamanho removível vs total
        total_size = result.get("total_size", size)
        if result.get("key") == "journal_logs" and total_size != size:
            size_display = f"{fmt(size)} / {fmt(total_size)}"
        else:
            size_display = fmt(size) if size > 0 else "0 B"
        self._det_size_lbl.config(
            text=size_display,
            fg=WARNING if size > 50*1024*1024 else (YELLOW if size > 0 else TEXT_MUT)
        )
        self._det_items_lbl.config(
            text=f"{count} item(s)" if count else "—"
        )
        self._det_sudo_lbl.config(
            text="Sim ⚠️" if needs_sudo else "Não ✅",
            fg=WARNING if needs_sudo else SUCCESS
        )
        self._det_safe_lbl.config(
            text="✅ Seguro" if safe else "⚠️  Verificar antes",
            fg=SUCCESS if safe else WARNING
        )
        paths = result.get("paths", [])
        path_str = paths[0] if paths else "—"
        if len(path_str) > 45:
            path_str = "…" + path_str[-43:]
        self._det_paths_lbl.config(text=path_str, fg=INFO)

        # ── Área de conteúdo (texto) ──
        dt = self._detail_text
        dt.config(state=tk.NORMAL)
        dt.delete("1.0", tk.END)

        # Subpastas ~/.cache/
        subdirs = result.get("subdirs", [])
        if subdirs:
            dt.insert(tk.END, f"Subpastas de ~/.cache/  ({len(subdirs)} pastas)\n", "header")
            dt.insert(tk.END, "─" * 40 + "\n", "dim")
            for name, sz, path in subdirs:
                bar_filled = int(sz / max(subdirs[0][1], 1) * 20) if subdirs[0][1] > 0 else 0
                bar = "█" * bar_filled + "░" * (20 - bar_filled)
                tag = "warn" if sz > 50*1024*1024 else "dim"
                dt.insert(tk.END, f"  {fmt(sz):>9}  {bar}  {name}\n", tag)

        # Pacotes órfãos
        pkgs = result.get("packages", [])
        if pkgs:
            dt.insert(tk.END, f"Pacotes a remover  ({len(pkgs)})\n", "header")
            dt.insert(tk.END, "─" * 40 + "\n", "dim")
            # 3 colunas
            cols = 3
            for i in range(0, len(pkgs), cols):
                row_pkgs = pkgs[i:i+cols]
                dt.insert(tk.END, "  " + "  ".join(f"{p:<28}" for p in row_pkgs) + "\n", "dim")

        # Ficheiros
        files = result.get("files_list", [])
        if files:
            dt.insert(tk.END, f"Ficheiros detectados  ({len(files)})\n", "header")
            dt.insert(tk.END, "─" * 40 + "\n", "dim")
            for fp in files[:60]:
                dt.insert(tk.END, f"  {fp}\n", "dim")
            if len(files) > 60:
                dt.insert(tk.END, f"  … e mais {len(files)-60} ficheiros\n", "dim")

        # Flatpak runtimes
        all_runtimes = result.get("all_runtimes", [])
        unused_refs = result.get("unused_refs", [])
        if all_runtimes:
            dt.insert(tk.END, f"Runtimes instalados  ({len(all_runtimes)})\n", "header")
            dt.insert(tk.END, "─" * 40 + "\n", "dim")
            for rt in all_runtimes:
                is_unused = any(rt["id"] in ur or ur in rt["id"] for ur in unused_refs)
                tag = "warn" if is_unused else "dim"
                marker = "⚠️ " if is_unused else "   "
                dt.insert(tk.END, f"  {marker}{rt['size_str']:>8}  {rt['id']}\n", tag)
            if unused_refs:
                dt.insert(tk.END, f"\n⚠️  {len(unused_refs)} marcados para remoção\n", "warn")

        # Snaps desactivados
        snaps_detail = result.get("disabled_detail", [])
        blocked_snaps = result.get("blocked_snaps", [])
        snaps = result.get("disabled_snaps", [])

        if snaps_detail:
            dt.insert(tk.END, f"Versões removíveis  ({len(snaps_detail)})\n", "header")
            dt.insert(tk.END, "─" * 40 + "\n", "dim")
            for s in snaps_detail:
                size_str = fmt(s.get("size", 0)) if s.get("size") else ""
                dt.insert(tk.END, f"  🔩  {s['name']}  rev {s['rev']}  {size_str}\n", "warn")
        elif snaps:
            dt.insert(tk.END, f"Versões removíveis  ({len(snaps)})\n", "header")
            dt.insert(tk.END, "─" * 40 + "\n", "dim")
            for s in snaps:
                dt.insert(tk.END, f"  🔩  {s}\n", "warn")

        if blocked_snaps:
            dt.insert(tk.END, f"\nSnaps de sistema (não removíveis)  ({len(blocked_snaps)})\n", "header")
            dt.insert(tk.END, "─" * 40 + "\n", "dim")
            for s in blocked_snaps:
                size_str = fmt(s.get("size", 0)) if s.get("size") else ""
                dt.insert(tk.END,
                    f"  🔒  {s['name']}  rev {s['rev']}  {size_str}  — {s.get('reason','')}\n",
                    "dim")

        if not snaps_detail and not snaps and not blocked_snaps:
            pass  # handled by generic fallback below

        # Docker
        stopped = result.get("stopped", [])
        dangling = result.get("dangling", [])
        if stopped or dangling:
            if stopped:
                dt.insert(tk.END, f"Containers parados  ({len(stopped)})\n", "header")
                dt.insert(tk.END, "─" * 40 + "\n", "dim")
                for c in stopped[:20]:
                    dt.insert(tk.END, f"  🐳  {c}\n", "warn")
            if dangling:
                dt.insert(tk.END, f"\nImagens dangling  ({len(dangling)})\n", "header")
                dt.insert(tk.END, "─" * 40 + "\n", "dim")
                for img in dangling[:20]:
                    dt.insert(tk.END, f"  📦  {img}\n", "dim")

        # Nada para mostrar
        if not any([subdirs, pkgs, files, snaps, stopped, dangling]):
            if size == 0:
                dt.insert(tk.END, "  Nada encontrado — categoria já limpa.\n", "ok")
            else:
                dt.insert(tk.END, f"  {fmt(size)} a libertar.\n", "size")
                if paths:
                    dt.insert(tk.END, "\nCaminhos:\n", "header")
                    for p in paths[:5]:
                        dt.insert(tk.END, f"  {p}\n", "dim")

        dt.config(state=tk.DISABLED)

    def _clean_selected_scan(self):
        if not self._selected_result:
            messagebox.showinfo("HCMaint", "Seleccione uma categoria na lista.")
            return
        r = self._selected_result
        if r["size"] == 0:
            messagebox.showinfo("HCMaint", "Nada para limpar nesta categoria.")
            return
        if not messagebox.askyesno("Confirmar Limpeza",
                                    f"Limpar '{r['label']}'?\n\nTamanho: {fmt(r['size'])}"):
            return
        threading.Thread(target=lambda: self._do_clean_one(r), daemon=True).start()

    def _do_clean_one(self, r):
        def log(msg, tag="recv"):
            self.after(0, lambda m=msg, t=tag: self._dlog(m, t))

        key = r["key"]
        self.after(0, lambda: self._show("dashboard"))

        freed_size = r.get("size", 0)

        if key == "apt_cache":
            clean_apt_cache(log_cb=log)
        elif key == "apt_orphans":
            clean_apt_orphans(log_cb=log)
        elif key == "journal_logs":
            clean_journal_logs(log_cb=log)
        elif key == "var_logs":
            clean_var_logs(log_cb=log)
        elif key == "thumbnails":
            clean_thumbnails(log_cb=log)
        elif key == "trash":
            clean_trash(log_cb=log)
        elif key == "flatpak_unused":
            clean_flatpak_unused(log_cb=log, unused_refs=r.get("unused_refs", []))
        elif key == "python_cache":
            clean_python_cache(r.get("files_list", []), log_cb=log)
        elif key == "docker":
            clean_docker_prune(log_cb=log)
        elif key == "snap_cache":
            snaps = r.get("disabled_snaps", [])
            if snaps:
                clean_snap_old(snaps, log_cb=log)
            else:
                log("ℹ️  Nenhuma versão desactivada de Snap para remover", "info")
        elif key == "user_cache":
            self.after(0, lambda: self._show_cache_dialog(r))
            return
        else:
            log(f"⚠️  Limpeza manual necessária para: {r['label']}", "warn")

        # Registar no histórico
        if freed_size > 0:
            add_history_entry("limpeza", r.get("label", key), freed_size,
                               details=f"Página de Análise")

        self.after(0, lambda: self.set_status(f"Limpeza concluída: {r['label']} — a re-analisar...", "success"))
        # Re-analisar para actualizar os valores
        self.after(500, self._quick_scan)

    def _show_cache_dialog(self, r):
        subdirs = r.get("subdirs", [])
        if not subdirs:
            messagebox.showinfo("HCMaint", "Nenhuma subpasta encontrada.")
            return

        win = tk.Toplevel(self)
        win.title("Seleccionar Cache a Limpar")
        win.configure(bg=BG_MAIN)
        win.geometry("500x460")
        win.transient(self)
        win.grab_set()

        tk.Label(win, text="Seleccione as pastas de cache a remover:",
                 font=("Segoe UI", 10), bg=BG_MAIN, fg=TEXT_PRI).pack(
            padx=16, pady=(14, 6), anchor=tk.W)

        frame = tk.Frame(win, bg=BG_MAIN)
        frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        canvas = tk.Canvas(frame, bg=BG_MAIN, bd=0, highlightthickness=0)
        vsb = ttk.Scrollbar(frame, style="HC.Vertical.TScrollbar", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=BG_MAIN)
        canvas.create_window((0, 0), window=inner, anchor=tk.NW)

        vars_ = []
        for name, sz, path in subdirs:
            v = tk.BooleanVar(value=sz > 5 * 1024 * 1024)  # pre-seleccionar > 5MB
            vars_.append((v, path, sz))
            row = tk.Frame(inner, bg=BG_MAIN)
            row.pack(fill=tk.X, pady=1)
            tk.Checkbutton(row, variable=v, bg=BG_MAIN, fg=TEXT_PRI,
                           activebackground=BG_PANEL, selectcolor=BG_CARD,
                           bd=0).pack(side=tk.LEFT)
            tk.Label(row, text=f"{fmt(sz):>9}  {name}",
                     font=("Consolas", 9), bg=BG_MAIN,
                     fg=WARNING if sz > 50*1024*1024 else TEXT_PRI).pack(side=tk.LEFT)

        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

        def do_clean():
            selected = [(path, sz) for v, path, sz in vars_ if v.get()]
            win.destroy()
            if not selected:
                return

            def worker():
                def log(msg, tag="recv"):
                    self.after(0, lambda m=msg, t=tag: self._dlog(m, t))
                for path, sz in selected:
                    clean_user_cache_subdir(path, log_cb=log)
                self.after(0, lambda: self.set_status("Cache do utilizador limpa", "success"))

            threading.Thread(target=worker, daemon=True).start()
            self._show("dashboard")

        btn_f = tk.Frame(win, bg=BG_MAIN)
        btn_f.pack(fill=tk.X, padx=14, pady=10)
        create_button(btn_f, "🗑️  Limpar Seleccionado", do_clean, "primary").pack(side=tk.RIGHT, padx=4)
        create_button(btn_f, "Cancelar", win.destroy, "secondary").pack(side=tk.RIGHT, padx=4)

    # ── Página Limpeza ──────────────────────────────────────────

    def _pg_clean(self):
        page = tk.Frame(self._content, bg=BG_MAIN)

        hdr = tk.Frame(page, bg=BG_MAIN)
        hdr.pack(fill=tk.X, padx=20, pady=(16, 6))
        tk.Label(hdr, text="🧹  Limpeza", font=("Segoe UI", 16, "bold"),
                 bg=BG_MAIN, fg=TEXT_PRI).pack(side=tk.LEFT)
        tk.Frame(page, bg=DIVIDER, height=1).pack(fill=tk.X, padx=20, pady=4)

        # Grid de botões de limpeza individuais
        grid = tk.Frame(page, bg=BG_MAIN)
        grid.pack(fill=tk.X, padx=20, pady=8)

        actions = [
            ("📦  APT Clean",        self._act_apt_clean,     "teal",
             "Remove .deb em cache\n/var/cache/apt/archives/"),
            ("🗑️  APT Autoremove",   self._act_apt_autoremove,"teal",
             "Remove pacotes não necessários"),
            ("📋  Journal (30d)",    self._act_journal,        "teal",
             "Limpa logs com mais de 30 dias"),
            ("🗒️  Logs Antigos",     self._act_var_logs,       "teal",
             "Remove *.gz e *.old em /var/log/"),
            ("🖼️  Miniaturas",       self._act_thumbs,         "teal",
             "Limpa ~/.cache/thumbnails/"),
            ("🗑️  Reciclagem",       self._act_trash,          "teal",
             "Esvazia ~/.local/share/Trash/"),
            ("🐍  Cache Python",     self._act_pycache,        "teal",
             "Remove __pycache__ e .pyc em ~/Programas"),
            ("📱  Flatpak Unused",   self._act_flatpak,        "olive",
             "Remove runtimes Flatpak não usados"),
            ("🐳  Docker Prune",     self._act_docker,         "olive",
             "Remove containers e imagens parados"),
            ("🔩  Snap Old",         self._act_snap,           "olive",
             "Remove versões desactivadas de Snaps"),
        ]

        cols = 2
        for i, (label, cmd, style, tooltip) in enumerate(actions):
            row = i // cols
            col = i % cols
            cell = tk.Frame(grid, bg=BG_CARD,
                             highlightthickness=1, highlightbackground=BORDER)
            cell.grid(row=row, column=col, padx=6, pady=5, sticky="nsew")
            grid.columnconfigure(col, weight=1)

            tk.Label(cell, text=label, font=("Segoe UI", 10, "bold"),
                     bg=BG_CARD, fg=TEXT_PRI, anchor=tk.W).pack(
                fill=tk.X, padx=12, pady=(10, 2))
            tk.Label(cell, text=tooltip, font=("Segoe UI", 8),
                     bg=BG_CARD, fg=TEXT_MUT, anchor=tk.W,
                     wraplength=340, justify=tk.LEFT).pack(
                fill=tk.X, padx=12, pady=(0, 6))
            create_button(cell, "Executar →", cmd, style).pack(
                anchor=tk.E, padx=12, pady=(0, 10))

        # Log de limpeza
        lc = create_card(page, title="LOG DE LIMPEZA")
        lc.pack(fill=tk.BOTH, expand=True, padx=20, pady=(6, 14))
        lf, lt = setup_log_area(lc)
        lf.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self._clean_log = lt

        return page

    def _clog(self, msg, tag="recv"):
        self._clean_log.config(state=tk.NORMAL)
        ts = datetime.now().strftime("%H:%M:%S")
        self._clean_log.insert(tk.END, f"[{ts}]  {msg}\n", tag)
        self._clean_log.see(tk.END)
        self._clean_log.config(state=tk.DISABLED)

    def _run_clean(self, fn, *args):
        def log(msg, tag="recv"):
            self.after(0, lambda m=msg, t=tag: self._clog(m, t))
        def worker():
            fn(*args, log_cb=log)
            self.after(0, lambda: self.set_status("Pronto", "success"))
        threading.Thread(target=worker, daemon=True).start()

    def _act_apt_clean(self):     self._run_clean(clean_apt_cache)
    def _act_apt_autoremove(self):
        if messagebox.askyesno("APT Autoremove", "Remover pacotes órfãos?\n(apt-get autoremove --purge)"):
            self._run_clean(clean_apt_orphans)
    def _act_journal(self):       self._run_clean(clean_journal_logs, 30)
    def _act_var_logs(self):      self._run_clean(clean_var_logs)
    def _act_thumbs(self):        self._run_clean(clean_thumbnails)
    def _act_trash(self):
        if messagebox.askyesno("Reciclagem", "Esvaziar reciclagem permanentemente?"):
            self._run_clean(clean_trash)
    def _act_pycache(self):
        r = next((r for r in self._scan_results if r["key"] == "python_cache"), None)
        if r:
            self._run_clean(clean_python_cache, r.get("files_list", []))
        else:
            messagebox.showinfo("HCMaint", "Execute uma Análise primeiro para detectar caches Python.")
    def _act_flatpak(self):       self._run_clean(clean_flatpak_unused)
    def _act_docker(self):
        if messagebox.askyesno("Docker Prune", "Remover containers parados e imagens não usadas?"):
            self._run_clean(clean_docker_prune)
    def _act_snap(self):
        r = next((r for r in self._scan_results if r["key"] == "snap_cache"), None)
        disabled = r.get("disabled_snaps", []) if r else []
        if disabled:
            self._run_clean(clean_snap_old, disabled)
        else:
            messagebox.showinfo("HCMaint", "Nenhuma versão desactivada de Snap encontrada.")

    # ── Página Ferramentas ─────────────────────────────────────

    def _pg_tools(self):
        page = tk.Frame(self._content, bg=BG_MAIN)
        hdr = tk.Frame(page, bg=BG_MAIN)
        hdr.pack(fill=tk.X, padx=20, pady=(16, 6))
        tk.Label(hdr, text="🛠️  Ferramentas", font=("Segoe UI", 16, "bold"),
                 bg=BG_MAIN, fg=TEXT_PRI).pack(side=tk.LEFT)
        tk.Frame(page, bg=DIVIDER, height=1).pack(fill=tk.X, padx=20, pady=4)

        # Tab buttons frame
        tab_f = tk.Frame(page, bg=BG_MAIN)
        tab_f.pack(fill=tk.X, padx=20, pady=(4, 0))
        tab_content = tk.Frame(page, bg=BG_MAIN)
        tab_content.pack(fill=tk.BOTH, expand=True, padx=20, pady=8)

        self._tools_frames = {}
        tab_btns = {}

        def switch_tab(key):
            for k, (f, btn) in self._tools_frames.items():
                if k == key:
                    f.pack(fill=tk.BOTH, expand=True)
                    btn.config(bg=ACCENT, fg="white")
                else:
                    f.pack_forget()
                    btn.config(bg=BG_PANEL, fg=TEXT_SEC)

        for key, label in [("dev", "📦  Caches Dev"), ("large", "🔍  Ficheiros Grandes"), ("history", "📋  Histórico")]:
            btn = tk.Button(tab_f, text=label, bg=BG_PANEL, fg=TEXT_SEC,
                           font=("Segoe UI", 9), bd=0, padx=14, pady=6,
                           cursor="hand2", relief="flat",
                           activebackground=ACCENT, activeforeground="white",
                           command=lambda k=key: switch_tab(k))
            btn.pack(side=tk.LEFT, padx=(0, 4))
            tab_btns[key] = btn

        dev_f = tk.Frame(tab_content, bg=BG_MAIN)
        self._tools_frames["dev"] = (dev_f, tab_btns["dev"])
        self._build_dev_tab(dev_f)

        large_f = tk.Frame(tab_content, bg=BG_MAIN)
        self._tools_frames["large"] = (large_f, tab_btns["large"])
        self._build_large_tab(large_f)

        hist_f = tk.Frame(tab_content, bg=BG_MAIN)
        self._tools_frames["history"] = (hist_f, tab_btns["history"])
        self._build_history_tab(hist_f)

        switch_tab("dev")
        return page

    def _build_dev_tab(self, parent):
        self._dev_results = []
        hdr = tk.Frame(parent, bg=BG_MAIN)
        hdr.pack(fill=tk.X, pady=(0, 8))
        create_button(hdr, "🔍 Analisar", self._scan_dev_caches, "teal").pack(side=tk.LEFT, padx=4)
        create_button(hdr, "🗑️ Limpar Seleccionado", self._clean_dev_selected, "primary").pack(side=tk.LEFT, padx=4)
        create_button(hdr, "✨ Limpar Tudo (Seguro)", self._clean_dev_all, "warning").pack(side=tk.LEFT, padx=4)
        self._dev_pb = ttk.Progressbar(parent, style="HC.Horizontal.TProgressbar", mode="determinate")
        self._dev_pb.pack(fill=tk.X, pady=(0, 8))
        paned = tk.PanedWindow(parent, orient=tk.HORIZONTAL, bg=BG_SIDEBAR, sashwidth=5, bd=0)
        paned.pack(fill=tk.BOTH, expand=True)
        left = create_card(paned, title="CACHES DETECTADAS")
        paned.add(left, minsize=300, width=360)
        self._dev_tree = ttk.Treeview(left, style="HC.Treeview",
                                       columns=("size", "safe"), show="tree headings", selectmode="browse")
        self._dev_tree.heading("#0", text="Ferramenta")
        self._dev_tree.heading("size", text="Tamanho")
        self._dev_tree.heading("safe", text="Seguro")
        self._dev_tree.column("#0", width=180, stretch=True)
        self._dev_tree.column("size", width=90, anchor=tk.E, stretch=False)
        self._dev_tree.column("safe", width=60, anchor=tk.CENTER, stretch=False)
        sb = ttk.Scrollbar(left, style="HC.Vertical.TScrollbar", command=self._dev_tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._dev_tree.configure(yscrollcommand=sb.set)
        self._dev_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._dev_tree.bind("<<TreeviewSelect>>", self._on_dev_select)
        self._dev_total_lbl = tk.Label(left, text="", font=("Segoe UI", 9, "bold"),
                                        bg=BG_TOPBAR, fg=ACCENT, anchor=tk.E, padx=10, pady=4)
        self._dev_total_lbl.pack(fill=tk.X)
        right = create_card(paned, title="DETALHES")
        paned.add(right, minsize=240)
        self._dev_detail = tk.Text(right, bg=LOG_BG, fg=TEXT_PRI, font=("Consolas", 9),
                                    bd=0, wrap=tk.WORD, state=tk.DISABLED)
        sb2 = ttk.Scrollbar(right, style="HC.Vertical.TScrollbar", command=self._dev_detail.yview)
        sb2.pack(side=tk.RIGHT, fill=tk.Y)
        self._dev_detail.configure(yscrollcommand=sb2.set)
        self._dev_detail.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        for tag, color in [("header", ACCENT), ("ok", SUCCESS), ("warn", WARNING), ("dim", TEXT_MUT), ("size", YELLOW)]:
            self._dev_detail.tag_config(tag, foreground=color)

    def _scan_dev_caches(self):
        self._dev_tree.delete(*self._dev_tree.get_children())
        self._dev_pb["value"] = 0
        self.set_status("A analisar caches de desenvolvimento...", "info")
        threading.Thread(target=self._scan_dev_worker, daemon=True).start()

    def _scan_dev_worker(self):
        self._dev_results = scan_dev_caches()
        self.after(0, self._refresh_dev_results)

    def _refresh_dev_results(self):
        self._dev_tree.delete(*self._dev_tree.get_children())
        total = 0
        for r in sorted(self._dev_results, key=lambda x: x["size"], reverse=True):
            total += r["size"]
            self._dev_tree.insert("", tk.END, iid=r["key"],
                                   text=f"  {r['icon']}  {r['label']}",
                                   values=(fmt(r["size"]), "✅" if r.get("safe") else "⚠️"),
                                   tags=("found",))
        self._dev_tree.tag_configure("found", foreground=WARNING)
        self._dev_total_lbl.config(text=f"Total:  {fmt(total)}")
        self._dev_pb["value"] = 100
        self.set_status(f"Caches dev: {fmt(total)} detectados", "success")

    def _on_dev_select(self, e=None):
        sel = self._dev_tree.selection()
        if not sel:
            return
        r = next((x for x in self._dev_results if x["key"] == sel[0]), None)
        if not r:
            return
        dt = self._dev_detail
        dt.config(state=tk.NORMAL)
        dt.delete("1.0", tk.END)
        dt.insert(tk.END, f"{r['icon']}  {r['label']}\n", "header")
        dt.insert(tk.END, "─"*40+"\n", "dim")
        dt.insert(tk.END, f"Tamanho: ", "dim")
        dt.insert(tk.END, f"{fmt(r['size'])}\n", "size")
        dt.insert(tk.END, f"Seguro: {'✅' if r.get('safe') else '⚠️'}\n",
                   "ok" if r.get("safe") else "warn")
        dt.insert(tk.END, f"\n{r.get('description', '')}\n", "dim")
        for path, sz in r.get("paths_found", []):
            dt.insert(tk.END, f"  {fmt(sz):>10}  {path}\n", "dim")
        dt.config(state=tk.DISABLED)

    def _clean_dev_selected(self):
        sel = self._dev_tree.selection()
        if not sel:
            messagebox.showinfo("HCMaint", "Seleccione uma cache.")
            return
        r = next((x for x in self._dev_results if x["key"] == sel[0]), None)
        if not r or r["size"] == 0:
            return
        if messagebox.askyesno("Limpar", f"Limpar {r['label']}?\nTamanho: {fmt(r['size'])}"):
            threading.Thread(target=lambda: self._do_clean_dev([r]), daemon=True).start()

    def _clean_dev_all(self):
        safe = [r for r in self._dev_results if r.get("safe") and r["size"] > 0]
        if not safe:
            messagebox.showinfo("HCMaint", "Execute 'Analisar' primeiro.")
            return
        total = sum(r["size"] for r in safe)
        if messagebox.askyesno("Limpar Tudo", f"Limpar {len(safe)} caches?\nTotal: {fmt(total)}"):
            threading.Thread(target=lambda: self._do_clean_dev(safe), daemon=True).start()

    def _do_clean_dev(self, caches):
        total_freed = 0
        for r in caches:
            freed, _ = clean_dev_cache(r)
            total_freed += freed
            if freed > 0:
                add_history_entry("limpeza", r["label"], freed)
        self.after(0, lambda: self.set_status(f"Caches dev: {fmt(total_freed)} libertados", "success"))
        self.after(500, self._scan_dev_caches)

    def _build_large_tab(self, parent):
        self._large_results = []
        self._large_min_mb = tk.IntVar(value=50)
        hdr = tk.Frame(parent, bg=BG_MAIN)
        hdr.pack(fill=tk.X, pady=(0, 6))
        tk.Label(hdr, text="Mínimo:", font=("Segoe UI", 9), bg=BG_MAIN, fg=TEXT_SEC).pack(side=tk.LEFT)
        for mb in [50, 100, 250, 500]:
            tk.Radiobutton(hdr, text=f"{mb} MB", variable=self._large_min_mb, value=mb,
                           bg=BG_MAIN, fg=TEXT_PRI, selectcolor=BG_CARD,
                           activebackground=BG_MAIN, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=3)
        create_button(hdr, "🔍 Pesquisar", self._scan_large_files, "teal").pack(side=tk.LEFT, padx=(10, 4))
        create_button(hdr, "🗑️ Apagar Seleccionado", self._delete_large_selected, "danger").pack(side=tk.LEFT, padx=4)
        create_button(hdr, "📄 Exportar", self._export_report, "olive").pack(side=tk.LEFT, padx=4)
        self._large_status = tk.Label(parent, text="Clique em Pesquisar",
                                       font=("Segoe UI", 9), bg=BG_MAIN, fg=TEXT_MUT, anchor=tk.W)
        self._large_status.pack(fill=tk.X, padx=4, pady=(0, 4))
        self._large_pb = ttk.Progressbar(parent, style="HC.Horizontal.TProgressbar", mode="indeterminate")
        self._large_pb.pack(fill=tk.X, pady=(0, 8))
        card = create_card(parent, title="FICHEIROS GRANDES")
        card.pack(fill=tk.BOTH, expand=True)
        cols = ("name", "size", "category", "path", "date")
        self._large_tree = ttk.Treeview(card, style="HC.Treeview", columns=cols,
                                         show="headings", selectmode="extended")
        self._large_tree.heading("name", text="Nome")
        self._large_tree.heading("size", text="Tamanho")
        self._large_tree.heading("category", text="Tipo")
        self._large_tree.heading("path", text="Caminho")
        self._large_tree.heading("date", text="Modificado")
        self._large_tree.column("name", width=200)
        self._large_tree.column("size", width=90, anchor=tk.E)
        self._large_tree.column("category", width=90, anchor=tk.CENTER)
        self._large_tree.column("path", width=300)
        self._large_tree.column("date", width=90, anchor=tk.CENTER)
        sb = ttk.Scrollbar(card, style="HC.Vertical.TScrollbar", command=self._large_tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._large_tree.configure(yscrollcommand=sb.set)
        self._large_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def _scan_large_files(self):
        self._large_tree.delete(*self._large_tree.get_children())
        self._large_pb.start(10)
        min_mb = self._large_min_mb.get()
        self._large_status.config(text=f"A pesquisar ficheiros > {min_mb} MB...")
        threading.Thread(target=lambda: self._scan_large_worker(min_mb), daemon=True).start()

    def _scan_large_worker(self, min_mb):
        def prog(msg):
            self.after(0, lambda m=msg: self._large_status.config(text=m))
        self._large_results = scan_large_files(min_size_mb=min_mb, progress_cb=prog)
        self.after(0, self._refresh_large_results)

    def _refresh_large_results(self):
        self._large_pb.stop()
        self._large_tree.delete(*self._large_tree.get_children())
        stats = get_stats(self._large_results)
        for f in self._large_results:
            short_path = f["path"] if len(f["path"]) < 55 else "..." + f["path"][-52:]
            self._large_tree.insert("", tk.END, values=(
                f["name"], f["size_str"], f"{f['icon']} {f['category']}", short_path, f["modified_str"]))
        n, total = stats["count"], stats["total"]
        self._large_status.config(text=f"{n} ficheiros  •  Total: {fmt(total)}")
        self.set_status(f"Ficheiros grandes: {n} ({fmt(total)})", "info")

    def _delete_large_selected(self):
        sel = self._large_tree.selection()
        if not sel:
            messagebox.showinfo("HCMaint", "Seleccione ficheiros.")
            return
        indices = [self._large_tree.index(s) for s in sel]
        files = [self._large_results[i] for i in indices if i < len(self._large_results)]
        total = sum(f["size"] for f in files)
        if not messagebox.askyesno("Apagar", f"Apagar {len(files)} ficheiro(s)?\nTotal: {fmt(total)}\n\nIrreversível!"):
            return
        def worker():
            freed = 0
            for f in files:
                ok, sz = delete_large_file(f["path"])
                if ok:
                    freed += sz
            add_history_entry("limpeza", "Ficheiros Grandes", freed, items_count=len(files))
            self.after(0, lambda: self.set_status(f"Apagados: {fmt(freed)}", "success"))
            self.after(0, self._scan_large_files)
        threading.Thread(target=worker, daemon=True).start()

    def _export_report(self):
        from tkinter import filedialog
        if not self._scan_results:
            messagebox.showinfo("HCMaint", "Execute uma Análise primeiro.")
            return
        html = messagebox.askyesno("Formato", "Exportar como HTML?\nSim=HTML  Não=TXT")
        ext = ".html" if html else ".txt"
        ts = datetime.now().strftime("%Y%m%d")
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[(ext.upper(), f"*{ext}"), ("Todos", "*.*")],
            initialfile=f"HCMaint_relatorio_{ts}{ext}")
        if not path:
            return
        fn = export_report_html if html else export_report_txt
        ok, result = fn(self._scan_results, path)
        if ok:
            add_history_entry("exportar", "Relatório", 0, details=result)
            messagebox.showinfo("Exportado", f"Guardado em:\n{result}")
            try:
                import subprocess
                subprocess.Popen(["xdg-open", result])
            except Exception:
                pass
        else:
            messagebox.showerror("Erro", result)

    def _build_history_tab(self, parent):
        hdr = tk.Frame(parent, bg=BG_MAIN)
        hdr.pack(fill=tk.X, pady=(0, 8))
        create_button(hdr, "🔄 Actualizar", self._refresh_history, "teal").pack(side=tk.LEFT, padx=4)
        create_button(hdr, "🗑️ Limpar Histórico", self._clear_history, "danger").pack(side=tk.LEFT, padx=4)
        create_button(hdr, "📄 Exportar", self._export_report, "olive").pack(side=tk.LEFT, padx=4)
        stats_f = tk.Frame(parent, bg=BG_MAIN)
        stats_f.pack(fill=tk.X, pady=(0, 8))
        self._hist_stat_labels = {}
        for title, key in [("Total Libertado", "freed"), ("Operações", "ops"), ("Última Limpeza", "last")]:
            c = tk.Frame(stats_f, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER)
            c.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
            tk.Label(c, text=title, font=("Segoe UI", 8), bg=BG_CARD, fg=TEXT_MUT).pack(pady=(8, 0))
            v = tk.Label(c, text="—", font=("Segoe UI", 13, "bold"), bg=BG_CARD, fg=ACCENT)
            v.pack(pady=(0, 8))
            self._hist_stat_labels[key] = v
        card = create_card(parent, title="HISTÓRICO DE LIMPEZAS")
        card.pack(fill=tk.BOTH, expand=True)
        cols = ("date", "action", "category", "freed", "details")
        self._hist_tree = ttk.Treeview(card, style="HC.Treeview", columns=cols,
                                        show="headings", selectmode="browse")
        for col, hd, w, anc in [
            ("date","Data/Hora",120,tk.CENTER), ("action","Acção",80,tk.CENTER),
            ("category","Categoria",180,tk.W), ("freed","Libertado",90,tk.E),
            ("details","Detalhes",260,tk.W)]:
            self._hist_tree.heading(col, text=hd)
            self._hist_tree.column(col, width=w, anchor=anc)
        sb = ttk.Scrollbar(card, style="HC.Vertical.TScrollbar", command=self._hist_tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._hist_tree.configure(yscrollcommand=sb.set)
        self._hist_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._refresh_history()

    def _refresh_history(self):
        history = load_history()
        stats = get_history_stats(history)
        self._hist_stat_labels["freed"].config(text=stats.get("total_freed_str", "0 B"))
        self._hist_stat_labels["ops"].config(text=str(stats.get("total_operations", 0)))
        self._hist_stat_labels["last"].config(text=stats.get("last_clean", "—") or "—")
        self._hist_tree.delete(*self._hist_tree.get_children())
        for entry in reversed(history):
            icon = "🧹" if entry.get("action") == "limpeza" else "📄"
            freed = entry.get("freed_str", "—") if entry.get("freed", 0) > 0 else "—"
            self._hist_tree.insert("", tk.END, values=(
                entry.get("date",""), f"{icon} {entry.get('action','')}",
                entry.get("category",""), freed, entry.get("details","")[:60]))

    def _clear_history(self):
        if messagebox.askyesno("Limpar Histórico", "Apagar todo o histórico?"):
            clear_history()
            self._refresh_history()
            self.set_status("Histórico apagado", "info")

    # ── Página Espaço ───────────────────────────────────────────────────────────

    def _pg_disk(self):
        page = tk.Frame(self._content, bg=BG_MAIN)

        hdr = tk.Frame(page, bg=BG_MAIN)
        hdr.pack(fill=tk.X, padx=20, pady=(16, 6))
        tk.Label(hdr, text="💾  Análise de Espaço em Disco", font=("Segoe UI", 16, "bold"),
                 bg=BG_MAIN, fg=TEXT_PRI).pack(side=tk.LEFT)
        create_button(hdr, "🔄 Actualizar", self._run_disk, "teal").pack(side=tk.RIGHT)
        tk.Frame(page, bg=DIVIDER, height=1).pack(fill=tk.X, padx=20, pady=4)

        # Barras de partições
        part_card = create_card(page, title="PARTIÇÕES MONTADAS")
        part_card.pack(fill=tk.X, padx=20, pady=(8, 0))
        self._disk_parts_frame = tk.Frame(part_card, bg=BG_CARD)
        self._disk_parts_frame.pack(fill=tk.X, padx=10, pady=8)

        # Top maiores pastas
        big_card = create_card(page, title="MAIORES PASTAS ( ~ e /var )")
        big_card.pack(fill=tk.BOTH, expand=True, padx=20, pady=(8, 14))

        cols = ("size", "path")
        self._disk_tree = ttk.Treeview(big_card, style="HC.Treeview",
                                        columns=cols, show="headings",
                                        selectmode="none")
        self._disk_tree.heading("size", text="Tamanho")
        self._disk_tree.heading("path", text="Caminho")
        self._disk_tree.column("size", width=100, anchor=tk.E)
        self._disk_tree.column("path", width=600)

        sb = ttk.Scrollbar(big_card, style="HC.Vertical.TScrollbar", command=self._disk_tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._disk_tree.configure(yscrollcommand=sb.set)
        self._disk_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        return page

    def _run_disk(self):
        self.set_status("A analisar disco...", "info")
        threading.Thread(target=self._run_disk_worker, daemon=True).start()

    def _run_disk_worker(self):
        import shutil as sh

        # Partições
        try:
            import subprocess
            rc, out, _ = (lambda r: (r.returncode, r.stdout, r.stderr))(
                subprocess.run(["df", "-h", "--output=target,size,used,avail,pcent,fstype"],
                               capture_output=True, text=True))
            partitions = []
            if rc == 0:
                for line in out.splitlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 5 and parts[0].startswith("/"):
                        mount, size, used, avail, pct, *_ = parts
                        try:
                            pct_val = int(pct.replace("%", ""))
                        except Exception:
                            pct_val = 0
                        partitions.append((mount, size, used, avail, pct_val))
        except Exception:
            partitions = []

        # Maiores pastas
        top = scan_disk_usage_top()

        self.after(0, lambda: self._refresh_disk(partitions, top))

    def _refresh_disk(self, partitions, top):
        # Limpar frame de partições
        for w in self._disk_parts_frame.winfo_children():
            w.destroy()

        for mount, size, used, avail, pct in partitions[:6]:
            row = tk.Frame(self._disk_parts_frame, bg=BG_CARD)
            row.pack(fill=tk.X, pady=3)

            # Label
            tk.Label(row, text=f"{mount}",
                     width=20, anchor=tk.W,
                     font=("Consolas", 9), bg=BG_CARD, fg=TEXT_PRI).pack(side=tk.LEFT)

            # Barra de progresso
            bar_bg = tk.Frame(row, bg=BG_PANEL, height=14, width=300)
            bar_bg.pack(side=tk.LEFT, padx=8)
            bar_bg.pack_propagate(False)
            color = DANGER if pct > 85 else (WARNING if pct > 60 else SUCCESS)
            bar_fill = tk.Frame(bar_bg, bg=color, height=14,
                                width=max(2, int(300 * pct / 100)))
            bar_fill.place(x=0, y=0)

            tk.Label(row, text=f"{pct}%  {used}/{size}  (livre: {avail})",
                     font=("Consolas", 9), bg=BG_CARD, fg=TEXT_MUT).pack(side=tk.LEFT)

        # Maiores pastas
        self._disk_tree.delete(*self._disk_tree.get_children())
        for size_str, path in top:
            self._disk_tree.insert("", tk.END, values=(size_str, path))

        self.set_status("Análise de disco actualizada", "success")


    # ── Página Sobre ────────────────────────────────────────────

    def _pg_about(self):
        import platform as _platform

        page = tk.Frame(self._content, bg=BG_MAIN)

        hdr = tk.Frame(page, bg=BG_MAIN)
        hdr.pack(fill=tk.X, padx=20, pady=(16, 6))
        tk.Label(hdr, text="ℹ️  Sobre o HCMaint", font=("Segoe UI", 16, "bold"),
                 bg=BG_MAIN, fg=TEXT_PRI).pack(side=tk.LEFT)
        tk.Frame(page, bg=DIVIDER, height=1).pack(fill=tk.X, padx=20, pady=4)

        # Card central com logo + info
        center = tk.Frame(page, bg=BG_MAIN)
        center.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Card principal
        main_card = tk.Frame(center, bg=BG_CARD,
                              highlightthickness=1, highlightbackground=BORDER)
        main_card.pack(fill=tk.X, pady=(0, 12))

        # Logo e título
        logo_f = tk.Frame(main_card, bg=BG_CARD)
        logo_f.pack(pady=24)

        if self.logo_image:
            tk.Label(logo_f, image=self.logo_image, bg=BG_CARD).pack()

        tk.Label(logo_f, text="HCMaint",
                 font=("Segoe UI", 22, "bold"),
                 bg=BG_CARD, fg=ACCENT).pack(pady=(10, 0))
        tk.Label(logo_f, text="Ferramenta de Manutenção do Linux",
                 font=("Segoe UI", 11),
                 bg=BG_CARD, fg=TEXT_MUT).pack()
        tk.Label(logo_f, text=f"v{APP_VERSION}",
                 font=("Segoe UI", 10),
                 bg=BG_CARD, fg=TEXT_SEC).pack(pady=(4, 0))

        tk.Frame(main_card, bg=DIVIDER, height=1).pack(fill=tk.X, padx=20, pady=8)

        # Grid de informações
        grid = tk.Frame(main_card, bg=BG_CARD)
        grid.pack(fill=tk.X, padx=30, pady=(0, 20))

        def info_row(label, value, color=TEXT_PRI):
            row = tk.Frame(grid, bg=BG_CARD)
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=label, font=("Segoe UI", 9),
                     bg=BG_CARD, fg=TEXT_MUT, width=18, anchor=tk.W).pack(side=tk.LEFT)
            tk.Label(row, text=value, font=("Segoe UI", 9, "bold"),
                     bg=BG_CARD, fg=color, anchor=tk.W).pack(side=tk.LEFT)

        info_row("Versão",        f"v{APP_VERSION}", ACCENT)
        info_row("Autor",         "HCsoftware")
        info_row("Localização",   "Silves, Algarve, Portugal")
        info_row("Licença",       "Uso privado e pessoal")
        info_row("Plataforma",    "Linux (Debian/Ubuntu/Mint)")
        info_row("Repositório",   "github.com/condessa/hcmaint", INFO)

        # Email clicável
        email_row = tk.Frame(grid, bg=BG_CARD)
        email_row.pack(fill=tk.X, pady=3)
        tk.Label(email_row, text="Contacto", font=("Segoe UI", 9),
                 bg=BG_CARD, fg=TEXT_MUT, width=18, anchor=tk.W).pack(side=tk.LEFT)
        email_lbl = tk.Label(email_row, text="condessasilva@gmail.com",
                              font=("Segoe UI", 9, "bold"),
                              bg=BG_CARD, fg=INFO, cursor="hand2", anchor=tk.W)
        email_lbl.pack(side=tk.LEFT)
        email_lbl.bind("<Button-1>", lambda e: __import__('webbrowser').open(
            "mailto:condessasilva@gmail.com?subject=HCMaint%20v" + APP_VERSION))
        email_lbl.bind("<Enter>", lambda e: email_lbl.config(fg=ACCENT, font=("Segoe UI", 9, "bold underline")))
        email_lbl.bind("<Leave>", lambda e: email_lbl.config(fg=INFO,   font=("Segoe UI", 9, "bold")))

        tk.Frame(main_card, bg=DIVIDER, height=1).pack(fill=tk.X, padx=20, pady=4)

        # Info do sistema
        sys_grid = tk.Frame(main_card, bg=BG_CARD)
        sys_grid.pack(fill=tk.X, padx=30, pady=(0, 20))

        try:
            import tkinter
            tk_ver = tkinter.TkVersion
        except Exception:
            tk_ver = "—"

        py_ver = _platform.python_version()
        so_info = f"{_platform.system()} {_platform.release()}"
        arch    = _platform.machine()

        tk.Label(sys_grid, text="SISTEMA", font=("Segoe UI", 8, "bold"),
                 bg=BG_CARD, fg=TEXT_MUT).pack(anchor=tk.W, pady=(0, 4))

        def sys_row(label, value, color=TEXT_SEC):
            row = tk.Frame(sys_grid, bg=BG_CARD)
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=label, font=("Segoe UI", 9),
                     bg=BG_CARD, fg=TEXT_MUT, width=18, anchor=tk.W).pack(side=tk.LEFT)
            tk.Label(row, text=value, font=("Segoe UI", 9, "bold"),
                     bg=BG_CARD, fg=color, anchor=tk.W).pack(side=tk.LEFT)

        sys_row("SO",         so_info)
        sys_row("Arquitectura", arch)
        sys_row("Python",     py_ver,       SUCCESS)
        sys_row("Interface",  "Tkinter",    SUCCESS)
        sys_row("Root",       "Sim ✅" if is_root() else "Não", SUCCESS if is_root() else WARNING)

        # Cards de funcionalidades
        feats_f = tk.Frame(center, bg=BG_MAIN)
        feats_f.pack(fill=tk.X)

        feats = [
            ("🧹", "Limpeza",         "Cache APT, logs,\nFlatpak, Snap, Docker"),
            ("🛠️", "Ferramentas",     "Caches dev, ficheiros grandes,\nhistórico, relatório"),
            ("💾", "Espaço em Disco", "Barras de partições,\nmaiores pastas"),
            ("🔄", "Actualizações",   "Verificação automática\nvia GitHub"),
        ]

        for icon, title, desc in feats:
            c = tk.Frame(feats_f, bg=BG_CARD,
                         highlightthickness=1, highlightbackground=BORDER)
            c.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
            tk.Label(c, text=icon, font=("Segoe UI Emoji", 18),
                     bg=BG_CARD).pack(pady=(12, 2))
            tk.Label(c, text=title, font=("Segoe UI", 9, "bold"),
                     bg=BG_CARD, fg=ACCENT).pack()
            tk.Label(c, text=desc, font=("Segoe UI", 8),
                     bg=BG_CARD, fg=TEXT_MUT,
                     justify=tk.CENTER).pack(pady=(2, 12))

        # Botão verificar actualizações
        btn_f = tk.Frame(page, bg=BG_MAIN)
        btn_f.pack(pady=12)
        create_button(btn_f, "🔄  Verificar Actualizações",
                      self._check_updates_background, "teal").pack(side=tk.LEFT, padx=6)
        create_button(btn_f, "🌐  GitHub",
                      lambda: __import__('webbrowser').open(f"https://github.com/{GITHUB_REPO}"),
                      "secondary").pack(side=tk.LEFT, padx=6)

        # Rodapé
        tk.Label(page, text=f"HCsoftware © 2026  •  v{APP_VERSION}  •  Silves, Algarve",
                 font=("Segoe UI", 8), bg=BG_MAIN, fg=TEXT_MUT).pack(pady=(0, 10))

        return page


# ─── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    app = HCMaint()
    app.mainloop()
