# 🐧 HCMaint v1.0.0
**HCsoftware** — Ferramenta de Manutenção do Linux (Debian/Ubuntu)

Interface gráfica (Tkinter) para limpeza e manutenção do sistema,
adaptada às necessidades reais do Linux.

---

## ✨ Funcionalidades

### 🔍 Análise Completa
Detecta automaticamente o que pode ser libertado:

| Categoria | O que detecta |
|---|---|
| Cache APT | `.deb` acumulados em `/var/cache/apt/archives/` |
| Pacotes Órfãos | Dependências sem uso (`autoremove`) |
| Logs Systemd | Tamanho do journal (`journalctl --disk-usage`) |
| Logs Antigos | `*.gz`, `*.1`, `*.old` em `/var/log/` |
| Cache Utilizador | Subpastas de `~/.cache/` por tamanho |
| Miniaturas | `~/.cache/thumbnails/` |
| Reciclagem | `~/.local/share/Trash/` |
| Flatpak | Runtimes não utilizados |
| Snap | Versões desactivadas |
| Docker | Containers parados + imagens dangling |
| Cache Python | `__pycache__/` e `.pyc` em `~/Programas/` |

### 🧹 Limpeza Individual
Botões por acção com log detalhado em tempo real.

### 💾 Análise de Espaço
- Barras visuais de uso das partições montadas
- Top maiores pastas em `~` e `/var`

---

## 🚀 Instalação

### Dependências do sistema
```bash
sudo apt-get install python3-tk python3-pip
```

### Executar
```bash
cd ~/Programas/HCMaint
bash run.sh
```

### Com acesso total (sudo para limpezas de sistema)
```bash
bash run.sh --sudo
```

### Instalar como aplicação do sistema
```bash
sudo cp -r . /opt/HCMaint
sudo cp hcmaint.desktop /usr/share/applications/
sudo chmod +x /opt/HCMaint/run.sh
```

---

## 📁 Estrutura
```
HCMaint/
├── main.py              ← Interface principal
├── hc_theme.py          ← Tema HCsoftware
├── modules/
│   └── scanner.py       ← Análise + limpeza
├── run.sh               ← Script de arranque
├── hcmaint.desktop      ← Entrada para menu do sistema
└── imagens/
    └── HCsoftware.png
```

---

## ⚠️ Notas

- **APT autoremove** e **limpeza de `/var/log/`** requerem `sudo`.
- A ferramenta **não remove** configurações do sistema nem ficheiros do utilizador sem confirmação explícita.
- O cache do utilizador (`~/.cache/`) é apresentado por subpasta para selecção granular.
- Flatpak, Snap e Docker só aparecem se estiverem instalados.

---

*HCsoftware © 2025 — Silves, Algarve, Portugal*
