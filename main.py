"""
HC-Cleaner v1.3.0
HCsoftware - Ferramenta de Manutenção e Limpeza do Windows
Alternativa ao CCleaner — sem bloatware, sem telemetria
"""

import os
import sys
import threading
import platform
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

# Adicionar raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hc_theme import (
    HCApplication, create_button, create_card, setup_log_area,
    BG_MAIN, BG_PANEL, BG_CARD, BG_TOPBAR, BG_SIDEBAR, BG_INPUT,
    ACCENT, ACCENT_HOV, ACCENT_DRK, TEXT_PRI, TEXT_SEC, TEXT_MUT,
    SUCCESS, DANGER, WARNING, INFO, GREEN, RED, YELLOW,
    BORDER, DIVIDER, LOG_BG, LOG_SENT, LOG_RECV,
)
from modules.cleaner import (
    CLEAN_TARGETS, scan_all, scan_category, clean_item,
    safe_clean_thumbnails, format_size,
    get_running_browsers, get_running_browsers_names,
    category_needs_browsers_closed, browsers_are_running,
)
from modules.registry import scan_all_registry, delete_registry_issue, REGISTRY_CHECKS
from modules.uninstaller import (
    get_installed_programs, uninstall_program, force_uninstall,
    uninstall_edge, clean_residuals, open_programs_and_features
)
from modules.malware import scan_all_threats, RISK_COLORS, RISK_ICONS, run_windows_defender_quick


# ─────────────────────────────────────────────
# NAV BUTTON
# ─────────────────────────────────────────────
class NavButton(tk.Frame):
    def __init__(self, parent, icon, label, command, **kwargs):
        super().__init__(parent, bg=BG_SIDEBAR, cursor="hand2", **kwargs)
        self._cmd = command
        self._active = False

        self._indicator = tk.Frame(self, bg=BG_SIDEBAR, width=3)
        self._indicator.pack(side=tk.LEFT, fill=tk.Y)

        inner = tk.Frame(self, bg=BG_SIDEBAR)
        inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=7)

        tk.Label(inner, text=icon, font=("Segoe UI Emoji", 13),
                 bg=BG_SIDEBAR, fg=TEXT_SEC).pack(side=tk.LEFT, padx=(0, 6))
        self._lbl = tk.Label(inner, text=label, font=("Segoe UI", 9),
                              bg=BG_SIDEBAR, fg=TEXT_SEC, anchor=tk.W)
        self._lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        for w in [self, inner, self._lbl]:
            w.bind("<Button-1>", self._click)
            w.bind("<Enter>", self._hover_on)
            w.bind("<Leave>", self._hover_off)

    def _click(self, e=None):
        self._cmd()

    def _hover_on(self, e=None):
        if not self._active:
            for w in [self, self.winfo_children()[1]]:
                w.configure(bg=BG_PANEL)
            self._lbl.configure(bg=BG_PANEL)

    def _hover_off(self, e=None):
        if not self._active:
            for w in [self, self.winfo_children()[1]]:
                w.configure(bg=BG_SIDEBAR)
            self._lbl.configure(bg=BG_SIDEBAR)

    def set_active(self, active):
        self._active = active
        bg = BG_CARD if active else BG_SIDEBAR
        fg = ACCENT if active else TEXT_SEC
        ind = ACCENT if active else BG_SIDEBAR
        self._indicator.configure(bg=ind)
        self.configure(bg=bg)
        self.winfo_children()[1].configure(bg=bg)
        self._lbl.configure(bg=bg, fg=fg,
                             font=("Segoe UI", 10, "bold") if active else ("Segoe UI", 10))


