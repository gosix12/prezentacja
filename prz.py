import streamlit as st
import pandas as pd
from PIL import Image
import plotly.express as px
import plotly.graph_objects as go
import os
import graphviz
import streamlit.components.v1 as components
st.set_page_config(page_title="SmartPromocje, czyli jak dane pomagają przewidywać sprzedaż leków", layout="wide")
top_years = [2022, 2023, 2024] # Lata, dla których masz pliki
def show_dashboard_block(df, title):
    st.subheader(f"Dashboard dla {title}")
    st.metric(label=f"Całkowita sprzedaż {title} (sztuki)", value=f"{df['Ilość'].sum():,.0f}")
    st.metric(label=f"Liczba unikalnych promocji {title}", value=f"{df['Rodzaj promocji'].nunique()}")
    st.dataframe(df.head(), use_container_width=True) # Pokazujemy head dla przykładu
    st.write("---")
@st.cache_data
def load_wsk_data():
    try:
        # Pamiętaj, aby te pliki zostały wcześniej wygenerowane jako Parquet!
        wskprz_df = pd.read_parquet('wskprz.parquet')
        wskwaga_df = pd.read_parquet('wskwaga.parquet')
        return wskprz_df, wskwaga_df
    except FileNotFoundError:
        st.error("Błąd: Nie znaleziono plików 'wskprz.parquet' lub 'wskwaga.parquet'.")
        st.stop()

@st.cache_data
def load_tab7_data():
    try:
        # Wczytujemy pojedyncze pliki, bo analiza jest na nich osobno
        waga_df = pd.read_parquet('waga_processed.parquet')
        przylepce_df = pd.read_parquet('przylepce_processed.parquet')
        return waga_df, przylepce_df
    except FileNotFoundError:
        st.error("Błąd: Nie znaleziono plików 'waga_processed.parquet' lub 'przylepce_processed.parquet'. "
                 "Upewnij się, że uruchomiłeś skrypt generujący te pliki!")
        st.stop() # Zatrzymaj aplikację, jeśli plików brakuje

# Wczytaj dane raz na początku aplikacji Streamlit
waga, przylepce = load_tab7_data()
month_names = { # Pełne nazwy miesięcy - używane do tworzenia kolumny 'Miesiąc_nazwa' w 'przygotuj_daty_cached'
    1: "Styczeń", 2: "Luty", 3: "Marzec", 4: "Kwiecień", 5: "Maj", 6: "Czerwiec",
    7: "Lipiec", 8: "Sierpień", 9: "Wrzesień", 10: "Październik", 11: "Listopad", 12: "Grudzień"
}
month_names_short = { # Skrócone nazwy miesięcy - używane w tabelach i pivotach
    1: "Sty", 2: "Lut", 3: "Mar", 4: "Kwi", 5: "Maj", 6: "Cze",
    7: "Lip", 8: "Sie", 9: "Wrz", 10: "Paź", 11: "Lis", 12: "Gru"
}

