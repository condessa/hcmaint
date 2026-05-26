# 🛡️ HCMaint Suite
**HCsoftware** — Ferramentas de Manutenção e Limpeza do Sistema

Suite completa de manutenção para **Linux** e **Windows**, desenvolvida em Python/Tkinter
com o tema visual HCsoftware. Alternativa limpa ao CCleaner (Windows) e BleachBit (Linux)
— sem telemetria, sem bloatware, código aberto.

> Testado em produção: libertou **+17 GB** num Debian com uso real.

---

## 📦 Projectos

### 🐧 [HCMaint — Linux](./linux/)
Ferramenta de manutenção para **Debian / Ubuntu / Linux Mint**

| Funcionalidade | Detalhe |
|---|---|
| Cache APT | Remove `.deb` acumulados |
| Pacotes Órfãos | `apt autoremove --purge` com streaming |
| Logs Systemd | Vacuum inteligente (só conta o removível) |
| Cache Utilizador | Selecção granular por subpasta |
| Flatpak | Runtimes obsoletos (via flatpak nativo) |
| Snap | Só versões removíveis — exclui `core*`/`snapd` |
| Docker | Containers parados + imagens dangling |
| Análise de Espaço | Barras visuais de partições + top pastas |

```bash
cd linux
bash run.sh              # utilizador normal
bash run.sh --sudo       # acesso total
```

---

### 🪟 [HCCleaner — Windows](./windows/)
Ferramenta de manutenção para **Windows 10 / 11**

| Funcionalidade | Detalhe |
|---|---|
| Limpeza de Ficheiros | Temp, cache browsers, prefetch, dumps, logs |
| Registo do Windows | Entradas inválidas, órfãos, DLLs inexistentes |
| Gestor de Programas | Lista + desinstalação via desinstalador oficial |
| Detecção de Ameaças | Análise heurística + lança Windows Defender |

```batch
cd windows
python main.py           # executar directamente
build.bat                # compilar para .exe (requer PyInstaller)
```

---

## 🎨 Tema Partilhado

Ambos os projectos usam o tema visual **HCsoftware** (`shared/hc_theme.py`):

| Constante | Cor | Uso |
|---|---|---|
| `BG_MAIN` | `#2b2b2b` | Fundo principal |
| `ACCENT` | `#4a90d9` | Azul accent |
| `WARNING` | `#f0ad4e` | Alertas |
| `SUCCESS` | `#5cb85c` | Sucesso |
| `DANGER` | `#d9534f` | Erros |
| `YELLOW` | `#FFD700` | Valores de destaque |

---

## 🚀 Instalação Rápida

### Linux
```bash
sudo apt-get install python3-tk python3-pip
cd linux && bash run.sh
```

### Windows
```batch
pip install Pillow
cd windows && python main.py
```

---

## 📁 Estrutura do Repositório

```
hcmaint/
├── linux/                  ← HCMaint (Debian/Ubuntu/Mint)
│   ├── main.py
│   ├── hc_theme.py
│   ├── modules/
│   │   └── scanner.py
│   ├── run.sh
│   └── hcmaint.desktop
│
├── windows/                ← HCCleaner (Windows 10/11)
│   ├── main.py
│   ├── hc_theme.py
│   ├── modules/
│   │   ├── cleaner.py
│   │   ├── registry.py
│   │   ├── uninstaller.py
│   │   └── malware.py
│   └── build.bat
│
├── shared/
│   └── hc_theme.py         ← Tema HCsoftware (referência)
│
└── README.md
```

---

## 🛠️ Requisitos

| | Linux | Windows |
|---|---|---|
| Python | 3.10+ | 3.10+ |
| Tkinter | `python3-tk` | incluído |
| Pillow | `pip install Pillow` | `pip install Pillow` |
| Extras | — | `winreg` (incluído) |

---

*HCsoftware © 2026 — Silves, Algarve, Portugal*  
*Desenvolvido com Python 3 + Tkinter*
