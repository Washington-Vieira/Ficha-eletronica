import tkinter as tk
from tkinter import messagebox, ttk, filedialog, simpledialog
import pandas as pd
from datetime import datetime
import os
import json
from utils.sheets_pedidos_sync import SheetsPedidosSync
import sys
import threading

# Função para obter o caminho absoluto do recurso (compatível com PyInstaller)
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Função para garantir que arquivos de saída fiquem no diretório do exe
def exe_dir_path(filename):
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), filename)
    else:
        return os.path.join(os.path.abspath("."), filename)

CONFIG_FILE = resource_path("config.json")
PENDENTES_FILE = exe_dir_path("leituras_pendentes.json")
SENHA_PADRAO = "pyh#1874"

# Função para salvar a URL da planilha no config.json
def salvar_url_planilha(url):
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    else:
        config = {}
    config['sheets_url'] = url
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# Função para carregar a URL da planilha do config.json
def carregar_url_planilha():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        return config.get('sheets_url', '')
    return ''

class PedidoLocalApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pedidos SCs")
        self.root.geometry("700x370")
        self.sheets_sync = SheetsPedidosSync(enable_sheets=True, config_file=CONFIG_FILE)
        self.leituras = []  # Lista de dicionários: serial, status, mensagem, hora
        self.url_config_visible = False
        self._build_interface()
        self.update_pendencias_status()
        self.sync_thread = threading.Thread(target=self.sync_pendencias_background, daemon=True)
        self.sync_thread.start()

    def _build_interface(self):
        # Frame para status da URL e importação do config.json
        self.frame_url = tk.Frame(self.root)
        self.frame_url.pack(fill=tk.X, padx=10, pady=(10, 0))
        self.lbl_url_status = tk.Label(self.frame_url, text="URL configurada" if carregar_url_planilha() else "URL não configurada", fg="green" if carregar_url_planilha() else "red")
        self.lbl_url_status.pack(side=tk.LEFT, padx=10)
        # Botão para importar config.json
        self.btn_importar_config = tk.Button(self.frame_url, text="Importar config.json", command=self.importar_config)
        self.btn_importar_config.pack(side=tk.LEFT, padx=10)
        # Status de pendências
        self.lbl_pendencias = tk.Label(self.frame_url, text="", fg="orange")
        self.lbl_pendencias.pack(side=tk.LEFT, padx=10)

        # Campo para código de barras
        frame_leitura = tk.Frame(self.root)
        frame_leitura.pack(fill=tk.X, padx=10, pady=(10, 0))
        tk.Label(frame_leitura, text="Escaneie o código de barras:").pack(side=tk.LEFT)
        self.codigo_var = tk.StringVar()
        self.codigo_entry = tk.Entry(frame_leitura, textvariable=self.codigo_var, width=40, font=("Arial", 16))
        self.codigo_entry.pack(side=tk.LEFT, padx=5)
        self.codigo_entry.focus()
        self.codigo_entry.bind('<Return>', self.on_leitura)

        # Tabela de leituras
        frame_tabela = tk.Frame(self.root)
        frame_tabela.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))
        columns = ("serial", "status", "mensagem", "hora")
        self.tree = ttk.Treeview(frame_tabela, columns=columns, show="headings", height=10)
        self.tree.heading("serial", text="Serial")
        self.tree.heading("status", text="Status")
        self.tree.heading("mensagem", text="Mensagem")
        self.tree.heading("hora", text="Hora")
        self.tree.column("serial", width=180)
        self.tree.column("status", width=80)
        self.tree.column("mensagem", width=300)
        self.tree.column("hora", width=100)
        self.tree.pack(fill=tk.BOTH, expand=True)
        # Adicionar tag para sucesso
        self.tree.tag_configure('sucesso', background='#d4fcd4')  # verde claro

    def importar_config(self):
        # Solicitar senha antes de importar
        senha = tk.simpledialog.askstring("Senha", "Digite a senha para importar o config.json:", show="*")
        if senha != SENHA_PADRAO:
            messagebox.showerror("Senha incorreta", "Senha inválida! Não é possível importar o config.json.")
            return
        file_path = filedialog.askopenfilename(title="Selecione o config.json", filetypes=[("JSON files", "*.json")])
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    config_data = json.load(f)
                # Verificar se tem as chaves necessárias
                if 'sheets_credentials' not in config_data or not config_data['sheets_credentials']:
                    messagebox.showerror("Configuração inválida", "O arquivo selecionado não contém as credenciais da API (sheets_credentials). Selecione o config.json correto.")
                    return
                if 'sheets_url' not in config_data or not config_data['sheets_url']:
                    url = tk.simpledialog.askstring("URL da Planilha", "Digite a URL da planilha Google Sheets:")
                    if not url:
                        messagebox.showwarning("Configuração", "Importação cancelada: URL não informada.")
                        return
                    config_data['sheets_url'] = url
                # Salvar config.json no diretório do executável
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(config_data, f, indent=4)
                # Recarregar config e credenciais
                if hasattr(self.sheets_sync, 'load_config'):
                    self.sheets_sync.load_config()
                if hasattr(self.sheets_sync, 'initialize_client'):
                    self.sheets_sync.initialize_client()
                self.lbl_url_status.config(text="URL configurada" if carregar_url_planilha() else "URL não configurada", fg="green" if carregar_url_planilha() else "red")
                messagebox.showinfo("Importação", "Arquivo config.json importado e aplicado com sucesso!")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao importar config.json: {str(e)}")

    def on_leitura(self, event=None):
        codigo = self.codigo_var.get().strip()
        hora_leitura = datetime.now().strftime("%H:%M:%S")
        if not codigo:
            self.add_leitura(codigo, "❌", "Campo vazio", hora_leitura)
            self.codigo_var.set("")
            self.codigo_entry.focus()
            self.codigo_entry.selection_range(0, tk.END)
            return
        # Salva localmente e libera o campo imediatamente
        self.salvar_leitura_pendente(codigo, hora_leitura)
        self.codigo_var.set("")
        self.codigo_entry.focus()
        self.codigo_entry.selection_range(0, tk.END)
        self.update_pendencias_status()

    def salvar_leitura_pendente(self, codigo, hora):
        pendencias = self.carregar_pendencias()
        pendencias.append({"codigo": codigo, "hora": hora})
        with open(PENDENTES_FILE, 'w') as f:
            json.dump(pendencias, f, indent=4)
        self.update_pendencias_status()

    def carregar_pendencias(self):
        if os.path.exists(PENDENTES_FILE):
            try:
                with open(PENDENTES_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def remover_pendencias(self, indices_remover):
        pendencias = self.carregar_pendencias()
        pendencias = [p for i, p in enumerate(pendencias) if i not in indices_remover]
        with open(PENDENTES_FILE, 'w') as f:
            json.dump(pendencias, f, indent=4)
        self.update_pendencias_status()

    def update_pendencias_status(self):
        pendencias = self.carregar_pendencias()
        if pendencias:
            self.lbl_pendencias.config(text=f"Pendências: {len(pendencias)} não sincronizadas", fg="orange")
        else:
            self.lbl_pendencias.config(text="Sincronizado", fg="green")

    def sync_pendencias(self):
        pendencias = self.carregar_pendencias()
        if not pendencias:
            self.update_pendencias_status()
            return
        indices_sucesso = []
        leituras_sincronizadas = []
        for i, pend in enumerate(pendencias):
            codigo = pend["codigo"]
            hora = pend["hora"]
            # Tenta criar pedido no Google Sheets
            if not self.sheets_sync.client or not self.sheets_sync.SPREADSHEET_URL:
                # Só mostra erro de conexão, não serial não encontrado
                continue
            try:
                df_paco = self.sheets_sync.get_paco_as_dataframe()
                df_paco.columns = [str(col).strip().title() for col in df_paco.columns]
                codigo_norm = codigo.strip().upper()
                pedido_encontrado = None
                for _, row in df_paco.iterrows():
                    serial = str(row.get('Serial', '')).strip().upper()
                    if serial and serial == codigo_norm:
                        pedido_encontrado = {
                            'serial': str(row.get('Serial', '')).strip(),
                            'maquina': str(row.get('Maquina', '')).strip(),
                            'posto': str(row.get('Posto', '')).strip(),
                            'coordenada': str(row.get('Coordenada', '')).strip(),
                            'modelo': str(row.get('Modelo', '')).strip(),
                            'ot': str(row.get('Ot', '')).strip(),
                            'semiacabado': str(row.get('Semiacabado', '')).strip(),
                            'pagoda': str(row.get('Pagoda', '')).strip()
                        }
                        break
                if not pedido_encontrado:
                    # Não mostra na tabela, apenas mantém como pendente
                    continue
                proximo_num = self.sheets_sync.get_proximo_numero_pedido(prefixo="REQ-")
                numero_pedido = f"REQ-{proximo_num:03d}"
                pedido_info = {
                    **pedido_encontrado,
                    "solicitante": "Pedido Local Desktop",
                    "observacoes": "",
                    "urgente": "Não",
                    "data": datetime.now(),
                    "ultima_atualizacao": datetime.now()
                }
                colunas_pedidos = [
                    "Numero_Pedido", "Data", "Serial", "Maquina", "Posto", "Coordenada", "Modelo", "OT", "Semiacabado", "Pagoda", "Status", "Urgente", "Ultima_Atualizacao", "Responsavel_Atualizacao", "Responsavel_Separacao", "Data_Separacao", "Responsavel_Coleta", "Data_Coleta", "Solicitante", "Observacoes"
                ]
                novo_pedido = {
                    "Numero_Pedido": numero_pedido,
                    "Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Serial": pedido_info['serial'],
                    "Maquina": pedido_info['maquina'],
                    "Posto": pedido_info['posto'],
                    "Coordenada": pedido_info['coordenada'],
                    "Modelo": pedido_info['modelo'],
                    "OT": pedido_info['ot'],
                    "Semiacabado": pedido_info['semiacabado'],
                    "Pagoda": pedido_info['pagoda'],
                    "Status": "PENDENTE",
                    "Urgente": pedido_info['urgente'],
                    "Ultima_Atualizacao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Responsavel_Atualizacao": pedido_info['solicitante'],
                    "Responsavel_Separacao": "",
                    "Data_Separacao": "",
                    "Responsavel_Coleta": "",
                    "Data_Coleta": "",
                    "Solicitante": pedido_info['solicitante'],
                    "Observacoes": pedido_info['observacoes']
                }
                df_pedidos = pd.DataFrame([[novo_pedido.get(col, "") for col in colunas_pedidos]], columns=colunas_pedidos)
                df_itens = pd.DataFrame([{
                    "Numero_Pedido": numero_pedido,
                    "Serial": pedido_info['serial'],
                    "Quantidade": 1
                }])
                success, message = self.sheets_sync.salvar_pedido_completo(df_pedidos, df_itens)
                if success:
                    leituras_sincronizadas.append({"serial": codigo, "status": "✅", "mensagem": f"Pedido {numero_pedido} criado! (sincronizado)", "hora": hora})
                    indices_sucesso.append(i)
                else:
                    # Só mostra erro de conexão
                    leituras_sincronizadas.append({"serial": codigo, "status": "❌", "mensagem": f"Erro ao sincronizar: {message}", "hora": hora})
            except Exception as e:
                # Só mostra erro de conexão
                leituras_sincronizadas.append({"serial": codigo, "status": "❌", "mensagem": f"Erro: {str(e)} (pendente)", "hora": hora})
        if indices_sucesso:
            self.remover_pendencias(indices_sucesso)
        self.update_pendencias_status()
        # Atualiza a tabela apenas com leituras sincronizadas ou erro de conexão
        for leitura in leituras_sincronizadas:
            self.add_leitura(leitura["serial"], leitura["status"], leitura["mensagem"], leitura["hora"])

    def sync_pendencias_background(self):
        while True:
            self.sync_pendencias()
            import time
            time.sleep(5)

    def add_leitura(self, serial, status, mensagem, hora):
        self.leituras.append({"serial": serial, "status": status, "mensagem": mensagem, "hora": hora})
        # Limitar aos últimos 10
        self.leituras = self.leituras[-10:]
        # Limpar tabela
        for row in self.tree.get_children():
            self.tree.delete(row)
        # Adicionar na tabela
        for leitura in self.leituras:
            tag = 'sucesso' if leitura["status"] == "✅" else ''
            self.tree.insert("", tk.END, values=(leitura["serial"], leitura["status"], leitura["mensagem"], leitura["hora"]), tags=(tag,))

if __name__ == "__main__":
    root = tk.Tk()
    app = PedidoLocalApp(root)
    root.mainloop() 