def info_card(title, value, color, icon):
    st.markdown(
        f"""
        <div style="
            background-color: {color};
            padding: 15px; /* Zwiększono padding */
            border-radius: 8px; /* Lekko zwiększono zaokrąglenie rogów */
            border: 2px solid rgba(255, 255, 255, 0.5); /* Dodano/zwiększono obwódkę */
            text-align: center;
            color: white;
            box-shadow: 3px 3px 8px rgba(0,0,0,0.3); /* Zwiększono cień dla lepszego efektu */
            height: 120px; /* Zwiększono wysokość karty */
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        ">
            <div style="font-size: 2.5em; margin-bottom: 5px;">{icon}</div> 
            <div style="font-weight: bold; font-size: 1.1em; margin-bottom: 3px;">{title}</div> 
            <div style="font-size: 1.8em;">{value:,}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
# --- Funkcje przygotowujące dane do wizualizacji (miesięczne) ---
@st.cache_data
def load_df_aggregated_categories():
    """
    Ładuje dane kategoryzacyjne z pliku Parquet.
    """
    try:
        df = pd.read_parquet("df_aggregated.parquet") 

        required_cols = ['Rok', 'Kategoria nazwa', 'sprzedaz_budzetowa_total', 'sprzedaz_ilosc_total']
        if not all(col in df.columns for col in required_cols):
            st.error(f"Błąd: Plik 'df_aggregated.parquet' nie zawiera wszystkich wymaganych kolumn: {', '.join(required_cols)}")
            return pd.DataFrame()
        df['Rok'] = df['Rok'].astype(int) # Upewnij się, że Rok jest intem
        return df
    except FileNotFoundError:
        # Zmieniono komunikat na bardziej pomocny
        st.error("BŁĄD WYSZUKIWANIA PLIKU: Plik 'df_aggregated.parquet' nie znaleziony. "
                 "Upewnij się, że plik jest w prawidłowej ścieżce względem skryptu Streamlit "
                 "(np. w tym samym folderze lub w podfolderze 'data/').")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Inny błąd podczas wczytywania pliku kategoryzacyjnego: {e}")
        return pd.DataFrame()
@st.cache_data
def load_aggregated_data():
    try:
        df_sales_by_category = pd.read_parquet('sales_by_category.parquet')
        df_sales_by_promotion = pd.read_parquet('sales_by_promotion.parquet')
        return df_sales_by_category, df_sales_by_promotion
    except FileNotFoundError:
        st.error("Błąd: Nie znaleziono plików 'sales_by_category.parquet' lub 'sales_by_promotion.parquet'. "
                 "Upewnij się, że uruchomiłeś skrypt generujący te pliki!")
        st.stop() # Zatrzymaj aplikację, jeśli plików brakuje

df_sales_by_category, df_sales_by_promotion = load_aggregated_data()

wskprz, wskwaga = load_wsk_data()
# --- Funkcje pomocnicze ---

# Funkcja wybierająca kolumnę (dostosowana do nowych nazw kolumn w Parquet)
def wybierz_kolumne_wg(filtr):
    # W plikach Parquet kolumna "Ilość" już nie ma spacji
    return 'Sprzedaż budżetowa' if filtr == "Sprzedaż wartościowa" else 'Ilość'

# Funkcja analizy Pareto (dostosowana do pracy z zagregowanymi danymi i filtrowaniem po roku)
def analiza_pareto_from_agg(df_agg, grupa_kolumna, filtr, prog, rok_filtr=None):
    kol = wybierz_kolumne_wg(filtr)

    df_current_year = df_agg
    if rok_filtr is not None:
        df_current_year = df_agg[df_agg['Rok'] == rok_filtr]

    # Jeśli po filtrowaniu nie ma danych, zwróć puste wyniki
    if df_current_year.empty:
        return 0, 0.0, pd.DataFrame(columns=[grupa_kolumna, kol, 'Skumulowany %']), pd.Series(dtype='float64')

    # Sumujemy już zagregowane dane dla danego roku/grupy
    sprzedaz = df_current_year.groupby(grupa_kolumna)[kol].sum().sort_values(ascending=False)

    # Upewniamy się, że nie dzielimy przez zero, jeśli suma sprzedaży wynosi 0
    total_sum = sprzedaz.sum()
    if total_sum == 0:
        return 0, 0.0, pd.DataFrame(columns=[grupa_kolumna, kol, 'Skumulowany %']), sprzedaz

    skumulowana = sprzedaz.cumsum()
    procent = 100 * skumulowana / total_sum

    ograniczone = sprzedaz[procent <= prog].to_frame(name=kol)
    ograniczone['Skumulowany %'] = procent[procent <= prog]

    liczba = len(ograniczone)
    procent_grup = 100 * liczba / len(sprzedaz) if len(sprzedaz) > 0 else 0

    return liczba, procent_grup, ograniczone, sprzedaz
@st.cache_data
def load_monthly_sales_data(sales_type: str, year: int) -> pd.DataFrame:
    """
    Wczytuje pojedynczy plik Parquet dla sprzedaży miesięcznej.
    sales_type: 'budzetowa' lub 'ilosciowa'
    """
    filename = f"sprzedaz_mies_{sales_type}_{year}.parquet"
    try:
        df = pd.read_parquet(filename)
        # Sprawdzamy wymagane kolumny
        required_cols = ['Rok', 'Miesiąc', 'sprzedaz_total', 'Miesiąc_nazwa']
        if not all(col in df.columns for col in required_cols):
            st.error(f"Błąd: Plik '{filename}' nie zawiera wszystkich wymaganych kolumn: {', '.join(required_cols)}")
            return pd.DataFrame()
        return df
    except FileNotFoundError:
        st.warning(f"Plik '{filename}' nie znaleziony. Pomięto dane dla roku {year}.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Błąd podczas wczytywania pliku '{filename}': {e}")
        return pd.DataFrame()

@st.cache_data
def load_all_monthly_sales(sales_type: str) -> dict:
    """
    Wczytuje wszystkie pliki miesięczne dla danego typu sprzedaży (ilosciowa/budzetowa)
    i zwraca słownik DataFrame'ów per rok.
    """
    all_data = {}
    for year in top_years:
        df = load_monthly_sales_data(sales_type, year)
        if not df.empty:
            all_data[year] = df
    return all_data

# Ładowanie danych miesięcznych z plików na początku działania aplikacji

monthly_sales_ilosciowa = load_all_monthly_sales('ilosciowa')
monthly_sales_budzetowa = load_all_monthly_sales('budzetowa')


@st.cache_data
def load_udzialy_data() -> pd.DataFrame:
    """
    Wczytuje dane z pliku udzial_all.parquet i mapuje nazwy kolumn.
    """
    filename = "udzial_all.parquet" # <--- Upewnij się, że plik jest w tym samym katalogu
    try:
        df = pd.read_parquet(filename)
        # Mapowanie nazw kolumn z obrazka na te oczekiwane w kodzie
        df = df.rename(columns={
            'sprzedaz ilo total': 'Sprzedaż ilość',
            'sprzedaz budzet total': 'Sprzedaż budżetowa',
            'daz rynek wartosc': 'Sprzedaż rynek wartość',
            'dzial rynek ilosc': 'Sprzedaż rynek ilość', # Domyślam się nazwy tej kolumny, bo jej nie widać w całości na obrazku
            'udzial ilosciowy': 'Udział ilościowy (%)',
            'dzial wartosciowy': 'Udział wartościowy (%)'
        })
        
        # Sprawdzenie, czy kluczowe kolumny do obliczeń są obecne po zmianie nazw
        required_cols_after_rename = [
            'Miesiąc', 'Rok',
            'Sprzedaż ilość', 'Sprzedaż budżetowa',
            'Sprzedaż rynek ilość', 'Sprzedaż rynek wartość',
            'Udział ilościowy (%)', 'Udział wartościowy (%)' # Dodane kolumny udziałów
        ]
        if not all(col in df.columns for col in required_cols_after_rename):
            st.error(f"Błąd: Plik '{filename}' po mapowaniu nie zawiera wszystkich wymaganych kolumn: {', '.join(required_cols_after_rename)}")
            st.info(f"Dostępne kolumny w pliku: {', '.join(df.columns)}") # Dodane, aby zobaczyć faktyczne nazwy
            return pd.DataFrame()

        # Upewnij się, że Rok i Miesiąc są numeryczne dla grupowania
        df['Rok'] = df['Rok'].astype(int)
        df['Miesiąc'] = df['Miesiąc'].astype(int)
        
        return df
    except FileNotFoundError:
        st.error(f"BŁĄD: Plik '{filename}' nie znaleziony. Upewnij się, że plik jest w prawidłowej ścieżce.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Błąd podczas wczytywania/przetwarzania pliku '{filename}': {e}")
        return pd.DataFrame()

# Ładowanie danych udziałów na początku działania aplikacji
df_udzialy_all = load_udzialy_data()


# --- Funkcje wizualizacji (ogólne i dla miesięcznych) ---

@st.cache_data
def przygotuj_daty_cached(df: pd.DataFrame) -> pd.DataFrame:
    df_copy = df.copy()
    df_copy['Data'] = pd.to_datetime(df_copy['Rok'].astype(str) + '-' + df_copy['Miesiąc'].astype(str) + '-01')
    return df_copy
# --- Zmodyfikowana funkcja show_podium_months do obsługi list słowników ---
def show_podium_months_static(data_list: list, title: str):
    """
    Wyświetla wizualne podium dla top 3 miesięcy na podstawie statycznej listy słowników.
    Każdy słownik powinien zawierać klucze 'miesiac' i 'liczba'.
    """
    if not data_list:
        st.write(f"Brak danych dla {title}")
        return

    # Przygotowanie danych z listy słowników
    # Upewniamy się, że zawsze mamy 3 elementy, nawet jeśli lista jest krótsza
    months = [item["miesiac"] for item in data_list] + ["-"] * (3 - len(data_list))
    counts = [item["liczba"] for item in data_list] + [0] * (3 - len(data_list))

    # HTML i CSS dla podium (bez zmian, tak jak podałeś)
    podium_html = f"""
    <style>
        .podium {{
            display: flex;
            justify-content: center;
            align-items: flex-end;
            gap: 20px;
            margin-bottom: 20px;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}
        .place {{
            text-align: center;
            color: #333;
            border-radius: 10px;
            padding: 10px;
            background: #e8f0fe;
            box-shadow: 2px 2px 6px rgba(65, 105, 225, 0.3);
        }}
        .first {{
            font-size: 1.6rem;
            font-weight: 700;
            height: 150px;
            background: #4169E1;
            color: white;
            flex: 1.5;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            padding-bottom: 15px;
            border-radius: 12px;
        }}
        .second {{
            font-size: 1.2rem;
            font-weight: 600;
            height: 120px;
            background: #89a9f7;
            color: white;
            flex: 1.2;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            padding-bottom: 10px;
            border-radius: 10px;
        }}
        .third {{
            font-size: 1rem;
            font-weight: 600;
            height: 100px;
            background: #c1cfff;
            color: #333;
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            padding-bottom: 10px;
            border-radius: 10px;
        }}
        .place .rank {{
            font-weight: 900;
            font-size: 1.4rem;
            margin-bottom: 5px;
        }}
        .place .month {{
            font-weight: 700;
        }}
        .place .count {{
            font-size: 1rem;
            opacity: 0.8;
        }}
    </style>
    <div class="podium">
        <div class="second place">
            <div class="rank">2</div>
            <div class="month">{months[1]}</div>
            <div class="count">Liczba: {counts[1]:,.0f}</div>
        </div>
        <div class="first place">
            <div class="rank">1</div>
            <div class="month">{months[0]}</div>
            <div class="count">Liczba: {counts[0]:,.0f}</div>
        </div>
        <div class="third place">
            <div class="rank">3</div>
            <div class="month">{months[2]}</div>
            <div class="count">Liczba: {counts[2]:,.0f}</div>
        </div>
    </div>
    """

    st.markdown(f"### 📅 Top 3 miesiące: {title}", unsafe_allow_html=True)
    st.markdown(podium_html, unsafe_allow_html=True)
@st.cache_data
def rysuj_wykres_liniowy_cached(df: pd.DataFrame, kolumna_do_wizualizacji: str, tytul: str) -> go.Figure:
    fig = go.Figure()
    for rok in sorted(df['Rok'].unique()):
        df_rok = df[df['Rok'] == rok]
        fig.add_trace(go.Scatter(
            x=df_rok['Data'],
            y=df_rok['sprzedaz_total'],
            mode='lines+markers',
            name=str(rok)
        ))
    fig.update_layout(
        title=tytul,
        xaxis_title='Miesiąc',
        yaxis_title=kolumna_do_wizualizacji,
        yaxis_tickformat=',',
        xaxis=dict(tickformat='%b'),
        yaxis_range=[0, df['sprzedaz_total'].max() * 1.1],
        hovermode='x unified'
    )
    return fig

def tabela_top_bottom(df, rok, kolumna_do_wizualizacji, st_col):
    if df.empty:
        st_col.write("Brak danych dla tego roku.")
        return

    st_col.markdown(f"### {rok} — Top 3 miesiące")
    top3 = df.nlargest(3, 'sprzedaz_total')[['Miesiąc_nazwa', 'sprzedaz_total']]
    top3['sprzedaz_total'] = top3['sprzedaz_total'].map('{:,.0f}'.format)
    st_col.table(top3.rename(columns={"Miesiąc_nazwa": "Miesiąc", "sprzedaz_total": kolumna_do_wizualizacji}))

    st_col.markdown(f"### {rok} — Bottom 3 miesiące")
    bottom3 = df.nsmallest(3, 'sprzedaz_total')[['Miesiąc_nazwa', 'sprzedaz_total']]
    bottom3['sprzedaz_total'] = bottom3['sprzedaz_total'].map('{:,.0f}'.format)
    st_col.table(bottom3.rename(columns={"Miesiąc_nazwa": "Miesiąc", "sprzedaz_total": kolumna_do_wizualizacji}))
# --- Funkcja pomocnicza do tworzenia formatowania dla DataFrame'ów ---
def get_numeric_columns_format_dict(df, format_string="{:,.2f}", exclude_columns=None):
    if exclude_columns is None:
        exclude_columns = []

    numeric_cols = df.select_dtypes(include=['number']).columns
    format_dict = {}
    for col in numeric_cols:
        if col not in exclude_columns:
            format_dict[col] = format_string
    return format_dict
@st.cache_data
def pivot_monthly_sales(df: pd.DataFrame) -> pd.DataFrame:
    if 'Miesiąc_nazwa_skrot' not in df.columns:
        df['Miesiąc_nazwa_skrot'] = df['Miesiąc'].map(month_names_short)

    pivot_df = df.pivot(index='Miesiąc_nazwa_skrot', columns='Rok', values='sprzedaz_total').reindex(
        list(month_names_short.values())
    )
    return pivot_df
@st.cache_data
def agreguj_sprzedaz_kategorie(df_aggregated: pd.DataFrame, sales_col: str) -> pd.DataFrame:
    """
    Agreguje sprzedaż po kategoriach dla wszystkich lat z df_aggregated.
    sales_col: nazwa kolumny sprzedaży w df_aggregated (np. 'sprzedaz_budzetowa_total')
    """
    if df_aggregated.empty:
        return pd.DataFrame(columns=['Kategoria nazwa', 'sprzedaz_total', 'Rok'])

    # Grupujemy po 'Kategoria nazwa' i 'Rok', sumując wybraną kolumnę sprzedaży
    df_agg = (
        df_aggregated.groupby(["Kategoria nazwa", "Rok"])
        .agg(sprzedaz_total=(sales_col, "sum"))
        .reset_index()
    )
    return df_agg
@st.cache_data
def rysuj_wykres_kategorie(df: pd.DataFrame, sales_col_name: str) -> go.Figure:
    fig = go.Figure()
    if df.empty:
        fig.add_annotation(text="Brak danych o kategoriach do wyświetlenia.",
                           xref="paper", yref="paper", showarrow=False,
                           font=dict(size=20, color="gray"))
        fig.update_layout(title="Sprzedaż wg kategorii — porównanie lat", height=400)
        return fig

    for rok in sorted(df["Rok"].unique()):
        df_rok = df[df["Rok"] == rok].sort_values("sprzedaz_total", ascending=False)
        fig.add_trace(go.Bar(
            x=df_rok["Kategoria nazwa"],
            y=df_rok["sprzedaz_total"],
            name=str(rok),
            text=df_rok["sprzedaz_total"].map(lambda x: f"{x:,.0f}"),
            textposition='outside'
        ))
    fig.update_layout(
        title=f"Sprzedaż wg kategorii — porównanie lat",
        xaxis_title="Kategoria",
        yaxis_title=sales_col_name,
        barmode='group',
        xaxis_tickangle=-45,
        yaxis_tickformat=',',
        legend_title="Rok",
        bargap=0.2,
        height=700,
        margin=dict(t=100, b=180)
    )
    max_val = df["sprzedaz_total"].max() * 1.2
    fig.update_yaxes(range=[0, max_val])
    return fig
@st.cache_data
def create_total_sales_chart(df_pivot: pd.DataFrame, sales_col_name: str) -> go.Figure:
    fig = go.Figure()
    if df_pivot.empty:
        fig.add_annotation(text="Brak danych do wyświetlenia wykresu.",
                           xref="paper", yref="paper", showarrow=False,
                           font=dict(size=20, color="gray"))
        fig.update_layout(title=f'Łączna {sales_col_name} — porównanie miesięcy', height=400)
        return fig

    for rok in df_pivot.columns:
        fig.add_trace(go.Scatter(
            x=df_pivot.index,
            y=df_pivot[rok],
            mode='lines+markers',
            name=str(rok)
        ))
    fig.update_layout(
        title=f'Łączna {sales_col_name} — porównanie miesięcy ({min(df_pivot.columns)}–{max(df_pivot.columns)})',
        xaxis_title='Miesiąc',
        yaxis_title=sales_col_name,
        yaxis_tickformat=',',
        hovermode='x unified',
        legend_title='Rok'
    )
    return fig


# Zakładki
tytul,tab00,tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "QR",
    "🏢 O firmie", 
    "📂 Charakterystyka danych", 
    "📊 Struktura danych",
    "📈 Wykresy czasowe",
    "🏆 Top 5",
    "🧮 Analiza Pareto",
    "🧩 Udziały rynkowe",
    "🛠️ Modele i dane",
    "📉 Statystyki najlepszego i najgorszego modelu"
])
with tytul:
       # Tytuł
    st.markdown("""
        <h1 style='text-align: center; font-size: 45px; color: #1f77b4;'>
            SmartPromocje, czyli jak dane pomagają przewidywać sprzedaż leków
        </h1>
        <hr>
    """, unsafe_allow_html=True)
    
    # Dane zespołu
    nazwa_zespolu = "💊 Lek na Dane"
    sklad = [
        "👩‍💼 Kierownik: Małgorzata Broniewicz",
        "👩‍💼 Analityk: Martyna Rutkowska",
        "👨‍💼 Analityk: Bartosz Wolski"
    ]
    # Układ: 2 kolumny
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        <h2 style='font-size: 40px; margin-bottom: 10px;'>🧾 Nazwa zespołu</h2>
        <p style='font-size: 30px; margin-top: -10px;'>💊 Lek na Dane</p>
        <h2 style='font-size: 40px; margin-bottom: 10px;'> Opiekun </h2>
        <p style='font-size: 30px; margin-top: -10px;'>🏢 mgr Ewelina Kałka </p>
        <h2 style='font-size: 36px; margin-bottom: 10px;'>👥 Skład zespołu</h2>
        <ul style='font-size: 30px; margin-top: -10px;'>
            <li>👩‍💼 Kierownik: Małgorzata Broniewicz</li>
            <li>👩‍💼 Analityk: Martyna Rutkowska</li>
            <li>👨‍💼 Analityk: Bartosz Wolski</li>
        </ul>

    """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("<h2 style='font-size: 40px;'>📎 Kod QR</h2>", unsafe_allow_html=True)
        qr_image = Image.open("qr2.png")  # Ścieżka do Twojego pliku
        st.image(qr_image)
        st.markdown('<p style="font-size: 37px; text-align: center; font-weight: bold;">Zeskanuj mnie! </p>', unsafe_allow_html=True)
    
    # Stopka
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("""
        <p style='text-align: center; color: gray; font-size: 16px;'>
            © 2025 Zespół Lek na Dane
        </p>
    """, unsafe_allow_html=True)

# --- Funkcje pomocnicze ---
with tab00:
    logo_path = "neuca_logo.png"
    logo = Image.open(logo_path)
    st.image(logo, width=300)

    html_code = """
    <style>
    .custom-tab .section {
        background-color: #ffffff;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        padding: 25px;
        margin-bottom: 30px;
        color: #111111;
        font-size: 20px;
        line-height: 1.6;
    }

    .custom-tab .timeline {
        border-left: 5px solid #1f77b4;
        padding-left: 20px;
        background-color: #ffffff;
        border-radius: 10px;
        box-shadow: inset 0 0 5px rgba(0,0,0,0.05);
        color: #111111;
    }

    .custom-tab .timeline-event {
        margin-bottom: 20px;
        font-size: 20px;
        color: #111111;
        font-weight: 600;
        line-height: 1.5;
    }

    .custom-tab .timeline-event strong {
        color: #1f77b4;
        font-weight: 800;
        font-size: 20px;
        margin-right: 15px;
    }

    .custom-tab h1, .custom-tab h2, .custom-tab h3 {
        font-size: 28px;
        color: #0d47a1;
        margin-bottom: 15px;
    }

    .custom-tab ul {
        font-size: 20px;
        line-height: 1.6;
        color: #111111;
    }

    .custom-tab p {
        color: #111111;
    }
    </style>

    <div class="custom-tab">
        <div class="section">
            <h1>🏢 O firmie NEUCA</h1>
            <p><strong>NEUCA S.A.</strong> to wiodąca firma z sektora ochrony zdrowia, która od ponad 30 lat aktywnie kształtuje polski rynek farmaceutyczny. Jej korzenie sięgają <strong>1990 roku</strong>, kiedy to w Toruniu powstała hurtownia leków TORFARM.</p>
            <p>Z małej, lokalnej inicjatywy NEUCA przekształciła się w jednego z kluczowych graczy w kraju. Dziś to <strong>strategiczny partner dla tysięcy aptek</strong>, placówek medycznych i firm z branży zdrowotnej.</p>
        </div>

        <div class="section">
            <h3>🕰 Kluczowe daty z historii firmy:</h3>
            <div class="timeline">
                <div class="timeline-event"><strong>1990</strong>– Kazimierz Herba zakłada hurtownię leków TORFARM w Toruniu</div>
                <div class="timeline-event"><strong>2001</strong>– firma obejmuje zasięgiem 90% powierzchni kraju</div>
                <div class="timeline-event"><strong>2007</strong>– powstaje Grupa TORFARM</div>
                <div class="timeline-event"><strong>2010</strong>– powstaje Grupa NEUCA, a TORFARM staje się jej częścią</div>
                <div class="timeline-event"><strong>2013</strong>– powstaje NEUCA Med, rozwijająca sieć przychodni</div>
                <div class="timeline-event"><strong>2018</strong>– uruchomienie centrum dystrybucyjnego przy ul. Fortecznej</div>
                <div class="timeline-event"><strong>2020</strong>– otwarcie nowej centrali firmy w Toruniu</div>
            </div>
        </div>

        <div class="section">
            <h3>🔍 Czym się zajmujemy?</h3>
            <ul>
                <li>💊 <strong>Dystrybucja leków</strong> – kompleksowe zaopatrzenie aptek i logistyka.</li>
                <li>🤝 <strong>Współpraca z aptekarzami</strong> – narzędzia, doradztwo, niezależność.</li>
                <li>🏥 <strong>Rozwój przychodni</strong> – NEUCA Med i Świat Zdrowia.</li>
                <li>🧪 <strong>Badania kliniczne</strong> – innowacyjne terapie i R&D.</li>
                <li>📡 <strong>Telemedycyna</strong> – zdalna opieka medyczna.</li>
                <li>🛒 <strong>E-commerce</strong> – cyfrowe platformy sprzedaży i wsparcia.</li>
            </ul>
        </div>

        <div class="section">
            <h3>🧭 Nasza misja</h3>
            <p>Celem NEUCA jest <strong>budowanie lepszego systemu opieki zdrowotnej</strong> w Polsce poprzez integrację logistyki, medycyny i technologii – w oparciu o zaufanie, jakość i innowację.</p>
        </div>
    </div>
    """

    components.html(html_code, height=1500, scrolling=True)
with tab0:
    st.markdown("""
    <style>
    .char-header {
        background-color: #000000;
        color: #ffffff;
        padding: 40px 30px;
        text-align: center;
        border-radius: 30px;
        font-size: 30px;
        margin-bottom: 30px;
    }

    .char-header h2 {
        font-size: 37px;
        margin-bottom: 20px;
        color: #ffffff;
    }

    .char-header p {
        font-size: 30px;
        color: #ffffff;
        margin: 0 auto;
        font-size: 30px;
        max-width: 850px;
    }
    .char-section h3 {
        font-size: 37px;
        font-weight: bold; /* Pogrubienie */
    }

    .char-section {
        background-color: #ffffff;
        padding: 25px 30px;
        border-radius: 15px;
        margin-bottom: 10px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08);
        color: #111111;
        font-size: 39px;
        line-height: 1.6;
    }
    </style>
    """, unsafe_allow_html=True)
    
    

    # Nagłówek
    st.markdown("""
    <div class="char-header">
        <h2>  📂 Charakterystyka otrzymanych danych</h2>
        <p>W ramach projektu przeanalizowaliśmy trzy główne źródła danych, dostarczone w postaci oddzielnych plików. Dane te są podstawą do dalszej analizy rynku oraz skuteczności działań promocyjnych.</p>
    </div>
    """, unsafe_allow_html=True)

    # 🧾 Dane rynkowe
    st.markdown("""
    <div class="char-section">
        <h3>🧾 Dane rynkowe 2022–2024</h3>
        <p>Zestaw zawiera dane rynkowe dotyczące sprzedaży leków na poziomie ogólnopolskim – pozwala przeanalizować trendy oraz zmiany rynkowe w czasie.</p>
        <p><em>(6 kolumn, 7 590 wierszy)</em></p>
        <p><strong>Dostępne kolumny:</strong></p>
        <ul>
            <li>Kategoria nazwa – nazwa kategorii leku</li>
            <li>Rok – rok sprzedaży na rynku</li>
            <li>Miesiąc – miesiąc sprzedaży na rynku</li>
            <li>Indeks – unikatowy identyfikator leku</li>
            <li>Sprzedaż rynek ilość – ilość sprzedanych sztuk leku</li>
            <li>Sprzedaż rynek wartość – wartość sprzedaży dla konkretnego leku</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # 💊 Dane sprzedaży
    st.markdown("""
    <div class="char-section">
        <h3>💊 Dane sprzedaży NEUCA (2022, 2023, 2024)</h3>
        <p>Szczegółowe informacje o sprzedaży leków przez firmę NEUCA, umożliwiające analizę trendów, sezonowości i potencjalnego wpływu działań marketingowych. Dane zostały podzielone na kategorie produktowe:</p>
        <ul>
            <li>Przylepce <em>(1 008 046 wierszy)</em></li>
            <li>Preparaty służące do zmniejszenia wagi ciała <em>(861 398 wierszy)</em></li>
            <li>Preparaty przeciwwymiotne <em>(621 996 wierszy)</em></li>
            <li>Preparaty przeciwalergiczne <em>(2 387 235 wierszy)</em></li>
            <li>Leczenie nałogów <em>(755 891 wierszy)</em></li>
        </ul>
        <p><strong>Najważniejsze kolumny:</strong></p>
        <ul>
            <li><strong>Kategoria nazwa</strong> – Segment lub grupa produktowa</li>
            <li><strong>Rok</strong> – Rok dokonania sprzedaży</li>
            <li><strong>Miesiąc</strong> – Miesiąc dokonania sprzedaży</li>
            <li><strong>Rodzaj promocji poziom 2</strong> – Szczegółowy typ promocji</li>
            <li><strong>id promocji</strong> – Unikalny identyfikator promocji</li>
            <li><strong>Producent sprzedażowy kod</strong> – Kod producenta</li>
            <li><strong>Indeks</strong> – Unikalny identyfikator produktu</li>
            <li><strong>Sprzedaż ilość</strong> – Ilość sprzedanych jednostek</li>
            <li><strong>Sprzedaż budżetowa</strong> – Łączna wartość budżetowana</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📊 Wszystkie dostępne kolumny w tym pliku"):
        st.markdown("""
        - **Kategoria nazwa**: Segment lub grupa produktowa  
        - **Rok**: Rok dokonania sprzedaży  
        - **Miesiąc**: Miesiąc dokonania sprzedaży  
        - **Rodzaj promocji poziom 1**: Główna kategoria działań promocyjnych  
        - **Rodzaj promocji poziom 2**: Szczegółowy typ promocji  
        - **id promocji**: Unikalny identyfikator promocji  
        - **Nazwa promocji**: Nazwa przypisana promocji  
        - **Kod SAP**: Systemowy kod produktu  
        - **Nazwa apteki**: Placówka sprzedażowa  
        - **Producent sprzedażowy kod**: Kod producenta  
        - **Producent sprzedażowy**: Nazwa producenta  
        - **Indeks**: Unikalny identyfikator produktu  
        - **Nazwa kartoteki**: Nazwa handlowa lub techniczna  
        - **RX/OTC**: Receptowy lub bez recepty  
        - **Typ dokumentu**: Rodzaj dokumentu sprzedaży  
        - **Sprzedaż ilość**: Ilość sprzedanych jednostek  
        - **Sprzedaż budżetowa promocyjna**: Sprzedaż w promocji  
        - **Sprzedaż budżetowa ZP**: Wartość z budżetu ZP  
        - **Sprzedaż budżetowa**: Łączna wartość budżetowana  
        """)

    # 📈 Wnioski promocyjne
    st.markdown("""
    <div class="char-section">
        <h3>📈 Wnioski promocyjne</h3>
        <p>Pliki zawierają informacje o działaniach promocyjnych – ich typie, czasie trwania i przypisaniu do konkretnych produktów. Są podzielone według kategorii leków:</p>
        <ul>
            <li>Przylepce <em>(35 390 wierszy)</em></li>
            <li>Preparaty służące do zmniejszenia wagi ciała <em>(24 795 wierszy)</em></li>
            <li>Preparaty przeciwwymiotne <em>(7 125 wierszy)</em></li>
            <li>Preparaty przeciwalergiczne <em>(36 516 wierszy)</em></li>
            <li>Leczenie nałogów <em>(31 348 wierszy)</em></li>
        </ul>
        <p><strong>Najważniejsze kolumny:</strong></p>
        <ul>
            <li><strong>Id promocji</strong> – Unikalny identyfikator zgłoszonej promocji</li>
            <li><strong>Nazwa promocji</strong> – Nazwa lub tytuł promocji</li>
            <li><strong>Data od - promocja</strong> – Data rozpoczęcia promocji</li>
            <li><strong>Data do - promocja</strong> – Data zakończenia promocji</li>
            <li><strong>Rabat promocyjny %</strong> – Rabat wyrażony w procentach</li>
            <li><strong>Wyłączenie rabatowania</strong> – Informacja o wyłączeniu rabatowania</li>
            <li><strong>Zamówienie telefoniczne</strong> – Możliwość zamówienia przez telefon</li>
            <li><strong>Zamówienie modemowe</strong> – Możliwość zamówienia przez system</li>
            <li><strong>Rodzaj progu</strong> – Typ progu (np. ilościowy, wartościowy)</li>
        </ul>        
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📋 Wszystkie dostępne kolumny w tym pliku"):
        st.markdown("""
        - **Id promocji**: Unikalny identyfikator zgłoszonej promocji  
        - **Nazwa promocji**: Nazwa lub tytuł promocji  
        - **Data od - promocja**: Data rozpoczęcia promocji  
        - **Data do - promocja**: Data zakończenia promocji  
        - **Wyłączenie rabatowania**: Informacja o wyłączeniu rabatowania (tak/nie)  
        - **Zamówienie telefoniczne**: Czy można zamawiać telefonicznie  
        - **Zamówienie modemowe**: Czy można zamawiać przez modem/system  
        - **Zamówienie producenckie**: Czy zamówienie odbywa się bezpośrednio przez producenta  
        - **Warunek płatności**: Szczegóły warunków płatności  
        - **Id producenta sprzedaży**: Identyfikator producenta  
        - **Nazwa producenta sprzedaży**: Pełna nazwa producenta  
        - **Id kartoteki**: Unikalny kod produktu objętego promocją  
        - **Nazwa**: Nazwa produktu objętego promocją  
        - **Identyfikator warunku**: ID określający warunek promocji  
        - **Rabat promocyjny %**: Rabat wyrażony w procentach  
        - **Rabat kwotowy**: Rabat podany w wartościach złotówkowych  
        - **Rodzaj progu**: Typ progu w promocji (np. ilościowy, wartościowy)  
        """)

    # 📊 Podsumowanie
    st.markdown("""
    <div class="char-section">
        <h3>📊 Podsumowanie wszystkich danych</h3>
        <p>Po połączeniu wszystkich danych otrzymujemy bardzo obszerny zbiór:</p>
        <ul>
            <li><strong>Wnioski promocyjne:</strong> 135 174 wierszy (17 kolumn)</li>
            <li><strong>Dane sprzedażowe NEUCA:</strong> 5 634 566 wierszy (20 kolumn)</li>
            <li><strong>Dane rynkowe:</strong> 7 590 wierszy (6 kolumn)</li>
        </ul>
        <p><strong>Łączna liczba wierszy:</strong> <span style="color:#0d47a1;">5 777 330</span></p>
    </div>
    """, unsafe_allow_html=True)

    
colors = {
    'drugs_2022': "#1e8449", 'promos_2022': "#0066cc", 'prod_2022': "#6c3483",
    'drugs_2023': "#58d68d", 'promos_2023': "#66b3ff", 'prod_2023': "#af7ac5",
    'drugs_2024': "#a3d9a5", 'promos_2024': "#869CE8", 'prod_2024': "#CF6FED",
}
with tab1:
 st.markdown("# ✨ Podsumowanie rocznych unikalności")
 # Kolory dla kafelków (możesz je dostosować)
 colors = {
    'drugs_2022': "#1e8449", 'promos_2022': "#0066cc", 'prod_2022': "#6c3483",
    'drugs_2023': "#58d68d", 'promos_2023': "#66b3ff", 'prod_2023': "#af7ac5",
    'drugs_2024': "#a3d9a5", 'promos_2024': "#869CE8", 'prod_2024': "#CF6FED",
 }
 icons = {
    'drugs': "💊", 'promos': "🎯", 'prod': "🏭"
 }
 col1, col2, col3, col4, col5, col6, col7,col8,col9 = st.columns(9)

 # Wywołujemy funkcję dla każdego roku i wyświetlamy wyniki
 with col1:
     info_card("Unikalne leki 2022",288, "#1e8449", "💊")
 with col2:
     info_card("Promocje 2022", 5193, "#0066cc", "🎯")    
 with col3:
     info_card("Unikalni producenci 2022",73, "#6c3483", "📂")  
 with col4:
     info_card("Unikalne leki 2023", 297, "#58d68d", "💊")
 with col5:
     info_card("Promocje 2023", 5377, "#66b3ff", "🎯")
 with col6:
     info_card("Unikalni producenci 2023",80, "#af7ac5", "📂")
 with col7:
     info_card("Unikalne leki 2024", 309, "#a3d9a5", "💊")
 with col8:
     info_card("Promocje 2024",4606, "#869CE8", "🎯")
 with col9:
     info_card("Unikalni producenci 2024", 81,  "#CF6FED", "📂")
 precalculated_data = {
    'LECZENIE NAŁOGÓW': {
        2022: {'unique_drugs': 36, 'unique_promos': 1223, 'unique_prod': 8},
        2023: {'unique_drugs': 36, 'unique_promos': 1223, 'unique_prod': 9},
        2024: {'unique_drugs': 43, 'unique_promos': 1146, 'unique_prod': 10},
    },
    'PREPARATY PRZECIWALERGICZNE': {
        2022: {'unique_drugs': 67, 'unique_promos': 3229, 'unique_prod': 37},
        2023: {'unique_drugs': 70, 'unique_promos': 3327, 'unique_prod': 37},
        2024: {'unique_drugs': 78, 'unique_promos': 2825, 'unique_prod': 35},
    },
    'PREPARATY PRZECIWWYMIOTNE': {
        2022: {'unique_drugs': 24, 'unique_promos': 989, 'unique_prod': 12},
        2023: {'unique_drugs': 27, 'unique_promos': 1135, 'unique_prod': 16},
        2024: {'unique_drugs': 29, 'unique_promos': 1125, 'unique_prod': 18},
    },
    'PREPARATY SŁUŻĄCE DO ZMNIEJSZENIA WAGI CIAŁA': {
        2022: {'unique_drugs': 81, 'unique_promos': 1722, 'unique_prod': 27},
        2023: {'unique_drugs': 96, 'unique_promos': 1753, 'unique_prod': 30},
        2024: {'unique_drugs': 95, 'unique_promos': 1411, 'unique_prod': 33},
    },
    'PRZYLEPCE': {
        2022: {'unique_drugs': 80, 'unique_promos': 925, 'unique_prod': 8},
        2023: {'unique_drugs': 68, 'unique_promos': 972, 'unique_prod': 8},
        2024: {'unique_drugs': 64, 'unique_promos': 850, 'unique_prod': 8},
    },
    }

# Lista unikalnych kategorii (pobierana z kluczy słownika)
 kategorie = list(precalculated_data.keys())


 for kat in kategorie:
    st.markdown(f"## 🧬 {kat}")

    # Pobieranie danych dla bieżącej kategorii z precalculated_data
    counts_2022 = precalculated_data[kat][2022]
    counts_2023 = precalculated_data[kat][2023]
    counts_2024 = precalculated_data[kat][2024]

    # Kafelki – 3 rzędy po 3 kolumny
    r1 = st.columns(3)
    r2 = st.columns(3)
    r3 = st.columns(3)

    with r1[0]:
        info_card("Leki 2022", counts_2022['unique_drugs'], colors['drugs_2022'], icons['drugs'])
    with r1[1]:
        info_card("Promocje 2022", counts_2022['unique_promos'], colors['promos_2022'], icons['promos'])
    with r1[2]:
        info_card("Producenci 2022", counts_2022['unique_prod'], colors['prod_2022'], icons['prod'])

    with r2[0]:
        info_card("Leki 2023", counts_2023['unique_drugs'], colors['drugs_2023'], icons['drugs'])
    with r2[1]:
        info_card("Promocje 2023", counts_2023['unique_promos'], colors['promos_2023'], icons['promos'])
    with r2[2]:
        info_card("Producenci 2023", counts_2023['unique_prod'], colors['prod_2023'], icons['prod'])

    with r3[0]:
        info_card("Leki 2024", counts_2024['unique_drugs'], colors['drugs_2024'], icons['drugs'])
    with r3[1]:
        info_card("Promocje 2024", counts_2024['unique_promos'], colors['promos_2024'], icons['promos'])
    with r3[2]:
        info_card("Producenci 2024", counts_2024['unique_prod'], colors['prod_2024'], icons['prod'])

    st.markdown("---")
with tab2: # Odpowiada za "Wykresy czasowe"
    # WYBÓR TYPU DANYCH DLA WIZUALIZACJI
    # Ten radio button będzie wpływał zarówno na wykresy miesięczne, jak i kategoryczne.
    kolumna_wybor = st.radio(
        " ## Wybierz typ danych do analizy:",
        [" Sprzedaż ilościowa", " Sprzedaż wartościowa"],
        horizontal=True,
        key="sales_type_radio"
    )

    # Ustawienie nazw kolumn i źródeł danych na podstawie wyboru
    if kolumna_wybor == "Sprzedaż wartościowa":
        selected_monthly_data_by_year = monthly_sales_budzetowa
        sales_col_display_name = "Sprzedaż wartość"
        # Ta zmienna zawiera teraz nazwę kolumny w df_aggregated do sumowania
        sales_col_for_category_agg = "sprzedaz_budzetowa_total"
    else: # Sprzedaż ilościowa
        selected_monthly_data_by_year = monthly_sales_ilosciowa
        sales_col_display_name = "Sprzedaż ilość"
        # Ta zmienna zawiera teraz nazwę kolumny w df_aggregated do sumowania
        sales_col_for_category_agg = "sprzedaz_ilosc_total"

    st.subheader("Sprzedaż wg kategorii w podziale na lata")

    # --- Wczytywanie df_aggregated TUTAJ ---
    df_aggregated_categories_data = load_df_aggregated_categories() # <--- This is the line from your error
    
    if not df_aggregated_categories_data.empty: # Use the new variable name here
        df_kategorie = agreguj_sprzedaz_kategorie(df_aggregated_categories_data, sales_col_for_category_agg)
        fig_kategorie = rysuj_wykres_kategorie(df_kategorie, sales_col_display_name)
        st.plotly_chart(fig_kategorie, use_container_width=True)
    else:
        st.warning("Brak danych kategoryzacyjnych do wyświetlenia.")

    # --- Wykresy czasowe łącznej sprzedaży miesięcznej ---
    st.subheader("Wykresy czasowe łącznej sprzedaży miesięcznej")

    all_monthly_df_for_chart = pd.concat(selected_monthly_data_by_year.values(), ignore_index=True)

    if not all_monthly_df_for_chart.empty:
        all_monthly_df_for_chart = przygotuj_daty_cached(all_monthly_df_for_chart)
        fig_total_sales = create_total_sales_chart(
            pivot_monthly_sales(all_monthly_df_for_chart),
            sales_col_display_name
        )
        st.plotly_chart(fig_total_sales, use_container_width=True)
    else:
        st.warning("Brak danych miesięcznych do wyświetlenia wykresu liniowego.")


    st.markdown("---")
    st.subheader("Miesięczne Top/Bottom 3 - Przegląd")
    cols = st.columns(len(top_years))
    for i, rok in enumerate(top_years):
        df_rok_for_table = selected_monthly_data_by_year.get(rok, pd.DataFrame())
        with cols[i]:
            if not df_rok_for_table.empty:
                tabela_top_bottom(df_rok_for_table, rok, sales_col_display_name, cols[i])
            else:
                st.markdown(f"### {rok}")
                st.write("Brak danych.")


    st.markdown("---")
    
with tab3:
    st.header("TOP 5 producentów i produktów wg sprzedaży")
    sortowanie_po = st.radio("Sortuj TOP 5 wg", ["Sprzedaży ilościowej", "Sprzedaży wartościowej"])
    
    # --- Stałe i konfiguracja ---
    top_years = [2022, 2023, 2024] # Lata, dla których masz pliki
    podium_ikony = ["🥇", "🥈", "🥉", "🏅", "🎖️"]
    kolory_tla_top5 = [
        "#007acc",  # 🥇 ciemny niebieski
        "#3399ff",  # 🥈 średni niebieski
        "#66b2ff",  # 🥉 jasny niebieski
        "#99ccff",  # 🏅 pastelowy
        "#b3d9ff"    # 🎖️ mniej jasny niż wcześniej, nadal czytelny z białym tekstem
    ]
    
    # ======= Funkcja do wczytywania i przygotowywania danych (cachowana) =======
    @st.cache_data
    def load_and_prepare_top5_data() -> dict:
        
        all_top_data = {}
        
        for year in top_years:
            # --- Wczytywanie danych dla PRODUCENTÓW ---
            filename_producent = f"top_producent_{year}.parquet"
            try:
                df_prod = pd.read_parquet(filename_producent)
                # Jeśli w plikach producentów kolumna nadal nazywa się 'Producent sprzedażowy kod',
                # zmieniamy ją na 'Indeks', aby pasowała do reszty kodu.
                if 'Producent sprzedażowy kod' in df_prod.columns:
                    df_prod = df_prod.rename(columns={'Producent sprzedażowy kod': 'Indeks'})
                
                # Sprawdzenie, czy kluczowe kolumny istnieją po wczytaniu
                if not all(col in df_prod.columns for col in ['Rok', 'Indeks', 'Sprzedaz_ilosc', 'Sprzedaz_wartosc']):
                    st.error(f"Błąd: Plik '{filename_producent}' nie zawiera wszystkich wymaganych kolumn (Rok, Indeks, Sprzedaz_ilosc, Sprzedaz_wartosc).")
                    continue # Pomiń ten rok dla producentów
                
                all_top_data[f"producent_{year}"] = df_prod.copy()
    
            except FileNotFoundError:
                st.warning(f"Plik '{filename_producent}' nie znaleziony. Upewnij się, że został wygenerowany i jest w tym samym folderze.")
            except Exception as e:
                st.error(f"Błąd podczas wczytywania pliku '{filename_producent}': {e}")
    
    
            # --- Wczytywanie danych dla LEKÓW (produktów) ---
            filename_lek = f"top_lek_{year}.parquet"
            try:
                df_lek = pd.read_parquet(filename_lek)
                
                # Dla leków, kolumna powinna już nazywać się 'Indeks'. Sprawdzamy dla bezpieczeństwa.
                if 'Indeks' not in df_lek.columns:
                     st.error(f"Błąd: Plik '{filename_lek}' nie zawiera wymaganej kolumny 'Indeks'.")
                     continue # Pomiń ten rok dla leków
    
                # Sprawdzenie, czy kluczowe kolumny istnieją po wczytaniu
                if not all(col in df_lek.columns for col in ['Rok', 'Indeks', 'Sprzedaz_ilosc', 'Sprzedaz_wartosc']):
                    st.error(f"Błąd: Plik '{filename_lek}' nie zawiera wszystkich wymaganych kolumn (Rok, Indeks, Sprzedaz_ilosc, Sprzedaz_wartosc).")
                    continue # Pomiń ten rok dla leków
    
                all_top_data[f"lek_{year}"] = df_lek.copy()
    
            except FileNotFoundError:
                st.warning(f"Plik '{filename_lek}' nie znaleziony. Upewnij się, że został wygenerowany i jest w tym samym folderze.")
            except Exception as e:
                st.error(f"Błąd podczas wczytywania pliku '{filename_lek}': {e}")
                
        return all_top_data
    
    # Wczytaj i przygotuj dane raz na początku działania aplikacji
    all_cached_data = load_and_prepare_top5_data()
    
    
    # ======= Funkcja do pobierania i sortowania danych TOP 5 z wczytanych danych =======
    @st.cache_data
    def get_top5_for_display(data_dict: dict, year: int, item_type: str, sort_by_option: str) -> pd.DataFrame:
        """
        Pobiera odpowiedni DataFrame z wczytanych danych i sortuje go, 
        aby zwrócić TOP 5 dla wyświetlania.
        """
        # item_type będzie "producenci" lub "produkty"
        # Zamieniamy na "producent" lub "lek" dla klucza słownika
        key_prefix = "producent" if item_type == "producenci" else "lek"
        df_key = f"{key_prefix}_{year}"
        
        if df_key not in data_dict:
            return pd.DataFrame() # Zwróć pusty DataFrame, jeśli danych nie ma
            
        df_to_sort = data_dict[df_key].copy()
        
        # Wybierz kolumnę do sortowania na podstawie wyboru użytkownika
        if sort_by_option == "Sprzedaży ilościowej":
            sort_col = 'Sprzedaz_ilosc'
        else: # "Sprzedaży wartościowej"
            sort_col = 'Sprzedaz_wartosc'
            
        return df_to_sort.sort_values(by=sort_col, ascending=False).head(5)
    
    
    # ======= Sekcja producentów =======
    st.subheader("Podium producentów")
    kolumny = st.columns(len(top_years))
    for idx, rok in enumerate(top_years):
        # Wywołujemy nową funkcję get_top5_for_display
        df_rok_producenci = get_top5_for_display(all_cached_data, rok, "producenci", sortowanie_po)
    
        with kolumny[idx]:
            st.markdown(f"### Rok {rok}")
            if not df_rok_producenci.empty:
                for miejsce, (_, rzad) in enumerate(df_rok_producenci.iterrows()):
                    producent = rzad["Indeks"] # Kolumna już nazywa się 'Indeks'
                    ilosc = int(rzad["Sprzedaz_ilosc"])
                    wartosc = int(rzad["Sprzedaz_wartosc"])
                    ikona = podium_ikony[miejsce] if miejsce < len(podium_ikony) else f"{miejsce+1}."
                    
                    kolor_tla = kolory_tla_top5[miejsce] if miejsce < len(kolory_tla_top5) else "#f8f9fa"
                    
                    st.markdown(f"""
                    <div style='
                        background-color: {kolor_tla};
                        border-radius: 15px;
                        padding: 12px;
                        margin-bottom: 10px;
                        text-align:center;
                    '>
                        <div style='font-size:22px; font-weight:bold;'>{ikona} {producent}</div>
                        <div style='font-size:14px;'>💊 {ilosc:,.0f} szt. &nbsp;&nbsp; 💰 {wartosc:,.0f} zł</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.write("Brak danych do wyświetlenia.")
    
    # ======= Sekcja produktów =======
    st.subheader("Podium produktów")
    kolumny_p = st.columns(len(top_years))
    for idx, rok in enumerate(top_years):
        # Wywołujemy nową funkcję get_top5_for_display
        df_rok_produkty = get_top5_for_display(all_cached_data, rok, "produkty", sortowanie_po)
    
        with kolumny_p[idx]:
            st.markdown(f"### Rok {rok}")
            if not df_rok_produkty.empty:
                for miejsce, (_, rzad) in enumerate(df_rok_produkty.iterrows()):
                    indeks = rzad["Indeks"]
                    ilosc = int(rzad["Sprzedaz_ilosc"])
                    wartosc = int(rzad["Sprzedaz_wartosc"])
                    ikona = podium_ikony[miejsce] if miejsce < len(podium_ikony) else f"{miejsce+1}."
                    
                    kolor_tla = kolory_tla_top5[miejsce] if miejsce < len(kolory_tla_top5) else "#f8f9fa"
                    
                    st.markdown(f"""
                    <div style='
                        background-color: {kolor_tla};
                        border-radius: 15px;
                        padding: 12px;
                        margin-bottom: 10px;
                        text-align:center;
                    '>
                        <div style='font-size:22px; font-weight:bold;'>{ikona} {indeks}</div>
                        <div style='font-size:14px;'>💊 {ilosc:,.0f} szt. &nbsp;&nbsp; 💰 {wartosc:,.0f} zł</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.write("Brak danych do wyświetlenia.")

with tab4:
    kolory = ['#7EC8E3', '#0074D9', '#F6A5A5']
    prog_pareto = st.selectbox("Wybierz próg koncentracji (Pareto)", [70, 80, 90], index=1)
    st.header("📊 Podsumowanie sprzedaży wg lat")
    analiza_wg = st.radio(
        "Wybierz typ danych:",
        ("Ilość sztuk", "Sprzedaż wartościowa"),
        horizontal=True,
        key="analiza_wg_radio"
    )
    
    def suma_wg_roku_agg(df_agg, kolumna_do_sumowania):
        yearly_sums = df_sales_by_category.groupby('Rok')[kolumna_do_sumowania].sum()
        return yearly_sums.reindex([2022, 2023, 2024]) # Upewnij się, że lata są w odpowiedniej kolejności
    
    
    left_col, right_col = st.columns([3, 2])
    
    with left_col:
        kol1, kol2, kol3 = st.columns(3)
        for i, rok in enumerate([2022, 2023, 2024]):
            # Obliczanie sum rocznych bezpośrednio z zagregowanych danych
            sprzedaz_ilosc = df_sales_by_category[df_sales_by_category['Rok'] == rok]['Ilość'].sum()
            sprzedaz_wartosc = df_sales_by_category[df_sales_by_category['Rok'] == rok]['Sprzedaż budżetowa'].sum()
            kol = [kol1, kol2, kol3][i]
    
            with kol:
                st.markdown(f"""
                    <div style="font-size:30px; font-weight:bold; margin-bottom:3px;">Rok {rok}</div>
                    <div style="font-size:25px;">Ilość sztuk:<br><b>{int(sprzedaz_ilosc):,}</b></div>
                    <div style="font-size:25px;">Wartość sprzedaży:<br><b>{sprzedaz_wartosc:,.2f} zł</b></div>
                """, unsafe_allow_html=True)
    
    with right_col:
        # Kolumny wykresowe teraz są zgodne z nowymi nazwami w plikach Parquet
        kolumna_wykres_do_plot = 'Sprzedaż budżetowa' if analiza_wg == "Sprzedaż wartościowa" else 'Ilość'
        y_label = "Wartość sprzedaży [zł]" if analiza_wg == "Sprzedaż wartościowa" else "Sprzedaż ilość" # Etykieta może być nadal "Sprzedaż ilość"
    
        # Obliczamy sumy roczne za pomocą nowej funkcji na zagregowanych danych
        wartosci_roczne = suma_wg_roku_agg(df_sales_by_category, kolumna_wykres_do_plot)
    
        fig_lata = go.Figure(go.Bar(
            x=wartosci_roczne.index.astype(str),
            y=wartosci_roczne.values,
            marker_color=kolory
        ))
        fig_lata.update_layout(
            title="Podsumowanie wg lat",
            yaxis_title=y_label,
            xaxis_title="Rok",
            height=300,
            margin=dict(l=10, r=10, t=30, b=30),
            xaxis=dict(
                tickmode='array',
                tickvals=wartosci_roczne.index.astype(str),
                ticktext=wartosci_roczne.index.astype(str)
            )
        )
        st.plotly_chart(fig_lata, use_container_width=True)
    
    # Kolumna dla wykresów Pareto będzie teraz dynamicznie nazywana
    kolumna_wykres_for_pareto = wybierz_kolumne_wg(analiza_wg)
    
    
    # --- Sekcja koncentracji sprzedaży wg kategorii (Używa df_sales_by_category) ---
    with left_col:
        st.header("📊 Koncentracja sprzedaży wg kategorii")
        kat_cols = st.columns(3)
        for i, rok in enumerate([2022, 2023, 2024]):
            with kat_cols[i]:
                # Używamy nowej funkcji analiza_pareto_from_agg z df_sales_by_category
                liczba_kat, procent_kat, kat_ogran, sprzedaz_kat = analiza_pareto_from_agg(
                    df_sales_by_category, 'Kategoria', analiza_wg, prog_pareto, rok_filtr=rok
                )
                st.markdown(f"### Rok {rok}")
                st.markdown(
                    f"""
                    <table style='font-size:12px; width:100%;'>
                        <tr><td><b>Liczba kategorii ({prog_pareto}%)</b></td><td>{liczba_kat}</td></tr>
                        <tr><td><b>Procent kategorii</b></td><td>{procent_kat:.1f}%</td></tr>
                    </table>
                    """, unsafe_allow_html=True
                )
                styl_df = kat_ogran.style \
                    .format({kolumna_wykres_for_pareto: "{:,.0f}", 'Skumulowany %': "{:.1f} %"}) \
                    .set_table_styles([
                        {'selector': 'th', 'props': [('font-size', '11px')]},
                        {'selector': 'td', 'props': [('font-size', '11px')]},
                    ])
                st.dataframe(styl_df, use_container_width=True)
        st.write("---")
    
    # --- Sekcja koncentracji sprzedaży wg promocji (Używa df_sales_by_promotion) ---
    with left_col:
        st.header("📊 Koncentracja sprzedaży wg promocji")
        promo_cols = st.columns(3)
        for i, rok in enumerate([2022, 2023, 2024]):
            with promo_cols[i]:
                # Używamy nowej funkcji analiza_pareto_from_agg z df_sales_by_promotion
                liczba_prom, procent_prom, prom_ogran, sprzedaz_prom = analiza_pareto_from_agg(
                    df_sales_by_promotion, 'Rodzaj promocji', analiza_wg, prog_pareto, rok_filtr=rok
                )
                st.markdown(f"### Rok {rok}")
                st.markdown(
                    f"""
                    <table style='font-size:12px; width:100%;'>
                        <tr><td><b>Liczba promocji ({prog_pareto}%)</b></td><td>{liczba_prom}</td></tr>
                        <tr><td><b>Procent promocji</b></td><td>{procent_prom:.1f}%</td></tr>
                    </table>
                    """, unsafe_allow_html=True
                )
                styl_df = prom_ogran.style \
                    .format({kolumna_wykres_for_pareto: "{:,.0f}", 'Skumulowany %': "{:.1f} %"}) \
                    .set_table_styles([
                        {'selector': 'th', 'props': [('font-size', '11px')]},
                        {'selector': 'td', 'props': [('font-size', '11px')]},
                    ])
                st.dataframe(styl_df, use_container_width=True)
        st.write("---")
    
    # --- Sekcja wykresów Pareto (Używa df_sales_by_category i df_sales_by_promotion) ---
    with right_col:
        st.header("📊 Wykresy Pareto - kategorie i promocje")
    
        df_kat_all_plot = []
        for rok in [2022, 2023, 2024]:
            # Aby wykres pokazywał wszystkie kategorie/promocje, ustawiamy próg Pareto na 100
            _, _, _, sprzedaz_kat = analiza_pareto_from_agg(df_sales_by_category, 'Kategoria', analiza_wg, 100, rok_filtr=rok)
            df_tmp = sprzedaz_kat.reset_index()
            df_tmp['Rok'] = rok
            df_kat_all_plot.append(df_tmp)
        df_kat_all_plot = pd.concat(df_kat_all_plot)
    
        fig_kat = go.Figure()
    
        for i, rok in enumerate([2022, 2023, 2024]):
            df_rok_plot = df_kat_all_plot[df_kat_all_plot['Rok'] == rok]
            fig_kat.add_trace(go.Bar(
                x=df_rok_plot['Kategoria'],
                y=df_rok_plot[kolumna_wykres_for_pareto],
                name=str(rok),
                marker_color=kolory[i]
            ))
        fig_kat.update_layout(
            barmode='group',
            title=f"Sprzedaż wg kategorii",
            yaxis_title=analiza_wg,
            height=350,
            margin=dict(l=10, r=10, t=40, b=40),
            xaxis_tickangle=-45
        )
        st.plotly_chart(fig_kat, use_container_width=True)
    
        df_prom_all_plot = []
        for rok in [2022, 2023, 2024]:
            # Aby wykres pokazywał wszystkie kategorie/promocje, ustawiamy próg Pareto na 100
            _, _, _, sprzedaz_prom = analiza_pareto_from_agg(df_sales_by_promotion, 'Rodzaj promocji', analiza_wg, 100, rok_filtr=rok)
            df_tmp = sprzedaz_prom.reset_index()
            df_tmp['Rok'] = rok
            df_prom_all_plot.append(df_tmp)
        df_prom_all_plot = pd.concat(df_prom_all_plot)
    
        fig_prom = go.Figure()
        for i, rok in enumerate([2022, 2023, 2024]):
            df_rok_plot = df_prom_all_plot[df_prom_all_plot['Rok'] == rok]
            fig_prom.add_trace(go.Bar(
                x=df_rok_plot['Rodzaj promocji'],
                y=df_rok_plot[kolumna_wykres_for_pareto],
                name=str(rok),
                marker_color=kolory[i]
            ))
        fig_prom.update_layout(
            barmode='group',
            title=f"Sprzedaż wg promocji",
            yaxis_title=analiza_wg,
            height=350,
            margin=dict(l=10, r=10, t=40, b=40),
            xaxis_tickangle=-45
        )
    
        st.plotly_chart(fig_prom, use_container_width=True)

        
with tab5:
    st.title("Analiza udziałów rynkowych i struktury sprzedaży Neuca na podstawie wybranych kategorii leków")

    if df_udzialy_all.empty:
        st.warning("Brak danych do analizy udziałów rynkowych. Upewnij się, że plik 'udzial_all.parquet' jest poprawny.")
    else:
        udzialy_2023 = df_udzialy_all[df_udzialy_all["Rok"] == 2023].copy()
        udzialy_2024 = df_udzialy_all[df_udzialy_all["Rok"] == 2024].copy()
        
        @st.cache_data
        def oblicz_udzial_roczny_cached(df_year: pd.DataFrame):
            # Upewnij się, że kolumny są typu numerycznego
            df_year['Sprzedaż ilość'] = pd.to_numeric(df_year['Sprzedaż ilość'], errors='coerce')
            df_year['Sprzedaż budżetowa'] = pd.to_numeric(df_year['Sprzedaż budżetowa'], errors='coerce')
            df_year['Sprzedaż rynek ilość'] = pd.to_numeric(df_year['Sprzedaż rynek ilość'], errors='coerce')
            df_year['Sprzedaż rynek wartość'] = pd.to_numeric(df_year['Sprzedaż rynek wartość'], errors='coerce')
    
            neuca_sum_ilosc = df_year["Sprzedaż ilość"].sum()
            neuca_sum_budzet = df_year["Sprzedaż budżetowa"].sum()
            
            rynek_sum_ilosc = df_year["Sprzedaż rynek ilość"].sum()
            rynek_sum_wartosc = df_year["Sprzedaż rynek wartość"].sum()
            
            udzial_ilosc = (100 * neuca_sum_ilosc / rynek_sum_ilosc) if rynek_sum_ilosc != 0 else 0
            udzial_wartosc = (100 * neuca_sum_budzet / rynek_sum_wartosc) if rynek_sum_wartosc != 0 else 0
            
            return round(udzial_ilosc, 2), round(udzial_wartosc, 2)
        
        udzial_ilosc_2023, udzial_wartosc_2023 = oblicz_udzial_roczny_cached(udzialy_2023)
        udzial_ilosc_2024, udzial_wartosc_2024 = oblicz_udzial_roczny_cached(udzialy_2024)
        
        rok_wybrany = 2024 
        
        pokaz_ilosc = udzial_ilosc_2024
        delta_ilosc = udzial_ilosc_2024 - udzial_ilosc_2023
        
        pokaz_wartosc = udzial_wartosc_2024
        delta_wartosc = udzial_wartosc_2024 - udzial_wartosc_2023
    
        col1, col2 = st.columns(2)
    
        with col1:
            st.metric(
                label=f" Udział ilościowy Neuca ({rok_wybrany}) w odniesieniu do 2023",
                value=f"{pokaz_ilosc:.2f}%",
                delta=f"{delta_ilosc:+.2f} pp"  # <== zmiana tu
            )

        with col2:
            st.metric(
                label=f" Udział wartościowy Neuca ({rok_wybrany}) w odniesieniu do 2023",
                value=f"{pokaz_wartosc:.2f}%",
                delta=f"{delta_wartosc:+.2f} pp"  # <== zmiana tu
            )
        st.subheader("Miesięczne udziały Neuca w rynku")
        st.markdown("---") # separator dla wykresów miesięcznych
        koly = {
            2023: '#0074D9',  # przykładowy kolor dla 2023 (niebieski)
            2024: '#F6A5A5'   # przykładowy kolor dla 2024 (pomarańczowy)
        }
        df_udzialy_all['Miesiąc'] = df_udzialy_all['Miesiąc'].map(month_names_short)
        # Wykresy miesięczne bazujące bezpośrednio na df_udzialy_all
        fig_ilosc = px.line(
            df_udzialy_all,
            x="Miesiąc",
            y="Udział ilościowy (%)",
            color='Rok',
            markers=True,
            title="Udział ilościowy Neuca w rynku po miesiącach",
            color_discrete_map=koly
        )
        
        fig_wartosc = px.line(
            df_udzialy_all,
            x="Miesiąc",
            y="Udział wartościowy (%)",
            color='Rok',
            markers=True,
            title="Udział wartościowy Neuca w rynku po miesiącach",
            color_discrete_map=koly
        )
        
        fig_ilosc.update_yaxes(range=[0, 60])
        fig_wartosc.update_yaxes(range=[0, 60])
    
        with col1:
            st.plotly_chart(fig_ilosc, use_container_width=True)
        
        with col2:
            st.plotly_chart(fig_wartosc, use_container_width=True)

  
    def formatuj_liczbe(x):
     if pd.isna(x):
        return ""
     return f"{int(x):,}".replace(",", " ")

    def przygotuj_tabele_porownawcza_surowa(tabela_2024, tabela_2023):
        """
        Łączy dwie tabele (dla 2024 i 2023) i formatuje kolumny do porównania.
        Oczekuje tabel już przygotowanych z obliczeniami procentowymi.
        """
        tabela_2024 = tabela_2024.copy()
        tabela_2023 = tabela_2023.copy()
    
        # Znajdź wspólne kolumny, które nie są 'Miesiąc_str'
        wspolne_kolumny = [col for col in tabela_2024.columns if col in tabela_2023.columns and col != "Miesiąc_str"]
    
        # Zmieniamy nazwy kolumn, żeby były unikalne dla każdego roku przed połączeniem
        tabela_2024_renamed = tabela_2024.rename(columns={col: f"{col}_2024" for col in wspolne_kolumny})
        tabela_2023_renamed = tabela_2023.rename(columns={col: f"{col}_2023" for col in wspolne_kolumny})
        # Łączymy tabele na podstawie kolumny 'Miesiąc_str'. Użyj 'outer' join, aby uwzględnić miesiące,
        # które mogą być obecne tylko w jednym z lat.
        tabela = tabela_2024_renamed.merge(tabela_2023_renamed, on='Miesiąc_str', how='outer').sort_values('Miesiąc_str')
    
        def sformatuj_kolumne_porownawcza(wart_2024, wart_2023, is_percent_col=False):
            """
            Formatuje pojedynczą komórkę w tabeli porównawczej, dodając informacje o zmianie.
            """
            if pd.isna(wart_2024) and pd.isna(wart_2023):
                return ""
                
            if pd.notna(wart_2024) and pd.notna(wart_2023) and wart_2023 >= 0:
                if is_percent_col:
                    delta_pp = wart_2024 - wart_2023
                    if delta_pp > 0:
                        return f"{wart_2024:.2f}% ({wart_2023:.2f}%) <span style='color:green'>▲ {delta_pp:.2f} p.p.</span>"
                    elif delta_pp < 0:
                        return f"{wart_2024:.2f}% ({wart_2023:.2f}%) <span style='color:red'>▼ {abs(delta_pp):.2f} p.p.</span>"
                    else:
                        return f"{wart_2024:.2f}% ({wart_2023:.2f}%)"
                else:
                    tekst = f"{formatuj_liczbe(wart_2024)} ({formatuj_liczbe(wart_2023)})"
                    if wart_2023 != 0:
                        zmiana_procentowa = ((wart_2024 - wart_2023) / abs(wart_2023)) * 100
                        if zmiana_procentowa > 0:
                            tekst += f" <span style='color:green'>▲ {zmiana_procentowa:.2f}%</span>"
                        elif zmiana_procentowa < 0:
                            tekst += f" <span style='color:red'>▼ {abs(zmiana_procentowa):.2f}%</span>"
                    return tekst
            else: # Obsługa NaN lub przypadków, gdzie nie ma sensu porównywać
                if pd.notna(wart_2024) and pd.isna(wart_2023):
                    return f"{formatuj_liczbe(wart_2024)} (-)" if not is_percent_col else f"{wart_2024:.2f}% (-)"
                elif pd.isna(wart_2024) and pd.notna(wart_2023):
                    return f"(-) ({formatuj_liczbe(wart_2023)})" if not is_percent_col else f"(-) ({wart_2023:.2f}%)"
                return "" # Jeśli obie NaN, pusty string
    
        # Lista kolumn, które mają być traktowane jako procentowe
        percent_cols = ['NEUCA%', 'PROMO%', 'ZP%', 'NORMAL%']
    
        for col in wspolne_kolumny:
            is_percent = col in percent_cols
            tabela[col] = tabela.apply(
                lambda row: sformatuj_kolumne_porownawcza(
                    row.get(f"{col}_2024", pd.NA), # Użyj .get() z wartością domyślną pd.NA
                    row.get(f"{col}_2023", pd.NA), # Użyj .get() z wartością domyślną pd.NA
                    is_percent_col=is_percent
                ),
                axis=1
            )
    
        tabela.rename(columns={'Miesiąc_str': 'Miesiąc'}, inplace=True)
    
        # Sortuj kolumny, aby "Miesiąc" był pierwszy, a potem pozostałe wspólne kolumny
        return tabela[["Miesiąc"] + wspolne_kolumny]

    
    # --- Ładowanie danych dla wartości ---
    try:
        tabela_2024_wartosc = pd.read_parquet('tabela_2024_wartosc.parquet')
        tabela_2023_wartosc = pd.read_parquet('tabela_2023_wartosc.parquet')
    except FileNotFoundError as e:
        st.error(f"Błąd: Nie znaleziono pliku danych dla wartości: {e}. Upewnij się, że pliki .parquet są w odpowiednim katalogu.")
        st.stop() # Zatrzymuje aplikację
    
    # --- Ładowanie danych dla ilości ---
    try:
        tabela_2024_ilosc = pd.read_parquet('tabela_2024_ilosc.parquet')
        tabela_2023_ilosc = pd.read_parquet('tabela_2023_ilosc.parquet')
    except FileNotFoundError as e:
        st.error(f"Błąd: Nie znaleziono pliku danych dla ilości: {e}. Upewnij się, że pliki .parquet są w odpowiednim katalogu.")
        st.stop() # Zatrzymuje aplikację
    
    # --- Generowanie tabel porównawczych ---
    # Tabela wartości
    tabela_porownawcza_wartosc = przygotuj_tabele_porownawcza_surowa(tabela_2024_wartosc, tabela_2023_wartosc)
    
    # Tabela ilości
    tabela_porownawcza_ilosc = przygotuj_tabele_porownawcza_surowa(tabela_2024_ilosc, tabela_2023_ilosc)
    
    # --- Wyświetlanie w st.expander ---
    
    with st.expander("📊 Tabela sprzedaży wg wartości dla roku 2024 w porównaniu do 2023", expanded=False):
        st.subheader("Sprzedaż wartościowa 2024 (2023)")
        st.html(tabela_porownawcza_wartosc.to_html(escape=False, index=False))
    
    with st.expander("📦 Tabela sprzedaży wg ilości dla roku 2024 w porównaniu do 2023", expanded=False):
        st.subheader("Sprzedaż ilościowa 2024 (2023)")
        st.html(tabela_porownawcza_ilosc.to_html(escape=False, index=False))
        
with tab6:
    st.markdown("# 🛠️ Modele i dane")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        ## **Modele:**  
       ### - 🌳 Drzewo Decyzyjne  
       ### - 🌲 Random Forest  
       ### - 🌴 Extra Trees  
        """)

    with col2:
        st.markdown("""
        ## **Dane:**  
        ### 5 grup produktowych:  
       #### - Przylepce  
       #### - Odchudzanie  
       #### - Przeciwwymiotne  
       #### - Alergiczne  
       #### - Nałogi  
        """)

    st.markdown("---")

    st.markdown("## 🔍 Najważniejsze zmienne w analizie")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
       #### - 🎯  Zmienna celu: sprzedaż_sztuki
       #### - 🏷️  Rodzaj promocji
       #### - 🏢  Producent sprzedażowy kod
       #### - 💸  Rabat promocyjny %
        """)
    with col2:
        st.markdown("""
        #### - 📈 **Neuca_sprzedaz_przed**
        #### - 📊 **Sprzedaz_rynkowa_w_trakcie_rok_wczesniej**
        #### - 📉 **Neuca_sprzedaz_przed_rok_wczesniej**
        """)

    with st.expander("📋 Wszystkie zmienne w tabeli danych"):
        st.markdown("""
        - **sprzedaż_sztuki** – liczba jednostek produktu sprzedanych w ramach promocji  
        - **Producent sprzedażowy kod** – unikalny identyfikator producenta leku w systemie NEUCA  
        - **Indeks** – unikalny kod produktu 
        - **czas_trwania** – liczba miesięcy trwania promocji  
        - **Wyłączenie rabatowania** – czy promocja wyłącza standardowe rabaty apteczne  
        - **Zamówienie telefoniczne** – możliwość zamawiania telefonicznego 
        - **Zamówienie modemowe** – możliwość zamawiania przez system/modem  
        - **Zamówienie producenckie** – czy zamówienie odbywało się bezpośrednio przez producenta  
        - **Rabat promocyjny %** – wysokość rabatu wyrażona w procentach  
        - **Rabat kwotowy** – wartość rabatu w złotówkach na jednostkę  
        - **Miesiąc rozpoczęcia** – miesiąc rozpoczęcia promocji  
        - **Miesiąc zakończenia** – miesiąc zakończenia promocji  
        - **Neuca_sprzedaz_przed** – sprzedaż NEUCA przed rozpoczęciem promocji  
        - **Sprzedaz_rynkowa_przed** – sprzedaż całego rynku przed promocją  
        - **Rodzaj promocji** – typ zastosowanej promocji  
        - **Neuca_sprzedaz_przed_rok_wczesniej** – sprzedaż NEUCA przed promocją, w tym samym okresie rok wcześniej  
        - **Neuca_sprzedaz_w_trakcie_rok_wczesniej** – sprzedaż NEUCA w trakcie promocji, rok wcześniej  
        - **Neuca_sprzedaz_po_rok_wczesniej** – sprzedaż NEUCA po zakończeniu promocji, rok wcześniej  
        - **Sprzedaz_rynkowa_przed_rok_wczesniej** – sprzedaż rynkowa przed promocją, rok wcześniej  
        - **Sprzedaz_rynkowa_w_trakcie_rok_wczesniej** – sprzedaż rynkowa w trakcie promocji, rok wcześniej  
        - **Sprzedaz_rynkowa_po_rok_wczesniej** – sprzedaż rynkowa po zakończeniu promocji, rok wcześniej  
        """)

    st.markdown("### 🔁 Walidacja modeli")

    st.markdown("""
    #### 🔁 K-Fold Cross-Validation **
    #### 🔁 Nested Cross-Validation (GridSearch wewnętrzny)
    """)

    st.subheader(" 🔁 Nested Cross-Validation (GridSearch + CV)")
    df_nested = pd.DataFrame({
        'Grupa': ['Nałogi', 'Przeciwalergiczne','Przeciwwymiotne', 'Przylepce', 'Waga'],
        'Model': ['Extra Trees']*5,
        'MSE': [736.4988381618172, 5768.768688014003, 1911.4496950519285,15980.954956393925, 292.30500166618054],
        'RMSE': [27.121228912350393, 75.55755332064275,42.976824993253274,125.7031788207044, 16.97081180449384],
        'MAE': [13.256088689730703, 38.244279871610075, 20.698899244465498,58.28214017262464, 9.162161988206265],
        'MAPE(%)': [2.5224405921311193, 4.382407356704275, 3.000465067380612,5.799360158805493, 1.8526702732328826]
    })
    st.dataframe(df_nested.style.format(precision=2), use_container_width=True)

    # 📊 Dodanie Twojej tabeli w expanderze
    with st.expander(" 📊 Szczegółowe wyniki modeli dla wszystkich zestawów"):
        import pandas as pd

        # --- Dane ---
        kategoria_1 = 'Nałogi'
        models_1 = ['Drzewo Decyzyjne', 'Drzewo Decyzyjne (Nested CV)', 'Drzewo Decyzyjne (Tuned)', 'Extra Trees', 'Extra Trees (Nested CV)', 'Extra Trees (Tuned)', 'Random Forest', 'Random Forest (Nested CV)', 'Random Forest (Tuned)']
        mse_1 = [1193.405665658999, 973.8207504276121, 876.8322465050321, 803.0011507826147, 736.4988381618172, 705.615092154201, 742.8895265209549,721.314638118937,719.3734819873622]
        rmse_1 = [34.51656019676582, 31.195633788392126, 29.61135333795185, 28.320257635958143, 27.121228912350393, 26.56341642474102, 27.24956657091109, 26.850518139678314, 26.82113871533724]
        mae_1 = [15.947378897064615, 15.001225529931938, 14.173813329261677, 13.088504922924633, 13.256088689730703, 13.05587935881901, 13.474954989054174, 13.36649110208013, 13.339421341540245]
        mape_1 = [2.5081209563915983, 2.6295521100574635, 2.5450052449008127, 2.2895816604793184, 2.5224405921311193, 2.484187731014533, 2.518661572675375, 2.5228062096508763, 2.514281840846281]

        kategoria_2 = 'Przeciwalergiczne'
        models_2 = ['Drzewo Decyzyjne', 'Drzewo Decyzyjne (Nested CV)', 'Drzewo Decyzyjne (Tuned)', 'Extra Trees', 'Extra Trees (Nested CV)', 'Extra Trees (Tuned)', 'Random Forest', 'Random Forest (Nested CV)', 'Random Forest (Tuned)']
        mse_2 = [10134.655354871575, 6762.222989280572, 6570.5645668443885, 6853.865563494478 ,5768.768688014003, 5673.749111053263, 6267.151825895178, 6093.4814391320515, 5920.98788742497]
        rmse_2 = [100.581664741877, 81.90375202047876, 81.05901903455523, 82.72834966519994, 75.55755332064275, 75.32429296749663, 79.0238359870972, 77.73708372145283, 76.94795570660061]
        mae_2 = [47.22870096293604, 42.93232147179006, 42.62033492909579, 39.412239750331594, 38.244279871610075, 37.749177071792026, 39.7477477452296, 40.36437189476353, 39.82870323086608]
        mape_2 = [4.540272800614068, 4.911708129060613, 5.0554892614238325, 3.8593625428372924, 4.382407356704275, 4.184183770494591, 4.385057975185538, 4.935414112858877, 4.744548883599978]

        kategoria_3 = 'Przeciwwymiotne'
        models_3 = ['Drzewo Decyzyjne', 'Drzewo Decyzyjne (Nested CV)', 'Drzewo Decyzyjne (Tuned)', 'Extra Trees', 'Extra Trees (Nested CV)', 'Extra Trees (Tuned)', 'Random Forest', 'Random Forest (Nested CV)', 'Random Forest (Tuned)']
        mse_3 = [3160.7090050340717, 2563.0147608159864, 2030.0213510619492, 2150.681297632903, 1911.4496950519285, 1648.9144361498443, 2003.5525164970932, 2274.7911300798373, 1887.6404714846474]
        rmse_3 = [55.45141293698397, 50.097136509741404, 45.05575824533363, 45.322818429625144, 42.976824993253274, 40.60682745733585, 44.26609186625587, 46.82438449602674, 43.446984607503516]
        mae_3 = [24.39714164237123 ,22.876781656239633, 22.772058551256208, 20.022069497084548, 20.698899244465498, 19.357594446084068, 20.77819014735598, 22.19682518468597, 20.45512157427325]
        mape_3 = [2.6332247572981595, 2.999492647917716, 3.8257985895657525, 2.29763601601161, 3.000465067380612, 2.5610582398460573, 2.747851774738087, 3.208492091004252, 2.903231755251853]

        kategoria_4 = 'Przylepce'
        models_4 = ['Drzewo Decyzyjne', 'Drzewo Decyzyjne (Nested CV)', 'Drzewo Decyzyjne (Tuned)', 'Extra Trees', 'Extra Trees (Nested CV)', 'Extra Trees (Tuned)', 'Random Forest', 'Random Forest (Nested CV)', 'Random Forest (Tuned)']
        mse_4 = [22596.04430822329, 19279.171473485767, 16739.415467926865, 19880.636279303337, 15980.954956393925, 15637.99342281514, 17342.305879140702, 15859.734243471787, 15488.753631101305]
        rmse_4 = [149.31426289199476, 137.64233726045177, 129.38089297854944, 140.47304080999555, 125.7031788207044, 125.05196289069252, 130.91318625216906, 124.52814781428181, 124.45382127962687]
        mae_4 = [63.67126720139258, 63.92291932574386, 60.97236784443244, 60.55091480676306, 58.28214017262464, 57.2541113627064, 58.11046454894878, 59.19707220113658, 59.252131202807256 ]
        mape_4 = [4.517257953007553, 5.955563048242834, 5.847992975764371, 4.766316276787663, 5.799360158805493, 5.634400063825014, 4.958481661927348, 5.943999391813489, 6.074218956521882]

        kategoria_5 = 'Waga'
        models_5 = ['Drzewo Decyzyjne', 'Drzewo Decyzyjne (Nested CV)', 'Drzewo Decyzyjne (Tuned)', 'Extra Trees', 'Extra Trees (Nested CV)', 'Extra Trees (Tuned)', 'Random Forest','Random Forest (Nested CV)', 'Random Forest (Tuned)']
        mse_5 = [430.0562827350901, 362.8077951192792, 331.7485139397452, 311.26098778961864, 292.30500166618054, 281.95716670047125, 296.6378152986429, 299.15775616171925, 291.71028426807834]
        rmse_5 = [20.684705863886254, 18.901262112576457, 18.213964805603013, 17.563288038607794, 16.97081180449384, 16.79158023238049, 17.096903980060997, 17.168964118776646, 17.079528221472582]
        mae_5 = [10.591358236890734, 10.09224810758159, 9.946831525528431, 9.204944626662245, 9.162161988206265, 8.968090394408273, 9.204091420248883, 9.387190059516218, 9.24008842905443]
        mape_5 = [1.6827220967113299, 1.9397781774719476, 1.8732374522268684, 1.6631484129062692, 1.8526702732328826, 1.7619796192701553, 1.773972483126246, 1.8870210689309317, 1.8543948435707853]

        data = []

        for kat, models, mse, rmse, mae, mape in [
            (kategoria_1, models_1, mse_1, rmse_1, mae_1, mape_1),
            (kategoria_2, models_2, mse_2, rmse_2, mae_2, mape_2),
            (kategoria_3, models_3, mse_3, rmse_3, mae_3, mape_3),
            (kategoria_4, models_4, mse_4, rmse_4, mae_4, mape_4),
            (kategoria_5, models_5, mse_5, rmse_5, mae_5, mape_5)
        ]:
            for i in range(len(models)):
                data.append({
                    'Kategoria': kat,
                    'Model': models[i],
                    'MSE': mse[i],
                    'RMSE': rmse[i],
                    'MAE': mae[i],
                    'MAPE (%)': mape[i]
                })

        df_final = pd.DataFrame(data)
        df_final.index = range(1, len(df_final) + 1)

        st.dataframe(df_final.style.format({
            'MSE': "{:.2f}",
            'RMSE': "{:.2f}",
            'MAE': "{:.2f}",
            'MAPE (%)': "{:.2f}"
        }), use_container_width=True)


    st.markdown("---")

    st.subheader("🔧 Hiperparametry – GridSearchCV")

    with st.expander("🌳 Drzewo Decyzyjne"):
        st.table(pd.DataFrame({
            "Parametr": ["max_depth", "min_samples_split", "min_samples_leaf", "max_features", "splitter"],
            "Wartości testowane": [
                "[3, 5, 10, 15, 20, 25, None]",
                "[2, 5, 10, 20]",
                "[1, 2, 5, 10]",
                '["sqrt", "log2", None]',
                '["best", "random"]'
            ]
        }))

    with st.expander("🌲 Random Forest"):
        st.table(pd.DataFrame({
            "Parametr": ["n_estimators", "max_depth", "min_samples_split", "min_samples_leaf", "bootstrap", "max_features"],
            "Wartości testowane": [
                "[50, 100, 200, 300]",
                "[5, 10, 15, 20, None]",
                "[2, 5, 10, 15]",
                "[1, 2, 4, 8]",
                "[True, False]",
                '["sqrt", "log2", None]'
            ]
        }))

    with st.expander("🌴 Extra Trees"):
        st.table(pd.DataFrame({
            "Parametr": ["n_estimators", "max_depth", "min_samples_split", "min_samples_leaf", "max_features", "bootstrap"],
            "Wartości testowane": [
                "[50, 100, 200, 300]",
                "[5, 10, 15, 20, None]",
                "[2, 5, 10, 15]",
                "[1, 2, 4, 8]",
                '["sqrt", "log2", None]',
                "[False, True]"
            ]
        }))

    st.markdown("---")

    shap_image_path = "shape.jpg"
    feature_image_path = "feature_importance_extra_trees_nested_cv.png"

    # Sprawdzanie, czy pliki istnieją, zanim spróbujemy je otworzyć
    if os.path.exists(shap_image_path) and os.path.exists(feature_image_path):
        try:
            i = Image.open(shap_image_path)
            n = Image.open(feature_image_path)

            st.subheader("📊 Ważność predyktorów dla modelu")
            st.image(n, caption="Feature Importance", use_container_width=False, width=700)
            st.markdown("---")

            st.subheader("📊 Wykres SHAP")
            st.image(i, caption="SHAP Summary Plot", use_container_width=False, width=700)

        except Exception as e:
            st.error(f"Błąd podczas ładowania obrazów SHAP/Feature Importance: {e}")
            st.write(f"DEBUG: Ścieżka SHAP: {shap_image_path}, Typ: {type(shap_image_path)}")
            st.write(f"DEBUG: Ścieżka Feature: {feature_image_path}, Typ: {type(feature_image_path)}")
    else:
        st.warning("Nie znaleziono lokalnych plików obrazów SHAP/Feature Importance.")
        st.info(f"Upewnij się, że pliki '{shap_image_path}' i '{feature_image_path}' znajdują się w tym samym katalogu co Twój skrypt Streamlit.")
# Dla "Wagi" (lewa kolumna)
top3_rozpoczecia_waga = [
    {"miesiac": "Kwiecień", "liczba": 299, "medal": "🥇", "color": "#E3F2FD"},
    {"miesiac": "Lipiec", "liczba": 279, "medal": "🥈", "color": "#F3E5F5"},
    {"miesiac": "Wrzesień", "liczba": 167, "medal": "🥉", "color": "#FFF3E0"},
]

top3_zakonczenia_waga = [
    {"miesiac": "Czerwiec", "liczba": 264, "medal": "🥇", "color": "#E3F2FD"},
    {"miesiac": "Wrzesień", "liczba": 259, "medal": "🥈", "color": "#F3E5F5"},
    {"miesiac": "Sierpień", "liczba": 169, "medal": "🥉", "color": "#FFF3E0"},
]

# Dla "Przylepców" (prawa kolumna)
top3_rozpoczecia_przylepce = [
    {"miesiac": "Kwiecień", "liczba": 532, "medal": "🥇", "color": "#E3F2FD"},
    {"miesiac": "Marzec", "liczba": 486, "medal": "🥈", "color": "#F3E5F5"},
    {"miesiac": "Lipiec", "liczba": 466, "medal": "🥉", "color": "#FFF3E0"},
]

top3_zakonczenia_przylepce = [
    {"miesiac": "Czerwiec", "liczba": 500, "medal": "🥇", "color": "#E3F2FD"},
    {"miesiac": "Wrzesień", "liczba": 470, "medal": "🥈", "color": "#F3E5F5"},
    {"miesiac": "Marzec", "liczba": 413, "medal": "🥉", "color": "#FFF3E0"},
]

with tab7:
        col1, col2, col3 = st.columns(3)
        with col1:
            rabat_wazony_waga = 10.09 # Jeśli to jest stała wartość

            st.markdown(f"""
            <div style='border: 2px solid #6c757d; border-radius: 15px; padding: 15px; background-color: #f0f4ff; box-shadow: 2px 2px 5px rgba(100, 149, 237, 0.3);'>
                <h3 style='color: #4169E1;'>📊 Dane: Waga </h3>
                <p style='color: black;'><b>Liczba wierszy:</b> 1670</p>
                <p style='color: black;'><b>Liczba kolumn:</b> 21</p>
                <p style='color: black; font-weight: bold;'>🎯 Średni rabat ważony: {rabat_wazony_waga:.2f}%</p>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("### 📊 Statystyki wybranych wskaźników (Waga)")
            format_for_wskwaga = get_numeric_columns_format_dict(
                wskwaga,
                format_string="{:,.2f}",
                exclude_columns=[] # Dostosuj, jeśli masz kolumny, których nie chcesz formatować
            )
            styl_wskwaga = wskwaga.style.format(format_for_wskwaga)
            st.dataframe(styl_wskwaga, use_container_width=True)

        # --- Wywołanie nowej funkcji dla statycznych danych Wagi ---
            show_podium_months_static(top3_rozpoczecia_waga, "rozpoczęcia promocji (Waga)")
            show_podium_months_static(top3_zakonczenia_waga, "zakończenia promocji (Waga)")

        with col2:
            rabat_wazony_przylepce = 21.97 # Jeśli to jest stała wartość

            st.markdown(f"""
            <div style='border: 2px solid #6c757d; border-radius: 15px; padding: 15px; background-color: #f0f4ff; box-shadow: 2px 2px 5px rgba(100, 149, 237, 0.3);'>
                <h3 style='color: #4169E1;'>📊 Dane: Przylepce </h3>
                <p style='color: black;'><b>Liczba wierszy:</b> 2998</p>
                <p style='color: black;'><b>Liczba kolumn:</b> 21</p>
                <p style='color: black; font-weight: bold;'>🎯 Średni rabat ważony: {rabat_wazony_przylepce:.2f}%</p>
                </div>
            """, unsafe_allow_html=True)

            st.markdown("### 📊 Statystyki wybranych wskaźników (Przylepce)")
            format_for_wskprz = get_numeric_columns_format_dict(
                wskprz,
                format_string="{:,.2f}",
                exclude_columns=[] # Dostosuj, jeśli masz kolumny, których nie chcesz formatować
                )
            styl_wskprz = wskprz.style.format(format_for_wskprz)
            st.dataframe(styl_wskprz, use_container_width=True)

            # --- Wywołanie nowej funkcji dla statycznych danych Przylepców ---
            show_podium_months_static(top3_rozpoczecia_przylepce, "rozpoczęcia promocji (Przylepce)")
            show_podium_months_static(top3_zakonczenia_przylepce, "zakończenia promocji (Przylepce)")

        with col3:
            # Tworzymy DataFrame podsumowujący bezpośrednio z danych z tabeli na zdjęciu
            podsumowanie_data = {
                "Rodzaj promocji": ['Centralne','IPRA','Partner','RPM','Regionalne pozostałe','Sieciowe','Synoptis - akcje własne','ZGZ'],
                "Częstość (%)": [7.9, 10.66, 13.17, 32.16, 5.99, 22.4, 2.46, 5.27],
                "Sprzedaż (%)": [12.47, 11.83, 16.54, 15.58, 3.02, 17.26, 21.24, 2.07]
            }

            podsumowanie = pd.DataFrame(podsumowanie_data).set_index("Rodzaj promocji")
    
            # ------------------ PIERWSZE PODIUM ------------------
            st.markdown("### 🏆 Najczęstsze rodzaje promocji (wg częstości wystąpień)")
    
            colors = ["#E3F2FD", "#F3E5F5", "#FFF3E0"]
            medale = ["🥇", "🥈", "🥉"]
            cols = st.columns(3)
    
            # Dokładne dane z obrazka
            top_czestosc_data = [
                ("RPM", 32.16),
                ("Sieciowe", 22.40),
                ("Partner", 13.17)
            ]
    
            for i, (nazwa, wartosc) in enumerate(top_czestosc_data):
                with cols[i]:
                    st.markdown(f"""
                    <div style='background-color: {colors[i]}; padding: 15px; border-radius: 12px; text-align: center; box-shadow: 2px 2px 8px rgba(0,0,0,0.15);'>
                        <h4 style='color: black;'>{medale[i]} {nazwa}: {wartosc}%</h4>
                    </div>
                    """, unsafe_allow_html=True)
    
            # ------------------ DRUGIE PODIUM ------------------
            st.markdown("### 🏆 Rodzaje promocji z największym udziałem w sprzedaży promocyjnej")
    
            cols = st.columns(3)
    
            # Dokładne dane z obrazka
            top_sprzedaz_data = [
                ("Synoptis-akcje", 21.24),
                ("Sieciowe", 17.26),
                ("Partner", 16.54)
            ]
    
            for i, (nazwa, wartosc) in enumerate(top_sprzedaz_data):
                with cols[i]:
                    st.markdown(f"""
                    <div style='background-color: {colors[i]}; padding: 15px; border-radius: 12px; text-align: center; box-shadow: 2px 2px 8px rgba(0,0,0,0.15);'>
                        <h4 style='color: black;'>{medale[i]} {nazwa}: {wartosc}%</h4>
                    </div>
                    """, unsafe_allow_html=True)
    
            # ------------------ TABELA PODSUMOWUJĄCA ------------------
            st.markdown("### 📋 Pozostałe rodzaje promocji")
            podsumowanie_do_wyswietlenia = podsumowanie.copy()
            podsumowanie_do_wyswietlenia["Częstość (%)"] = podsumowanie_do_wyswietlenia["Częstość (%)"].astype(str) + "%"
            podsumowanie_do_wyswietlenia["Sprzedaż (%)"] = podsumowanie_do_wyswietlenia["Sprzedaż (%)"].astype(str) + "%"
            st.dataframe(podsumowanie_do_wyswietlenia, use_container_width=True)
    
            # Udział procentowy sprzedaży D19 (dokładne dane z obrazka)
            liczba_lekow_d19 = 5 
            sprzedaz_d19_stale = 10270
            udzial_d19_stale = 29.08
            sprzedaz_leku_69065 = 2373
            udzial_leku_69065 = 6.72
            st.markdown("### Diagram ważniejszych predyktorów")
            # Tworzenie grafu (zaktualizowane wartości na podstawie obrazka)
            graf = graphviz.Digraph()
            graf.node("Producent", " Producent: D19\n(jedyny uczestniczący w promocji Synoptis)",shape='folder', style='filled', fillcolor='#E0F7FA')
            graf.node("Udział", "Udział promocyjny (Synoptis)\n w sprzedaży leków największy mimo bycia najrzadszą kategorią",shape='folder', style='filled', fillcolor='#FFF3E0')
            graf.node("Typ zamówienia", "W tej promocji jedynie \n zamówienia modemowe i telefoniczne", shape='folder', style='filled', fillcolor='#FFF3E0')
            graf.node("Produkty", f"💊 Produkty D19:\n{liczba_lekow_d19} unikalnych",shape='folder', style='filled', fillcolor='#F3E5F5')
            graf.node("Sprzedaż", f"📈 Sprzedaż produktów D19:\n{sprzedaz_d19_stale:,} sztuk\n({udzial_d19_stale}% ogółem)",shape='folder', style='filled', fillcolor='#E1F5FE')
            graf.node("Przykład", "📌 Przykład leku:\nIndeks 69065\n(należy do D19)", shape='folder', style='filled', fillcolor='#FFEBEE')
            graf.node("Lek", f"📌 \nIndeks 69065\n sprzedaż {sprzedaz_leku_69065}, a jego udział {udzial_leku_69065}%", shape='folder', style='filled', fillcolor='#FFEBEE')
            graf.edge("Producent", "Typ zamówienia", style='dashed')
            graf.edge("Producent", "Udział", style='dashed')
            graf.edge("Producent", "Produkty", style='dashed')
            graf.edge("Produkty", "Sprzedaż", style='dashed')
            graf.edge("Produkty", "Przykład", style='dashed')
            graf.edge("Przykład", "Lek", style='dashed')
            # Wyświetlenie
            st.graphviz_chart(graf)
            
            
            
            
            


 