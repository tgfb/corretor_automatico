import customtkinter as ctk
import subprocess
import sys
import threading
import time

# --- Lista de scripts na ordem ---
scripts_ordem = [
    "download_main.py",
    "beecrowd_main.py",
    "compare_main.py",
    "spreadsheet_main.py",
]

# --- Aparência global ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# --- Janela principal ---
root = ctk.CTk()
root.title("Executar Scripts")
root.attributes("-fullscreen", True)  # inicia em tela cheia
root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))


# --- Funções ---
def rodar_sequencia(input_text):
    scripts = [
        (scripts_ordem[0], check1_var),
        (scripts_ordem[1], check2_var),
        (scripts_ordem[2], check3_var),
        (scripts_ordem[3], check4_var),
    ]

    def task():
        total_scripts = sum(var.get() for _, var in scripts)
        executed_count = 0
        total_start = time.time()

        for idx, (script, var) in enumerate(scripts, start=1):
            if var.get():
                terminal.insert(
                    "end",
                    f"\n[Script {idx}/{len(scripts_ordem)}] ▶ Executando {script} com argumento '{input_text}'\n",
                    "running",
                )
                terminal.see("end")

                start_time = time.time()
                process = subprocess.Popen(
                    [sys.executable, "-u", script, input_text],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )

                # Saída em tempo real
                for line in iter(process.stdout.readline, ""):
                    if line.strip():
                        terminal.insert("end", f"[STDOUT] {line}", "running")
                        terminal.see("end")
                        terminal.update_idletasks()
                for line in iter(process.stderr.readline, ""):
                    if line.strip():
                        terminal.insert("end", f"[ERRO] {line}", "error")
                        terminal.see("end")
                        terminal.update_idletasks()

                process.stdout.close()
                process.stderr.close()
                process.wait()
                elapsed = time.time() - start_time
                executed_count += 1

                terminal.insert(
                    "end",
                    f"✓ [Script {idx}] {script} finalizado em {elapsed:.2f}s\n",
                    "success",
                )
                terminal.see("end")

        total_elapsed = time.time() - total_start
        terminal.insert("end", f"\n=== Resumo Final ===\n", "info")
        terminal.insert(
            "end", f"Scripts executados: {executed_count}/{total_scripts}\n", "info"
        )
        terminal.insert("end", f"Tempo total: {total_elapsed:.2f}s\n", "info")
        terminal.see("end")

    threading.Thread(target=task, daemon=True).start()


def enviar_input():
    texto = entrada.get()
    if not texto:
        terminal.insert(
            "end", "⚠ Digite algum texto para enviar como argumento.\n", "warn"
        )
        return
    rodar_sequencia(texto)
    entrada.delete(0, "end")


def limpar_terminal():
    terminal.delete("1.0", "end")


def exportar_log():
    with open("log.txt", "w", encoding="utf-8") as f:
        f.write(terminal.get("1.0", "end"))
    terminal.insert("end", "✅ Log exportado para log.txt\n", "success")
    terminal.see("end")


# --- Frame checkboxes ---
frame_check = ctk.CTkFrame(root)
frame_check.pack(pady=20, padx=20, fill="x")

check1_var = ctk.BooleanVar(value=True)
check2_var = ctk.BooleanVar(value=True)
check3_var = ctk.BooleanVar(value=True)
check4_var = ctk.BooleanVar(value=True)

check1 = ctk.CTkCheckBox(
    frame_check, text="Download", variable=check1_var, font=("Arial", 16)
)
check1.pack(side="left", padx=15, pady=15)

check2 = ctk.CTkCheckBox(
    frame_check, text="Beecrowd", variable=check2_var, font=("Arial", 16)
)
check2.pack(side="left", padx=15, pady=15)

check3 = ctk.CTkCheckBox(
    frame_check, text="Compare", variable=check3_var, font=("Arial", 16)
)
check3.pack(side="left", padx=15, pady=15)

check4 = ctk.CTkCheckBox(
    frame_check, text="Spreadsheet", variable=check4_var, font=("Arial", 16)
)
check4.pack(side="left", padx=15, pady=15)

# --- Frame input ---
frame_input = ctk.CTkFrame(root)
frame_input.pack(pady=10, padx=20, fill="x")

lbl_input = ctk.CTkLabel(frame_input, text="Nome da lista:", font=("Arial", 18, "bold"))
lbl_input.pack(side="left", padx=10)

entrada = ctk.CTkEntry(frame_input, width=300)
entrada.pack(side="left", padx=10)

btn_enviar = ctk.CTkButton(
    frame_input,
    text="Executar Selecionados",
    command=enviar_input,
    font=("Arial", 16, "bold"),
)
btn_enviar.pack(side="left", padx=10)

btn_limpar = ctk.CTkButton(
    frame_input,
    text="Limpar Terminal",
    fg_color="#d9534f",
    hover_color="#c9302c",
    command=limpar_terminal,
    font=("Arial", 16, "bold"),
)
btn_limpar.pack(side="left", padx=10)

btn_exportar = ctk.CTkButton(
    frame_input,
    text="Exportar Log",
    fg_color="#5cb85c",
    hover_color="#4cae4c",
    command=exportar_log,
    font=("Arial", 16, "bold"),
)
btn_exportar.pack(side="left", padx=10)

# --- Terminal ---
frame_terminal = ctk.CTkFrame(root)
frame_terminal.pack(padx=20, pady=20, fill="both", expand=True)

terminal = ctk.CTkTextbox(
    frame_terminal, wrap="word", text_color="#00FF00", font=("Consolas", 14)
)
terminal.pack(padx=10, pady=10, fill="both", expand=True)

# Tags para cores
terminal.tag_config("error", foreground="#FF4500")  # laranja/vermelho
terminal.tag_config("warn", foreground="#FFFF00")  # amarelo
terminal.tag_config("success", foreground="#00FF00")  # verde
terminal.tag_config("running", foreground="#00BFFF")  # azul
terminal.tag_config("info", foreground="#00FF00")  # verde padrão

root.mainloop()
