# 🪟 HCCleaner v1.0.0
**HCsoftware** — Ferramenta de Manutenção e Limpeza do Windows 10/11

Alternativa ao CCleaner — sem bloatware, sem telemetria, código aberto.

---

## ✨ Funcionalidades

### 🧹 Limpeza de Ficheiros (13 categorias)
- Temporários do Windows (`%TEMP%`, `C:\Windows\Temp`)
- Cache dos browsers (Chrome, Firefox, Edge)
- Prefetch, Windows Update cache
- Miniaturas e cache de ícones
- Relatórios de erros (WER), Dumps de memória
- Logs do sistema, Reciclagem

### 🔑 Limpeza do Registo
- Entradas de arranque inválidas (HKCU + HKLM)
- Desinstaladores órfãos
- DLLs partilhadas inexistentes
- Associações de ficheiros inválidas
- Listas MRU (ficheiros recentes)

### 📦 Gestor de Programas
- Lista todos os programas instalados com pesquisa em tempo real
- Desinstalação via desinstalador oficial
- Mostra versão, fabricante, tamanho e data

### 🦠 Detecção de Ameaças (Heurística)
- Executáveis em pastas temporárias
- Entradas de arranque suspeitas
- Processos com nomes suspeitos
- Verificação do ficheiro `hosts`
- Lançamento do Windows Defender

---

## Instalação

### Requisitos
- Windows 10 / 11
- Python 3.10+
- Pillow (`pip install Pillow`)

### Executar
```batch
cd windows
python main.py
```

### Compilar para .exe
```batch
build.bat
```
Gera `dist\HCCleaner.exe` com elevação UAC automática.

---

## Estrutura
```
windows/
├── main.py              <- Interface principal
├── hc_theme.py          <- Tema HCsoftware
├── modules/
│   ├── cleaner.py       <- 13 categorias de limpeza
│   ├── registry.py      <- Limpeza do registo
│   ├── uninstaller.py   <- Gestor de programas
│   └── malware.py       <- Deteccao de ameacas
├── build.bat            <- Compilação PyInstaller
└── imagens/
    └── HCsoftware.png
```

---

Nota: Crie sempre um ponto de restauro antes de limpar o registo.
Win + R -> rstrui -> Criar ponto de restauro.

---

*HCsoftware 2026 - Silves, Algarve, Portugal*
