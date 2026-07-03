import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import io

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Nakit Akış Yönetimi", layout="wide")

# --- VERİTABANI İŞLEMLERİ ---
def init_db():
    conn = sqlite3.connect('nakit_akis.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS cekler 
                 (id INTEGER PRIMARY KEY, cek_no TEXT, aciklama TEXT, vade DATE, tutar REAL, durum TEXT DEFAULT 'Ödenmedi')''')
    c.execute('''CREATE TABLE IF NOT EXISTS borclar 
                 (id INTEGER PRIMARY KEY, alacakli TEXT, aciklama TEXT, vade DATE, tutar REAL, durum TEXT DEFAULT 'Ödenmedi')''')
    c.execute('''CREATE TABLE IF NOT EXISTS dbs_odemeler 
                 (id INTEGER PRIMARY KEY, kurum_banka TEXT, aciklama TEXT, vade DATE, tutar REAL, durum TEXT DEFAULT 'Ödenmedi')''')
    
    for table in ['cekler', 'borclar', 'dbs_odemeler']:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN durum TEXT DEFAULT 'Ödenmedi'")
        except sqlite3.OperationalError:
            pass
            
    conn.commit()
    conn.close()

def run_query(query, params=()):
    conn = sqlite3.connect('nakit_akis.db')
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def execute_query(query, params=()):
    conn = sqlite3.connect('nakit_akis.db')
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Veri')
    processed_data = output.getvalue()
    return processed_data

init_db()

# --- ARAYÜZ ---
st.title("💸 Nakit Akış Yönetim Paneli")

tab_dash, tab_cek, tab_borc, tab_dbs = st.tabs([
    "📊 Dashboard", "📝 Çekler", "💳 Borçlar/Ödenecekler", "🏦 DBS"
])

bugun = datetime.now().date()
iki_gun_sonrasi = bugun + timedelta(days=2)

# --- 1. DASHBOARD ---
with tab_dash:
    st.header("Genel Durum ve Hatırlatmalar")
    
    yaklasan_toplam_odeme = 0.0
    bildirimler = []

    cek_df = run_query("SELECT * FROM cekler WHERE durum='Ödenmedi'")
    borc_df = run_query("SELECT * FROM borclar WHERE durum='Ödenmedi'")
    dbs_df = run_query("SELECT * FROM dbs_odemeler WHERE durum='Ödenmedi'")

    if not cek_df.empty:
        cek_df['vade'] = pd.to_datetime(cek_df['vade']).dt.date
        yaklasan_cekler = cek_df[cek_df['vade'] <= iki_gun_sonrasi]
        yaklasan_toplam_odeme += yaklasan_cekler['tutar'].sum()
        for _, row in yaklasan_cekler.iterrows():
            durum = "VADESİ GEÇTİ!" if row['vade'] < bugun else "Vade Yaklaştı"
            bildirimler.append(f"**⚠️ Çek ({durum}):** {row['cek_no']} | Vade: {row['vade']} | Tutar: {row['tutar']:,.2f} ₺")

    if not borc_df.empty:
        borc_df['vade'] = pd.to_datetime(borc_df['vade']).dt.date
        yaklasan_borclar = borc_df[borc_df['vade'] <= iki_gun_sonrasi]
        yaklasan_toplam_odeme += yaklasan_borclar['tutar'].sum()
        for _, row in yaklasan_borclar.iterrows():
            durum = "VADESİ GEÇTİ!" if row['vade'] < bugun else "Vade Yaklaştı"
            bildirimler.append(f"**🚨 Borç ({durum}):** {row['alacakli']} | Vade: {row['vade']} | Tutar: {row['tutar']:,.2f} ₺")

    if not dbs_df.empty:
        dbs_df['vade'] = pd.to_datetime(dbs_df['vade']).dt.date
        yaklasan_dbs = dbs_df[dbs_df['vade'] <= iki_gun_sonrasi]
        yaklasan_toplam_odeme += yaklasan_dbs['tutar'].sum()
        for _, row in yaklasan_dbs.iterrows():
            durum = "VADESİ GEÇTİ!" if row['vade'] < bugun else "Vade Yaklaştı"
            bildirimler.append(f"**🏦 DBS ({durum}):** {row['kurum_banka']} | Vade: {row['vade']} | Tutar: {row['tutar']:,.2f} ₺")

    st.error(f"### 🛑 YAKLAŞAN/GECİKEN TOPLAM ÖDEME: {yaklasan_toplam_odeme:,.2f} ₺")
    
    st.subheader("🚨 Detaylı Bildirimler (Son 2 Gün ve Gecikenler)")
    if bildirimler:
        for b in bildirimler:
            st.warning(b)
    else:
        st.success("Şu an için yaklaşan veya geciken bir ödemeniz bulunmuyor. Harika!")

    st.markdown("---")
    st.write("##### Bekleyen (Ödenmemiş) Toplam Yükümlülükleriniz")
    col1, col2, col3 = st.columns(3)
    toplam_borc = borc_df['tutar'].sum() if not borc_df.empty else 0
    toplam_cek = cek_df['tutar'].sum() if not cek_df.empty else 0
    toplam_dbs = dbs_df['tutar'].sum() if not dbs_df.empty else 0

    col1.metric("Bekleyen Toplam Borç", f"{toplam_borc:,.2f} ₺")
    col2.metric("Bekleyen Toplam Çek", f"{toplam_cek:,.2f} ₺")
    col3.metric("Bekleyen Toplam DBS", f"{toplam_dbs:,.2f} ₺")

# --- 2. ÇEKLER ---
with tab_cek:
    with st.expander("➕ Yeni Çek Ekle"):
        with st.form("cek_ekle_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            cek_no = c1.text_input("Çek No")
            vade = c2.date_input("Vade Tarihi")
            tutar = c3.number_input("Tutar (₺)", min_value=0.0, format="%.2f")
            aciklama = st.text_input("Açıklama/Keşideci")
            if st.form_submit_button("Çek Ekle"):
                execute_query("INSERT INTO cekler (cek_no, aciklama, vade, tutar) VALUES (?, ?, ?, ?)", (cek_no, aciklama, vade, tutar))
                st.success("Çek başarıyla eklendi!")
                st.rerun()

    df_c = run_query("SELECT id, cek_no as 'Çek No', aciklama as 'Açıklama', vade as 'Vade', tutar as 'Tutar (₺)', durum as 'Durum' FROM cekler")
    
    if not df_c.empty:
        st.markdown("### 🔍 Arama ve Filtreleme")
        f1, f2, f3 = st.columns([2, 1, 2])
        arama_cek = f1.text_input("Çek No veya Açıklama ara...", key="ara_cek")
        sadece_odenmeyen_cek = f2.checkbox("Sadece Ödenmeyenler", value=False, key="chk_cek")
        tarih_cek = f3.date_input("Vade Aralığı Seçin", value=(), key="tarih_cek")

        df_c_filtered = df_c.copy()
        if sadece_odenmeyen_cek:
            df_c_filtered = df_c_filtered[df_c_filtered['Durum'] == 'Ödenmedi']
        if arama_cek:
            df_c_filtered = df_c_filtered[df_c_filtered['Çek No'].str.contains(arama_cek, case=False, na=False) | 
                                          df_c_filtered['Açıklama'].str.contains(arama_cek, case=False, na=False)]
        if len(tarih_cek) == 2:
            df_c_filtered['Vade_dt'] = pd.to_datetime(df_c_filtered['Vade']).dt.date
            df_c_filtered = df_c_filtered[(df_c_filtered['Vade_dt'] >= tarih_cek[0]) & (df_c_filtered['Vade_dt'] <= tarih_cek[1])]
            df_c_filtered = df_c_filtered.drop(columns=['Vade_dt'])

        df_c_filtered.insert(0, "Seç", False)
        edited_df_c = st.data_editor(df_c_filtered, hide_index=True, use_container_width=True, 
                                     column_config={"Seç": st.column_config.CheckboxColumn("Seç", default=False), "id": None},
                                     disabled=["Çek No", "Açıklama", "Vade", "Tutar (₺)", "Durum"], key="editor_cek")
        
        st.download_button("Excel'e Aktar", to_excel(df_c_filtered.drop(columns=['Seç'])), "cekler.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="export_cek")
        
        secilenler_c = edited_df_c[edited_df_c["Seç"] == True]["id"].tolist()
        if secilenler_c:
            st.markdown("---")
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            if col_btn1.button("✅ Ödendi İşaretle", key="cek_odendi"):
                for sid in secilenler_c: execute_query("UPDATE cekler SET durum='Ödendi' WHERE id=?", (sid,))
                st.rerun()
            if col_btn2.button("⏳ Ödenmedi İşaretle", key="cek_odenmedi"):
                for sid in secilenler_c: execute_query("UPDATE cekler SET durum='Ödenmedi' WHERE id=?", (sid,))
                st.rerun()
            if col_btn3.button("🗑️ Kaydı Sil", key="cek_sil"):
                for sid in secilenler_c: execute_query("DELETE FROM cekler WHERE id=?", (sid,))
                st.rerun()

# --- 3. BORÇLAR / ÖDENECEKLER ---
with tab_borc:
    with st.expander("➕ Yeni Borç Ekle"):
        with st.form("borc_ekle_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            alacakli = c1.text_input("Alacaklı Kişi/Kurum")
            vade_b = c2.date_input("Son Ödeme Tarihi")
            tutar_b = c3.number_input("Tutar (₺)", min_value=0.0, format="%.2f")
            aciklama_b = st.text_input("Borç Açıklaması")
            if st.form_submit_button("Borç Ekle"):
                execute_query("INSERT INTO borclar (alacakli, aciklama, vade, tutar) VALUES (?, ?, ?, ?)", (alacakli, aciklama_b, vade_b, tutar_b))
                st.success("Borç başarıyla eklendi!")
                st.rerun()

    df_b = run_query("SELECT id, alacakli as 'Alacaklı', aciklama as 'Açıklama', vade as 'Vade', tutar as 'Tutar (₺)', durum as 'Durum' FROM borclar")
    
    if not df_b.empty:
        st.markdown("### 🔍 Arama ve Filtreleme")
        f1, f2, f3 = st.columns([2, 1, 2])
        arama_borc = f1.text_input("Alacaklı veya Açıklama ara...", key="ara_borc")
        sadece_odenmeyen_borc = f2.checkbox("Sadece Ödenmeyenler", value=False, key="chk_borc")
        tarih_borc = f3.date_input("Vade Aralığı Seçin", value=(), key="tarih_borc")

        df_b_filtered = df_b.copy()
        if sadece_odenmeyen_borc:
            df_b_filtered = df_b_filtered[df_b_filtered['Durum'] == 'Ödenmedi']
        if arama_borc:
            df_b_filtered = df_b_filtered[df_b_filtered['Alacaklı'].str.contains(arama_borc, case=False, na=False) | 
                                          df_b_filtered['Açıklama'].str.contains(arama_borc, case=False, na=False)]
        if len(tarih_borc) == 2:
            df_b_filtered['Vade_dt'] = pd.to_datetime(df_b_filtered['Vade']).dt.date
            df_b_filtered = df_b_filtered[(df_b_filtered['Vade_dt'] >= tarih_borc[0]) & (df_b_filtered['Vade_dt'] <= tarih_borc[1])]
            df_b_filtered = df_b_filtered.drop(columns=['Vade_dt'])

        df_b_filtered.insert(0, "Seç", False)
        edited_df_b = st.data_editor(df_b_filtered, hide_index=True, use_container_width=True, 
                                     column_config={"Seç": st.column_config.CheckboxColumn("Seç", default=False), "id": None},
                                     disabled=["Alacaklı", "Açıklama", "Vade", "Tutar (₺)", "Durum"], key="editor_borc")
        
        st.download_button("Excel'e Aktar", to_excel(df_b_filtered.drop(columns=['Seç'])), "borclar.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="export_borc")
        
        secilenler_b = edited_df_b[edited_df_b["Seç"] == True]["id"].tolist()
        if secilenler_b:
            st.markdown("---")
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            if col_btn1.button("✅ Ödendi İşaretle", key="borc_odendi"):
                for sid in secilenler_b: execute_query("UPDATE borclar SET durum='Ödendi' WHERE id=?", (sid,))
                st.rerun()
            if col_btn2.button("⏳ Ödenmedi İşaretle", key="borc_odenmedi"):
                for sid in secilenler_b: execute_query("UPDATE borclar SET durum='Ödenmedi' WHERE id=?", (sid,))
                st.rerun()
            if col_btn3.button("🗑️ Kaydı Sil", key="borc_sil"):
                for sid in secilenler_b: execute_query("DELETE FROM borclar WHERE id=?", (sid,))
                st.rerun()

# --- 4. DBS ÖDEME HATIRLATICI ---
with tab_dbs:
    with st.expander("➕ Yeni DBS Ödeme Notu Ekle"):
        with st.form("dbs_ekle_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            kurum_banka = c1.text_input("Kurum / Banka Adı")
            vade_dbs = c2.date_input("Ödeme (Vade) Tarihi")
            tutar_dbs = c3.number_input("Ödenecek Tutar (₺)", min_value=0.0, format="%.2f")
            aciklama_dbs = st.text_input("Ödeme Detayı / Notu")
            if st.form_submit_button("Ödeme Notunu Kaydet"):
                execute_query("INSERT INTO dbs_odemeler (kurum_banka, aciklama, vade, tutar) VALUES (?, ?, ?, ?)", (kurum_banka, aciklama_dbs, vade_dbs, tutar_dbs))
                st.success("DBS Ödeme notu başarıyla kaydedildi!")
                st.rerun()

    df_dbs = run_query("SELECT id, kurum_banka as 'Kurum/Banka', aciklama as 'Açıklama', vade as 'Vade', tutar as 'Tutar (₺)', durum as 'Durum' FROM dbs_odemeler")
    
    if not df_dbs.empty:
        st.markdown("### 🔍 Arama ve Filtreleme")
        f1, f2, f3 = st.columns([2, 1, 2])
        arama_dbs = f1.text_input("Kurum veya Açıklama ara...", key="ara_dbs")
        sadece_odenmeyen_dbs = f2.checkbox("Sadece Ödenmeyenler", value=False, key="chk_dbs")
        tarih_dbs = f3.date_input("Vade Aralığı Seçin", value=(), key="tarih_dbs")

        df_dbs_filtered = df_dbs.copy()
        if sadece_odenmeyen_dbs:
            df_dbs_filtered = df_dbs_filtered[df_dbs_filtered['Durum'] == 'Ödenmedi']
        if arama_dbs:
            df_dbs_filtered = df_dbs_filtered[df_dbs_filtered['Kurum/Banka'].str.contains(arama_dbs, case=False, na=False) | 
                                              df_dbs_filtered['Açıklama'].str.contains(arama_dbs, case=False, na=False)]
        if len(tarih_dbs) == 2:
            df_dbs_filtered['Vade_dt'] = pd.to_datetime(df_dbs_filtered['Vade']).dt.date
            df_dbs_filtered = df_dbs_filtered[(df_dbs_filtered['Vade_dt'] >= tarih_dbs[0]) & (df_dbs_filtered['Vade_dt'] <= tarih_dbs[1])]
            df_dbs_filtered = df_dbs_filtered.drop(columns=['Vade_dt'])

        df_dbs_filtered.insert(0, "Seç", False)
        edited_df_dbs = st.data_editor(df_dbs_filtered, hide_index=True, use_container_width=True, 
                                       column_config={"Seç": st.column_config.CheckboxColumn("Seç", default=False), "id": None},
                                       disabled=["Kurum/Banka", "Açıklama", "Vade", "Tutar (₺)", "Durum"], key="editor_dbs")
        
        st.download_button("Excel'e Aktar", to_excel(df_dbs_filtered.drop(columns=['Seç'])), "dbs_odeme_plani.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="export_dbs")
        
        secilenler_dbs = edited_df_dbs[edited_df_dbs["Seç"] == True]["id"].tolist()
        if secilenler_dbs:
            st.markdown("---")
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            if col_btn1.button("✅ Ödendi İşaretle", key="dbs_odendi"):
                for sid in secilenler_dbs: execute_query("UPDATE dbs_odemeler SET durum='Ödendi' WHERE id=?", (sid,))
                st.rerun()
            if col_btn2.button("⏳ Ödenmedi İşaretle", key="dbs_odenmedi"):
                for sid in secilenler_dbs: execute_query("UPDATE dbs_odemeler SET durum='Ödenmedi' WHERE id=?", (sid,))
                st.rerun()
            if col_btn3.button("🗑️ Kaydı Sil", key="dbs_sil"):
                for sid in secilenler_dbs: execute_query("DELETE FROM dbs_odemeler WHERE id=?", (sid,))
                st.rerun()