import tkinter as tk
import subprocess
import sys
import threading
import time

# Lista de scripts na ordem
scripts_ordem = [
    "download_main.py",
    "beecrowd_main.py",
    "compare_main.py",
    "spreadsheet_main.py"
]

def rodar_sequencia(input_text, dificuldade):
    """Executa os scripts selecionados na ordem, enviando input_text e (se for compare) também dificuldade"""
    scripts = [
        (scripts_ordem[0], check1_var),
        (scripts_ordem[1], check2_var),
        (scripts_ordem[2], check3_var),  # Compare
        (scripts_ordem[3], check4_var)
    ]

    def task():
        for script, var in scripts:
            if var.get():
                # Monta os argumentos
                if script == "compare_main.py":
                    args = [sys.executable, "-u", script, input_text, str(dificuldade)]
                    terminal.insert(tk.END, f"\nExecutando {script} com argumentos '{input_text}' e dificuldade {dificuldade}...\n")
                else:
                    args = [sys.executable, "-u", script, input_text]
                    terminal.insert(tk.END, f"\nExecutando {script} com argumento '{input_text}'...\n")

                terminal.see(tk.END)

                start_time = time.time()
                process = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )

                # Saída em tempo real
                for line in iter(process.stdout.readline, ''):
                    terminal.insert(tk.END, line)
                    terminal.see(tk.END)
                for line in iter(process.stderr.readline, ''):
                    terminal.insert(tk.END, "ERRO: " + line)
                    terminal.see(tk.END)

                process.stdout.close()
                process.stderr.close()
                process.wait()
                elapsed = time.time() - start_time

                terminal.insert(tk.END, f"{script} finalizado em {elapsed:.2f} segundos.\n")
                terminal.see(tk.END)

    threading.Thread(target=task, daemon=True).start()

def enviar_input():
    texto = entrada.get()
    dificuldade = entrada_dificuldade.get()

    if not texto:
        terminal.insert(tk.END, "Por favor, digite algum texto para enviar como argumento.\n")
        return

    if not dificuldade.isdigit() or not (1 <= int(dificuldade) <= 10):
        terminal.insert(tk.END, "Por favor, insira uma dificuldade válida (1 a 10).\n")
        return

    terminal.insert(tk.END, f"> Enviando '{texto}' (dificuldade {dificuldade} apenas para Compare) para os scripts selecionados\n")
    rodar_sequencia(texto, int(dificuldade))
    entrada.delete(0, tk.END)

def limpar_terminal():
    terminal.delete("1.0", tk.END)

# --- Configuração da janela ---
root = tk.Tk()
root.title("Executar Scripts")
root.attributes("-fullscreen", True)
root.configure(bg="#f0f0f0")
root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))

# --- Frame de checkboxes ---
frame_check = tk.LabelFrame(root, text="Scripts", font=("Arial", 16, "bold"), padx=10, pady=10, bg="#f0f0f0")
frame_check.pack(side=tk.TOP, pady=10, padx=10, fill=tk.X)

check1_var = tk.BooleanVar(value=True)
check2_var = tk.BooleanVar(value=True)
check3_var = tk.BooleanVar(value=True)
check4_var = tk.BooleanVar(value=True)

check1 = tk.Checkbutton(frame_check, text="Download", variable=check1_var, font=("Arial", 16, "bold"),
                        height=3, width=20, bg="#f0f0f0")
check1.pack(side=tk.LEFT, padx=5)

check2 = tk.Checkbutton(frame_check, text="Beecrowd", variable=check2_var, font=("Arial", 16, "bold"),
                        height=3, width=20, bg="#f0f0f0")
check2.pack(side=tk.LEFT, padx=5)

check3 = tk.Checkbutton(frame_check, text="Compare", variable=check3_var, font=("Arial", 16, "bold"),
                        height=3, width=20, bg="#f0f0f0")
check3.pack(side=tk.LEFT, padx=5)

check4 = tk.Checkbutton(frame_check, text="Spreadsheet", variable=check4_var, font=("Arial", 16, "bold"),
                        height=3, width=20, bg="#f0f0f0")
check4.pack(side=tk.LEFT, padx=5)

# --- Frame de input e botão de execução ---
frame_input_config = tk.LabelFrame(root, text="Configuração", font=("Arial", 16, "bold"),
                                padx=10, pady=10, bg="#f0f0f0")
frame_input_config.pack(side=tk.TOP, pady=10, padx=10, fill=tk.X)

lbl_input = tk.Label(frame_input_config, text="Nome da lista:", font=("Arial", 14), bg="#f0f0f0")
lbl_input.pack(side=tk.LEFT, padx=5)

entrada = tk.Entry(frame_input_config, font=("Arial", 14), width=25)
entrada.pack(side=tk.LEFT, padx=5)

lbl_dificuldade = tk.Label(frame_input_config, text="Dificuldade (1-10):", font=("Arial", 14), bg="#f0f0f0")
lbl_dificuldade.pack(side=tk.LEFT, padx=5)

# Spinbox em vez de Entry, com valor padrão 5
entrada_dificuldade = tk.Spinbox(frame_input_config, from_=1, to=10, font=("Arial", 14), width=5)
entrada_dificuldade.delete(0, tk.END)
entrada_dificuldade.insert(0, "2")  # valor padrão
entrada_dificuldade.pack(side=tk.LEFT, padx=5)

btn_enviar = tk.Button(frame_input_config, text="Executar Selecionados", command=enviar_input,
                       height=2, width=25, font=("Arial", 14, "bold"),
                       bg="#4CAF50", fg="white", activebackground="#45a049")
btn_enviar.pack(side=tk.LEFT, padx=5)

btn_limpar = tk.Button(frame_input_config, text="Limpar Terminal", command=limpar_terminal,
                       height=2, width=15, font=("Arial", 14, "bold"),
                       bg="#f44336", fg="white", activebackground="#e53935")
btn_limpar.pack(side=tk.LEFT, padx=5)

# --- Área de texto para saída ---
terminal = tk.Text(root, wrap="word", bg="#111111", fg="#00FF00", font=("Consolas", 12),
                   bd=5, relief=tk.SUNKEN)
terminal.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

root.mainloop()
