# 🐧 HCMaint

**HCsoftware** — Ferramenta de Manutenção do Linux (Debian/Ubuntu/Mint)

Interface gráfica em Python/Tkinter para limpeza e manutenção do sistema Linux,
desenvolvida como alternativa leve ao BleachBit — sem telemetria, sem bloatware,
com tema visual HCsoftware.

> Testado em produção: libertou **+17 GB** num Debian com uso real.

---

## ✨ Funcionalidades

### 🔍 Análise Inteligente
Só mostra o que **realmente pode ser removido** — não reporta como "lixo" o que é obrigatório:

| Categoria | O que detecta | Inteligência |
|---|---|---|
| Cache APT | `.deb` em `/var/cache/apt/archives/` | ✅ |
| Pacotes Órfãos | Dependências sem uso (`autoremove`) | ✅ |
| Logs Systemd | Journal com >30 dias | Só conta o removível |
| Logs Antigos | `*.gz`, `*.1`, `*.old` em `/var/log/` | ✅ |
| Cache Utilizador | Subpastas de `~/.cache/` por tamanho | Selecção granular |
| Miniaturas | `~/.cache/thumbnails/` | ✅ |
| Reciclagem | `~/.local/share/Trash/` | ✅ |
| Flatpak | Runtimes não utilizados (via `flatpak`) | Confia no flatpak |
| Snap | Só versões desactivadas removíveis | Exclui `core*`/`snapd` |
| Docker | Containers parados + imagens dangling | ✅ |
| Cache Python | `__pycache__/` e `.pyc` em `~/Programas/` | ✅ |

### 🧹 Limpeza
- Limpeza individual por categoria com **log em tempo real**
- Botão "Limpeza Segura" para categorias 100% seguras com um clique
- Diálogo de selecção granular para `~/.cache/`
- Re-análise automática após cada limpeza

### 💾 Análise de Espaço
- Barras visuais de uso de cada partição montada
- Top maiores pastas em `~` e `/var`

### 📊 Dashboard
- Cards clicáveis com navegação directa
- Log de actividade com timestamps
- Análise rápida com um clique

---

## 🚀 Instalação

### Dependências
```bash
sudo apt-get install python3-tk python3-pip
```

### Executar
```bash
cd ~/Programas/HCMaint
bash run.sh              # utilizador normal
bash run.sh --sudo       # acesso total (APT, Snap, logs de sistema)
```

### Instalar no menu do sistema
```bash
sudo cp -r . /opt/HCMaint
sudo cp hcmaint.desktop /usr/share/applications/
sudo chmod +x /opt/HCMaint/run.sh
```

---

## 📁 Estrutura

```
HCMaint/
├── main.py              ← Interface principal (Tkinter, 4 páginas)
├── hc_theme.py          ← Tema visual HCsoftware
├── modules/
│   └── scanner.py       ← 11 scanners + executores de limpeza
├── run.sh               ← Script de arranque (instala deps automaticamente)
├── hcmaint.desktop      ← Entrada para menu GNOME/KDE/XFCE
├── requirements.txt
└── imagens/
    └── HCsoftware.png
```

---

## ⚠️ Notas

- APT, Snap e limpeza de `/var/log/` requerem `sudo` (ou `pkexec`)
- A ferramenta **nunca remove** sem confirmação explícita
- Snaps de sistema (`core22`, `core24`, `snapd`) são correctamente identificados como não removíveis e não contam para o total
- Flatpak, Snap e Docker só aparecem se estiverem instalados no sistema
- O journal só reporta tamanho removível (logs >30 dias), não o total

---

## 🖼️ Screenshots

> Dashboard com análise em tempo real e cards clicáveis  
> Página de Análise com painel de detalhes por categoria  
> Limpeza com log de output em tempo real  

---

*HCsoftware © 2026 — Silves, Algarve, Portugal*  
*Desenvolvido com Python 3 + Tkinter*
