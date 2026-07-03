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
    # Vade sistem için şart, gizli otomatik ekleniyor
    data['vade'] = datetime.now().strftime('%Y-%m-%d')
    supabase.table(table).insert(data).execute()

def update_status(table, id, status):
    supabase.table(table).update({"durum": status}).eq("id", id).execute()

def delete_data(table, id):
    supabase.table(table).delete().eq("id", id).execute()

# --- DETAY BELİRLEME MANTIĞI ---
def get_detay(row, tip):
    # Çekler için açıklamayı baz alıyoruz, diğerleri için kendi özel sütunları
    if tip == 'Çek': return row.get('aciklama', '')
    if tip == 'Borç': return row.get('alacakli', '')
    if tip == 'DBS': return row.get('kurum_banka', '')
    return row.get('aciklama', '')

# --- ARAYÜZ ---
st.title("💸 Ödeme Takip")
tab_dash, tab_cek, tab_borc, tab_dbs, tab_aylik = st.tabs(["📊 Dashboard", "📝 Çekler", "💳 Borçlar", "🏦 DBS", "📅 Aylık Rapor"])

# --- DASHBOARD ---
with tab_dash:
    st.header("📊 Genel Durum")
    cek_df, borc_df, dbs_df = get_data("cekler"), get_data("borclar"), get_data("dbs_odemeler")
    
    yarin = datetime.now().date() + timedelta(days=3)
    tum_veriler = []
    for df, tip in [(cek_df, 'Çek'), (borc_df, 'Borç'), (dbs_df, 'DBS')]:
        if not df.empty and 'vade' in df.columns:
            df['tip'] = tip
            df['detay_bilgi'] = df.apply(lambda row: get_detay(row, tip), axis=1)
            tum_veriler.append(df)
    
    if tum_veriler:
        df_hepsi = pd.concat(tum_veriler)
        df_hepsi['vade'] = pd.to_datetime(df_hepsi['vade']).dt.date
        yaklasanlar = df_hepsi[(df_hepsi['vade'] <= yarin) & (df_hepsi['durum'] == 'Ödenmedi')]
        
        if not yaklasanlar.empty:
            for _, row in yaklasanlar.iterrows():
                st.warning(f"⚠️ **{row['tip']} ({row['detay_bilgi']})** yaklaştı! Tutar: {row['tutar']:,.2f} ₺")
    
    col1, col2, col3 = st.columns(3)
    for df, col, label in [(borc_df, col1, "Borç"), (cek_df, col2, "Çek"), (dbs_df, col3, "DBS")]:
        if not df.empty and 'durum' in df.columns:
            col.metric(f"Bekleyen {label}", f"{df[df['durum'] == 'Ödenmedi']['tutar'].sum():,.2f} ₺")

# --- AYLIK RAPOR ---
with tab_aylik:
    st.header("📅 Aylık Rapor")
    ay_secimi = st.selectbox("Ay:", ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"])
    
    if st.button("Raporu Getir"):
        ay_map = {"Ocak": 1, "Şubat": 2, "Mart": 3, "Nisan": 4, "Mayıs": 5, "Haziran": 6, "Temmuz": 7, "Ağustos": 8, "Eylül": 9, "Ekim": 10, "Kasım": 11, "Aralık": 12}
        r_list = []
        for tablo, tip in [("cekler", "Çek"), ("borclar", "Borç"), ("dbs_odemeler", "DBS")]:
            df = get_data(tablo)
            if not df.empty:
                df['vade'] = pd.to_datetime(df['vade'])
                f_df = df[df['vade'].dt.month == ay_map[ay_secimi]]
                if not f_df.empty:
                    f_df['Detay'] = f_df.apply(lambda row: get_detay(row, tip), axis=1)
                    r_list.append(f_df[['Detay', 'aciklama', 'tutar', 'durum']])
        
        if r_list:
            final_df = pd.concat(r_list)
            st.metric("Bu Ay Toplam Ödeme", f"{final_df['tutar'].sum():,.2f} ₺")
            st.dataframe(final_df, use_container_width=True)
        else:
            st.info("Bu ay kayıt bulunamadı.")

# --- YÖNETİM ---
def render_tab(table_name, title, columns_map):
    st.header(title)
    with st.expander(f"➕ Yeni {title} Ekle"):
        with st.form(f"{table_name}_form", clear_on_submit=True):
            inputs = {k: st.number_input(l, format="%.2f") if "tutar" in k else st.text_input(l) for k, l in columns_map.items()}
            if st.form_submit_button("Kaydet"):
                add_data(table_name, inputs)
                st.rerun()

    df = get_data(table_name)
    if not df.empty:
        display_df = df.drop(columns=['vade'], errors='ignore')
        display_df.insert(0, "Seç", False)
        edited_df = st.data_editor(display_df, use_container_width=True, hide_index=True)
        
        c1, c2, c3 = st.columns(3)
        if c1.button("✅ Ödendi", key=f"b1_{table_name}"):
            for sid in edited_df[edited_df["Seç"] == True]["id"]: update_status(table_name, sid, 'Ödendi')
            st.rerun()
        if c2.button("⏳ Ödenmedi", key=f"b2_{table_name}"):
            for sid in edited_df[edited_df["Seç"] == True]["id"]: update_status(table_name, sid, 'Ödenmedi')
            st.rerun()
        if c3.button("🗑️ Sil", key=f"b3_{table_name}"):
            for sid in edited_df[edited_df["Seç"] == True]["id"]: delete_data(table_name, sid)
            st.rerun()

with tab_cek: render_tab("cekler", "Çek", {"aciklama": "Açıklama", "tutar": "Tutar"})
with tab_borc: render_tab("borclar", "Borç", {"alacakli": "Alacaklı", "aciklama": "Açıklama", "tutar": "Tutar"})
with tab_dbs: render_tab("dbs_odemeler", "DBS", {"kurum_banka": "Kurum/Banka", "aciklama": "Açıklama", "tutar": "Tutar"})
