#!/usr/bin/env python3
"""
llm_server_check.py
====================
Complete hardware diagnostics for running LLMs locally.

Install optional dependencies for more details:

pip install psutil gputil torch
"""

import os
import platform
import subprocess
import shutil


# ─── Cores de terminal ───────────────────────────────────────────────────────
VERDE  = "\033[92m"
AMARELO = "\033[93m"
VERMELHO = "\033[91m"
AZUL   = "\033[94m"
NEGRITO = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {VERDE}✓{RESET}  {msg}")
def aviso(msg): print(f"  {AMARELO}!{RESET}  {msg}")
def erro(msg): print(f"  {VERMELHO}✗{RESET}  {msg}")
def info(msg): print(f"     {msg}")
def titulo(msg): print(f"\n{NEGRITO}{AZUL}{'─'*60}{RESET}\n{NEGRITO} {msg}{RESET}\n{'─'*60}")


def run(cmd):
    """Corre um comando shell e devolve o stdout, ou '' se falhar."""
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL,
                                       text=True).strip()
    except Exception:
        return ""


# ─── 1. SISTEMA OPERATIVO ────────────────────────────────────────────────────
titulo("Sistema operativo")
info(f"OS       : {platform.system()} {platform.release()}")
info(f"Versão   : {platform.version()[:80]}")
info(f"Máquina  : {platform.machine()}")
info(f"Node     : {platform.node()}")

