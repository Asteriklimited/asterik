import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta
import io

# --- BAĞLANTI AYARLARI ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Ödeme Takip", layout="wide")

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
st.title("💸 Ödeme Takip")

# SEKMELERİ GÜNCELLEDİK
tab_dash, tab_cek, tab_borc, tab_dbs, tab_aylik = st.tabs(["📊 Dashboard", "📝 Çekler", "💳 Borçlar", "🏦 DBS", "📅 Aylık Rapor"])

# --- DASHBOARD ---
with tab_dash:
    st.header("📊 Genel Durum ve Bildirimler")
    cek_df = get_data("cekler")
    borc_df = get_data("borclar")
    dbs_df = get_data("dbs_odemeler")
    
    yarin = datetime.now().date() + timedelta(days=3)
    
    tum_veriler = []
    for df, tip in [(cek_df, 'Çek'), (borc_df, 'Borç'), (dbs_df, 'DBS')]:
        if not df.empty:
            df['tip'] = tip
            tum_veriler.append(df)
    
    if tum_veriler:
        df_hepsi = pd.concat(tum_veriler)
        df_hepsi['vade'] = pd.to_datetime(df_hepsi['vade']).dt.date
        yaklasanlar = df_hepsi[(df_hepsi['vade'] <= yarin) & (df_hepsi['durum'] == 'Ödenmedi')]
        
        if not yaklasanlar.empty:
            for _, row in yaklasanlar.iterrows():
                st.warning(f"⚠️ **{row['tip']} Ödemesi Yaklaştı!** | Vade: {row['vade']} | Tutar: {row['tutar']:,.2f} ₺ | Detay: {row['aciklama']}")
        else:
            st.success("✅ Yaklaşan ödemeniz bulunmuyor.")

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    for df, col, label in [(borc_df, col1, "Borç"), (cek_df, col2, "Çek"), (dbs_df, col3, "DBS")]:
        if not df.empty and 'durum' in df.columns:
            tutar = df[df['durum'] == 'Ödenmedi']['tutar'].sum()
            col.metric(f"Bekleyen {label}", f"{tutar:,.2f} ₺")

# --- AYLIK RAPOR SEKMESİ ---
with tab_aylik:
    st.header("📅 Aylık Ödeme Raporu")
    ay_secimi = st.selectbox("Ay Seçin:", ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"])
    yil_secimi = st.number_input("Yıl:", min_value=2024, max_value=2030, value=datetime.now().year)
    
    if st.button("Raporu Getir"):
        ay_map = {"Ocak": 1, "Şubat": 2, "Mart": 3, "Nisan": 4, "Mayıs": 5, "Haziran": 6, "Temmuz": 7, "Ağustos": 8, "Eylül": 9, "Ekim": 10, "Kasım": 11, "Aralık": 12}
        rapor_list = []
        for tablo in ["cekler", "borclar", "dbs_odemeler"]:
            df = get_data(tablo)
            if not df.empty:
                df['vade'] = pd.to_datetime(df['vade'])
                f_df = df[(df['vade'].dt.month == ay_map[ay_secimi]) & (df['vade'].dt.year == yil_secimi)]
                if not f_df.empty: rapor_list.append(f_df)
        
        if rapor_list:
            r_df = pd.concat(rapor_list)
            st.subheader(f"Toplam Ödeme: {r_df['tutar'].sum():,.2f} ₺")
            st.dataframe(r_df, use_container_width=True)
        else:
            st.info("Kayıt bulunamadı.")

# --- GENEL YÖNETİM ---
def render_tab(table_name, title, columns_map):
    st.header(title)
    with st.expander(f"➕ Yeni {title} Ekle"):
        with st.form(f"{table_name}_form", clear_on_submit=True):
            cols = st.columns(len(columns_map))
            inputs = {}
            for i, (key, label) in enumerate(columns_map.items()):
                k = f"{table_name}_{key}"
                if "vade" in key: inputs[key] = cols[i].date_input(label, key=f"{k}_date")
                elif "tutar" in key: inputs[key] = cols[i].number_input(label, format="%.2f", key=f"{k}_num")
                else: inputs[key] = cols[i].text_input(label, key=f"{k}_text")
            
            if st.form_submit_button("Kaydet"):
                for k, v in inputs.items():
                    if hasattr(v, 'isoformat'): inputs[k] = v.isoformat()
                add_data(table_name, inputs)
                st.rerun()

    df = get_data(table_name)
    if not df.empty:
        ara = st.text_input("Ara...", key=f"{table_name}_ara")
        sadece_acik = st.checkbox("Sadece Ödenmeyenler", key=f"{table_name}_chk")
        filtered_df = df.copy()
        if sadece_acik: filtered_df = filtered_df[filtered_df['durum'] == 'Ödenmedi']
        if ara: filtered_df = filtered_df[filtered_df.apply(lambda row: row.astype(str).str.contains(ara, case=False).any(), axis=1)]

        filtered_df.insert(0, "Seç", False)
        edited_df = st.data_editor(filtered_df, use_container_width=True, hide_index=True, key=f"{table_name}_edit")
        
        secilenler = edited_df[edited_df["Seç"] == True]["id"].tolist()
        if secilenler:
            c1, c2, c3 = st.columns(3)
            if c1.button("✅ Ödendi", key=f"b1_{table_name}"):
                for sid in secilenler: update_status(table_name, sid, 'Ödendi')
                st.rerun()
            if c2.button("⏳ Ödenmedi", key=f"b2_{table_name}"):
                for sid in secilenler: update_status(table_name, sid, 'Ödenmedi')
                st.rerun()
            if c3.button("🗑️ Sil", key=f"b3_{table_name}"):
                for sid in secilenler: delete_data(table_name, sid)
                st.rerun()

# --- SEKMELERİ ÇAĞIR ---
with tab_cek: render_tab("cekler", "Çek", {"cek_no": "Çek No", "aciklama": "Açıklama", "vade": "Vade", "tutar": "Tutar"})
with tab_borc: render_tab("borclar", "Borç", {"alacakli": "Alacaklı", "aciklama": "Açıklama", "vade": "Vade", "tutar": "Tutar"})
with tab_dbs: render_tab("dbs_odemeler", "DBS", {"kurum_banka": "Kurum/Banka", "aciklama": "Açıklama", "vade": "Vade", "tutar": "Tutar"})
