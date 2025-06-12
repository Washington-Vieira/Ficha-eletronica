import streamlit as st
import pandas as pd
from datetime import datetime
import os
from utils.sheets_pedidos_sync import SheetsPedidosSync

st.set_page_config(page_title="Pedido Local - Sincronização Google Sheets", page_icon="📦", layout="centered")

st.title("📦 Pedido Local - Sincronização com Google Sheets")

# Inicializar integração com Google Sheets
sheets_sync = SheetsPedidosSync(enable_sheets=True)

if not sheets_sync.client or not sheets_sync.SPREADSHEET_URL:
    st.error("Google Sheets não configurado corretamente. Configure no app principal.")
    st.stop()

# Carregar dados da aba 'paco' do Google Sheets
@st.cache_data(ttl=60)
def carregar_paco():
    df = sheets_sync.get_paco_as_dataframe()
    df.columns = [str(col).strip().title() for col in df.columns]
    return df.fillna("")

df_paco = carregar_paco()

st.markdown("---")
st.markdown("### 📄 Leitura de Código de Barras")

codigo = st.text_input("Escaneie ou digite o código de barras:", "", key="codigo_barra")

if st.button("Criar Pedido e Sincronizar", use_container_width=True):
    if not codigo.strip():
        st.warning("Digite ou escaneie um código de barras!")
    else:
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
        if pedido_encontrado:
            pedido_info = {
                **pedido_encontrado,
                "solicitante": "Pedido Local",
                "observacoes": "",
                "urgente": "Não",
                "data": datetime.now(),
                "ultima_atualizacao": datetime.now()
            }
            try:
                # Buscar próximo número sequencial REQ - N
                proximo_num = sheets_sync.get_proximo_numero_pedido(prefixo="REQ-")
                numero_pedido = f"REQ-{proximo_num}"
                df_pedidos = pd.DataFrame([{
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
                    "Solicitante": pedido_info['solicitante'],
                    "Observacoes": pedido_info['observacoes'],
                    "Urgente": pedido_info['urgente'],
                    "Status": "PENDENTE",
                    "Ultima_Atualizacao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Responsavel_Atualizacao": pedido_info['solicitante']
                }])
                df_itens = pd.DataFrame([{
                    "Numero_Pedido": numero_pedido,
                    "Serial": pedido_info['serial'],
                    "Quantidade": 1
                }])
                success, message = sheets_sync.salvar_pedido_completo(df_pedidos, df_itens)
                if success:
                    st.success(f"Pedido {numero_pedido} criado e sincronizado com sucesso!")
                else:
                    st.error(f"Erro ao sincronizar: {message}")
            except Exception as e:
                st.error(f"Erro ao criar pedido: {str(e)}")
        else:
            st.error("Serial não encontrado na planilha do Google Sheets!")

st.markdown("---")
st.info("Todos os pedidos criados aqui serão sincronizados e poderão ser visualizados no app principal.") 