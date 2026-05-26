# 🛡️ HCCleaner v1.0.0
**HCsoftware** — Ferramenta de Manutenção e Limpeza do Windows

Alternativa ao CCleaner — sem bloatware, sem telemetria, código aberto.

---

## ✨ Funcionalidades

### 🧹 Limpeza de Ficheiros
- Temporários do Windows (`%TEMP%`, `C:\Windows\Temp`)
- Cache dos browsers (Chrome, Firefox, Edge)
- Prefetch do Windows
- Cache do Windows Update
- Miniaturas e cache de ícones
- Ficheiros recentes e atalhos
- Relatórios de erros (WER)
- Dumps de memória
- Logs do sistema
- Reciclagem

### 🔑 Limpeza do Registo
- Entradas de arranque inválidas (HKCU + HKLM)
- Desinstaladores órfãos (programas já removidos)
- DLLs partilhadas inexistentes
- Associações de ficheiros inválidas
- Caminhos de aplicação inválidos
- Listas MRU (ficheiros recentes)

### 📦 Gestor de Programas
- Lista todos os programas instalados
- Pesquisa em tempo real
- Desinstalação via desinstalador oficial
- Acesso rápido ao Painel de Controlo
- Mostra versão, fabricante, tamanho e data

### 🦠 Detecção de Ameaças (Heurística)
- Executáveis em pastas temporárias
- Entradas de arranque suspeitas
- Processos com nomes suspeitos
- Verificação do ficheiro `hosts`
- Lançamento do Windows Defender

---

## 🔧 Instalação e Uso

### Requisitos
- Windows 10/11 (recomendado)
- Python 3.10+ (para executar da fonte)
- `uv` para gestão de dependências

### Executar da fonte
```bash
# Instalar dependências
uv pip install Pillow

# Executar (como Administrador para acesso completo)
python main.py
```

### Compilar para .exe
```bash
build.bat
```
O executável gerado em `dist\HCCleaner.exe` requer privilégios de Administrador
(configurado automaticamente via `--uac-admin`).

---

## ⚠️ Notas Importantes

- **Registo**: Crie sempre um ponto de restauro antes de limpar o registo.
  `Win + R` → `rstrui` → Criar ponto de restauro.
- **Malware**: A detecção é heurística e complementar — não substitui um antivírus.
- **Administrador**: Algumas limpezas (Prefetch, Windows Update cache) requerem
  privilégios elevados para acesso completo.
- **Reciclagem**: A limpeza da reciclagem é permanente e irreversível.

---

## 📁 Estrutura do Projeto

```
HCCleaner/
├── main.py              ← Aplicação principal + interface
├── hc_theme.py          ← Tema visual HCsoftware
├── modules/
│   ├── cleaner.py       ← Limpeza de ficheiros
│   ├── registry.py      ← Limpeza do registo
│   ├── uninstaller.py   ← Gestor de programas
│   └── malware.py       ← Detecção de ameaças
├── imagens/
│   └── HCsoftware.png   ← Logótipo
├── requirements.txt
├── build.bat            ← Script de compilação
└── README.md
```

---

## 📜 Licença
HCsoftware © 2025 — Uso privado e pessoal.

---

*Desenvolvido com ❤️ em Python/Tkinter para substituir o CCleaner
sem as suas desvantagens modernas.*