# ─────────────────────────────────────────────
# MAIN APPLICATION
# ─────────────────────────────────────────────
class HCCleaner(HCApplication):
    def __init__(self):
        super().__init__(title="", geometry="1100x680")
        self.resizable(True, True)

        self._pages = {}
        self._nav_btns = {}
        self._current_page = None

        self._cleaner_results = {}
        self._registry_issues = []
        self._malware_findings = []
        self._programs_list = []

        self._build_layout()
        self._show_page("dashboard")
        self.set_status("HC-Cleaner pronto  •  " + platform.platform(), "info")

    # ──────────── LAYOUT ────────────
    def _build_layout(self):
        sidebar = tk.Frame(self.main_container, bg=BG_SIDEBAR, width=168)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # Cabeçalho sidebar
        hdr = tk.Frame(sidebar, bg=BG_TOPBAR, height=38)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="HC-Cleaner",
                 font=("Segoe UI", 10, "bold"),
                 bg=BG_TOPBAR, fg=SUCCESS).pack(side=tk.LEFT, padx=12, pady=8)

        tk.Frame(sidebar, bg=ACCENT_DRK, height=2).pack(fill=tk.X)

        nav_items = [
            ("⌂",  "Dashboard",  "dashboard"),
            ("🧹", "Limpeza",    "cleaner"),
            ("🔑", "Registo",    "registry"),
            ("📦", "Programas",  "programs"),
            ("🦠", "Malware",    "malware"),
            ("ℹ️",  "Sobre",      "about"),
        ]
        for icon, label, key in nav_items:
            btn = NavButton(sidebar, icon, label, lambda k=key: self._show_page(k))
            btn.pack(fill=tk.X)
            self._nav_btns[key] = btn

        tk.Frame(sidebar, bg=DIVIDER, height=1).pack(fill=tk.X, pady=(6, 0))
        tk.Label(sidebar, text="v1.4.9  •  HCsoftware",
                 font=("Segoe UI", 7), bg=BG_SIDEBAR, fg=TEXT_MUT).pack(
            side=tk.BOTTOM, pady=6)

        self._content = tk.Frame(self.main_container, bg=BG_MAIN)
        self._content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._pages["dashboard"] = self._build_dashboard()
        self._pages["cleaner"]   = self._build_cleaner()
        self._pages["registry"]  = self._build_registry()
        self._pages["programs"]  = self._build_programs()
        self._pages["malware"]   = self._build_malware()
        self._pages["about"]     = self._build_about()

    def _show_page(self, key):
        if self._current_page:
            self._pages[self._current_page].pack_forget()
            self._nav_btns[self._current_page].set_active(False)
        self._pages[key].pack(fill=tk.BOTH, expand=True)
        self._nav_btns[key].set_active(True)
        self._current_page = key

    # ──────────── DASHBOARD ────────────
    def _build_dashboard(self):
        page = tk.Frame(self._content, bg=BG_MAIN)

        hdr = tk.Frame(page, bg=BG_MAIN)
        hdr.pack(fill=tk.X, padx=16, pady=(10, 6))
        tk.Label(hdr, text="Dashboard", font=("Segoe UI", 14, "bold"),
                 bg=BG_MAIN, fg=TEXT_PRI).pack(side=tk.LEFT)
        tk.Label(hdr, text=datetime.now().strftime("  %d/%m/%Y"),
                 font=("Segoe UI", 9), bg=BG_MAIN, fg=TEXT_MUT).pack(side=tk.LEFT)
        tk.Frame(page, bg=DIVIDER, height=1).pack(fill=tk.X, padx=16)

        mid = tk.Frame(page, bg=BG_MAIN)
        mid.pack(fill=tk.BOTH, expand=True, padx=14, pady=8)

        # ── ESQUERDA ──
        left_col = tk.Frame(mid, bg=BG_MAIN, width=260)
        left_col.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_col.pack_propagate(False)

        circle_card = create_card(left_col, title="PROGRESSO")
        circle_card.pack(fill=tk.X, pady=(0, 6))

        self._progress_canvas = tk.Canvas(
            circle_card, width=160, height=160,
            bg=BG_CARD, highlightthickness=0)
        self._progress_canvas.pack(pady=8)
        self._draw_progress_circle(0, "idle")

        self._phase_lbl = tk.Label(circle_card,
            text="Pronto para analisar",
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD, fg=ACCENT, wraplength=220, justify=tk.CENTER)
        self._phase_lbl.pack(pady=(0, 2))

        self._subphase_lbl = tk.Label(circle_card,
            text="", font=("Segoe UI", 7),
            bg=BG_CARD, fg=TEXT_MUT, wraplength=220, justify=tk.CENTER)
        self._subphase_lbl.pack(pady=(0, 6))

        phases_card = create_card(left_col, title="FASES")
        phases_card.pack(fill=tk.X, pady=(0, 6))

        self._phase_indicators = {}
        for key, icon, label in [
            ("clean",    "🧹", "Ficheiros"),
            ("registry", "🔑", "Registo"),
            ("malware",  "🦠", "Malware"),
            ("programs", "📦", "Programas"),
        ]:
            row = tk.Frame(phases_card, bg=BG_CARD)
            row.pack(fill=tk.X, padx=8, pady=2)
            dot = tk.Label(row, text="⬤", font=("Segoe UI", 7), bg=BG_CARD, fg=TEXT_MUT)
            dot.pack(side=tk.LEFT, padx=(0, 5))
            tk.Label(row, text=f"{icon} {label}",
                     font=("Segoe UI", 8), bg=BG_CARD, fg=TEXT_SEC).pack(side=tk.LEFT)
            val_lbl = tk.Label(row, text="—", font=("Segoe UI", 8, "bold"),
                               bg=BG_CARD, fg=TEXT_MUT, anchor=tk.E)
            val_lbl.pack(side=tk.RIGHT)
            self._phase_indicators[key] = {"dot": dot, "val": val_lbl}

        btn_frame = tk.Frame(left_col, bg=BG_MAIN)
        btn_frame.pack(fill=tk.X, pady=4)
        create_button(btn_frame, "⚡ Análise Completa",
                      self._run_full_analysis, "primary").pack(fill=tk.X, pady=(0, 4))
        create_button(btn_frame, "🧹 Limpeza Rápida",
                      self._quick_clean, "teal").pack(fill=tk.X)

        # ── DIREITA ──
        right_col = tk.Frame(mid, bg=BG_MAIN)
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        cards_frame = tk.Frame(right_col, bg=BG_MAIN)
        cards_frame.pack(fill=tk.X, pady=(0, 8))

        self._dash_cards = {}
        summary = [
            ("🧹", "Limpeza",   "—", ACCENT,  "cleaner"),
            ("🔑", "Registo",   "—", WARNING, "registry"),
            ("🦠", "Ameaças",   "—", DANGER,  "malware"),
            ("📦", "Programas", "—", SUCCESS, "programs"),
        ]
        for icon, title, subtitle, color, page_key in summary:
            card = tk.Frame(cards_frame, bg=BG_CARD,
                            highlightthickness=1, highlightbackground=BORDER,
                            cursor="hand2")
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
            lbl_icon  = tk.Label(card, text=icon, font=("Segoe UI Emoji", 18), bg=BG_CARD, fg=color)
            lbl_icon.pack(pady=(10, 2))
            lbl_val   = tk.Label(card, text=subtitle, font=("Segoe UI", 12, "bold"), bg=BG_CARD, fg=color)
            lbl_val.pack()
            lbl_title = tk.Label(card, text=title, font=("Segoe UI", 8), bg=BG_CARD, fg=TEXT_MUT)
            lbl_title.pack()
            lbl_hint  = tk.Label(card, text="clique para abrir →", font=("Segoe UI", 7), bg=BG_CARD, fg=TEXT_MUT)
            lbl_hint.pack(pady=(0, 8))

            def _make_handlers(pk, c, lh):
                def on_enter(e):
                    c.configure(highlightbackground=ACCENT, highlightthickness=2)
                    lh.configure(fg=ACCENT)
                def on_leave(e):
                    c.configure(highlightbackground=BORDER, highlightthickness=1)
                    lh.configure(fg=TEXT_MUT)
                def on_click(e): self._show_page(pk)
                return on_enter, on_leave, on_click

            on_enter, on_leave, on_click = _make_handlers(page_key, card, lbl_hint)
            for w in [card, lbl_icon, lbl_val, lbl_title, lbl_hint]:
                w.bind("<Enter>",    on_enter)
                w.bind("<Leave>",    on_leave)
                w.bind("<Button-1>", on_click)
            self._dash_cards[title] = lbl_val

        log_card = create_card(right_col, title="ACTIVIDADE")
        log_card.pack(fill=tk.BOTH, expand=True)
        lf, lt = setup_log_area(log_card)
        lf.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self._dash_log = lt

        self._anim_angle   = 0
        self._anim_job     = None
        self._analysis_pct = 0

        return page

    # ── Círculo de progresso ──
    def _draw_progress_circle(self, pct, state="idle"):
        import math
        c = self._progress_canvas
        c.delete("all")
        cx, cy, r_out, r_in = 80, 80, 68, 50

        ring_color, text_color = {
            "idle":    (BG_PANEL, TEXT_MUT),
            "running": (ACCENT,   TEXT_PRI),
            "done":    (SUCCESS,  SUCCESS),
            "error":   (DANGER,   DANGER),
        }.get(state, (BG_PANEL, TEXT_MUT))

        c.create_oval(cx-r_out, cy-r_out, cx+r_out, cy+r_out,
                      outline=BG_PANEL, width=14, fill=BG_CARD)
        if pct > 0:
            c.create_arc(cx-r_out, cy-r_out, cx+r_out, cy+r_out,
                         start=90, extent=-min(359.9, pct*3.6),
                         outline=ring_color, width=14, style="arc")
        c.create_oval(cx-r_in, cy-r_in, cx+r_in, cy+r_in, fill=BG_CARD, outline=BG_CARD)

        if state == "done":
            c.create_text(cx, cy-8,  text="✓", font=("Segoe UI", 22, "bold"), fill=SUCCESS, anchor=tk.CENTER)
            c.create_text(cx, cy+16, text="Concluído", font=("Segoe UI", 8),  fill=SUCCESS, anchor=tk.CENTER)
        elif state == "idle":
            c.create_text(cx, cy-6,  text="🛡️", font=("Segoe UI Emoji", 20), fill=TEXT_MUT, anchor=tk.CENTER)
            c.create_text(cx, cy+18, text="Pronto",    font=("Segoe UI", 8),  fill=TEXT_MUT, anchor=tk.CENTER)
        else:
            c.create_text(cx, cy-8, text=f"{int(pct)}%", font=("Segoe UI", 14, "bold"),
                          fill=text_color, anchor=tk.CENTER)
            angle_rad = math.radians(self._anim_angle)
            sx = cx + r_out * math.cos(angle_rad)
            sy = cy - r_out * math.sin(angle_rad)
            c.create_oval(sx-4, sy-4, sx+4, sy+4, fill="white", outline="")

    def _animate_circle(self):
        if self._anim_job is None: return
        self._anim_angle = (self._anim_angle - 6) % 360
        self._draw_progress_circle(self._analysis_pct, "running")
        self._anim_job = self.after(50, self._animate_circle)

    def _start_circle_animation(self):
        self._anim_angle = 0; self._analysis_pct = 0
        if self._anim_job: self.after_cancel(self._anim_job)
        self._anim_job = self.after(50, self._animate_circle)

    def _stop_circle_animation(self, state="done"):
        if self._anim_job: self.after_cancel(self._anim_job); self._anim_job = None
        self._draw_progress_circle(100 if state == "done" else self._analysis_pct, state)

    def _set_phase(self, phase_key, pct, label, sublabel="", value=None, value_color=None):
        self._analysis_pct = pct
        self.after(0, lambda: self._phase_lbl.config(text=label))
        self.after(0, lambda: self._subphase_lbl.config(text=sublabel))
        if phase_key and phase_key in self._phase_indicators:
            ind = self._phase_indicators[phase_key]
            if value is not None:
                co = value_color or SUCCESS
                self.after(0, lambda i=ind, v=value, c=co: (
                    i["dot"].config(fg=c), i["val"].config(text=v, fg=c)))
            else:
                self.after(0, lambda i=ind: (
                    i["dot"].config(fg=ACCENT), i["val"].config(text="...", fg=ACCENT)))

    def _log_dash(self, msg, tag="recv"):
        self._dash_log.config(state=tk.NORMAL)
        ts = datetime.now().strftime("%H:%M:%S")
        self._dash_log.insert(tk.END, f"[{ts}] {msg}\n", tag)
        self._dash_log.see(tk.END)
        self._dash_log.config(state=tk.DISABLED)

    def _run_full_analysis(self):
        self._log_dash("▶  Análise completa iniciada...", "info")
        for ind in self._phase_indicators.values():
            ind["dot"].config(fg=TEXT_MUT); ind["val"].config(text="—", fg=TEXT_MUT)
        self._start_circle_animation()
        threading.Thread(target=self._full_analysis_worker, daemon=True).start()

    def _full_analysis_worker(self):
        # 1. Ficheiros
        self._set_phase("clean", 2, "A analisar ficheiros...", "Temporários, cache, logs")
        self.after(0, lambda: self._log_dash("🧹 A analisar ficheiros...", "info"))
        def prog_clean(i, total, msg):
            self._analysis_pct = (i / max(total, 1)) * 25
            short = msg[:55] + "..." if len(msg) > 55 else msg
            self.after(0, lambda m=short: self._subphase_lbl.config(text=m))
            self.after(0, lambda m=msg: self._log_dash(f"   {m}", "muted"))
        self._cleaner_results = scan_all(progress_callback=prog_clean)
        total_size = sum(r["size"] for r in self._cleaner_results.values())
        self._set_phase("clean", 25, "Ficheiros concluído", value=format_size(total_size), value_color=ACCENT)
        self.after(0, lambda: self._log_dash(f"✅ Ficheiros: {format_size(total_size)} encontrados", "ok"))
        self.after(0, lambda: self._dash_cards["Limpeza"].config(text=format_size(total_size)))

        # 2. Registo
        self._set_phase("registry", 26, "A analisar registo...", "Chaves inválidas, orphans")
        self.after(0, lambda: self._log_dash("🔑 A analisar registo...", "info"))
        def prog_reg(i, total, msg):
            self._analysis_pct = 25 + (i / max(total, 1)) * 25
            short = msg[:55] + "..." if len(msg) > 55 else msg
            self.after(0, lambda m=short: self._subphase_lbl.config(text=m))
        self._registry_issues = scan_all_registry(progress_callback=prog_reg)
        n_reg = len(self._registry_issues)
        self._set_phase("registry", 50, "Registo concluído",
                        value=f"{n_reg} problemas", value_color=WARNING if n_reg > 0 else SUCCESS)
        self.after(0, lambda: self._log_dash(f"✅ Registo: {n_reg} problemas encontrados", "ok"))
        self.after(0, lambda: self._dash_cards["Registo"].config(
            text=f"{n_reg} {'problema' if n_reg == 1 else 'problemas'}"))

        # 3. Malware
        self._set_phase("malware", 51, "A verificar ameaças...", "Executáveis suspeitos, autorun, hosts")
        self.after(0, lambda: self._log_dash("🦠 A verificar ameaças...", "warn"))
        from modules.malware import (
            scan_temp_executables, scan_autorun_entries, scan_winlogon,
            scan_running_processes, scan_hosts_file,
            TIMEOUT_TEMP, TIMEOUT_AUTORUN, TIMEOUT_WINLOGON,
            TIMEOUT_PROCESSES, TIMEOUT_HOSTS, _run_with_timeout,
        )
        mal_phase_steps = [
            ("Executáveis em temporários...", scan_temp_executables,  TIMEOUT_TEMP + 2),
            ("Entradas de arranque...",        scan_autorun_entries,   TIMEOUT_AUTORUN + 2),
            ("Winlogon Shell/Userinit...",     scan_winlogon,          TIMEOUT_WINLOGON + 2),
            ("Processos suspeitos...",         scan_running_processes, TIMEOUT_PROCESSES + 3),
            ("Ficheiro hosts...",              scan_hosts_file,        TIMEOUT_HOSTS + 2),
        ]
        self._malware_findings = []
        for idx, (step_msg, step_fn, step_timeout) in enumerate(mal_phase_steps):
            self._analysis_pct = 51 + (idx / len(mal_phase_steps)) * 24
            self.after(0, lambda m=step_msg: self._subphase_lbl.config(text=m))
            self.after(0, lambda m=step_msg: self._log_dash(f"   {m}", "muted"))
            result, err = _run_with_timeout(step_fn, step_timeout, default=[])
            if result: self._malware_findings.extend(result)
            if err:
                self.after(0, lambda e=err, m=step_msg: self._log_dash(f"   ⚠️ {m} — {e}", "warn"))
        n_mal = len(self._malware_findings)
        color_mal = DANGER if n_mal > 0 else SUCCESS
        self._set_phase("malware", 75, "Malware concluído",
                        value=f"{n_mal} {'ameaça' if n_mal == 1 else 'ameaças'}", value_color=color_mal)
        self.after(0, lambda: self._log_dash(
            f"{'⚠️' if n_mal else '✅'} Malware: {n_mal} ameaças", "warn" if n_mal else "ok"))
        self.after(0, lambda: self._dash_cards["Ameaças"].config(
            text=f"{n_mal} {'ameaça' if n_mal == 1 else 'ameaças'}", fg=color_mal))

        # 4. Programas
        self._set_phase("programs", 76, "A listar programas instalados...", "")
        self.after(0, lambda: self._log_dash("📦 A listar programas...", "info"))
        self._programs_list = get_installed_programs()
        n_prog = len(self._programs_list)
        self._set_phase("programs", 100, "Programas concluído",
                        value=f"{n_prog} instalados", value_color=SUCCESS)
        self.after(0, lambda: self._log_dash(f"✅ Programas: {n_prog} instalados", "ok"))
        self.after(0, lambda: self._dash_cards["Programas"].config(text=f"{n_prog} instalados"))

        # Concluído
        self.after(0, lambda: self._stop_circle_animation("done"))
        self.after(0, lambda: self._phase_lbl.config(text="✅  Análise completa concluída!", fg=SUCCESS))
        self.after(0, lambda: self._subphase_lbl.config(text=""))
        self.after(0, lambda: self._log_dash("─── Análise concluída ───", "ok"))
        self.after(0, lambda: self.set_status("Análise completa concluída", "success"))
        self.after(100, self._refresh_cleaner_results)
        self.after(200, self._refresh_registry_results)
        self.after(300, self._refresh_malware_results)
        self.after(400, self._refresh_programs_list)

    def _quick_clean(self):
        if not self._cleaner_results:
            messagebox.showinfo("HC-Cleaner", "Execute primeiro uma Análise Completa.")
            return
        if messagebox.askyesno("Limpeza Rápida", "Limpar todos os ficheiros desnecessários encontrados?"):
            threading.Thread(target=self._quick_clean_worker, daemon=True).start()

    def _quick_clean_worker(self):
        self.after(0, lambda: self._phase_lbl.config(text="🧹  A limpar ficheiros...", fg=ACCENT))
        self.after(0, lambda: self._start_circle_animation())
        total_cleaned = 0; total_failed = 0
        all_items = [item for r in self._cleaner_results.values() for item in r.get("items", [])]
        for i, item in enumerate(all_items):
            self._analysis_pct = (i / max(len(all_items), 1)) * 100
            ok, _ = clean_item(item)
            if ok: total_cleaned += item["size"]
            else:  total_failed  += 1
        for key in self._cleaner_results:
            self._cleaner_results[key]["items"] = []; self._cleaner_results[key]["size"] = 0
        self.after(0, lambda: self._stop_circle_animation("done"))
        self.after(0, lambda: self._phase_lbl.config(text=f"✅  Limpo: {format_size(total_cleaned)}", fg=SUCCESS))
        self.after(0, lambda: self._subphase_lbl.config(text=""))
        self.after(0, lambda: self._log_dash(
            f"🧹 Limpeza rápida: {format_size(total_cleaned)} libertados, {total_failed} erros", "ok"))
        self.after(0, lambda: self.set_status(f"Limpeza concluída: {format_size(total_cleaned)} libertados", "success"))
        self.after(0, lambda: self._dash_cards["Limpeza"].config(text="Limpo ✓"))
        self.after(0, self._refresh_cleaner_results)
        self.after(0, lambda: self._file_tree.delete(*self._file_tree.get_children()))
        self.after(0, lambda: self._clean_total_lbl.config(text="Total detectado:  0 B"))
        self.after(0, lambda: self._clean_progress.__setitem__("value", 0))

    # ──────────── CLEANER PAGE ────────────
    def _build_cleaner(self):
        page = tk.Frame(self._content, bg=BG_MAIN)
        hdr = tk.Frame(page, bg=BG_MAIN)
        hdr.pack(fill=tk.X, padx=14, pady=(10, 6))
        tk.Label(hdr, text="🧹  Limpeza de Ficheiros", font=("Segoe UI", 13, "bold"),
                 bg=BG_MAIN, fg=TEXT_PRI).pack(side=tk.LEFT)
        btn_f = tk.Frame(hdr, bg=BG_MAIN)
        btn_f.pack(side=tk.RIGHT)
        create_button(btn_f, "🔍 Analisar",          self._scan_cleaner,   "teal"   ).pack(side=tk.LEFT, padx=4)
        create_button(btn_f, "🗑️ Limpar Selecionado", self._clean_selected, "primary").pack(side=tk.LEFT, padx=4)
        create_button(btn_f, "✨ Limpar Tudo",        self._clean_all,      "warning").pack(side=tk.LEFT, padx=4)
        tk.Frame(page, bg=DIVIDER, height=1).pack(fill=tk.X, padx=14, pady=3)

        # Barra de aviso de browsers abertos
        self._browser_warn_bar = tk.Frame(page, bg="#5a1a00")
        self._browser_warn_lbl = tk.Label(
            self._browser_warn_bar,
            text="",
            font=("Segoe UI", 9, "bold"),
            bg="#5a1a00", fg="#ffaa44",
            pady=4, padx=12, anchor=tk.W
        )
        self._browser_warn_lbl.pack(fill=tk.X)
        self._update_browser_warning()

        self._clean_progress = ttk.Progressbar(page, style="HC.Horizontal.TProgressbar", mode="determinate")
        self._clean_progress.pack(fill=tk.X, padx=14, pady=(3, 6))
        split = tk.Frame(page, bg=BG_MAIN)
        split.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))

        left = create_card(split, title="CATEGORIAS")
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left.configure(width=280); left.pack_propagate(False)
        self._cat_tree = ttk.Treeview(left, style="HC.Treeview",
                                       columns=("size",), show="tree headings", selectmode="browse")
        self._cat_tree.heading("#0", text="Categoria")
        self._cat_tree.heading("size", text="Tamanho")
        self._cat_tree.column("#0", width=180)
        self._cat_tree.column("size", width=80, anchor=tk.E)
        self._cat_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._cat_tree.bind("<<TreeviewSelect>>", self._on_cat_select)

        right = create_card(split, title="FICHEIROS ENCONTRADOS")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._file_tree = ttk.Treeview(right, style="HC.Treeview",
                                        columns=("path", "size", "type"),
                                        show="headings", selectmode="extended")
        self._file_tree.heading("path", text="Caminho")
        self._file_tree.heading("size", text="Tamanho")
        self._file_tree.heading("type", text="Tipo")
        self._file_tree.column("path", width=400)
        self._file_tree.column("size", width=90, anchor=tk.E)
        self._file_tree.column("type", width=70, anchor=tk.CENTER)
        sb = ttk.Scrollbar(right, style="HC.Vertical.TScrollbar", command=self._file_tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._file_tree.configure(yscrollcommand=sb.set)
        self._file_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._clean_total_lbl = tk.Label(page, text="Total: —",
                                          font=("Segoe UI", 10, "bold"),
                                          bg=BG_MAIN, fg=ACCENT, anchor=tk.E)
        self._clean_total_lbl.pack(fill=tk.X, padx=24, pady=(0, 4))
        return page

    def _update_browser_warning(self):
        """Actualiza a barra de aviso de browsers a cada 3 segundos."""
        try:
            running = get_running_browsers_names()
            if running:
                names = ", ".join(running)
                self._browser_warn_lbl.config(
                    text=f"\u26a0\ufe0f  BROWSERS ABERTOS: {names}  \u2014  Feche-os antes de limpar temporários e cache!"
                )
                self._browser_warn_bar.pack(fill=tk.X, padx=14, pady=(0, 4))
            else:
                self._browser_warn_bar.pack_forget()
        except Exception:
            pass
        # Reagendar a cada 3 segundos
        self.after(3000, self._update_browser_warning)

    def _scan_cleaner(self):
        self._cat_tree.delete(*self._cat_tree.get_children())
        self._file_tree.delete(*self._file_tree.get_children())
        self._clean_progress["value"] = 0
        self.set_status("A analisar ficheiros...", "info")
        threading.Thread(target=self._scan_cleaner_worker, daemon=True).start()

    def _scan_cleaner_worker(self):
        def prog(i, total, msg):
            self.after(0, lambda: self._clean_progress.__setitem__("value", i/max(total,1)*100))
            self.after(0, lambda m=msg: self.set_status(m, "info"))
        self._cleaner_results = scan_all(progress_callback=prog)
        self.after(0, self._refresh_cleaner_results)

    def _refresh_cleaner_results(self):
        self._cat_tree.delete(*self._cat_tree.get_children())
        total = 0
        for key, result in self._cleaner_results.items():
            cat  = CLEAN_TARGETS.get(key, {})
            size = result["size"]; total += size
            self._cat_tree.insert("", tk.END, iid=key,
                                  text=f"  {cat.get('icon','📁')}  {result['label']}",
                                  values=(format_size(size),),
                                  tags=("found",) if size > 0 else ())
        self._cat_tree.tag_configure("found", foreground=WARNING)
        self._clean_total_lbl.config(text=f"Total detectado:  {format_size(total)}")
        self._clean_progress["value"] = 100
        self.set_status(f"Análise concluída: {format_size(total)} a limpar", "success")

    def _on_cat_select(self, e=None):
        sel = self._cat_tree.selection()
        if not sel: return
        result = self._cleaner_results.get(sel[0], {})
        self._file_tree.delete(*self._file_tree.get_children())
        for item in result.get("items", []):
            short = item["path"]
            if len(short) > 80: short = "..." + short[-77:]
            ftype = "📁" if item.get("type") == "folder" else "📄"
            self._file_tree.insert("", tk.END, values=(short, format_size(item["size"]), ftype))

    def _check_browsers_and_warn(self, cat_key):
        """Verifica browsers abertos antes de limpar. Retorna True se pode prosseguir."""
        if not category_needs_browsers_closed(cat_key):
            return True
        running = get_running_browsers_names()
        if not running:
            return True
        browsers_str = "\n".join(f"  \u2022 {b}" for b in running)
        msg = (
            f"\u26a0\ufe0f  BROWSERS EM EXECU\u00c7\u00c3O DETECTADOS\n\n"
            f"Os seguintes browsers est\u00e3o abertos:\n{browsers_str}\n\n"
            f"Limpar ficheiros tempor\u00e1rios com browsers abertos pode causar:\n"
            f"  \u2022 Corrup\u00e7\u00e3o de dados e cache do browser\n"
            f"  \u2022 Perda de sess\u00f5es e passwords guardadas\n"
            f"  \u2022 Problemas em actualiza\u00e7\u00f5es do browser\n\n"
            f"RECOMENDA\u00c7\u00c3O: Feche todos os browsers antes de continuar.\n\n"
            f"Deseja continuar mesmo assim? (n\u00e3o recomendado)"
        )
        return messagebox.askyesno("\u26a0\ufe0f Aviso de Seguran\u00e7a", msg, icon="warning")

    def _clean_selected(self):
        sel = self._cat_tree.selection()
        if not sel:
            messagebox.showinfo("HC-Cleaner", "Selecione uma categoria primeiro."); return
        key    = sel[0]
        result = self._cleaner_results.get(key, {})
        items  = result.get("items", [])
        if not items:
            messagebox.showinfo("HC-Cleaner", "Nenhum ficheiro nesta categoria."); return
        # Verificar browsers antes de limpar categorias sensíveis
        if not self._check_browsers_and_warn(key):
            self.set_status("Limpeza cancelada — feche os browsers primeiro", "warning")
            return
        if messagebox.askyesno("Limpar", f"Limpar {format_size(result['size'])} de '{result['label']}'?"):
            threading.Thread(target=lambda: self._do_clean(items, key), daemon=True).start()

    def _clean_all(self):
        total = sum(r["size"] for r in self._cleaner_results.values())
        if not total:
            messagebox.showinfo("HC-Cleaner", "Execute primeiro 'Analisar'."); return

        # Verificar se há browsers abertos (limpeza geral inclui categorias sensíveis)
        running = get_running_browsers_names()
        if running:
            browsers_str = ", ".join(running)
            msg = (
                f"\u26a0\ufe0f  BROWSERS ABERTOS DETECTADOS\n\n"
                f"Est\u00e3o abertos: {browsers_str}\n\n"
                f"A Limpeza Geral inclui ficheiros tempor\u00e1rios e cache\n"
                f"que podem estar a ser usados pelos browsers.\n\n"
                f"Feche todos os browsers antes de continuar para evitar\n"
                f"corrup\u00e7\u00e3o de dados e problemas de actualiza\u00e7\u00e3o.\n\n"
                f"Deseja continuar mesmo assim?"
            )
            if not messagebox.askyesno("\u26a0\ufe0f Aviso de Seguran\u00e7a", msg, icon="warning"):
                self.set_status("Limpeza cancelada — feche os browsers primeiro", "warning")
                return

        if messagebox.askyesno("Limpar Tudo",
                f"Limpar {format_size(total)} de ficheiros?\n\nEsta a\u00e7\u00e3o \u00e9 irrevers\u00edvel."):
            all_items = [item for r in self._cleaner_results.values() for item in r.get("items", [])]
            threading.Thread(target=lambda: self._do_clean(all_items, None), daemon=True).start()

    def _do_clean(self, items, cat_key):
        cleaned = 0; failed = 0
        total_items = max(len(items), 1)

        # Miniaturas: parar Explorer para evitar corrupção de ícones
        if cat_key == "thumbnail_cache":
            def pb(msg):
                self.after(0, lambda m=msg: self.set_status(m, "info"))
            _, freed, errs = safe_clean_thumbnails(items, progress_cb=pb)
            cleaned = freed; failed = errs
            self.after(0, lambda: self._clean_progress.__setitem__("value", 100))
        else:
            for i, item in enumerate(items):
                ok, _ = clean_item(item)
                if ok: cleaned += item.get("size", 0)
                else:  failed  += 1
                self.after(0, lambda p=(i+1)/total_items*100: self._clean_progress.__setitem__("value", p))

        if cat_key:
            self._cleaner_results[cat_key]["items"] = []; self._cleaner_results[cat_key]["size"] = 0
        else:
            for key in self._cleaner_results:
                self._cleaner_results[key]["items"] = []; self._cleaner_results[key]["size"] = 0
        def _update_ui():
            self._refresh_cleaner_results()
            self._file_tree.delete(*self._file_tree.get_children())
            self._clean_total_lbl.config(text="Total detectado:  0 B")
            self._clean_progress["value"] = 0
            self.set_status(f"✅ Limpo: {format_size(cleaned)}  •  {failed} erros",
                            "success" if not failed else "warning")
            messagebox.showinfo("Limpeza Concluída",
                f"✅  {format_size(cleaned)} libertados\n"
                f"{'⚠️  ' + str(failed) + ' ficheiros não foi possível remover' if failed else '🧹  Tudo limpo!'}")
        self.after(0, _update_ui)

    # ──────────── REGISTRY PAGE ────────────
    def _build_registry(self):
        page = tk.Frame(self._content, bg=BG_MAIN)
        hdr = tk.Frame(page, bg=BG_MAIN)
        hdr.pack(fill=tk.X, padx=14, pady=(10, 6))
        tk.Label(hdr, text="🔑  Limpeza do Registo", font=("Segoe UI", 13, "bold"),
                 bg=BG_MAIN, fg=TEXT_PRI).pack(side=tk.LEFT)
        btn_f = tk.Frame(hdr, bg=BG_MAIN)
        btn_f.pack(side=tk.RIGHT)
        create_button(btn_f, "🔍 Analisar",             self._scan_registry,    "teal"   ).pack(side=tk.LEFT, padx=4)
        create_button(btn_f, "🗑️ Corrigir Selecionado", self._fix_selected_reg, "primary").pack(side=tk.LEFT, padx=4)
        create_button(btn_f, "✨ Corrigir Tudo",         self._fix_all_reg,      "warning").pack(side=tk.LEFT, padx=4)
        tk.Frame(page, bg=DIVIDER, height=1).pack(fill=tk.X, padx=14, pady=3)
        tk.Label(page,
            text="⚠️  Crie um ponto de restauro antes de modificar o registo. O HC-Cleaner apenas remove entradas inválidas confirmadas.",
            font=("Segoe UI", 9), bg=BG_MAIN, fg=WARNING, anchor=tk.W).pack(fill=tk.X, padx=14, pady=(0, 4))
        self._reg_progress = ttk.Progressbar(page, style="HC.Horizontal.TProgressbar", mode="determinate")
        self._reg_progress.pack(fill=tk.X, padx=14, pady=(0, 6))
        card = create_card(page, title="ENTRADAS PROBLEMÁTICAS NO REGISTO")
        card.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))
        cols = ("categoria", "descricao", "caminho", "gravidade")
        self._reg_tree = ttk.Treeview(card, style="HC.Treeview", columns=cols,
                                       show="headings", selectmode="extended")
        self._reg_tree.heading("categoria", text="Categoria")
        self._reg_tree.heading("descricao", text="Descrição")
        self._reg_tree.heading("caminho",   text="Chave de Registo")
        self._reg_tree.heading("gravidade", text="Risco")
        self._reg_tree.column("categoria", width=180)
        self._reg_tree.column("descricao", width=350)
        self._reg_tree.column("caminho",   width=280)
        self._reg_tree.column("gravidade", width=80, anchor=tk.CENTER)
        sb = ttk.Scrollbar(card, style="HC.Vertical.TScrollbar", command=self._reg_tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._reg_tree.configure(yscrollcommand=sb.set)
        self._reg_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._reg_count_lbl = tk.Label(page, text="", font=("Segoe UI", 10, "bold"),
                                        bg=BG_MAIN, fg=ACCENT, anchor=tk.E)
        self._reg_count_lbl.pack(fill=tk.X, padx=24, pady=(0, 4))
        return page

    def _scan_registry(self):
        if platform.system() != "Windows":
            messagebox.showinfo("HC-Cleaner", "Apenas disponível no Windows."); return
        self._reg_tree.delete(*self._reg_tree.get_children())
        self._reg_progress["value"] = 0
        self.set_status("A analisar registo...", "info")
        threading.Thread(target=self._scan_registry_worker, daemon=True).start()

    def _scan_registry_worker(self):
        def prog(i, total, msg):
            self.after(0, lambda: self._reg_progress.__setitem__("value", i/max(total,1)*100))
            self.after(0, lambda m=msg: self.set_status(m, "info"))
        self._registry_issues = scan_all_registry(progress_callback=prog)
        self.after(0, self._refresh_registry_results)

    def _refresh_registry_results(self):
        self._reg_tree.delete(*self._reg_tree.get_children())
        color_map = {"warning": ("médio", WARNING), "info": ("baixo", INFO), "error": ("alto", DANGER)}
        for i, issue in enumerate(self._registry_issues):
            risk, color = color_map.get(issue.get("severity", "info"), ("baixo", INFO))
            self._reg_tree.insert("", tk.END, iid=str(i),
                                  values=(issue.get("label",""),
                                          issue.get("description","")[:80],
                                          f"{issue.get('hive','')}\\...\\{issue.get('name','')}",
                                          risk.upper()))
            self._reg_tree.tag_configure(risk, foreground=color)
            self._reg_tree.item(str(i), tags=(risk,))
        n = len(self._registry_issues)
        self._reg_count_lbl.config(text=f"Total: {n} entrada{'s' if n!=1 else ''} problemática{'s' if n!=1 else ''}")
        self._reg_progress["value"] = 100
        self.set_status(f"Registo: {n} problemas encontrados", "warning" if n > 0 else "success")

    def _fix_selected_reg(self):
        sel = self._reg_tree.selection()
        if not sel:
            messagebox.showinfo("HC-Cleaner", "Selecione entradas para corrigir."); return
        issues = [self._registry_issues[int(s)] for s in sel if int(s) < len(self._registry_issues)]
        if messagebox.askyesno("Corrigir Registo",
                f"Remover {len(issues)} entrada(s) do registo?\n\nEsta ação pode ser irreversível."):
            self._do_fix_registry(issues)

    def _fix_all_reg(self):
        if not self._registry_issues:
            messagebox.showinfo("HC-Cleaner", "Execute 'Analisar' primeiro."); return
        if messagebox.askyesno("Corrigir Tudo", f"Remover {len(self._registry_issues)} entradas problemáticas?"):
            self._do_fix_registry(self._registry_issues)

    def _do_fix_registry(self, issues):
        ok_count = fail_count = 0
        for issue in issues:
            ok, _ = delete_registry_issue(issue)
            if ok: ok_count += 1
            else:  fail_count += 1
        messagebox.showinfo("Registo Limpo",
            f"✅ {ok_count} entradas removidas\n❌ {fail_count} falhas (podem requerer Admin)")
        self._registry_issues = [i for i in self._registry_issues if i not in issues]
        self._refresh_registry_results()

    # ──────────── PROGRAMS PAGE ────────────
    def _build_programs(self):
        page = tk.Frame(self._content, bg=BG_MAIN)
        hdr = tk.Frame(page, bg=BG_MAIN)
        hdr.pack(fill=tk.X, padx=14, pady=(10, 4))
        tk.Label(hdr, text="📦  Programas Instalados", font=("Segoe UI", 13, "bold"),
                 bg=BG_MAIN, fg=TEXT_PRI).pack(side=tk.LEFT)
        btn_f = tk.Frame(hdr, bg=BG_MAIN)
        btn_f.pack(side=tk.RIGHT)
        create_button(btn_f, "🔄 Actualizar", self._load_programs,        "teal"    ).pack(side=tk.LEFT, padx=3)
        create_button(btn_f, "⚙️ Painel",     open_programs_and_features, "secondary").pack(side=tk.LEFT, padx=3)
        tk.Frame(page, bg=DIVIDER, height=1).pack(fill=tk.X, padx=14, pady=3)

        act_f = tk.Frame(page, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER)
        act_f.pack(fill=tk.X, padx=14, pady=(0, 6))
        tk.Label(act_f, text="  Desinstalação:", font=("Segoe UI", 9, "bold"),
                 bg=BG_PANEL, fg=TEXT_SEC).pack(side=tk.LEFT, padx=(8, 12), pady=8)
        create_button(act_f, "🗑️  Normal",   self._uninstall_selected,       "primary").pack(side=tk.LEFT, padx=4, pady=6)
        create_button(act_f, "💪  Forçada",  self._force_uninstall_selected, "warning").pack(side=tk.LEFT, padx=4, pady=6)
        create_button(act_f, "🔷  Remover Edge", self._uninstall_edge,        "danger" ).pack(side=tk.LEFT, padx=4, pady=6)
        self._auto_clean_var = tk.BooleanVar(value=True)
        tk.Checkbutton(act_f, text="Limpar resíduos automaticamente após desinstalar",
                       variable=self._auto_clean_var, bg=BG_PANEL, fg=TEXT_SEC,
                       selectcolor=BG_CARD, activebackground=BG_PANEL,
                       activeforeground=TEXT_PRI, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=16)

        search_f = tk.Frame(page, bg=BG_MAIN)
        search_f.pack(fill=tk.X, padx=14, pady=(0, 4))
        tk.Label(search_f, text="🔍", font=("Segoe UI", 11), bg=BG_MAIN, fg=TEXT_SEC).pack(side=tk.LEFT, padx=(0, 6))
        self._prog_search = tk.Entry(search_f, bg=BG_INPUT, fg=TEXT_PRI, font=("Segoe UI", 10),
                                      bd=0, highlightthickness=1, highlightbackground=BORDER,
                                      highlightcolor=ACCENT, insertbackground=TEXT_PRI)
        self._prog_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._prog_search.bind("<KeyRelease>", self._filter_programs)

        split = tk.Frame(page, bg=BG_MAIN)
        split.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))

        left = create_card(split, title="LISTA DE PROGRAMAS")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        cols = ("name", "version", "publisher", "size", "date", "tipo")
        self._prog_tree = ttk.Treeview(left, style="HC.Treeview", columns=cols,
                                        show="headings", selectmode="browse")
        for col, text, width, anchor in [
            ("name",      "Nome",        240, tk.W),
            ("version",   "Versão",       80, tk.W),
            ("publisher", "Fabricante",  150, tk.W),
            ("size",      "Tamanho",      75, tk.E),
            ("date",      "Instalação",   80, tk.CENTER),
            ("tipo",      "Tipo",         80, tk.CENTER),
        ]:
            self._prog_tree.heading(col, text=text)
            self._prog_tree.column(col, width=width, anchor=anchor)
        self._prog_tree.tag_configure("protected", foreground=WARNING)
        self._prog_tree.tag_configure("no_uninst",  foreground=TEXT_MUT)
        sb = ttk.Scrollbar(left, style="HC.Vertical.TScrollbar", command=self._prog_tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._prog_tree.configure(yscrollcommand=sb.set)
        self._prog_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._prog_count_lbl = tk.Label(left, text="", font=("Segoe UI", 8),
                                         bg=BG_CARD, fg=TEXT_MUT, anchor=tk.W, padx=6)
        self._prog_count_lbl.pack(fill=tk.X, pady=(0, 4))

        right = create_card(split, title="LOG DE OPERAÇÕES")
        right.pack(side=tk.LEFT, fill=tk.BOTH)
        right.configure(width=320); right.pack_propagate(False)
        lf, lt = setup_log_area(right)
        lf.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self._prog_log = lt
        return page

    def _prog_log_write(self, msg, tag="recv"):
        self._prog_log.config(state=tk.NORMAL)
        ts = datetime.now().strftime("%H:%M:%S")
        self._prog_log.insert(tk.END, f"[{ts}] {msg}\n", tag)
        self._prog_log.see(tk.END)
        self._prog_log.config(state=tk.DISABLED)

    def _load_programs(self):
        self.set_status("A carregar programas...", "info")
        threading.Thread(target=self._load_programs_worker, daemon=True).start()

    def _load_programs_worker(self):
        self._programs_list = get_installed_programs()
        self.after(0, self._refresh_programs_list)

    def _refresh_programs_list(self):
        self._prog_tree.delete(*self._prog_tree.get_children())
        for prog in self._programs_list:
            size_str  = f"{prog['size_mb']} MB" if prog['size_mb'] else "—"
            protected = prog.get("protected_type")
            has_u     = prog.get("has_uninstaller", True)
            if protected:   tipo, tag = "🔷 Protegido",   "protected"
            elif not has_u: tipo, tag = "⚠️ Sem uninst.", "no_uninst"
            else:           tipo, tag = "✅ Normal",       ""
            self._prog_tree.insert("", tk.END,
                values=(prog["name"], prog["version"] or "—", prog["publisher"] or "—",
                        size_str, prog["install_date"] or "—", tipo),
                tags=(tag,) if tag else ())
        n = len(self._programs_list)
        self._prog_count_lbl.config(text=f"  {n} programas encontrados")
        self.set_status(f"{n} programas instalados", "info")

    def _filter_programs(self, e=None):
        q = self._prog_search.get().lower()
        self._prog_tree.delete(*self._prog_tree.get_children())
        filtered = [p for p in self._programs_list
                    if q in p["name"].lower() or q in (p["publisher"] or "").lower()]
        for prog in filtered:
            size_str  = f"{prog['size_mb']} MB" if prog['size_mb'] else "—"
            protected = prog.get("protected_type")
            has_u     = prog.get("has_uninstaller", True)
            if protected:   tipo, tag = "🔷 Protegido",   "protected"
            elif not has_u: tipo, tag = "⚠️ Sem uninst.", "no_uninst"
            else:           tipo, tag = "✅ Normal",       ""
            self._prog_tree.insert("", tk.END,
                values=(prog["name"], prog["version"] or "—", prog["publisher"] or "—",
                        size_str, prog["install_date"] or "—", tipo),
                tags=(tag,) if tag else ())
        self._prog_count_lbl.config(text=f"  {len(filtered)} de {len(self._programs_list)} programas")

    def _get_selected_program(self):
        sel = self._prog_tree.selection()
        if not sel:
            messagebox.showinfo("HC-Cleaner", "Selecione um programa primeiro."); return None
        prog_name = self._prog_tree.item(sel[0])["values"][0]
        return next((p for p in self._programs_list if p["name"] == prog_name), None)

    def _uninstall_selected(self):
        prog = self._get_selected_program()
        if not prog: return
        if not prog.get("has_uninstaller"):
            if messagebox.askyesno("Sem Desinstalador",
                    f"'{prog['name']}' não tem desinstalador.\nUsar Desinstalação Forçada?"):
                self._force_uninstall_selected()
            return
        if messagebox.askyesno("Desinstalar",
                f"Desinstalar '{prog['name']}'?\n"
                f"{'✅ Resíduos serão limpos automaticamente.' if self._auto_clean_var.get() else ''}"):
            threading.Thread(target=self._do_uninstall_normal, args=(prog,), daemon=True).start()

    def _do_uninstall_normal(self, prog):
        name = prog["name"]
        self.after(0, lambda: self._prog_log_write(f"▶ A desinstalar: {name}", "info"))
        self.after(0, lambda: self.set_status(f"A desinstalar {name}...", "warning"))
        def cb(msg): self.after(0, lambda m=msg: self._prog_log_write(f"   {m}", "muted"))
        ok, msg = uninstall_program(prog, callback=cb)
        if ok:
            self.after(0, lambda: self._prog_log_write(f"✅ {name} desinstalado", "ok"))
            if self._auto_clean_var.get():
                self.after(0, lambda: self._prog_log_write("🧹 A limpar resíduos...", "warn"))
                self._do_clean_residuals(prog)
            self.after(0, lambda: self.set_status(f"'{name}' removido com sucesso", "success"))
            self.after(500, self._load_programs)
        else:
            self.after(0, lambda: self._prog_log_write(f"❌ Erro: {msg}", "error"))
            self.after(0, lambda: self.set_status(f"Erro ao desinstalar {name}", "error"))

    def _force_uninstall_selected(self):
        prog = self._get_selected_program()
        if not prog: return
        if not messagebox.askyesno("⚠️ Desinstalação Forçada",
                f"Remover '{prog['name']}' sem desinstalador?\n\n"
                "• Termina processos\n• Apaga pasta\n• Limpa registo\n\nIRREVERSÍVEL. Continuar?"):
            return
        threading.Thread(target=self._do_force_uninstall, args=(prog,), daemon=True).start()

    def _do_force_uninstall(self, prog):
        name = prog["name"]
        self.after(0, lambda: self._prog_log_write(f"💪 Remoção forçada: {name}", "warn"))
        self.after(0, lambda: self.set_status(f"Remoção forçada de {name}...", "warning"))
        def cb(msg): self.after(0, lambda m=msg: self._prog_log_write(f"   {m}", "muted"))
        ok, report = force_uninstall(prog, callback=cb)
        folders  = len(report.get("folders_removed", []))
        reg_keys = len(report.get("reg_keys_removed", []))
        procs    = len(report.get("processes_killed", []))
        errors   = len(report.get("errors", []))
        self.after(0, lambda: self._prog_log_write(
            f"{'✅' if ok else '⚠️'} {procs} processos, {folders} pastas, {reg_keys} chaves, {errors} erros",
            "ok" if ok else "warn"))
        if self._auto_clean_var.get():
            self.after(0, lambda: self._prog_log_write("🧹 A limpar resíduos...", "warn"))
            self._do_clean_residuals(prog)
        self.after(0, lambda: self.set_status(
            f"'{name}' removido — {folders} pastas, {reg_keys} chaves",
            "success" if ok else "warning"))
        self.after(500, self._load_programs)

    def _uninstall_edge(self):
        if not messagebox.askyesno("🔷 Remover Microsoft Edge",
                "Remover o Microsoft Edge?\n\n"
                "⚠️  Tenha outro browser instalado antes de continuar.\n\nContinuar?"):
            return
        threading.Thread(target=self._do_uninstall_edge, daemon=True).start()

    def _do_uninstall_edge(self):
        self.after(0, lambda: self._prog_log_write("🔷 A remover Microsoft Edge...", "warn"))
        self.after(0, lambda: self.set_status("A remover Microsoft Edge...", "warning"))
        def cb(msg): self.after(0, lambda m=msg: self._prog_log_write(f"   {m}", "muted"))
        ok, msg = uninstall_edge(callback=cb)
        if ok:
            self.after(0, lambda: self._prog_log_write(f"✅ {msg}", "ok"))
            edge_prog = {"name": "Microsoft Edge",
                         "install_location": r"C:\Program Files (x86)\Microsoft\Edge",
                         "key_name": "", "hive": "HKLM",
                         "reg_path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"}
            if self._auto_clean_var.get():
                self.after(0, lambda: self._prog_log_write("🧹 A limpar resíduos...", "warn"))
                self._do_clean_residuals(edge_prog)
            self.after(0, lambda: self.set_status("Microsoft Edge removido", "success"))
            self.after(500, self._load_programs)
        else:
            self.after(0, lambda: self._prog_log_write(f"❌ {msg}", "error"))
            self.after(0, lambda: self.set_status("Não foi possível remover o Edge", "error"))
            self.after(0, lambda: messagebox.showerror("Edge",
                f"Falha ao remover Edge:\n\n{msg}\n\nTenta a Desinstalação Forçada."))

    def _do_clean_residuals(self, prog):
        def cb(msg): self.after(0, lambda m=msg: self._prog_log_write(f"   {m}", "muted"))
        report  = clean_residuals(prog, callback=cb)
        freed   = report.get("bytes_freed", 0)
        folders = len(report.get("folders_removed", []))
        reg_k   = len(report.get("reg_keys_removed", []))
        self.after(0, lambda: self._prog_log_write(
            f"🧹 {format_size(freed)} libertados, {folders} pastas, {reg_k} chaves", "ok"))

    # ──────────── MALWARE PAGE ────────────
    def _build_malware(self):
        page = tk.Frame(self._content, bg=BG_MAIN)
        hdr = tk.Frame(page, bg=BG_MAIN)
        hdr.pack(fill=tk.X, padx=14, pady=(10, 6))
        tk.Label(hdr, text="🦠  Detecção de Ameaças", font=("Segoe UI", 13, "bold"),
                 bg=BG_MAIN, fg=TEXT_PRI).pack(side=tk.LEFT)
        btn_f = tk.Frame(hdr, bg=BG_MAIN)
        btn_f.pack(side=tk.RIGHT)
        create_button(btn_f, "🔍 Analisar",        self._scan_malware, "teal"   ).pack(side=tk.LEFT, padx=4)
        create_button(btn_f, "🛡️ Windows Defender", self._run_defender, "primary").pack(side=tk.LEFT, padx=4)
        tk.Frame(page, bg=DIVIDER, height=1).pack(fill=tk.X, padx=14, pady=3)
        tk.Label(page,
            text="ℹ️  Análise heurística local. Para protecção completa, use o Windows Defender ou um antivírus dedicado.",
            font=("Segoe UI", 9), bg=BG_MAIN, fg=INFO, anchor=tk.W).pack(fill=tk.X, padx=14, pady=(0, 4))
        self._mal_progress = ttk.Progressbar(page, style="HC.Horizontal.TProgressbar", mode="indeterminate")
        self._mal_progress.pack(fill=tk.X, padx=14, pady=(0, 6))

        stats_f = tk.Frame(page, bg=BG_MAIN)
        stats_f.pack(fill=tk.X, padx=14, pady=(0, 6))
        self._mal_stat_labels = {}
        for label, color in [("🔴 Alto Risco", DANGER), ("🟡 Médio Risco", WARNING), ("🔵 Baixo Risco", INFO)]:
            sc = tk.Frame(stats_f, bg=BG_CARD, highlightthickness=1, highlightbackground=BORDER)
            sc.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
            tk.Label(sc, text=label, font=("Segoe UI", 8), bg=BG_CARD, fg=TEXT_MUT).pack(pady=(6, 0))
            lbl = tk.Label(sc, text="—", font=("Segoe UI", 14, "bold"), bg=BG_CARD, fg=color)
            lbl.pack(pady=(0, 6))
            self._mal_stat_labels[label] = lbl

        card = create_card(page, title="AMEAÇAS DETECTADAS")
        card.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))
        cols = ("risk", "type", "description", "path", "action")
        self._mal_tree = ttk.Treeview(card, style="HC.Treeview", columns=cols,
                                       show="headings", selectmode="browse")
        for col, text, width, anchor in [
            ("risk",        "Risco",       70,  tk.CENTER),
            ("type",        "Tipo",        140, tk.W),
            ("description", "Descrição",   300, tk.W),
            ("path",        "Localização", 280, tk.W),
            ("action",      "Acção",        80, tk.CENTER),
        ]:
            self._mal_tree.heading(col, text=text)
            self._mal_tree.column(col, width=width, anchor=anchor)
        sb = ttk.Scrollbar(card, style="HC.Vertical.TScrollbar", command=self._mal_tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._mal_tree.configure(yscrollcommand=sb.set)
        self._mal_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        return page

    def _scan_malware(self):
        self._mal_tree.delete(*self._mal_tree.get_children())
        self._mal_progress.start(12)
        self.set_status("A verificar ameaças...", "warning")
        threading.Thread(target=self._scan_malware_worker, daemon=True).start()

    def _scan_malware_worker(self):
        from modules.malware import (
            scan_temp_executables, scan_autorun_entries, scan_winlogon,
            scan_running_processes, scan_hosts_file,
            TIMEOUT_TEMP, TIMEOUT_AUTORUN, TIMEOUT_WINLOGON,
            TIMEOUT_PROCESSES, TIMEOUT_HOSTS, _run_with_timeout,
        )
        steps = [
            ("Executáveis em temporários...", scan_temp_executables,  TIMEOUT_TEMP + 2),
            ("Entradas de arranque...",        scan_autorun_entries,   TIMEOUT_AUTORUN + 2),
            ("Winlogon Shell/Userinit...",     scan_winlogon,          TIMEOUT_WINLOGON + 2),
            ("Processos suspeitos...",         scan_running_processes, TIMEOUT_PROCESSES + 3),
            ("Ficheiro hosts...",              scan_hosts_file,        TIMEOUT_HOSTS + 2),
        ]
        self._malware_findings = []
        for step_msg, step_fn, step_timeout in steps:
            self.after(0, lambda m=step_msg: self.set_status(f"   {m}", "warning"))
            result, _ = _run_with_timeout(step_fn, step_timeout, default=[])
            if result: self._malware_findings.extend(result)
        self.after(0, self._refresh_malware_results)

    def _refresh_malware_results(self):
        self._mal_progress.stop()
        self._mal_progress["value"] = 100
        self._mal_tree.delete(*self._mal_tree.get_children())
        type_labels = {
            "temp_executable":    "Executável Temporário",
            "autorun_missing":    "Arranque Inválido",
            "autorun_suspicious": "Arranque Suspeito",
            "winlogon_hijack":    "Winlogon Hijack",
            "suspicious_process": "Processo Suspeito",
            "hosts_redirect":     "Redireccionamento Hosts",
            "hosts_large":        "Ficheiro Hosts Alterado",
        }
        risk_counts = {"alto": 0, "médio": 0, "baixo": 0}
        for finding in self._malware_findings:
            risk = finding.get("risk", "baixo")
            risk_counts[risk] = risk_counts.get(risk, 0) + 1
            icon = RISK_ICONS.get(risk, "⚪")
            path_short = finding["path"]
            if len(path_short) > 50: path_short = "..." + path_short[-47:]
            self._mal_tree.insert("", tk.END, values=(
                f"{icon} {risk.upper()}",
                type_labels.get(finding.get("type", ""), finding.get("type", "")),
                finding.get("description", "")[:80],
                path_short, finding.get("action", "—"),
            ))
        for lbl_text, risk_key in [("🔴 Alto Risco","alto"),("🟡 Médio Risco","médio"),("🔵 Baixo Risco","baixo")]:
            self._mal_stat_labels[lbl_text].config(text=str(risk_counts.get(risk_key, 0)))
        n = len(self._malware_findings)
        self.set_status("✅ Nenhuma ameaça detectada" if n == 0
                        else f"⚠️ {n} ameaças detectadas — reveja os resultados",
                        "success" if n == 0 else "warning")

    def _run_defender(self):
        ok, msg = run_windows_defender_quick()
        if ok: messagebox.showinfo("Windows Defender", msg)
        else:  messagebox.showwarning("Windows Defender", msg)

    # ──────────── ABOUT PAGE ────────────
    def _build_about(self):
        page = tk.Frame(self._content, bg=BG_MAIN)
        hdr = tk.Frame(page, bg=BG_MAIN)
        hdr.pack(fill=tk.X, padx=14, pady=(10, 6))
        tk.Label(hdr, text="ℹ️  Sobre o HC-Cleaner",
                 font=("Segoe UI", 13, "bold"), bg=BG_MAIN, fg=TEXT_PRI).pack(side=tk.LEFT)
        tk.Frame(page, bg=DIVIDER, height=1).pack(fill=tk.X, padx=14, pady=3)

        body = tk.Frame(page, bg=BG_MAIN)
        body.pack(fill=tk.BOTH, expand=True, padx=40, pady=20)

        logo_card = create_card(body)
        logo_card.pack(fill=tk.X, pady=(0, 12))
        logo_inner = tk.Frame(logo_card, bg=BG_CARD)
        logo_inner.pack(fill=tk.X, padx=20, pady=20)
        if self.logo_image:
            lbl = tk.Label(logo_inner, image=self.logo_image, bg=BG_CARD)
            lbl.image = self.logo_image
            lbl.pack(pady=(0, 8))
        tk.Label(logo_inner, text="HC-Cleaner",
                 font=("Segoe UI", 22, "bold"), bg=BG_CARD, fg=ACCENT).pack()
        tk.Label(logo_inner, text="Ferramenta de Manutenção e Limpeza do Windows",
                 font=("Segoe UI", 10), bg=BG_CARD, fg=TEXT_SEC).pack(pady=(4, 0))
        tk.Label(logo_inner, text="v1.4.9",
                 font=("Segoe UI", 9), bg=BG_CARD, fg=TEXT_MUT).pack(pady=(2, 0))

        info_frame = tk.Frame(body, bg=BG_MAIN)
        info_frame.pack(fill=tk.X, pady=(0, 12))
        left_col  = tk.Frame(info_frame, bg=BG_MAIN)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        right_col = tk.Frame(info_frame, bg=BG_MAIN)
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def info_card(parent, title, rows):
            card = create_card(parent, title=title)
            card.pack(fill=tk.X, pady=(0, 8))
            for label, value, color in rows:
                row = tk.Frame(card, bg=BG_CARD)
                row.pack(fill=tk.X, padx=14, pady=4)
                tk.Label(row, text=label, font=("Segoe UI", 9), bg=BG_CARD,
                         fg=TEXT_MUT, width=18, anchor=tk.W).pack(side=tk.LEFT)
                tk.Label(row, text=value, font=("Segoe UI", 9, "bold"),
                         bg=BG_CARD, fg=color, anchor=tk.W).pack(side=tk.LEFT)

        info_card(left_col, "INFORMAÇÕES", [
            ("Versão",      "1.4.9",           ACCENT),
            ("Autor",       "HCsoftware",      TEXT_PRI),
            ("Localização", "Silves, Algarve", TEXT_PRI),
            ("Licença",     "Uso privado",     TEXT_PRI),
            ("Plataforma",  "Windows 10/11",   TEXT_PRI),
        ])
        info_card(left_col, "TECNOLOGIA", [
            ("Linguagem",  "Python 3.10+", SUCCESS),
            ("Interface",  "Tkinter",      SUCCESS),
            ("Compilador", "PyInstaller",  SUCCESS),
            ("GitHub",     "condessa",     ACCENT),
        ])
        info_card(right_col, "FUNCIONALIDADES", [
            ("🧹 Limpeza",   "13 categorias de ficheiros",   TEXT_PRI),
            ("🔑 Registo",   "8 tipos de verificação",       TEXT_PRI),
            ("📦 Programas", "Desinstalação normal/forçada", TEXT_PRI),
            ("🦠 Malware",   "5 fases heurísticas",          TEXT_PRI),
            ("🔷 Edge",      "Remoção forçada suportada",    TEXT_PRI),
        ])
        info_card(right_col, "SISTEMA", [
            ("SO",           platform.system() + " " + platform.release(), TEXT_PRI),
            ("Arquitectura", platform.machine(),                            TEXT_PRI),
            ("Python",       platform.python_version(),                    TEXT_PRI),
            ("Computador",   platform.node(),                              TEXT_PRI),
        ])

        footer = tk.Frame(body, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER)
        footer.pack(fill=tk.X, pady=(4, 0))
        tk.Label(footer,
                 text="HC-Cleaner é uma alternativa ao CCleaner — sem telemetria, sem bloatware, código aberto.\n"
                      "Desenvolvido em Python com tema HCsoftware. Distribua livremente para uso pessoal.",
                 font=("Segoe UI", 9), bg=BG_PANEL, fg=TEXT_MUT,
                 justify=tk.CENTER, pady=12).pack()

        def open_github():
            import webbrowser
            webbrowser.open("https://github.com/condessa")
        create_button(body, "🔗  GitHub — condessa", open_github, "teal").pack(pady=(10, 0))
        return page


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if platform.system() != "Windows":
        r = tk.Tk(); r.withdraw()
        messagebox.showwarning("HC-Cleaner",
            "⚠️  O HC-Cleaner foi desenvolvido para Windows.\n\n"
            "Algumas funções (registo, desinstalador, Windows Defender)\n"
            "não estarão disponíveis neste sistema operativo.\n\n"
            "A interface continuará funcional para demonstração.")
        r.destroy()
    app = HCCleaner()
    app.mainloop()