distro = run("cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"'")
if distro:
    info(f"Distro   : {distro}")

uptime = run("uptime -p 2>/dev/null || uptime")
if uptime:
    info(f"Uptime   : {uptime}")


# ─── 2. CPU ──────────────────────────────────────────────────────────────────
titulo("CPU — Processador")

try:
    import psutil
    cpu_count_logical  = psutil.cpu_count(logical=True)
    cpu_count_physical = psutil.cpu_count(logical=False)
    cpu_freq = psutil.cpu_freq()
    cpu_percent = psutil.cpu_percent(interval=1)

    info(f"Cores físicos  : {cpu_count_physical}")
    info(f"Threads lógicas: {cpu_count_logical}")
    if cpu_freq:
        info(f"Frequência     : {cpu_freq.current:.0f} MHz  (max {cpu_freq.max:.0f} MHz)")
    info(f"Uso actual     : {cpu_percent:.1f}%")
    ok("psutil disponível — dados detalhados de CPU")

except ImportError:
    aviso("psutil não instalado. A usar /proc/cpuinfo como alternativa.")
    model = run("grep 'model name' /proc/cpuinfo | head -1 | cut -d: -f2").strip()
    cores = run("nproc")
    mhz   = run("grep 'cpu MHz' /proc/cpuinfo | head -1 | cut -d: -f2").strip()
    if model: info(f"Modelo : {model}")
    if cores: info(f"Threads: {cores}")
    if mhz:   info(f"MHz    : {mhz}")

lscpu = run("lscpu | grep -E 'Architecture|Vendor|Socket|Core|Thread'")
if lscpu:
    for linha in lscpu.splitlines():
        info(linha.strip())


# ─── 3. MEMÓRIA RAM ──────────────────────────────────────────────────────────
titulo("RAM — Memória do sistema")

try:
    import psutil
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    total_gb = mem.total / 1024**3
    avail_gb = mem.available / 1024**3
    used_gb  = mem.used / 1024**3
    swap_gb  = swap.total / 1024**3

    info(f"Total      : {total_gb:.1f} GB")
    info(f"Usada      : {used_gb:.1f} GB  ({mem.percent:.0f}%)")
    info(f"Disponível : {avail_gb:.1f} GB")
    info(f"Swap       : {swap_gb:.1f} GB")

    if avail_gb >= 64:  ok(f"{avail_gb:.0f} GB livres — suficiente para modelos grandes (70B+)")
    elif avail_gb >= 32: ok(f"{avail_gb:.0f} GB livres — suficiente para modelos médios (30B)")
    elif avail_gb >= 16: aviso(f"{avail_gb:.0f} GB livres — suficiente para modelos pequenos (7B–14B)")
    else:                aviso(f"{avail_gb:.0f} GB livres — limitado; usa quantização agressiva")

except ImportError:
    mem_raw = run("grep -E 'MemTotal|MemAvailable|SwapTotal' /proc/meminfo")
    for linha in mem_raw.splitlines():
        info(linha)


# ─── 4. GPU ──────────────────────────────────────────────────────────────────
titulo("GPU — Placa gráfica")

nvidia_smi = shutil.which("nvidia-smi")

if nvidia_smi:
    ok("nvidia-smi encontrado — GPU NVIDIA detectada")

    # Informação por GPU
    query = run(
        "nvidia-smi --query-gpu=index,name,driver_version,memory.total,"
        "memory.used,memory.free,temperature.gpu,utilization.gpu,"
        "utilization.memory,power.draw,power.limit "
        "--format=csv,noheader,nounits"
    )

    gpus = []
    if query:
        for linha in query.splitlines():
            partes = [p.strip() for p in linha.split(",")]
            if len(partes) >= 11:
                idx, nome, driver, mem_total, mem_used, mem_free, temp, util_gpu, util_mem, power, power_max = partes[:11]
                gpus.append({
                    "idx": idx, "nome": nome, "driver": driver,
                    "mem_total": float(mem_total), "mem_used": float(mem_used),
                    "mem_free": float(mem_free), "temp": temp,
                    "util_gpu": util_gpu, "util_mem": util_mem,
                    "power": power, "power_max": power_max
                })
                print()
                info(f"GPU #{idx}  : {nome}")
                info(f"Driver  : {driver}")
                info(f"VRAM    : {float(mem_total)/1024:.1f} GB total  |  {float(mem_free)/1024:.1f} GB livre  |  {float(mem_used)/1024:.1f} GB usada")
                info(f"Temp    : {temp} °C  |  GPU: {util_gpu}%  |  Memória: {util_mem}%")
                try:
                    info(f"Potência: {float(power):.0f} W / {float(power_max):.0f} W")
                except Exception:
                    pass

    # CUDA
    cuda_ver = run("nvidia-smi | grep 'CUDA Version' | awk '{print $NF}'")
    if cuda_ver:
        info(f"\nVersão CUDA (driver): {cuda_ver}")

    nvcc = run("nvcc --version | grep 'release'")
    if nvcc:
        info(f"nvcc (toolkit)      : {nvcc.strip()}")
    else:
        aviso("nvcc não encontrado no PATH (CUDA toolkit pode não estar instalado)")

else:
    rocm = run("rocm-smi 2>/dev/null | head -5")
    if rocm:
        aviso("Sem NVIDIA, mas ROCm (AMD) detectado:")
        info(rocm)
    else:
        lspci_gpu = run("lspci 2>/dev/null | grep -iE 'vga|3d|display'")
        if lspci_gpu:
            aviso("Nenhum driver NVIDIA/ROCm, mas hardware detectado:")
            for l in lspci_gpu.splitlines():
                info(l)
        else:
            erro("Nenhuma GPU detectada (ou sem permissões)")
        aviso("Serás limitado a inferência em CPU (muito lenta para modelos grandes)")


# ─── 5. PyTorch / CUDA via Python ────────────────────────────────────────────
titulo("PyTorch e CUDA")

try:
    import torch
    info(f"PyTorch versão : {torch.__version__}")
    if torch.cuda.is_available():
        ok("CUDA disponível via PyTorch")
        info(f"Dispositivos   : {torch.cuda.device_count()} GPU(s)")
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            vram_total = props.total_memory / 1024**3
            info(f"  GPU {i}: {props.name}  —  {vram_total:.1f} GB VRAM")
    else:
        aviso("CUDA não disponível via PyTorch (CPU apenas)")
except ImportError:
    aviso("PyTorch não instalado. Instala com: pip install torch")


# ─── 6. ARMAZENAMENTO ────────────────────────────────────────────────────────
titulo("Armazenamento")

df = run("df -h / 2>/dev/null | tail -1")
if df:
    partes = df.split()
    if len(partes) >= 5:
        info(f"Disco (/)  : {partes[1]} total  |  {partes[2]} usado  |  {partes[3]} livre  ({partes[4]})")
        try:
            pct = int(partes[4].replace('%',''))
            if pct > 90:  aviso("Disco quase cheio! Os modelos LLM precisam de espaço.")
            elif pct > 75: aviso(f"Disco com {pct}% ocupado — verifica espaço antes de descarregar modelos.")
            else:          ok(f"Disco com {pct}% ocupado.")
        except Exception:
            pass

# Espaço nas pastas mais comuns de modelos
for pasta in ["~/.ollama", "~/.cache/huggingface", "~/models"]:
    p = os.path.expanduser(pasta)
    if os.path.exists(p):
        tam = run(f"du -sh {p} 2>/dev/null | cut -f1")
        if tam:
            info(f"{pasta:<30}: {tam} ocupado")


# ─── 7. FERRAMENTAS LLM INSTALADAS ──────────────────────────────────────────
titulo("Ferramentas LLM instaladas")

ferramentas = {
    "ollama"          : "Ollama (motor de modelos locais)",
    "python3"         : "Python 3",
    "pip3"            : "pip (gestor de pacotes Python)",
    "git"             : "Git",
    "wget"            : "wget",
    "curl"            : "curl",
    "conda"           : "Conda / Mamba",
    "docker"          : "Docker",
}

for cmd, nome in ferramentas.items():
    caminho = shutil.which(cmd)
    if caminho:
        versao = run(f"{cmd} --version 2>/dev/null | head -1")
        ok(f"{nome:<35} {versao[:40] if versao else ''}")
    else:
        info(f"  — {nome} não encontrado")

# Pacotes Python relevantes
titulo("Pacotes Python para LLMs")
pacotes = ["torch", "transformers", "llama_cpp", "ollama", "psutil",
           "accelerate", "bitsandbytes", "huggingface_hub", "vllm"]

for pkg in pacotes:
    try:
        mod = __import__(pkg.replace("-", "_").replace("llama_cpp", "llama_cpp"))
        ver = getattr(mod, "__version__", "?")
        ok(f"{pkg:<25} v{ver}")
    except ImportError:
        info(f"  — {pkg:<25} não instalado  (pip install {pkg})")


# ─── 8. RECOMENDAÇÕES FINAIS ─────────────────────────────────────────────────
titulo("Recomendações para LLMs")

# Colectar dados para recomendar
vram_disponivel = 0.0
n_gpus = 0
ram_gb = 0.0

try:
    import psutil
    ram_gb = psutil.virtual_memory().available / 1024**3
except Exception:
    pass

try:
    import torch
    if torch.cuda.is_available():
        n_gpus = torch.cuda.device_count()
        for i in range(n_gpus):
            props = torch.cuda.get_device_properties(i)
            vram_disponivel += props.total_memory / 1024**3
except Exception:
    pass

if vram_disponivel == 0 and nvidia_smi:
    raw = run("nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits")
    try:
        vram_disponivel = sum(float(x) for x in raw.splitlines()) / 1024
    except Exception:
        pass

print()
if vram_disponivel >= 80:
    ok(f"{vram_disponivel:.0f} GB VRAM — podes correr Llama 4 Maverick, DeepSeek R1 70B")
elif vram_disponivel >= 40:
    ok(f"{vram_disponivel:.0f} GB VRAM — podes correr Llama 4 Scout, DeepSeek R1 32B, Gemma 4 31B")
elif vram_disponivel >= 20:
    ok(f"{vram_disponivel:.0f} GB VRAM — podes correr Gemma 4 31B (Q4), MedGemma 27B")
elif vram_disponivel >= 12:
    ok(f"{vram_disponivel:.0f} GB VRAM — podes correr Gemma 4 26B MoE, Phi-4, DeepSeek 14B")
elif vram_disponivel >= 6:
    ok(f"{vram_disponivel:.0f} GB VRAM — podes correr Gemma 4 E4B, MedGemma 4B, Phi-4 (Q4)")
elif vram_disponivel >= 4:
    ok(f"{vram_disponivel:.0f} GB VRAM — podes correr Gemma 4 E2B, modelos 3B–7B em Q4")
elif vram_disponivel > 0:
    aviso(f"{vram_disponivel:.0f} GB VRAM — muito limitado; usa modelos 1B–3B ou CPU")
else:
    aviso("Sem VRAM detectada — inferência apenas em CPU (lenta)")
    if ram_gb >= 32:
        info(f"RAM disponível: {ram_gb:.0f} GB — podes tentar modelos 7B–13B em CPU (lento)")
    elif ram_gb >= 16:
        info(f"RAM disponível: {ram_gb:.0f} GB — podes tentar modelos 7B em CPU")
    else:
        info(f"RAM disponível: {ram_gb:.0f} GB — limita-te a modelos 3B ou usa API remota")

# print()
# info("Próximos passos sugeridos:")
# info("  1. Instalar Ollama:       curl -fsSL https://ollama.com/install.sh | sh")
# info("  2. Descarregar um modelo: ollama pull gemma4:e4b")
# info("  3. Testar:                ollama run gemma4:e4b 'Olá, funciona?'")
# info("  4. Usar em Python:        pip install ollama")
# print()