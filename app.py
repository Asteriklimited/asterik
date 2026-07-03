import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime
import io

# --- BAĞLANTI AYARLARI ---
# Secret'lar Streamlit Cloud'da Settings > Secrets kısmına girilmelidir.
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Nakit Akış Yönetimi", layout="wide")

# --- VERİTABANI FONKSİYONLARI ---
def get_data(table):
    response = supabase.table(table).select("*").execute()
    return pd.DataFrame(response.data)

def add_data(table, data):
    supabase.table(table).insert(data).execute()

def update_status(table, id, status):
    supabase.table(table).update({"durum": status}).eq("id", id).execute()

def delete_data(table, id):
    supabase.table(table).delete().eq("id", id).execute()

# --- ARAYÜZ ---
st.title("💸 Nakit Akış Yönetim Paneli (Online)")

tab_dash, tab_cek, tab_borc, tab_dbs = st.tabs(["📊 Dashboard", "📝 Çekler", "💳 Borçlar", "🏦 DBS"])

# --- DASHBOARD ---
with tab_dash:
    st.header("📊 Genel Durum ve Bildirimler")
    
    # Tüm verileri güncel çek
    cek_df = get_data("cekler")
    borc_df = get_data("borclar")
    dbs_df = get_data("dbs_odemeler")
    
    # Uyarı mantığı: Bugün + 3 gün
    yarin = datetime.now().date() + timedelta(days=3)
    bugun = datetime.now().date()
    
    uyarilar = []
    
    # Tüm tabloları birleştirip kontrol et
    tum_veriler = []
    if not cek_df.empty: 
        cek_df['tip'] = 'Çek'
        tum_veriler.append(cek_df)
    if not borc_df.empty: 
        borc_df['tip'] = 'Borç'
        tum_veriler.append(borc_df)
    if not dbs_df.empty: 
        dbs_df['tip'] = 'DBS'
        tum_veriler.append(dbs_df)
    
    if tum_veriler:
        df_hepsi = pd.concat(tum_veriler)
        df_hepsi['vade'] = pd.to_datetime(df_hepsi['vade']).dt.date
        
        # 3 GÜN İÇİNDE VADESİ GELENLER
        yaklasanlar = df_hepsi[(df_hepsi['vade'] <= yarin) & (df_hepsi['durum'] == 'Ödenmedi')]
        
        if not yaklasanlar.empty:
            for _, row in yaklasanlar.iterrows():
                st.warning(f"⚠️ **{row['tip']} Ödemesi Yaklaştı!** | Vade: {row['vade']} | Tutar: {row['tutar']:,.2f} ₺ | Detay: {row['aciklama']}")
        else:
            st.success("✅ Yaklaşan ödemeniz bulunmuyor.")

    # Özet Metrikler
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    for df, col, label in [(borc_df, col1, "Borç"), (cek_df, col2, "Çek"), (dbs_df, col3, "DBS")]:
        if not df.empty and 'durum' in df.columns:
            tutar = df[df['durum'] == 'Ödenmedi']['tutar'].sum()
            col.metric(f"Bekleyen {label}", f"{tutar:,.2f} ₺")

# --- GENEL YÖNETİM FONKSİYONU ---
def render_tab(table_name, title, columns_map):
    st.header(title)
    
    # Ekleme Formu
    with st.expander(f"➕ Yeni {title} Ekle"):
        with st.form(f"{table_name}_form", clear_on_submit=True):
            cols = st.columns(len(columns_map))
            inputs = {}
            for i, (key, label) in enumerate(columns_map.items()):
                # Benzersiz key ataması
                k = f"{table_name}_{key}"
                if "vade" in key:
                    inputs[key] = cols[i].date_input(label, key=f"{k}_date")
                elif "tutar" in key:
                    inputs[key] = cols[i].number_input(label, format="%.2f", key=f"{k}_num")
                else:
                    inputs[key] = cols[i].text_input(label, key=f"{k}_text")
            
            if st.form_submit_button("Kaydet"):
                # Tarihleri string'e çevir
                for k, v in inputs.items():
                    if hasattr(v, 'isoformat'):
                        inputs[k] = v.isoformat()
                add_data(table_name, inputs)
                st.rerun()

    # Tablo ve Filtreleme
    df = get_data(table_name)
    if not df.empty:
        st.markdown("### 🔍 Arama ve Filtreleme")
        f1, f2 = st.columns(2)
        ara = f1.text_input("Ara...", key=f"{table_name}_ara")
        sadece_acik = f2.checkbox("Sadece Ödenmeyenler", key=f"{table_name}_chk")
        
        filtered_df = df.copy()
        if sadece_acik:
            filtered_df = filtered_df[filtered_df['durum'] == 'Ödenmedi']
        if ara:
            filtered_df = filtered_df[filtered_df.apply(lambda row: row.astype(str).str.contains(ara, case=False).any(), axis=1)]

        filtered_df.insert(0, "Seç", False)
        edited_df = st.data_editor(filtered_df, use_container_width=True, hide_index=True, key=f"{table_name}_edit")
        
        secilenler = edited_df[edited_df["Seç"] == True]["id"].tolist()
        if secilenler:
            c1, c2, c3 = st.columns(3)
            if c1.button("✅ Ödendi", key=f"btn_odendi_{table_name}"):
                for sid in secilenler: update_status(table_name, sid, 'Ödendi')
                st.rerun()
            if c2.button("⏳ Ödenmedi", key=f"btn_odenmedi_{table_name}"):
                for sid in secilenler: update_status(table_name, sid, 'Ödenmedi')
                st.rerun()
            if c3.button("🗑️ Sil", key=f"btn_sil_{table_name}"):
                for sid in secilenler: delete_data(table_name, sid)
                st.rerun()

# --- SEKMELERİ ÇAĞIR ---
with tab_cek:
    render_tab("cekler", "Çek", {"cek_no": "Çek No", "aciklama": "Açıklama", "vade": "Vade", "tutar": "Tutar"})
with tab_borc:
    render_tab("borclar", "Borç", {"alacakli": "Alacaklı", "aciklama": "Açıklama", "vade": "Vade", "tutar": "Tutar"})
with tab_dbs:
    render_tab("dbs_odemeler", "DBS", {"kurum_banka": "Kurum/Banka", "aciklama": "Açıklama", "vade": "Vade", "tutar": "Tutar"})
